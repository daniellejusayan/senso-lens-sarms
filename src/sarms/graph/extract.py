"""Monitor, part 1: the implemented architecture of one commit, written down.

    uv run python -m sarms.graph.extract data/raw/REPO                       # HEAD of the default branch
    uv run python -m sarms.graph.extract data/raw/REPO --sha 9039f82a        # any commit
    uv run python -m sarms.graph.extract data/raw/REPO --root kedro          # when there is no import-linter record

Builds the module-level import graph with grimp (the same library import-linter uses, so the
edges here are the edges the contracts are checked on) and writes it under
data/REPO/graph/<sha12>/ in forms people and tools can read:

  edges.parquet / edges.csv   one row per import statement: importer, imported, line_number,
                              line_contents, plus package_from/package_to (second dotted level)
  modules.csv                 one row per module: in_degree, out_degree, package, is_unassigned
                              (named by no layer/rule of the record), scc_id (its cycle, if any)
  packages.csv                the package-level roll-up: package_from, package_to, n_imports
  packages.dot                the package graph for Graphviz (`dot -Tsvg packages.dot > packages.svg`)
  summary.json                counts: modules, edges, packages, cycles, largest cycle, unassigned,
                              top hubs by fan-in — the numbers vocabulary.md quotes for kedro

Root packages come from the import-linter record at that commit (root_package(s)); --root
overrides. The clone is a partial clone, so the first run on a commit fetches its blobs.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

import grimp
import networkx as nx
import pandas as pd

from sarms.mining.common import IL_FILES, find_il_config, git, read_il_options, resolve_ref


def record_names(opts):
    """Every module name a contract names (layers, containers, source/forbidden/independent modules)."""
    names = set()
    for c in opts.contracts_options:
        for k in ("layers", "containers", "source_modules", "forbidden_modules", "modules", "protected_modules"):
            v = c.get(k)
            items = v if isinstance(v, list) else ([v] if v else [])
            for item in items:
                for part in re.split(r"\s*\|\s*", str(item)):
                    names.add(part.strip("() ").strip())
    return {n for n in names if n}


def rule_names(opts, roots):
    """record_names minus the root packages themselves (a `containers = kedro` line names everything)."""
    return {n for n in record_names(opts) if n not in set(roots)}


def assigned(module, roots, names):
    """True when a layer/rule names this module or an ancestor/descendant of it (container-relative too)."""
    for n in names:
        cands = {n} | {f"{r}.{n}" for r in roots}
        for c in cands:
            if module == c or module.startswith(c + ".") or c.startswith(module + "."):
                return True
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("repo_path")
    ap.add_argument("--sha", help="commit (default: the default branch's HEAD)")
    ap.add_argument("--root", nargs="*", help="root package(s); default: from the import-linter record")
    ap.add_argument("--config", help="import-linter config path inside the repo (monorepos)")
    ap.add_argument("--src", nargs="*", help="source roots relative to the repo, if auto-detection fails")
    ap.add_argument("--out", help="output folder (default data/REPO/graph/<sha12>)")
    a = ap.parse_args()
    repo = Path(a.repo_path).resolve()
    sha = git(repo, "rev-parse", a.sha or resolve_ref(repo)).strip()
    name = repo.name
    out = Path(a.out) if a.out else Path("data") / name / "graph" / sha[:12]
    out.mkdir(parents=True, exist_ok=True)

    # a checked-out repository at that very commit (our own, say) is read in place; a partial
    # clone gets one reused worktree beside it, as the replay does
    has_tree = git(repo, "rev-parse", "--is-inside-work-tree", check=False).strip() == "true"
    if has_tree and git(repo, "rev-parse", "HEAD").strip() == sha and (repo / "pyproject.toml").exists():
        wt = repo
    else:
        wt = Path(f"{repo}.wt")
        if not wt.exists():
            git(repo, "worktree", "add", "--detach", "-f", str(wt.resolve()), sha)
        git(wt, "checkout", "-q", "--force", sha)
        git(wt, "clean", "-fdq")  # the replay shares this worktree; its leftovers must not become modules here

    files = [a.config] if a.config else IL_FILES
    fname, text = find_il_config(repo, sha, files)
    opts = read_il_options(fname, text) if fname else None
    roots = a.root
    if not roots:
        if not opts:
            sys.exit("no import-linter record at this commit; pass --root PACKAGE")
        so = opts.session_options
        roots = so.get("root_packages") or [so.get("root_package")]
    names = rule_names(opts, roots) if opts else set()

    # make the subject importable for grimp without importing it ourselves
    bases = [wt / p for p in a.src] if a.src else [wt / "src", wt, wt / "python", wt / "lib"]
    for g_ in ("packages", "libs", "apps"):
        if (wt / g_).is_dir():
            bases += [d for d in sorted((wt / g_).iterdir()) if d.is_dir()]
    for b in bases:
        if any((b / r.split(".")[0]).is_dir() for r in roots) and str(b) not in sys.path:
            sys.path.insert(0, str(b))
    cache = Path(f"{repo}.ilcache").resolve()
    graph = grimp.build_graph(*roots, cache_dir=str(cache))

    rows = []
    for m in graph.modules:
        for n in graph.find_modules_directly_imported_by(m):
            for d in graph.get_import_details(importer=m, imported=n):
                rows.append({"importer": m, "imported": n, "line_number": d["line_number"], "line_contents": d["line_contents"]})
    pkg = lambda m: ".".join(m.split(".")[:2])  # noqa: E731
    edges = pd.DataFrame(rows, columns=["importer", "imported", "line_number", "line_contents"])
    edges["package_from"], edges["package_to"] = edges.importer.map(pkg), edges.imported.map(pkg)
    edges.to_parquet(out / "edges.parquet", index=False)
    edges.to_csv(out / "edges.csv", index=False)

    G = nx.DiGraph()
    G.add_nodes_from(graph.modules)
    G.add_edges_from(edges[["importer", "imported"]].drop_duplicates().itertuples(index=False))
    sccs = [sorted(s) for s in nx.strongly_connected_components(G) if len(s) >= 2]
    sccs.sort(key=len, reverse=True)
    scc_of = {m: i for i, s in enumerate(sccs) for m in s}
    mods = pd.DataFrame({"module": sorted(graph.modules)})
    mods["package"] = mods.module.map(pkg)
    mods["in_degree"] = mods.module.map(dict(G.in_degree()))
    mods["out_degree"] = mods.module.map(dict(G.out_degree()))
    mods["is_unassigned"] = [not assigned(m, roots, names) if names else None for m in mods.module]
    mods["scc_id"] = mods.module.map(scc_of)
    mods.to_csv(out / "modules.csv", index=False)

    P = edges[edges.package_from != edges.package_to].groupby(["package_from", "package_to"]).size().reset_index(name="n_imports")
    P.to_csv(out / "packages.csv", index=False)
    with open(out / "packages.dot", "w") as fh:
        fh.write(f'digraph "{name}@{sha[:8]}" {{\n  rankdir=LR; node [shape=box, fontname=Helvetica];\n')
        for r in P.itertuples(index=False):
            fh.write(f'  "{r.package_from}" -> "{r.package_to}" [label="{r.n_imports}"];\n')
        fh.write("}\n")

    top_unassigned = sorted({m for m, u in zip(mods.module, mods.is_unassigned, strict=True) if u and m.count(".") == 1})
    hubs = mods.sort_values("in_degree", ascending=False).head(8)
    summary = {"repo": name, "sha": sha, "roots": roots, "record": fname or "", "modules": int(len(mods)), "edges": int(len(edges)),
               "distinct_module_edges": int(G.number_of_edges()), "packages": int(mods.package.nunique()),
               "cycles": len(sccs), "largest_cycle": len(sccs[0]) if sccs else 0,
               "largest_cycle_members": sccs[0][:40] if sccs else [],
               "top_level_unassigned": top_unassigned,
               "hubs_by_fan_in": [{"module": m, "in_degree": int(d)} for m, d in zip(hubs.module, hubs.in_degree, strict=True)]}
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    with open(out / "README.txt", "w") as fh:
        fh.write(__doc__.split("Builds", 1)[1])
    print(f"{name}@{sha[:8]}: {summary['modules']} modules, {summary['edges']} import statements "
          f"({summary['distinct_module_edges']} module edges), {summary['packages']} packages, {summary['cycles']} cycles "
          f"(largest {summary['largest_cycle']}), unassigned top-level: {top_unassigned} -> {out}")


if __name__ == "__main__":
    csv.field_size_limit(1 << 20)
    main()

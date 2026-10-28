"""The Differ (Monitor): one commit's import graph against the compiled rules -> the four labels.

    uv run python -m sarms.differ.diff data/raw/kedro --rules data/kedro/rms/rules --out data/kedro/rms
    uv run python -m sarms.differ.diff data/raw/kedro --sha 9039f82a --rules ... --out ...

Reads the rule bundle the compiler wrote (contracts.json + the rule files), checks the commit
with import-linter's own engine (the lint worker, in a fresh process) and writes
<out>/differ/<sha12>/differ.json and differ.sarif. The Differ never calls the model.

What one run produces:
  rows        one per labelled edge:
                ADDITIONAL / INVERTED  a violation import-linter reports under the strict record
                                       (ignore_imports removed), labelled by the rule it breaks;
                                       acknowledged = it disappears under the contracts as written
                CONFIRMED              a module-level import an `allowed` rule covers (layers:
                                       higher -> lower)
                MISSING                only from `required` rules (ADRs); none from contracts
              with the import lines behind it (edges) and direct = one import line is the whole route
  checks      one per contract: kept | broken | error | package_missing | graph_error
  indicators  drift, never a violation: unassigned top-level packages and import cycles (SCCs);
              hub growth needs the series, so the ledger computes it from fan_in
  graph_hash  of the module edges, so the ledger can reuse rows when nothing changed

The replay over a first-parent chain is `sarms.differ.replay`.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

import networkx as nx

from sarms.mining.common import git, module_matches, resolve_ref, worktree_path
from sarms.replay.proxy_lint import WORKER, pythonpath, uses_missing
from sarms.rules.compile import load_bundle, load_rules

VIOLATION_LABELS = ("ADDITIONAL", "INVERTED", "MISSING")


def run_worker(tree, bundle, cache_dir=None, src=None, timeout=900, want_edges=True, want_details=True):
    """Check one checked-out tree. Returns the worker's JSON, or {"graph_error": ...}."""
    tree = Path(tree).resolve()
    session = bundle["session"]
    pp, missing = pythonpath(tree, session["root_packages"], src)
    strict = [c for c in bundle["contracts_strict"] if not uses_missing(c, missing)]
    asis = [c for c in bundle["contracts_asis"] if not uses_missing(c, missing)]
    skipped = [c["name"] for c in bundle["contracts_strict"] if uses_missing(c, missing)]
    if not pp or not strict:
        return {"graph_error": f"missing root(s): {' '.join(missing)}", "package_missing": skipped}
    session_here = {**session, "root_packages": [r for r in session["root_packages"] if r.split(".")[0] not in missing]}
    spec = {"pythonpath": pp, "session_options": session_here, "contracts": strict, "contracts_asis": asis,
            "cache_dir": str(cache_dir) if cache_dir else None, "want_edges": want_edges, "want_details": want_details}
    try:
        p = subprocess.run([sys.executable, str(WORKER)], input=json.dumps(spec), capture_output=True,
                           text=True, timeout=timeout, cwd=tree)
        out = json.loads(p.stdout.strip().splitlines()[-1]) if p.stdout.strip() else {"graph_error": p.stderr[-400:]}
    except subprocess.TimeoutExpired:
        out = {"graph_error": "timeout"}
    out["package_missing"] = skipped
    return out


def match_rule(rules, contract, importer, imported, kind="forbidden"):
    for r in rules:
        if r["source"]["id"] == contract and r["kind"] == kind and r.get("evaluable", True) \
                and module_matches(r["from"], importer) and module_matches(r["to"], imported):
            return r
    return None


def rule_names(rules, roots):
    names = set()
    for r in rules:
        for k in ("from", "to"):
            v = r[k].replace("*", "").strip(".")
            if v and v not in roots and v != "?":
                names.add(v)
    return names


def assigned(module, roots, names):
    for n in names:
        for c in {n} | {f"{r}.{n}" for r in roots}:
            if module == c or module.startswith(c + ".") or c.startswith(module + "."):
                return True
    return False


def label(bundle, rules, res, sha, ts):
    """Turn the worker's result into rows, checks, indicators and a summary."""
    rows, checks = [], []
    for name in res.get("package_missing", []):
        checks.append({"sha": sha, "ts": ts, "contract": name, "status": "package_missing", "error": ""})
    if "graph_error" in res:
        for c in bundle["contracts_strict"]:
            if c["name"] not in res.get("package_missing", []):
                checks.append({"sha": sha, "ts": ts, "contract": c["name"], "status": "graph_error", "error": res["graph_error"]})
        return {"sha": sha, "ts": ts, "rows": rows, "checks": checks, "indicators": [], "graph_hash": None, "summary": {}}

    asis = {(r["contract"], v["importer"], v["imported"]) for r in res.get("results_asis", []) for v in r["violations"]}
    details = res.get("details", {})
    for r in res["results"]:
        checks.append({"sha": sha, "ts": ts, "contract": r["contract"], "status": r["status"], "error": r["error"]})
        for v in r["violations"]:
            rule = match_rule(rules, r["contract"], v["importer"], v["imported"])
            lab = "INVERTED" if rule and rule["source"].get("sentence", "").startswith("layers:") else "ADDITIONAL"
            lines = [{"edge": e, **d} for e in v["edges"] for d in details.get(e, [])]
            rows.append({"sha": sha, "ts": ts, "rule_id": rule["id"] if rule else None, "contract": r["contract"],
                         "edge_from": v["importer"], "edge_to": v["imported"], "label": lab,
                         "acknowledged": (r["contract"], v["importer"], v["imported"]) not in asis,
                         "n_routes": v["n_routes"], "edges": list(v["edges"]),
                         "direct": len(v["edges"]) == 1, "lines": lines})

    edges = [tuple(e) for e in res.get("edges", [])]
    allowed = [r for r in rules if r["kind"] == "allowed" and r.get("evaluable", True)]
    for m, n in edges:
        for r in allowed:
            if module_matches(r["from"], m) and module_matches(r["to"], n):
                rows.append({"sha": sha, "ts": ts, "rule_id": r["id"], "contract": r["source"]["id"],
                             "edge_from": m, "edge_to": n, "label": "CONFIRMED", "acknowledged": False,
                             "n_routes": 1, "edges": [f"{m}->{n}"], "direct": True, "lines": []})
                break

    roots = list(bundle["session"]["root_packages"])
    names = rule_names(rules, roots)
    g = nx.DiGraph()
    g.add_edges_from(edges)
    modules = sorted(g.nodes)
    top = sorted({m for m in modules if m.count(".") == 1 and m.split(".")[0] in roots})
    indicators = []
    unassigned = [m for m in top if not assigned(m, roots, names)]
    for m in unassigned:
        indicators.append({"sha": sha, "ts": ts, "indicator": "unassigned", "edge_from": m, "edge_to": "", "n": 1})
    sccs = [sorted(c) for c in nx.strongly_connected_components(g) if len(c) > 1]
    for comp in sorted(sccs, key=lambda c: (-len(c), c[0])):
        for m in comp:
            indicators.append({"sha": sha, "ts": ts, "indicator": "cycle", "edge_from": m, "edge_to": f"scc:{comp[0]}", "n": len(comp)})
    fan_in = {m: d for m, d in g.in_degree() if d}
    summary = {"modules": len(modules), "edges": len(edges), "cycles": len(sccs),
               "largest_cycle": max((len(c) for c in sccs), default=0), "unassigned": unassigned,
               "fan_in": dict(sorted(fan_in.items(), key=lambda kv: -kv[1])),
               "violations": sum(r["label"] in VIOLATION_LABELS for r in rows),
               "acknowledged": sum(r["label"] in VIOLATION_LABELS and r["acknowledged"] for r in rows),
               "confirmed": sum(r["label"] == "CONFIRMED" for r in rows)}
    gh = hashlib.sha256(json.dumps(edges).encode()).hexdigest()[:16]
    return {"sha": sha, "ts": ts, "rows": rows, "checks": checks, "indicators": indicators, "graph_hash": gh, "summary": summary}


def sarif(result, repo_label, tree):
    """A minimal SARIF 2.1.0 report of the violations (decision records point at these)."""
    results = []
    for r in result["rows"]:
        if r["label"] not in VIOLATION_LABELS:
            continue
        locs = []
        for ln in r["lines"]:
            mod = ln["edge"].split("->")[0]
            locs.append({"physicalLocation": {"artifactLocation": {"uri": mod.replace(".", "/") + ".py"},
                                              "region": {"startLine": ln["line_number"], "snippet": {"text": ln["line_contents"]}}}})
        results.append({"ruleId": r["rule_id"] or r["contract"], "level": "note" if r["acknowledged"] else "error",
                        "message": {"text": f"{r['label']}: {r['edge_from']} -> {r['edge_to']} breaks '{r['contract']}'"
                                            + (" (acknowledged exception)" if r["acknowledged"] else "")
                                            + ("" if r["direct"] else f", through {len(r['edges'])} imports")},
                        "locations": locs[:10], "properties": {"label": r["label"], "acknowledged": r["acknowledged"],
                                                                "direct": r["direct"], "edges": r["edges"]}})
    return {"version": "2.1.0", "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
            "runs": [{"tool": {"driver": {"name": "sarms differ", "version": "0.1"}},
                      "versionControlProvenance": [{"repositoryUri": repo_label, "revisionId": result["sha"]}],
                      "results": results}]}


def checkout(repo_dir, sha, worktree=None):
    """A tree at `sha`: the repository itself when its HEAD is that commit and it is a normal
    checkout, else a detached worktree <repo>.wt (reused between calls)."""
    repo_dir = Path(repo_dir)
    head = git(repo_dir, "rev-parse", "HEAD", check=False).strip()
    bare = git(repo_dir, "rev-parse", "--is-bare-repository").strip() == "true"
    if head == sha and not bare and not worktree:
        return repo_dir
    wt = Path(worktree) if worktree else worktree_path(repo_dir, "wt")
    if not wt.exists():
        git(repo_dir, "worktree", "add", "--detach", "-f", str(wt.resolve()), sha)
    else:
        git(wt, "checkout", "-q", "--force", sha)
        git(wt, "clean", "-fdq")
    return wt


def diff_commit(repo_dir, sha=None, rules_dir=None, out_dir=None, src=None, tree=None, write_files=True, repo_label=None):
    """Run the Differ on one commit. Returns the result dict (and writes differ.json / .sarif)."""
    repo_dir = Path(repo_dir)
    sha = git(repo_dir, "rev-parse", sha or resolve_ref(repo_dir)).strip()
    ts = git(repo_dir, "log", "-1", "--format=%cI", sha).strip()
    rules_dir = Path(rules_dir) if rules_dir else repo_dir / ".rms" / "rules"
    bundle, rules = load_bundle(rules_dir), load_rules(rules_dir)
    tree = Path(tree) if tree else checkout(repo_dir, sha)
    cache = worktree_path(repo_dir, "ilcache").resolve()
    t0 = time.time()
    res = run_worker(tree, bundle, cache, src)
    result = label(bundle, rules, res, sha, ts)
    result["seconds"] = round(time.time() - t0, 1)
    result["rules_dir"] = str(rules_dir)
    if write_files:
        out = Path(out_dir) if out_dir else repo_dir / ".rms"
        d = out / "differ" / sha[:12]
        d.mkdir(parents=True, exist_ok=True)
        (d / "differ.json").write_text(json.dumps(result, indent=1, default=str))
        (d / "differ.sarif").write_text(json.dumps(sarif(result, repo_label or repo_dir.name, tree), indent=1))
        result["paths"] = {"json": str(d / "differ.json"), "sarif": str(d / "differ.sarif")}
    return result


def describe(result):
    """Plain-language lines for a terminal."""
    s = result.get("summary", {})
    viol = [r for r in result["rows"] if r["label"] in VIOLATION_LABELS]
    out = [f"commit {result['sha'][:12]} ({str(result['ts'])[:10]}): {s.get('modules', 0)} modules, {s.get('edges', 0)} imports, "
           f"{len(viol)} broken rules ({sum(r['acknowledged'] for r in viol)} acknowledged), "
           f"{s.get('confirmed', 0)} confirmed edges, {s.get('cycles', 0)} cycle(s), "
           f"{len(s.get('unassigned', []))} unassigned packages"]
    for r in sorted(viol, key=lambda r: (r["acknowledged"], not r["direct"], r["edge_from"])):
        how = "direct" if r["direct"] else f"through {len(r['edges'])} imports"
        out.append(f"  {r['label']:10s} {r['edge_from']} -> {r['edge_to']}   [{r['rule_id'] or r['contract']}] {how}"
                   f"{'  (acknowledged)' if r['acknowledged'] else ''}")
    for c in result["checks"]:
        if c["status"] not in ("kept", "broken"):
            out.append(f"  {c['status']}: {c['contract']} {c['error']}")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("repo_dir")
    ap.add_argument("--sha")
    ap.add_argument("--rules", help="rule bundle directory (default <repo>/.rms/rules)")
    ap.add_argument("--out", help="output root (default <repo>/.rms)")
    ap.add_argument("--src", nargs="*", help="source roots inside the repo if auto-detection fails")
    a = ap.parse_args()
    r = diff_commit(a.repo_dir, a.sha, a.rules, a.out, a.src)
    print(describe(r))
    if "paths" in r:
        print(f"-> {r['paths']['json']}")


if __name__ == "__main__":
    main()

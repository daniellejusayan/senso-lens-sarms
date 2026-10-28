"""Would rules recovered from the graph alone have caught the violations the written contracts caught?

    uv run python tools/replay_recovery.py OWNER/REPO [--cap 30] [--config PATH] [--src DIR ...] [--root PKG ...]

For every episode in data/REPO/episodes.csv (a violation of a written contract, introduced at
start_sha), extract the import graph of the parent commit (the system's view at push time, no
rules), recover rules from it with every method of tools/score_recovery.py, and ask whether the
unit pair of the violating edge is forbidden by the recovered rules. The history methods use
sampled graphs older than the parent when data/REPO/graph/ holds any (tools/sample_graphs.py).

Writes data/REPO/recovery/episodes.json and prints one line per episode plus the summary.
--cap keeps the N most recent distinct pairs (each pair's first episode) when there are more.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from score_recovery import (  # noqa: E402
    HISTORY_METHODS,
    METHODS,
    compile_contracts,
    covers,
    decide,
    load_graph,
    load_record,
    roots_of,
    unit_graph,
    units_auto,
    units_contract,
)

from sarms.mining.common import repo_name  # noqa: E402


def extract(repo_dir: Path, sha: str, roots, config, src, data: Path) -> Path | None:
    out = data / "graph" / sha[:12]
    if (out / "summary.json").exists():
        return out
    cmd = [sys.executable, "-m", "sarms.graph.extract", str(repo_dir), "--sha", sha, "--root", *roots]
    if config:
        cmd += ["--config", config]
    if src:
        cmd += ["--src", *src]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        (data / "recovery").mkdir(parents=True, exist_ok=True)
        with open(data / "recovery" / "extract_failures.log", "a") as fh:
            fh.write(f"== {sha}\n{p.stdout}\n{p.stderr}\n")
        return None
    return out


def chain_endpoints(edges_field, edge_from: str, edge_to: str):
    """The violating module edge's endpoints from the replay's chain: an importer under edge_from
    and an imported module under edge_to (the contract names may be coarser than the units)."""
    items = list(edges_field) if not isinstance(edges_field, str) else [x.strip() for x in edges_field.strip("[]").split(",") if x.strip()]
    pairs = [tuple(x.split("->", 1)) for x in items if "->" in x]
    src = [a for a, _ in pairs if covers(edge_from, a)]
    dst = [b for _, b in pairs if covers(edge_to, b)]
    return (src[0] if src else edge_from), (dst[0] if dst else edge_to)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("owner_repo")
    ap.add_argument("--cap", type=int, default=0, help="keep the N most recent distinct pairs (0 = all)")
    ap.add_argument("--config")
    ap.add_argument("--src", nargs="*")
    ap.add_argument("--root", nargs="*", help="root packages (default: the HEAD record's)")
    a = ap.parse_args()
    name = repo_name(a.owner_repo)
    data = Path("data") / name
    repo_dir = Path("data") / "raw" / name
    opts = load_record(data)
    roots = a.root or roots_of(opts)
    commits = pd.read_parquet(data / "commits.parquet", columns=["idx", "sha", "ts"]).sort_values("idx")
    sha_at = dict(zip(commits.idx, commits.sha, strict=True))
    idx_of = dict(zip(commits.sha, commits.idx, strict=True))
    episodes = pd.read_csv(data / "episodes.csv")
    episodes = episodes[episodes.edge_from.notna() & episodes.edge_to.notna()]
    viol = pd.read_parquet(data / "violations_sample.parquet")
    ext = episodes[~episodes.edge_to.apply(lambda t: any(covers(r, t) for r in roots))]
    episodes = episodes.drop(ext.index)
    firsts = episodes.sort_values("start_idx").drop_duplicates(["edge_from", "edge_to"], keep="first")
    if a.cap and len(firsts) > a.cap:
        firsts = firsts.sort_values("start_idx").tail(a.cap)
    print(f"{name}: {len(episodes) + len(ext)} episodes, {len(ext)} with an external target skipped, "
          f"{episodes[['edge_from', 'edge_to']].drop_duplicates().shape[0]} distinct pairs, scoring {len(firsts)} (first episode per pair)")
    gdirs = sorted(p for p in (data / "graph").iterdir() if (p / "summary.json").exists()) if (data / "graph").is_dir() else []
    samples = []
    for p in gdirs:
        s = json.loads((p / "summary.json").read_text())["sha"]
        if s in idx_of:
            samples.append((idx_of[s], p))
    rows = []
    for e in firsts.itertuples(index=False):
        parent_idx = int(e.start_idx) - 1
        if parent_idx < 0:
            continue
        parent = sha_at[parent_idx]
        row = {"contract": e.contract, "edge_from": e.edge_from, "edge_to": e.edge_to, "start_sha": e.start_sha, "start_idx": int(e.start_idx),
               "parent": parent, "pre_contract": bool(e.pre_contract), "repaired": bool(e.repaired)}
        gdir = extract(repo_dir, parent, roots, a.config, a.src, data)
        if gdir is None:
            row["status"] = "parent graph failed"
            rows.append(row)
            print(f"  {e.edge_from} -> {e.edge_to} @ {e.start_sha[:8]}: parent graph failed")
            continue
        modules, module_edges, _ = load_graph(gdir)
        v = viol[(viol.sha == e.start_sha) & (viol.edge_from == e.edge_from) & (viol.edge_to == e.edge_to)]
        src, dst = chain_endpoints(v.iloc[0].edges, e.edge_from, e.edge_to) if len(v) else (e.edge_from, e.edge_to)
        row.update({"module_from": src, "module_to": dst})
        hist = [load_graph(p)[1] for i, p in samples if i < parent_idx]
        contracts, named, _, _ = compile_contracts(opts, modules)
        for scheme in ("contract", "auto"):
            unit = units_contract(named, modules, roots) if scheme == "contract" else units_auto(modules, roots)[0]
            units = sorted(set(unit.values()))
            lookup = lambda m, unit=unit, units=units: unit.get(m) or next((u for u in sorted(units, key=len, reverse=True) if covers(u, m)), None)  # noqa: E731
            U, V = lookup(src), lookup(dst)
            if U is None or V is None or U == V:
                row[scheme] = {"status": "pair not expressible at this granularity", "units": [U, V]}
                continue
            W = unit_graph(unit, module_edges)
            seen = None
            if hist:
                seen = set()
                for edges_s in hist:
                    for x, y in edges_s:
                        ux, uy = lookup(x), lookup(y)
                        if ux and uy and ux != uy:
                            seen.add((ux, uy))
            D, levels, pos, F0 = decide(units, W, 0.0, seen)
            row[scheme] = {"units": [U, V], "edge_present_at_parent": W.get((U, V), 0), "reverse_edges_at_parent": W.get((V, U), 0),
                           "history_samples": len(hist), "flagged": {m: D[m].get((U, V)) for m in D}}
        row["status"] = "ok"
        rows.append(row)
        c = row.get("contract", {}).get("flagged", {})
        print(f"  {e.edge_from} -> {e.edge_to} @ {e.start_sha[:8]} (parent {parent[:8]}): " +
              " ".join(f"{m}={'F' if c.get(m) == 'forbidden' else ('a' if c.get(m) == 'allowed' else '?')}" for m in c))
    summary = {}
    for scheme in ("contract", "auto"):
        ok = [r for r in rows if r.get("status") == "ok" and isinstance(r.get(scheme), dict) and "flagged" in r[scheme]]
        summary[scheme] = {"scored": len(ok), "flagged": {m: sum(r[scheme]["flagged"].get(m) == "forbidden" for r in ok) for m in METHODS + HISTORY_METHODS},
                           "with_history": sum(r[scheme]["history_samples"] > 0 for r in ok)}
    out = {"repo": name, "roots": roots, "n_episodes": int(len(episodes) + len(ext)), "external_skipped": int(len(ext)), "scored_pairs": len(rows), "rows": rows, "summary": summary}
    (data / "recovery").mkdir(parents=True, exist_ok=True)
    (data / "recovery" / "episodes.json").write_text(json.dumps(out, indent=1, default=str))
    for scheme, s in summary.items():
        print(f"[{scheme}] {s['scored']} pairs scored ({s['with_history']} with history): " + ", ".join(f"{m} {n}" for m, n in s["flagged"].items()))
    print(f"-> {data / 'recovery' / 'episodes.json'}")


if __name__ == "__main__":
    main()

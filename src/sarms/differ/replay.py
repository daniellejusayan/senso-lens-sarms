"""The Differ over a first-parent chain: every commit (or every k-th) labelled with one rule bundle.

    uv run python -m sarms.differ.replay data/raw/kedro main data/kedro/rms --rules data/kedro/rms/rules
    uv run python -m sarms.differ.replay data/raw/kedro main data/kedro/rms --every 25 --since 2020-01-01

Writes <out>/differ/{edges,checks,indicators,graphs}.parquet: the per-commit output of
sarms.differ.diff stacked, with idx = position on the first-parent chain. This is what the
ledger loads. The rule bundle is fixed for the run (the HEAD record, as in the Step 1c replay);
--rules-asof recompiles the bundle at every commit whose config changed (the as-of variant).

Equal graphs are not re-checked: when a commit's tree hash of the source roots equals the
previous one's, the previous result is reused with the new sha (graph_hash marks it).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import pandas as pd

from sarms.differ.diff import checkout, label, run_worker
from sarms.mining.common import IL_FILES, find_il_config, first_parent, git, read_il_options, resolve_ref
from sarms.rules.compile import compile_all, load_bundle, load_rules, validate


def tree_hash(repo_dir, sha, paths):
    """Hash of the source roots' trees at sha (cheap; no checkout)."""
    hs = []
    for p in paths:
        h = git(repo_dir, "rev-parse", "-q", "--verify", f"{sha}:{p}", check=False).strip()
        hs.append(h or "-")
    return "|".join(hs)


def replay(repo_dir, branch, out_dir, rules_dir=None, every=1, since=None, src=None, rules_asof=False,
           config=None, repo_label=None, until=None, log=print):
    """until: stop the chain at this commit (inclusive), e.g. the last commit of a saved replay."""
    repo_dir, out = Path(repo_dir), Path(out_dir)
    (out / "differ").mkdir(parents=True, exist_ok=True)
    ref = resolve_ref(repo_dir, branch or None)
    chain = first_parent(repo_dir, ref, since=since)
    if until:
        full = git(repo_dir, "rev-parse", until).strip()
        pos = [i for i, c in enumerate(chain) if c[1] == full]
        if not pos:
            raise SystemExit(f"--until {until[:12]} is not on the first-parent chain of {ref}")
        chain = chain[:pos[0] + 1]
    sample = [c for n, c in enumerate(chain) if n % every == 0]
    if sample[-1] != chain[-1]:
        sample.append(chain[-1])
    rules_dir = Path(rules_dir) if rules_dir else repo_dir / ".rms" / "rules"
    bundle, rules = load_bundle(rules_dir), load_rules(rules_dir)
    label_repo = repo_label or bundle.get("repo") or repo_dir.name
    cache = Path(f"{repo_dir}.ilcache").resolve()
    roots = [r.split(".")[0] for r in bundle["session"]["root_packages"]]
    rows, checks, inds, graphs = [], [], [], []
    prev_hash, prev_res, last_cfg = None, None, None
    t0 = time.time()
    for n, (idx, sha, ts, _msg) in enumerate(sample, 1):
        if rules_asof:
            fname, text = find_il_config(repo_dir, sha, [config] if config else IL_FILES)
            if not fname:
                continue
            if text != last_cfg:
                opts = read_il_options(fname, text)
                if opts:
                    files, _ack, bundle = compile_all(opts, label_repo, sha, fname)
                    rules = [r for rs in files.values() for r in rs]
                    assert not validate(rules)
                last_cfg = text
        tree = checkout(repo_dir, sha)
        # candidate source dirs for the reuse check: wherever the roots live
        th = tree_hash(repo_dir, sha, [p for r in roots for p in (r, f"src/{r}", f"{r}.py")])
        if th == prev_hash and prev_res is not None:
            res = prev_res
        else:
            res = run_worker(tree, bundle, cache, src)
            prev_hash, prev_res = th, res
        r = label(bundle, rules, res, sha, ts)
        for x in r["rows"]:
            rows.append({"idx": idx, **{k: v for k, v in x.items() if k != "lines"},
                         "edges": list(x["edges"]), "n_lines": len(x["lines"])})
        for x in r["checks"]:
            checks.append({"idx": idx, **x})
        for x in r["indicators"]:
            inds.append({"idx": idx, **x})
        s = r["summary"]
        graphs.append({"idx": idx, "sha": sha, "ts": ts, "graph_hash": r["graph_hash"], "modules": s.get("modules", 0),
                       "edges": s.get("edges", 0), "cycles": s.get("cycles", 0), "largest_cycle": s.get("largest_cycle", 0),
                       "violations": s.get("violations", 0), "acknowledged": s.get("acknowledged", 0),
                       "confirmed": s.get("confirmed", 0), "fan_in": json.dumps(s.get("fan_in", {}))})
        if n % 25 == 0 or n == len(sample):
            el = time.time() - t0
            log(f"  {n}/{len(sample)} commits ({el:.0f}s, ~{el / n * (len(sample) - n):.0f}s left)")
    cols = {"edges": ["idx", "sha", "ts", "rule_id", "contract", "edge_from", "edge_to", "label", "acknowledged",
                      "n_routes", "edges", "direct", "n_lines"],
            "checks": ["idx", "sha", "ts", "contract", "status", "error"],
            "indicators": ["idx", "sha", "ts", "indicator", "edge_from", "edge_to", "n"]}
    frames = {"edges": pd.DataFrame(rows, columns=cols["edges"]), "checks": pd.DataFrame(checks, columns=cols["checks"]),
              "indicators": pd.DataFrame(inds, columns=cols["indicators"]), "graphs": pd.DataFrame(graphs)}
    for name, df in frames.items():
        if len(df):
            df["ts"] = pd.to_datetime(df["ts"], utc=True)
        df.to_parquet(out / "differ" / f"{name}.parquet", index=False)
    log(f"{len(sample)} commits labelled (every {every}); {len(frames['edges'])} edge rows, "
        f"{int((frames['edges'].label != 'CONFIRMED').sum()) if len(frames['edges']) else 0} violation rows -> {out / 'differ'}")
    return frames


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("repo_dir")
    ap.add_argument("branch", nargs="?", default="")
    ap.add_argument("out_dir")
    ap.add_argument("--rules", help="rule bundle (default <repo>/.rms/rules)")
    ap.add_argument("--every", type=int, default=1)
    ap.add_argument("--since")
    ap.add_argument("--src", nargs="*")
    ap.add_argument("--rules-asof", action="store_true", help="recompile the rules at each commit (as-of variant)")
    ap.add_argument("--config")
    ap.add_argument("--until", help="stop at this commit (inclusive)")
    a = ap.parse_args()
    replay(a.repo_dir, a.branch, a.out_dir, a.rules, a.every, a.since, a.src, a.rules_asof, a.config,
           until=a.until, log=lambda s: print(s, flush=True))


if __name__ == "__main__":
    sys.exit(main())

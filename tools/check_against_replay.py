"""The Differ's correctness test on a real subject: does the compiler + Differ + ledger reproduce
what the Step 1c replay found? (build-plan step 2 and 3, "done when")

    uv run python tools/check_against_replay.py kedro-org/kedro            # ~4 minutes on kedro
    uv run python tools/check_against_replay.py kedro-org/kedro --quick    # every 25th commit, ~20 s, edges only

Needs data/raw/REPO (the clone) and data/REPO/{episodes.csv, violations_sample.parquet,
record/contracts.csv} from run_step1.py. Writes data/REPO/rms/ and prints PASS or FAIL per check.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from sarms.differ.replay import replay
from sarms.ledger.build import build, summary
from sarms.rules.compile import compile_repo

ap = argparse.ArgumentParser()
ap.add_argument("owner_repo")
ap.add_argument("--branch", default="")
ap.add_argument("--quick", action="store_true")
ap.add_argument("--src", nargs="*")
ap.add_argument("--config")
a = ap.parse_args()
name = a.owner_repo.split("/")[-1]
raw, data = Path("data/raw") / name, Path("data") / name
rms = data / "rms"
if not raw.exists() or not (data / "violations_sample.parquet").exists():
    sys.exit(f"need data/raw/{name} and data/{name}/violations_sample.parquet first (tools/run_step1.py)")

out, rules, errors = compile_repo(raw, config=a.config, out_dir=rms / "rules", repo_label=name)
ok = True


def check(what, got, want):
    global ok
    good = got == want
    ok &= good
    print(f"{'PASS' if good else 'FAIL'} {what}: {got}" + ("" if good else f" (replay: {want})"))


check("rules validate against the schema", len(errors), 0)
print(f"     {len(rules)} rules compiled from {len({r['source']['id'] for r in rules})} contracts -> {out}")

frames = replay(raw, a.branch, rms, rms / "rules", every=25 if a.quick else 1, src=a.src, config=a.config,
                log=lambda s: print("    ", s, flush=True))
v_old = pd.read_parquet(data / "violations_sample.parquet")
v_new = frames["edges"][frames["edges"].label != "CONFIRMED"]
old_edges = set(map(tuple, v_old[["contract", "edge_from", "edge_to"]].drop_duplicates().values))
new_edges = set(map(tuple, v_new[["contract", "edge_from", "edge_to"]].drop_duplicates().values))
check("distinct violating edges", len(new_edges), len(old_edges))
if new_edges != old_edges:
    print("     only in Differ:", sorted(new_edges - old_edges), "\n     only in replay:", sorted(old_edges - new_edges))
if not a.quick:
    check("violation rows over the whole history", len(v_new), len(v_old))
    led = build(rms, a.owner_repo, data / "record" / "contracts.csv")
    print(summary(led, a.owner_repo))
    e_old = pd.read_csv(data / "episodes.csv")
    ep = led["episodes"]
    post_old, post_new = e_old[~e_old.pre_contract.astype(bool)], ep[~ep.pre_contract.astype(bool)]
    check("episodes after the contract", len(post_new), len(post_old))
    check("episodes repaired", int(post_new.repaired.sum()), int(post_old.repaired.sum()))
    ro, rn = post_old[post_old.repaired.astype(bool)], post_new[post_new.repaired.astype(bool)]
    check("median gap, commits", round(float(rn.gap_commits.median()), 1), round(float(ro.gap_commits.median()), 1))
    check("median gap, days", round(float(rn.gap_days.median()), 1), round(float(ro.gap_days.median()), 1))
print("ALL PASS" if ok else "SOME CHECKS FAILED")
sys.exit(0 if ok else 1)

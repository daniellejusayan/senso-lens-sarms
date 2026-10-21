"""Draw the labelling samples the evaluation protocol fixes, from the episodes the baseline wrote.

    uv run python tools/draw_sample.py kedro-org/kedro sqlfluff/sqlfluff bridgecrewio/checkov

Reads data/REPO/episodes.csv (written by sarms.replay.baseline) for the repositories given,
keeps post-contract episodes, and draws with numpy.random.default_rng(2569):
  data/samples/precision_100.csv   100 episodes, stratified by repository (equal shares,
                                   remainder to the largest), for the two-rater precision check
  data/samples/rootcause_50.csv    50 of those 100, for the root-cause labelling (kappa)
  docs/spec/pilot-sheet.csv        the 50 with the rater columns empty, ready to fill
Fewer episodes than requested -> every episode is taken and the shortfall is printed.
Commit the three files before anyone opens a case (evaluation-protocol.md).
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np
import pandas as pd

from sarms.mining.common import repo_name

RATER_COLS = ["rater", "differ_label_correct (y/n)", "root_cause", "evidence_sentence", "evidence_url", "notes"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("repos", nargs="+")
    ap.add_argument("--n-precision", type=int, default=100)
    ap.add_argument("--n-rootcause", type=int, default=50)
    ap.add_argument("--seed", type=int, default=2569)
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)
    frames = []
    for r in a.repos:
        f = Path("data") / repo_name(r) / "episodes.csv"
        if not f.exists():
            print(f"skip {r}: {f} missing (run tools/run_step1.py first)")
            continue
        e = pd.read_csv(f)
        e = e[~e.pre_contract.astype(bool)].copy()
        e.insert(0, "repo", r)
        frames.append(e)
    ep = pd.concat(frames, ignore_index=True)
    ep["case_id"] = [f"{repo_name(r)}-{s[:8]}-{i}" for i, (r, s) in enumerate(zip(ep.repo, ep.start_sha, strict=True))]
    ep["url_introduced"] = "https://github.com/" + ep.repo + "/commit/" + ep.start_sha
    ep["url_repaired"] = ["https://github.com/" + r + "/commit/" + str(s) if isinstance(s, str) else "" for r, s in zip(ep.repo, ep.end_sha, strict=True)]

    per = {r: g for r, g in ep.groupby("repo")}
    share = a.n_precision // len(per)
    picks = []
    for _r, g in sorted(per.items(), key=lambda kv: -len(kv[1])):
        k = min(share, len(g))
        picks.append(g.iloc[rng.choice(len(g), size=k, replace=False)])
    chosen = pd.concat(picks)
    rest = ep.drop(chosen.index)
    short = a.n_precision - len(chosen)
    if short > 0 and len(rest):
        chosen = pd.concat([chosen, rest.iloc[rng.choice(len(rest), size=min(short, len(rest)), replace=False)]])
    chosen = chosen.sort_values(["repo", "start_idx"]).reset_index(drop=True)
    out = Path("data/samples")
    out.mkdir(parents=True, exist_ok=True)
    cols = ["case_id", "repo", "contract", "edge_from", "edge_to", "start_sha", "start_ts", "end_sha", "end_ts",
            "gap_commits", "gap_days", "repaired", "url_introduced", "url_repaired"]
    chosen[cols].to_csv(out / "precision_100.csv", index=False)
    k = min(a.n_rootcause, len(chosen))
    rc = chosen.iloc[np.sort(rng.choice(len(chosen), size=k, replace=False))]
    rc[cols].to_csv(out / "rootcause_50.csv", index=False)
    with open("docs/spec/pilot-sheet.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(cols + RATER_COLS)
        for row in rc[cols].itertuples(index=False):
            w.writerow(list(row) + [""] * len(RATER_COLS))
    print(f"{len(ep)} post-contract episodes from {len(per)} repositories -> {len(chosen)} precision cases"
          f"{'' if len(chosen) >= a.n_precision else f' (short of {a.n_precision})'}, {k} root-cause cases; seed {a.seed}")
    print("-> data/samples/precision_100.csv, data/samples/rootcause_50.csv, docs/spec/pilot-sheet.csv")


if __name__ == "__main__":
    main()

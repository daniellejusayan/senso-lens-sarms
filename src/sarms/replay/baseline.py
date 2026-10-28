"""Step 1c, part 3: the awareness-gap baseline and criterion 4, per repository.

    uv run python -m sarms.replay.baseline data/REPO OWNER/REPO

Reads data/REPO/checks_sample.parquet, violations_sample.parquet and record/{events.parquet,
contracts.csv}; writes reports/awareness-gap-baseline/REPO.md and rebuilds
reports/awareness-gap-baseline.md (a summary table plus every repository's section).

Definitions (docs/spec/evaluation-protocol.md):
  violating edge   (contract, edge_from, edge_to) as import-linter reports it
  episode          consecutive sampled commits in which the edge is present
  introduced_at    first sampled commit of the episode
  repaired_at      first later sampled commit without it, while the contract could be checked
  gap              repaired_at - introduced_at in first-parent commits and in days; with a
                   stride of K the true gap is within +/- K commits of the value shown
  pre-contract     an episode that began before its contract was written: kept in the
                   series, flagged, excluded from the gap (runbook Step 1c)
  drop             a sampled interval in which the violation count (illegal routes over the
                   contracts that could be checked at both ends) fell: criterion 4
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

import pandas as pd

from sarms.ledger.episodes import episodes
from sarms.mining.common import REPORTS


def stat(s):
    return "–" if s.empty else f"{s.median():.0f} (p90 {s.quantile(.9):.0f})"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data_dir")
    ap.add_argument("owner_repo")
    ap.add_argument("--suffix", default="", help="'' for the strict HEAD run, '_asof' etc. for the variants")
    ap.add_argument("--exploratory", action="store_true", help="detection-only case: report under reports/exploratory/, kept out of the summary")
    a = ap.parse_args()
    d, repo = Path(a.data_dir), a.owner_repo
    checks = pd.read_parquet(d / f"checks_sample{a.suffix}.parquet")
    viols = pd.read_parquet(d / f"violations_sample{a.suffix}.parquet")
    ev = pd.read_parquet(d / "record/events.parquet") if (d / "record/events.parquet").exists() else pd.DataFrame()
    intro = {}
    if (d / "record/contracts.csv").exists():
        for r in csv.DictReader(open(d / "record/contracts.csv")):
            if r["introduced_at"]:
                intro[r["contract"]] = pd.Timestamp(r["introduced_at"]).tz_convert("UTC")
    samples = checks[["idx", "ts"]].drop_duplicates().sort_values("idx")
    stride = int(samples.idx.diff().median()) if len(samples) > 1 else 1

    ep = episodes(checks, viols, intro)
    post = ep[~ep.pre_contract]
    rep = post[post.repaired]
    ok = checks[checks.status.isin(["kept", "broken"])]
    routes = ok.groupby("idx").n_routes.sum().sort_index()
    same = ok.groupby("idx").contract.nunique().sort_index()
    same = same.eq(same.shift())
    drops = int(((routes.diff() < 0) & same).sum())
    rises = int(((routes.diff() > 0) & same).sum())
    fixed = ev[(ev.event == "debt_removed") & (ev.cause == "entry_removed")] if len(ev) else pd.DataFrame(columns=["sha"])
    url = f"https://github.com/{repo}/commit/"
    ex = rep.sort_values("gap_days", ascending=False).head(3)
    name = repo.split("/")[-1]
    lines = [
        f"## {repo}",
        "",
        f"Record: {len(intro)} contracts, first written {min(intro.values()):%Y-%m-%d}." if intro else "Record: no contracts found.",
        f"Sampled {len(samples)} first-parent commits, {samples.ts.min():%Y-%m-%d} to {samples.ts.max():%Y-%m-%d}, "
        f"median stride {stride} (resolution ±{stride} commits). Statuses: {checks.status.value_counts().to_dict()}.",
        "",
        "| Measure | Value |",
        "| --- | --- |",
        f"| Distinct violating edges seen | {ep[['contract', 'edge_from', 'edge_to']].drop_duplicates().shape[0]} |",
        f"| Episodes (after the contract / pre-contract) | {len(post)} / {int(ep.pre_contract.sum())} |",
        f"| Share later repaired (after the contract) | {len(rep)} of {len(post)} ({(len(rep) / len(post) * 100 if len(post) else 0):.0f}%) |",
        f"| Gap, commits: median (p90) | {stat(rep.gap_commits)} |",
        f"| Gap, days: median (p90) | {stat(rep.gap_days)} |",
        f"| Rises / drops in the violation count (criterion 4 = drops) | {rises} / {drops} |",
        f"| Commits that removed an `ignore_imports` exception | {fixed.sha.nunique() if len(fixed) else 0} |",
        "",
        "Longest repaired gaps:",
        "",
        *(f"- `{r.edge_from} → {r.edge_to}` ({r.contract}): introduced [{r.start_sha[:8]}]({url}{r.start_sha}) "
          f"{r.start_ts:%Y-%m-%d}, gone at [{r.end_sha[:8]}]({url}{r.end_sha}) {r.end_ts:%Y-%m-%d}, "
          f"{r.gap_commits:.0f} commits / {r.gap_days:.0f} days" for r in ex.itertuples()),
        "" if len(ex) else "- none repaired in the window",
        f"Caveat: resolution is the sampling stride (±{stride} commits); Weeks 2–3 recompute per commit with the Differ.",
        "",
    ]
    ep.to_csv(d / f"episodes{a.suffix}.csv", index=False)
    if a.exploratory:
        (REPORTS / "exploratory").mkdir(parents=True, exist_ok=True)
        note = ["", "Exploratory, detection only: this repository fails selection criteria 5–7 and is not a subject; "
                "its numbers are reported for what they show about repair behaviour, never used for drafts.", ""]
        (REPORTS / "exploratory" / f"{name}{a.suffix}.md").write_text("\n".join(lines[:2] + note + lines[2:]))
        print("\n".join(lines[:16]))
        print(f"-> {REPORTS / 'exploratory' / (name + a.suffix + '.md')}")
        return
    (REPORTS / "awareness-gap-baseline").mkdir(parents=True, exist_ok=True)
    (REPORTS / "awareness-gap-baseline" / f"{name}{a.suffix}.md").write_text("\n".join(lines))
    row = {"repo": repo, "variant": a.suffix or "head_strict", "sampled": len(samples), "stride": stride,
           "edges": ep[["contract", "edge_from", "edge_to"]].drop_duplicates().shape[0],
           "episodes_after_contract": len(post), "repaired": len(rep),
           "median_gap_commits": rep.gap_commits.median() if len(rep) else "",
           "median_gap_days": round(rep.gap_days.median(), 1) if len(rep) else "",
           "drops": drops, "exception_removal_commits": fixed.sha.nunique() if len(fixed) else 0}
    summary = REPORTS / "awareness-gap-baseline" / "summary.csv"
    old = [r for r in csv.DictReader(open(summary))] if summary.exists() else []
    old = [r for r in old if not (r["repo"] == repo and r["variant"] == row["variant"])] + [row]
    with open(summary, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(row))
        w.writeheader()
        w.writerows(old)
    sections = sorted((REPORTS / "awareness-gap-baseline").glob("*.md"))
    head = ["# Awareness-gap baseline (proxy run, Step 1c)", "",
            "Strict HEAD record applied to first-parent commits (every commit where the table says stride 1; "
            "otherwise every 25th plus commits whose message names imports, layers, dependencies, cycles or "
            "refactoring). Exceptions in `ignore_imports` count as violations. Pre-contract episodes are in the "
            "series but not in the gap. Windowed runs (--since) start a month before the first contract.", "",
            "| Repository | Sampled | Edges | Episodes | Repaired | Median gap (commits / days) | Drops (C4) | Exception removals |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for r in old:
        head.append(f"| {r['repo']} {'' if r['variant'] == 'head_strict' else '(' + r['variant'] + ')'} | {r['sampled']} | {r['edges']} | "
                    f"{r['episodes_after_contract']} | {r['repaired']} | {r['median_gap_commits'] or '–'} / {r['median_gap_days'] or '–'} | "
                    f"{r['drops']} | {r['exception_removal_commits']} |")
    body = [s.read_text() for s in sections]
    (REPORTS / "awareness-gap-baseline.md").write_text("\n".join(head + [""] + body))
    print("\n".join(lines[:16]))
    print(f"-> {REPORTS / 'awareness-gap-baseline.md'}")


if __name__ == "__main__":
    main()

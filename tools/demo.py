"""Show what Steps 1-2 produced for one repository, in plain words, from data already on disk.

    uv run python tools/demo.py kedro
    uv run python tools/demo.py checkov

Reads only: data/REPO/commits.parquet, record/contracts.csv, record/events.parquet,
violations_sample.parquet, episodes.csv, graph/*/summary.json and, when the loop has run,
rms/differ/*/differ.json and rms/drafts/*/result.json. Writes nothing, so it is safe
to run in front of anyone. Each section says which file the numbers come from.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd


def head(title):
    print(f"\n{'=' * 78}\n {title}\n{'=' * 78}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("repo", help="folder name under data/, e.g. kedro")
    a = ap.parse_args()
    d = Path("data") / a.repo
    if not d.exists():
        sys.exit(f"no data/{a.repo}; run: uv run python tools/run_step1.py OWNER/{a.repo} --every 1")

    head(f"1. HISTORY - every landing on the main branch          (data/{a.repo}/commits.parquet)")
    c = pd.read_parquet(d / "commits.parquet")
    print(f"  {len(c):,} commits on the main branch, {c.ts.min():%d %b %Y} -> {c.ts.max():%d %b %Y}")
    print(f"  {int(c.is_merge.sum())} merges; {c.author_hash.nunique()} distinct authors (salted codes, no names or e-mails)")

    head(f"2. THE TEAM'S OWN RULES - read from their config file  (data/{a.repo}/record/)")
    k = pd.read_csv(d / "record" / "contracts.csv")
    for r in k.itertuples(index=False):
        when = str(r.introduced_at)[:10] if isinstance(r.introduced_at, str) else "?"
        print(f"  [{r.type:12s}] {r.contract}   (written {when})")
    ev = pd.read_parquet(d / "record" / "events.parquet") if (d / "record" / "events.parquet").exists() else pd.DataFrame()
    if len(ev):
        added = int((ev.event == "debt_added").sum())
        removed = int((ev.event == "debt_removed").sum())
        print(f"  'ignore this' list over time: {added} exceptions added, {removed} removed")

    head(f"3. BROKEN RULES STILL IN THE CODE TODAY                 (data/{a.repo}/violations_sample.parquet)")
    v = pd.read_parquet(d / "violations_sample.parquet")
    now = v[v.idx == v.idx.max()]
    if now.empty:
        print("  none")
    for r in now.drop_duplicates(["contract", "edge_from", "edge_to"]).itertuples(index=False):
        print(f"  {r.edge_from} -> {r.edge_to}")
        print(f"      breaks: {r.contract}")
        chain = [] if r.edges is None else [r.edges] if isinstance(r.edges, str) else list(r.edges)
        if len(chain) == 1:
            print(f"      direct import: {chain[0].replace('->', ' imports ')}")
        elif chain:
            print(f"      indirect: reaches it through a chain of {len(chain)} imports")

    head(f"4. THE AWARENESS GAP - how long broken rules waited     (data/{a.repo}/episodes.csv)")
    e = pd.read_csv(d / "episodes.csv")
    post = e[~e.pre_contract.astype(bool)]
    fixed = post[post.repaired.astype(bool)]
    print(f"  {len(post)} times a rule was broken after it was written")
    print(f"  {len(fixed)} later fixed by a person, {len(post) - len(fixed)} never fixed")
    if len(fixed):
        print(f"  median wait: {fixed.gap_commits.median():.0f} commits / {fixed.gap_days.median():.0f} days"
              f"   (longest {fixed.gap_days.max():.0f} days)")
        print("  longest waits:")
        for r in fixed.sort_values("gap_days", ascending=False).head(3).itertuples(index=False):
            print(f"    {r.edge_from} -> {r.edge_to}: {str(r.start_ts)[:10]} to {str(r.end_ts)[:10]}"
                  f"  = {r.gap_commits:.0f} commits, {r.gap_days:.0f} days")

    graphs = sorted((d / "graph").glob("*/summary.json")) if (d / "graph").exists() else []
    if graphs:
        head(f"5. THE IMPORT GRAPH THE SYSTEM READS                    (data/{a.repo}/graph/)")
        for g in graphs:
            s = json.loads(g.read_text())
            when = c.loc[c.sha == s["sha"], "ts"]
            label = f"{when.iloc[0]:%d %b %Y}" if len(when) else s["sha"][:8]
            print(f"  {label}: {s['modules']} modules, {s['distinct_module_edges']} imports, "
                  f"{s['cycles']} cycle(s) (largest {s['largest_cycle']} modules)")
            if s.get("top_level_unassigned"):
                print(f"      packages no rule mentions: {', '.join(m.split('.')[-1] for m in s['top_level_unassigned'])}")

    runs = sorted((d / "rms" / "differ").glob("*/differ.json")) if (d / "rms" / "differ").exists() else []
    if runs:
        head(f"6. THE LIVE LOOP - what the system itself says today      (data/{a.repo}/rms/)")
        r = json.loads(max(runs, key=lambda p: p.stat().st_mtime).read_text())
        viol = [x for x in r["rows"] if x["label"] != "CONFIRMED"]
        print(f"  rules compiled from the team's contracts, checked on commit {r['sha'][:8]} in {r.get('seconds', '?')} s:")
        print(f"  {len(viol)} broken rules ({sum(x['acknowledged'] for x in viol)} on the team's 'ignore this' list), "
              f"{sum(x['direct'] for x in viol)} direct, {r['summary'].get('confirmed', 0)} imports confirmed as allowed")
        for x in viol:
            if x["direct"]:
                print(f"    direct: {x['edge_from']} -> {x['edge_to']}  ({len(x['lines'])} import line(s) in {x['lines'][0]['edge'].split('->')[0] if x['lines'] else '?'})")
        drafts = sorted((d / "rms" / "drafts").glob("*/result.json")) if (d / "rms" / "drafts").exists() else []
        for f in drafts:
            res = json.loads(f.read_text())
            v = res["violation"]
            last = res["attempts"][-1] if res["attempts"] else {}
            model = (last.get("model") or {}).get("model", res["class"])
            print(f"  draft {f.parent.name}: {v['edge_from']} -> {v['edge_to']} by {model}: {res['verdict']} "
                  f"after {res['tries']} attempt(s)" + (f"; {last['problems'][0][:90]}" if last.get("problems") else ""))
    print()


if __name__ == "__main__":
    main()

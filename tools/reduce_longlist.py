"""Step 1a, first pass: reduce the team's Step1_usable_repos list to the repositories worth
cloning, with one recorded reason per dropped row.

    uv run python tools/reduce_longlist.py data/Step1_usable_repos_230.csv

Writes data/longlist_decisions.csv (every input row, kept/dropped + rule) and data/longlist.txt
(the kept rows, in the format tools/screen.py reads). The rules are the ones frozen in
docs/repo-selection.md (R1-R4); nothing here needs a clone, so the whole list runs in a second.
The list's own columns are used as-is (contract and ADR counts, years, commits, stars); every
kept row is re-measured by tools/screen.py afterwards.
"""
from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

# Forks or duplicates of a repository that is itself on the list, and the checker's own repos.
FORKS = {"cloudflowdev/airflow": "fork of apache/airflow", "Rahil-Shah-3105/airflow-python": "fork of apache/airflow",
         "strcho/my-dify-fork": "fork of langgenius/dify", "pranowoaryawo-cyber/code": "copy of langgenius/dify (api/.importlinter)",
         "gru3zi/iris-fork": "fork", "seddonym/import-linter": "the checker itself", "seddonym/grimp": "the checker's graph library"}
# Repositories whose history cannot be fetched with a partial clone in the time we have are not
# dropped here; screen.py takes a "!nocheckout" flag for them.
HUGE = {"openedx/openedx-platform", "apache/airflow", "truenas/middleware"}


def num(s, rx):
    m = re.search(rx, s or "")
    return int(m.group(1)) if m else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--min-stars", type=int, default=50)
    ap.add_argument("--out-dir", default="data")
    a = ap.parse_args()
    rows = list(csv.DictReader(open(a.csv, encoding="utf-8-sig")))
    out, kept = [], []
    for r in rows:
        repo = r["Repository"].strip()
        intent = r.get("C2 Intent", "")
        contracts, adrs = num(intent, r"(\d+) import-linter"), num(intent, r"(\d+) ADRs")
        years = float(r.get("C3 Years of history") or 0)
        commits = int(float(r.get("Commits") or 0))
        stars = int(float(r.get("Stars") or 0))
        config = r.get("Rule config") or ""
        rule, why = "", ""
        if repo in FORKS:
            rule, why = "R3", FORKS[repo]
        elif not (contracts >= 2 or adrs >= 10):
            rule, why = "R1", f"intent too thin: {contracts} contracts, {adrs} ADRs (need >=2 or >=10)"
        elif not (years >= 2 and commits >= 1000):
            rule, why = "R2", f"history too short: {years:.1f} years, {commits} commits (need >=2 and >=1000)"
        elif stars < a.min_stars:
            rule, why = "R4", f"{stars} stars (< {a.min_stars}): no sign of a team behind it"
        elif "tach" in config.lower() and contracts == 0 and adrs < 10:
            rule, why = "R5", "tach-only rules; the replay tooling reads import-linter"
        decision = "dropped" if rule else "kept"
        if decision == "kept":
            kept.append(repo + (" !nocheckout" if repo in HUGE else ""))
        out.append({"repo": repo, "url": r.get("URL", ""), "decision": decision, "rule": rule, "reason": why,
                    "contracts_listed": contracts, "adrs_listed": adrs, "years_listed": years,
                    "commits_listed": commits, "stars_listed": stars, "config_listed": config,
                    "step1_status_listed": r.get("Step 1 status", "")})
    od = Path(a.out_dir)
    od.mkdir(parents=True, exist_ok=True)
    with open(od / "longlist_decisions.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    (od / "longlist.txt").write_text("# kept by tools/reduce_longlist.py (rules R1-R5 in docs/repo-selection.md)\n"
                                     + "\n".join(kept) + "\n")
    by = {}
    for o in out:
        by[o["rule"] or "kept"] = by.get(o["rule"] or "kept", 0) + 1
    print(f"{len(rows)} rows -> {len(kept)} kept; " + ", ".join(f"{k}: {v}" for k, v in sorted(by.items())))
    print(f"-> {od/'longlist_decisions.csv'}, {od/'longlist.txt'}")


if __name__ == "__main__":
    main()

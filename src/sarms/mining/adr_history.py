"""Step 1c for the ADR track: what the ADRs say and when they arrived.

    uv run python -m sarms.mining.adr_history data/raw/REPO "$BRANCH" data/REPO OWNER/REPO

Lists every ADR file at HEAD (same folder rules as tools/screen.py), dates each by the first
first-parent commit that added it, reads its title and status, and flags the ones whose text
states a dependency or structure rule — the "explicit, code-inferable" class the rule compiler
can take (the split reported in the proposal's [16]). Writes data/REPO/adrs.csv and a short
reports/adr-track/<repo>.md. No LLM; the flag is a keyword screen that Week 2 refines by hand.
"""
from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

from sarms.mining.common import ADR_DIR, ADR_FILE, ADR_SKIP, REPORTS, git, resolve_ref, show

STRUCTURAL = re.compile(
    r"\b(import|imports|importing|depend|dependency|dependencies|layer|layers|module|modules|package|packages|"
    r"boundary|boundaries|must not|shall not|should not|only through|never call|circular|coupling|interface)\b", re.I)
STATUS = re.compile(r"^\s*(?:\*\*)?status(?:\*\*)?\s*[:|]\s*(.+?)\s*$", re.I | re.M)
TITLE = re.compile(r"^#\s*(.+?)\s*$", re.M)


def adr_files(d, head):
    files = git(d, "ls-tree", "-r", "--name-only", head).splitlines()
    return [f for f in files if ADR_DIR.search(f) and ADR_FILE.search(f) and not ADR_SKIP.search(f)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("repo_path")
    ap.add_argument("branch")
    ap.add_argument("out_dir")
    ap.add_argument("owner_repo")
    a = ap.parse_args()
    d, out = Path(a.repo_path), Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    ref = resolve_ref(d, a.branch or None)
    head = git(d, "rev-parse", ref).strip()
    rows = []
    for f in adr_files(d, head):
        added = git(d, "log", "--first-parent", "--reverse", "--diff-filter=A", "--format=%H%x09%cs", ref, "--", f).splitlines()
        sha, date = (added[0].split("\t") if added else ("", ""))
        text = show(d, head, f) or ""
        title = (TITLE.search(text).group(1) if TITLE.search(text) else Path(f).stem)[:120]
        status = (STATUS.search(text).group(1) if STATUS.search(text) else "")[:40]
        hits = sorted({m.lower() for m in STRUCTURAL.findall(text)})
        rows.append({"path": f, "title": title, "status": status, "added_sha": sha, "added_date": date,
                     "words": len(text.split()), "structural_terms": " ".join(hits), "structural": len(hits) >= 2})
    rows.sort(key=lambda r: (r["added_date"], r["path"]))
    with open(out / "adrs.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]) if rows else ["path"])
        w.writeheader()
        w.writerows(rows)
    n_struct = sum(r["structural"] for r in rows)
    dates = [r["added_date"] for r in rows if r["added_date"]]
    name = a.owner_repo.split("/")[-1]
    url = f"https://github.com/{a.owner_repo}/blob/{head[:12]}/"
    lines = [f"# ADR track: {a.owner_repo}", "",
             f"{len(rows)} ADR files at `{head[:8]}`; first added {min(dates) if dates else '–'}, last {max(dates) if dates else '–'}; "
             f"{n_struct} flagged structural by keyword screen (≥ 2 distinct terms) — the candidates for rule compilation.", "",
             "| Added | Title | Status | Structural terms |", "| --- | --- | --- | --- |"]
    for r in rows:
        if r["structural"]:
            lines.append(f"| {r['added_date']} | [{r['title']}]({url}{r['path']}) | {r['status']} | {r['structural_terms']} |")
    (REPORTS / "adr-track").mkdir(parents=True, exist_ok=True)
    (REPORTS / "adr-track" / f"{name}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{len(rows)} ADRs, {n_struct} structural, {min(dates) if dates else '–'} -> {max(dates) if dates else '–'} -> {out/'adrs.csv'}, reports/adr-track/{name}.md")


if __name__ == "__main__":
    main()

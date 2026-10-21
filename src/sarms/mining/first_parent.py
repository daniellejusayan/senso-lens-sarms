"""Step 1b: the first-parent history of a repository, one row per commit.

    uv run python -m sarms.mining.first_parent data/raw/REPO "$BRANCH" data/REPO/commits.parquet

Same command and output path as the runbook. One `git log` call instead of one diff per
commit, so it is fast on large histories, and it reads only trees (`--name-status
--no-renames`), so it works on the partial clone without downloading file contents.

Columns: idx, sha, ts (committer time, UTC), author_ts, author_hash (salted, never the
e-mail), is_merge, n_parents, n_files, py_files (list), msg (first line, <= 200 chars),
pr_number (from "Merge pull request #N" or a trailing "(#N)"; null if none).

A merge commit is read with --diff-merges=first-parent, i.e. as what it added to the
branch. Plain `git log --name-status` (and PyDriller) report no files for a merge.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

from sarms.mining.common import git, pseudonym, resolve_ref

SEP = "\x1e"
FMT = SEP + "%H%x1f%P%x1f%cI%x1f%aI%x1f%ae%x1f%s"
PR = [re.compile(r"Merge pull request #(\d+)"), re.compile(r"\(#(\d+)\)\s*$")]


def pr_number(subject: str):
    for rx in PR:
        m = rx.search(subject)
        if m:
            return int(m.group(1))
    return None


def mine(repo_path: str, branch: str | None, out: str) -> pd.DataFrame:
    ref = resolve_ref(repo_path, branch)
    raw = git(repo_path, "log", "--first-parent", "--diff-merges=first-parent", "--no-renames",
              "--name-status", "--reverse", f"--format={FMT}", ref)
    rows = []
    for idx, block in enumerate(b for b in raw.split(SEP) if b.strip()):
        head, _, rest = block.partition("\n")
        sha, parents, cts, ats, email, subj = head.split("\x1f", 5)
        files = [line.split("\t")[-1] for line in rest.splitlines() if "\t" in line]
        np_ = len(parents.split())
        rows.append({
            "idx": idx, "sha": sha, "ts": cts, "author_ts": ats, "author_hash": pseudonym(email),
            "is_merge": np_ > 1, "n_parents": np_, "n_files": len(files),
            "py_files": [f for f in files if f.endswith(".py")], "msg": subj[:200],
            "pr_number": pr_number(subj),
        })
    df = pd.DataFrame(rows)
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    df["author_ts"] = pd.to_datetime(df["author_ts"], utc=True)
    df["pr_number"] = df["pr_number"].astype("Int64")
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)
    expected = int(git(repo_path, "rev-list", "--first-parent", "--count", ref))
    big = df.loc[df.is_merge, "n_files"].max() if df.is_merge.any() else 0
    print(f"{len(df)} first-parent commits -> {out}  (rev-list says {expected}: "
          f"{'OK' if expected == len(df) else 'MISMATCH'}); {int(df.is_merge.sum())} merges, "
          f"largest merge touches {big} files; {int(df.pr_number.notna().sum())} commits name a PR; "
          f"{df.ts.min():%Y-%m-%d} -> {df.ts.max():%Y-%m-%d}")
    return df


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit("usage: python -m sarms.mining.first_parent data/raw/REPO BRANCH data/REPO/commits.parquet")
    mine(sys.argv[1], sys.argv[2] or None, sys.argv[3])

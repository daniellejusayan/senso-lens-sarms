# Commands for Steps 1 and 2 (from the repository root)

```bash
# Step 1a — screen candidates (criteria: docs/repo-selection.md)
uv run python tools/rawscan.py data/longlist.txt          # fast: contracts at the root, no clone
uv run python tools/adrscan.py data/longlist.txt          # fast: common ADR folders
uv run python tools/screen.py data/longlist.txt           # full screening -> data/candidates.csv
tools/check_tests.sh OWNER/REPO '<install cmd>' '<test cmd>'   # criterion tests -> data/tests.csv

# Step 1b — mine the first-parent history (REPO = name without owner, clone in data/raw/REPO)
BRANCH=$(git -C data/raw/REPO symbolic-ref --short refs/remotes/origin/HEAD | cut -d/ -f2)
uv run python -m sarms.mining.first_parent data/raw/REPO "$BRANCH" data/REPO/commits.parquet

# Step 1c — freeze the record, replay it, write the baseline
uv run python -m sarms.rules.record_history data/raw/REPO "$BRANCH" data/REPO/record [--since YYYY-MM-DD]
uv run python -m sarms.replay.proxy_lint data/raw/REPO "$BRANCH" data/REPO                    # sampled
uv run python -m sarms.replay.proxy_lint data/raw/REPO "$BRANCH" data/REPO --every 1 --match ''  # every commit
uv run python -m sarms.replay.baseline data/REPO OWNER/REPO                                     # -> reports/awareness-gap-baseline.md

# Step 2 — validate the specification before tagging
uv run python tools/validate_spec.py      # prints the protocol hash for the P1 pack
```

Measured on kedro (1,957 first-parent commits): first_parent 1 s · record_history 60 s ·
proxy_lint 2 min sampled, 5 min every commit · baseline 2 s. The screening script needs a
clone per repository (partial, blob-less); `screen.py` makes it under `data/raw/`.

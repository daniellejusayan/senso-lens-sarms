# Commands for Steps 1 and 2 (from the repository root)

```bash
# Step 1a — screen candidates (criteria: docs/repo-selection.md)
uv run python tools/reduce_longlist.py data/Step1_usable_repos_230.csv   # the team's sheet -> data/longlist.txt + longlist_decisions.csv
uv run python tools/rawscan.py data/longlist.txt          # fast: contracts at the root, no clone
uv run python tools/adrscan.py data/longlist.txt          # fast: common ADR folders
uv run python tools/screen.py data/longlist.txt           # full screening -> data/candidates.csv
tools/check_tests.sh OWNER/REPO '<install cmd>' '<test cmd>'   # criterion tests -> data/tests.csv

# Steps 1b + 1c in one go (any OS; skips stages whose output exists; timings in data/REPO/timings.csv)
uv run python tools/run_step1.py OWNER/REPO --every 1                              # every commit
uv run python tools/run_step1.py OWNER/REPO --every 1 --since 2023-06-01           # large history: window
uv run python tools/run_step1.py OWNER/REPO --config apps/backend/pyproject.toml --src apps/backend   # monorepo
uv run python tools/run_step1.py OWNER/REPO --skip-proxy                            # ADR track: 1b + record only
uv run python -m sarms.mining.adr_history data/raw/REPO "$BRANCH" data/REPO OWNER/REPO   # ADR track: dates, titles, structural flag
uv run python -m sarms.graph.extract data/raw/REPO [--sha SHA]                      # the import graph of one commit -> data/REPO/graph/<sha>/
uv run python tools/render_graph.py data/REPO/graph/<sha12> reports/figures/NAME   # draw it (Graphviz)
uv run python tools/draw_sample.py OWNER/REPO [OWNER/REPO ...]                      # the seeded labelling samples (commit them)

# Step 1b — mine the first-parent history (REPO = name without owner, clone in data/raw/REPO)
BRANCH=$(git -C data/raw/REPO symbolic-ref --short refs/remotes/origin/HEAD | cut -d/ -f2)
uv run python -m sarms.mining.first_parent data/raw/REPO "$BRANCH" data/REPO/commits.parquet

# Step 1c — freeze the record, replay it, write the baseline
uv run python -m sarms.rules.record_history data/raw/REPO "$BRANCH" data/REPO/record [--since YYYY-MM-DD]
uv run python -m sarms.replay.proxy_lint data/raw/REPO "$BRANCH" data/REPO                    # sampled
uv run python -m sarms.replay.proxy_lint data/raw/REPO "$BRANCH" data/REPO --every 1 --match=  # every commit
uv run python -m sarms.replay.baseline data/REPO OWNER/REPO                                     # -> reports/awareness-gap-baseline.md

# Step 2 — validate the specification before tagging
uv run python tools/validate_spec.py      # prints the protocol hash for the P1 pack
```

Measured on kedro (1,957 first-parent commits): first_parent 1 s · record_history 60 s ·
proxy_lint 2 min sampled, 5 min every commit · baseline 2 s. The screening script needs a
clone per repository (partial, blob-less); `screen.py` makes it under `data/raw/`.

## Weeks 2–3 — the loop on one repository (build-plan.md steps 1–4)

```bash
# 1. rule compiler: the team's contracts -> the rule bundle (schema-checked)
uv run sarms compile data/raw/kedro --out data/kedro/rms/rules --repo kedro

# 2. the Differ on one commit (plain-language summary + .rms/differ/<sha>/differ.{json,sarif})
uv run sarms check data/raw/kedro --rules data/kedro/rms/rules --out data/kedro/rms
uv run sarms check data/raw/kedro --sha 9039f82a --rules data/kedro/rms/rules --out data/kedro/rms

# 2b. the Differ over the whole history (kedro: 3 min; equal trees are not re-checked)
uv run sarms replay data/raw/kedro main data/kedro/rms --rules data/kedro/rms/rules

# 3. the ledger (DuckDB, docs/spec/ledger.sql) from the Differ output, or from the Step 1c replay
uv run sarms ledger data/kedro/rms --repo kedro-org/kedro --record data/kedro/record/contracts.csv
uv run sarms ledger data/kedro/rms --repo kedro-org/kedro --from-replay data/kedro

# the "done when" of steps 1–3 in one command: reproduce the replay's 16 edges / 28 episodes / 92 commits / 156 days
uv run python tools/check_against_replay.py kedro-org/kedro          # ALL PASS

# 4. one drafted fix, tried in a copy (<repo>.draft), never committed; outputs in data/kedro/rms/drafts/
ollama serve & ollama pull qwen2.5-coder:7b                           # once; or set SARMS_LLM_BASE_URL/MODEL/API_KEY
uv run sarms draft data/raw/kedro --rules data/kedro/rms/rules --rms data/kedro/rms --pick direct
uv run sarms draft data/raw/kedro --rules data/kedro/rms/rules --rms data/kedro/rms \
    --edge "kedro.runner -> kedro.framework.project" --tests "python -m pytest tests/runner -q -x --no-cov -p no:cacheprovider"
uv run sarms draft data/raw/kedro --rules data/kedro/rms/rules --rms data/kedro/rms --template   # rule-based draft, no model
```

The draft step's `--tests` command runs inside the copy, so the copy needs the subject's test
dependencies installed in the current environment (for kedro: `uv pip install -e data/raw/kedro.draft[test]`
once; it is heavy). Without `--tests` the draft is judged on G1 only (violation gone, none new).

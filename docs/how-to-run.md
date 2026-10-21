# How to run sarms, step by step (Windows)

Last verified 21 October 2026 on Windows 11 with uv 0.13.4; every command below was run on that
machine. Run everything from the repository root, `C:\senso-lens-sarms\sarms`, in PowerShell
unless a step says otherwise.

## 1. Before you start

Three things must be on the machine, and each has a one-line check.

| Need | What it is for | Check | Expected |
| --- | --- | --- | --- |
| Git | clones repositories and mines their history | `git --version` | git version 2.x |
| uv 0.13 or newer | installs Python 3.13 and every dependency from `uv.lock` | `uv --version` | uv 0.13.4 or newer |
| The team salt in `.salt` | pseudonymises author e-mails during mining; git-ignored, never commit it | `Test-Path .salt` | True |

Python does not need to be installed separately. uv downloads Python 3.13, the version pinned in
`.python-version`, the first time you sync. If `uv` is missing, install it with
`winget install --id=astral-sh.uv -e`; if the terminal still cannot find it afterwards, see
section 7. If `.salt` is missing, get the salt from a teammate and paste it into a new `.salt`
file; `.salt.example` shows the format.

## 2. One-time setup

Setup is one `uv sync` and takes a few minutes; you do it once per machine and again only when
`uv.lock` changes.

1. Open PowerShell and go to the repository root:

   ```powershell
   cd C:\senso-lens-sarms\sarms
   ```

2. Confirm the terminal sees uv with `uv --version`. If it prints "not recognized", go to
   section 7 before continuing.

3. If a `.venv` folder already exists that uv did not create, delete it. Ours had a Linux `bin`
   folder next to a Windows `Scripts` folder and could not run anything. Skip this step on a
   fresh clone.

   ```powershell
   Remove-Item -Recurse -Force .venv
   ```

4. Install Python 3.13 and every dependency:

   ```powershell
   uv sync --all-groups
   ```

   uv reads `pyproject.toml` and `uv.lock`, downloads Python 3.13 into its own cache, creates
   `.venv`, and installs the runtime dependencies plus the dev group (pytest and ruff). It is
   done when `.venv\pyvenv.cfg` contains `uv = 0.13.4` and `version_info = 3.13`.

5. Do not activate the venv and do not use pip inside it. Every command in this guide starts
   with `uv run`, which uses the project venv automatically and re-syncs it if the lock file
   changed since the last run.

After a `git pull` that touches `pyproject.toml` or `uv.lock`, run `uv sync --all-groups` again.

## 3. Check the installation

Four commands are exactly what CI runs on every push (`.github/workflows/ci.yml`), and all four
pass as of 21 October 2026. Run them from the repository root, in this order.

| Step | Command | Expected output | Time |
| --- | --- | --- | --- |
| 1 | `uv run ruff check .` | All checks passed! | seconds |
| 2 | `uv run pytest -q` | 4 passed | about 1 minute; one test runs the spec validator, another builds a tiny git repository |
| 3 | `uv run lint-imports` | Contracts: 3 kept, 0 broken | seconds |
| 4 | `uv run python tools/validate_spec.py` | ALL PASS, plus a sha256 line that is the protocol hash for the P1 pack | seconds |

If all four pass, the installation matches CI and you can run anything below. The three
import-linter contracts in step 3 are our own layering rules from `.importlinter`: the Differ
and the gate may never import the model step.

The `sarms` console command exists (`uv run sarms`) but only prints "Hello from sarms!" today.
The real work lives in the tools and the modules in the next sections.

## 4. See it run in seconds

The last pipeline stage runs on the kedro data already in the repository, so you can watch real
output in about one second without cloning anything.

```powershell
uv run python -m sarms.replay.baseline data/kedro kedro-org/kedro
```

It reads `data/kedro/checks_sample.parquet`, `violations_sample.parquet` and `record/`, prints
the awareness-gap summary, and rewrites `reports/awareness-gap-baseline/kedro.md` plus the
combined `reports/awareness-gap-baseline.md`. The terminal shows this:

```
Record: 4 contracts, first written 2019-08-13.
Sampled 1957 first-parent commits, 2019-05-16 to 2026-10-19, median stride 1 (resolution ±1 commits).

| Measure | Value |
| Distinct violating edges seen | 16 |
| Episodes (after the contract / pre-contract) | 28 / 0 |
| Share later repaired (after the contract) | 19 of 28 (68%) |
| Gap, commits: median (p90) | 92 (p90 285) |
| Gap, days: median (p90) | 156 (p90 430) |
| Rises / drops in the violation count (criterion 4 = drops) | 7 / 4 |
-> reports\awareness-gap-baseline.md
```

Afterwards `git status` lists two modified report files. The numbers are identical to what is
committed; only the row order changed, because the repository regenerated last moves to the
bottom of the summary table. Discard that with:

```powershell
git checkout -- reports/awareness-gap-baseline.md reports/awareness-gap-baseline/
```

## 5. Run the full pipeline on a repository

One command runs Steps 1b and 1c for a repository, from clone to baseline report.

```powershell
uv run python tools/run_step1.py kedro-org/kedro --every 1
```

The argument is the GitHub `OWNER/REPO`. The runner clones into `data/raw/kedro` if the clone is
missing (a partial, blob-less clone, so the first run needs network), then runs five stages in
order. A stage is skipped when its output already exists, so re-running after an interruption
is cheap. Timings are from the kedro run of 1,957 commits.

1. **first_parent** mines the first-parent commit chain into `data/kedro/commits.parquet`.
   Author e-mails are replaced by a salted hash, so this stage needs `.salt`. 3 seconds.
2. **record_history** freezes the import-linter contracts at each commit into
   `data/kedro/record/`. 60 seconds.
3. **graph** extracts the import graph at HEAD into `data/kedro/graph/<sha12>/`: every import
   statement, every module with its fan-in and cycle id, the package roll-up, and
   `summary.json` with the cycle and hub numbers. 23 seconds. It needs an import-linter
   record at HEAD or `--root PACKAGE`; with neither it is skipped with a note.
4. **proxy_lint** checks out sampled commits in a reused worktree and runs import-linter
   against the HEAD contracts, writing `checks_sample.parquet` and `violations_sample.parquet`.
   22 minutes with `--every 1`; a couple of minutes at the default stride of 25.
5. **baseline** builds the report from section 4. 1 second.

Options you will actually use:

| Option | When | Example |
| --- | --- | --- |
| `--every N` | sample every Nth first-parent commit; default 25, and 1 means every commit | `--every 1` |
| `--since YYYY-MM-DD` | very large histories; start a month before the first contract, which record_history prints | `--since 2023-06-01` |
| `--force` | redo stages whose output already exists | `--force` |
| `--skip-proxy` | ADR-track repositories: mining and record only, no replay | `--skip-proxy` |
| `--config PATH --src DIR` | monorepos whose import-linter config is not at the root | `--config apps/backend/pyproject.toml --src apps/backend` |
| `--exploratory` | detection-only case; the report goes under `reports/exploratory/` and stays out of the summary | `--exploratory` |
| `--match REGEX` | also sample commits whose message matches; `''` adds none | `--match ''` |
| `--root PACKAGE` | repositories with no import-linter record at HEAD, so the graph stage knows which package to parse | `--root airflow` |

The other Step 1 tools, for screening the longlist, the ADR track and drawing the labelling
samples, are listed with their commands in `docs/runbook-commands.md`. Those lines are written
for bash; section 7 has the PowerShell forms.

## 6. Where the outputs land

A run writes its data under `data/REPO/` and its human-readable result under `reports/`; only
the reports are in git, the data travels in the team's data pack zip (see `data/README.md`).

| Path | Written by | In git | Holds |
| --- | --- | --- | --- |
| `data/raw/REPO/` | run_step1 or screen.py | no | the partial clone, plus `REPO.wt` (one reused worktree) and `REPO.ilcache` (grimp's cache) |
| `data/REPO/commits.parquet` | first_parent | no | the first-parent chain: idx, sha, timestamps, salted author hash, file counts, message, PR number |
| `data/REPO/record/` | record_history | no | `importlinter.HEAD.toml`, `contracts.csv`, `events.parquet` (contracts added, removed, changed) |
| `data/REPO/graph/<sha12>/` | graph | no | the whole import graph of that commit: `edges.csv`, `modules.csv` with fan-in and cycle id, `packages.csv`, `packages.dot`, `summary.json` |
| `data/REPO/checks_sample.parquet`, `violations_sample.parquet`, `sample.csv` | proxy_lint | no | one row per commit and contract; one row per violating edge |
| `data/REPO/episodes.csv` | baseline | no | violation episodes: introduced at, repaired at, gap |
| `data/REPO/<stage>.log`, `timings.csv` | run_step1 | no | each stage's full output; seconds and exit code per stage |
| `reports/awareness-gap-baseline/REPO.md`, `summary.csv` | baseline | yes | the per-repository report and its summary row |
| `reports/awareness-gap-baseline.md` | baseline | yes | the summary table plus every repository's section |

Reading a finished run:

- `data/REPO/timings.csv` has one line per stage: name, seconds, exit code. Exit 0 means the
  stage succeeded.
- The terminal prints `[exit 1] see data/REPO/<stage>.log` when a stage fails; the log has the
  full traceback.
- Open the report with `code reports/awareness-gap-baseline/kedro.md` or in any Markdown viewer.
- Peek inside a Parquet file without extra tools:

  ```powershell
  uv run python -c "import pandas as pd; print(pd.read_parquet('data/kedro/commits.parquet').head())"
  ```

## 7. Troubleshooting

These are the problems we hit while setting up on 21 October 2026, each with its fix.

**uv is "not recognized" right after installing it.** winget adds uv's folder to the saved user
PATH, but a running program keeps the PATH it started with. A new terminal inside VS Code
inherits VS Code's old environment, so opening another terminal does not help. Either quit VS
Code completely (File, then Exit; a window reload is not enough) and reopen it, or refresh the
PATH in the terminal you are using and run uv in that same terminal:

```powershell
$env:Path = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User')
uv --version
```

The full path works in any terminal: `& "$env:LOCALAPPDATA\Microsoft\WinGet\Links\uv.exe" --version`.

**"No salt: put the team's secret in .salt (git-ignored) or set RMS_SALT."** The mining stage
refuses to run without the salt. Put the team salt on one line in `.salt` at the repository
root, or set it for the session with `$env:RMS_SALT = "<salt>"`.

**uv sync refuses the existing `.venv`.** The folder was made by something other than uv.
Delete it (section 2, step 3) and sync again.

**uv warns "Failed to inspect Python interpreter ... chocolatey\bin\python3.14.exe".** A
leftover Chocolatey shim points at a Python that no longer exists. The warning is harmless
because uv uses its own Python 3.13; remove the stale shim with Chocolatey if you want it gone.

**pytest seems to hang.** It takes about a minute: one test runs the spec validator in a
subprocess and another builds a small git repository. Wait for `4 passed`.

**A runbook line fails in PowerShell.** `docs/runbook-commands.md` is written for bash. The
branch lookup and the ADR-track command become:

```powershell
$BRANCH = (git -C data/raw/kedro symbolic-ref --short refs/remotes/origin/HEAD).Split('/')[1]
uv run python -m sarms.mining.first_parent data/raw/kedro $BRANCH data/kedro/commits.parquet
uv run python -m sarms.mining.adr_history data/raw/kedro $BRANCH data/kedro kedro-org/kedro
```

`tools/check_tests.sh` is a bash script; run it from Git Bash, where `uv` is also available
after a fresh terminal.

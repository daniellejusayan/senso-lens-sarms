# Demo guide — Steps 1 and 2 (progress meeting)

Everything you type, what you should see, what it means, and what to say. About 6 minutes of
terminal, then the slides. All commands are for **PowerShell**, run from the repository folder.

---

## Before the meeting (do this once, the day before)

```powershell
cd C:\senso-lens-sarms\sarms
uv sync --all-groups
git pull
```

- `uv sync` installs every library at the exact versions the project uses (from `uv.lock`).
- `git pull` makes sure you have the latest commits from the team.

Then run steps 1–5 below once on your own, so nothing surprises you. If `uv` is "not
recognised", close PowerShell and open it again.

Keep these open in VS Code before you start:
`reports\figures\kedro-packages-head.png`, `reports\steps-1-2-report.md`,
`docs\repo-selection.md`, `docs\spec\gate.md`.

---

## Step 1 — "Our software is real and its checks pass" (about 20 seconds)

```powershell
uv run pytest -q
uv run lint-imports
uv run python tools/validate_spec.py
```

**You should see**

```
5 passed
Contracts: 3 kept, 0 broken.
evaluation-protocol.md sha256 (for the P1 pack): b0e2de5c...0065
ALL PASS
```

**What it means**

| Command | Meaning |
| --- | --- |
| `pytest` | Our own tests (small programs that check our code works) all pass. |
| `lint-imports` | Our own code follows our own architecture rules. One rule says the checking part may never call the AI part. We practise what we build. |
| `validate_spec.py` | The rulebook (`docs/spec/`) is complete and consistent. The long code is its **fingerprint**: if anyone changes the evaluation rules later, the code changes and it shows. |

**Say:** *"These three checks also run automatically on GitHub every time anyone pushes."*

---

## Step 2 — "How we chose the projects" (about 2 seconds)

```powershell
uv run python tools/reduce_longlist.py data/Step1_usable_repos_230.csv --out-dir data/demo
```

**You should see**

```
230 rows -> 38 kept; R1: 82, R2: 60, R3: 6, R4: 44, kept: 38
```

**What it means.** It takes our list of 230 candidate projects and applies five cut rules, which
we wrote **before** looking at any project:

| Rule | Removes a project when… | Removed |
| --- | --- | --- |
| R3 | it is a fork or copy of another project on the list | 6 |
| R1 | it has fewer than 2 import-linter rules and fewer than 10 ADRs (too little written architecture) | 82 |
| R2 | it has under 2 years or under 1,000 commits of history | 60 |
| R4 | it has under 50 stars (likely a personal project, no team) | 44 |
| R5 | its only rules are in a tool we can't read (tach) | 0 |

38 survive. Then we measured those 38 and picked 4 main ones: **kedro, checkov,
wemake-python-styleguide, gt4py**.

**Show:** open `data\demo\longlist_decisions.csv`. Every project has `kept`/`dropped`, the rule and
the reason. **Say:** *"Nothing was hand-picked; every rejection has a reason on file."*

**Where the rules live:** `docs\repo-selection.md` (top table = 8 criteria; section "From 230 to
the screening list" = R1–R5; section "Amendments" = dated changes).

---

## Step 3 — "We read a project's whole history" (about 10 seconds)

```powershell
uv run python -m sarms.mining.first_parent data/raw/kedro main data/demo/commits.parquet
```

**You should see**

```
1957 first-parent commits -> data/demo/commits.parquet  (rev-list says 1957: OK); 43 merges, ... 2019-05-16 -> 2026-10-19
```

**What it means.** Using **git**, it walks kedro's main branch from its first commit (May 2019) to
today and saves one row per commit: date, files changed, pull-request number, and the author as a
scrambled code (we never store names or e-mails). "First parent" means we follow the main branch
itself, so a merge counts as "everything that merge brought in". That matters because some
fixes arrived by merge.

**Say:** *"1,957 commits, seven years of kedro, in ten seconds."*

---

## Step 4 — "We check old versions against the team's own rules" (about 20–30 seconds)

```powershell
uv run python -m sarms.replay.proxy_lint data/raw/kedro main data/demo --every 200 --match ""
```

**You should see** something like

```
11 sampled commits (every 200), statuses {'broken': ..., 'kept': ...}, ... violation rows -> data/demo
```

**What it means.** kedro's team wrote 4 architecture rules (for example "runner must not import
config"). For each sampled old version of kedro, this checks every rule:
`kept` = rule followed, `broken` = rule broken. We remove the team's "ignore this" list first,
because those ignored imports are exactly the debt we want to see.

**Say:** *"This is a slice of 11 versions. The real run checked all 1,957 and took 22 minutes on
this laptop. The results are saved, which is what the next step reads."*

If this step is slow or shows an error, **skip it** and go to step 5. Step 5 never depends on it.

---

## Step 5 — "What we found" (1 second, the main one)

```powershell
uv run python tools/demo.py kedro
```

It prints five sections. Point at each:

| Section | What to say |
| --- | --- |
| **1. History** | "1,957 commits since 2019, 257 authors, all as codes." |
| **2. The team's own rules** | "kedro's 4 rules, all written in August 2019. Over time they added 9 'ignore this' exceptions and removed 4." |
| **3. Broken rules still in the code today** | "Nine broken rules are still in kedro today. 'Direct' means one import line breaks it; 'indirect' means it breaks it through a chain of imports." |
| **4. The awareness gap** | "28 times a rule was broken. 19 fixed by a person, 9 never. Median wait **92 commits / 156 days**. The longest, runner → config, waited **623 days**." |
| **5. The import graph** | "Today: 75 modules, one 29-module cycle no rule forbids, 7 packages no rule mentions. In 2020: no cycle at all. The architecture moved under the rules." |

Then the contrast:

```powershell
uv run python tools/demo.py wemake-python-styleguide
```

**Say:** *"This team enforces strictly, so almost nothing gets through. That's the finding: CI
blocks new violations, so what piles up is the 'ignore this' list, and that's what our system
will clean up."*

---

## Step 6 — Show the files (no typing)

| Open | Say |
| --- | --- |
| `reports\figures\kedro-packages-head.png` | "What the system reads. Red = an import the rules forbid; dashed = packages no rule mentions." |
| `reports\steps-1-2-report.md` | "The full write-up, with every term explained." |
| `docs\spec\gate.md` | "The nine checks every fix must pass before it is applied." |
| `docs\repo-selection.md` | "Our selection rules, dated before we looked at any project." |

---

## If something goes wrong

| Problem | Fix |
| --- | --- |
| `uv` is not recognised | Close and reopen PowerShell. |
| Step 4 is slow or errors | Skip it: "the full run is already saved". Go to step 5. |
| `demo.py` says `no data/...` | You typed the name wrong. Use `kedro`, `checkov`, `sqlfluff`, `faststream`, `ramses_rf` or `wemake-python-styleguide`. |
| Anything else | Go to the slides. Everything in steps 2–5 is also on slides 5–9. |

Steps 2–4 only write into `data\demo`, which git ignores, so the demo can never change the real
results. Delete `data\demo` afterwards if you like.

---

## Cheat sheet — if the teacher asks

| Word | Plain meaning |
| --- | --- |
| **Repository** | A project's code and its full history, kept by git. |
| **Commit** | One saved change. kedro has 1,957 on its main branch. |
| **Import-linter rule (contract)** | A rule a team writes in a config file, e.g. "runner must not import config". |
| **"Ignore this" list** (`ignore_imports`) | Violations a team agreed to tolerate. The checker stays green, but the debt remains. |
| **Violation** | One import that breaks one rule. |
| **Episode** | One violation's life: when it appeared, when (if ever) it was fixed. |
| **Awareness gap** | How long an episode lasted: commits and days until a person fixed it. |
| **Drops** | Commits where the number of violations went down; our stand-in for "a person repaired it". |
| **Import graph** | A map of which module imports which. What the system compares against the rules. |
| **Erosion / drift** | Erosion = a written rule is broken (fixed by the system). Drift = structure slowly moving without breaking a rule (recorded, not forced back). |
| **Specification / rulebook** | Our own documents in `docs/spec/`: what each term means, the nine gate checks, how we score the system. |
| **Frozen** | Locked: each rulebook file has a fingerprint, and changes are only allowed as dated notes. So targets can't move after we see results. |
| **Post-hoc audit** | Architects review the system's fixes *after* they're applied, instead of approving each one first. |
| **Fault injection** | We plant rule-breaking changes in a copy of a project and count how many the system fixes with no human. |
| **Detection-only (PostHog)** | A project we use only to test "does it spot the problem", not to test fixes. It's too big and too much TypeScript for the rest. |
| **Mining** | Reading a project's history with git and saving it as a table. |
| **Tools used** | git (history), import-linter (reads the rules), grimp (reads the imports), pandas/DuckDB (tables), uv (installs everything). |

**What we have NOT built yet** (say it before they ask): the part that *fixes* things, meaning the
comparison step, the AI draft, the nine checks in code, and the commit step. That's the next two
weeks, demo on 5 November: kedro gets a broken rule fixed automatically, with no human.

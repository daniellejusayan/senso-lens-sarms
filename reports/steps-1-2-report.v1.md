# Steps 1 and 2 — what was done, what came out, what changed (21 Oct 2026)

Deliverable for the week of 19–23 Oct: **Step 1** (data and evidence: subject repositories
selected by frozen criteria, their histories mined, the awareness-gap baseline measured) and
**Step 2** (the specification the build follows: vocabulary, rules, ledger, decision record,
gate, evaluation protocol, fault injection). Everything below was produced by the commands in
`docs/runbook-commands.md` and is reproducible from the clones; the data pack
`sarms-steps-1-2-data.zip` carries the outputs that are not in git.

## 1. Step 1a — selection

**Frozen first.** Eight criteria (intent recorded, ≥ 2 years and ≥ 1,500 first-parent commits,
tests under 10 minutes, repairs exist, ≥ 90% Python, 20k–400k lines, OSI licence, alive) were
written down on 19 Oct before any repository was chosen (`docs/repo-selection.md`), and the
team's own C1–C5 numbering was mapped onto them.

**230 → 38, every drop with a reason.** The team's Step 1 sheet (230 rows) was reduced by five
rules applied in order (`tools/reduce_longlist.py`): forks and the checker's own repositories
(6), intent too thin — fewer than 2 contracts and fewer than 10 ADRs (82), history under 2 years
or 1,000 commits (60), under 50 stars — no team behind it (44), tach-only rules (0). The result
and each row's rule are in `data/longlist_decisions.csv`; the 203-row near-miss sheet is the
reserve pool and was not screened.

**38 cloned and measured.** `tools/screen.py` cloned each survivor (partial clone, no blobs)
and measured criteria 1, 2, 5, 6, 7, 8 from the repository itself: contracts at HEAD (now also
in monorepo sub-packages), ADR files, first-parent count, first and last commit, Python line
count and share, licence text. Results: `data/candidates.csv`. Six contract-track repositories
and five ADR-track repositories pass everything that can be checked without running tests.

**Chosen** (full rationale in `docs/repo-selection.md` § Selected): primaries **kedro**,
**checkov**, **wemake-python-styleguide** (contracts) and **gt4py** (ADRs); reserves sqlfluff,
faststream, ramses_rf, qiskit-serverless, airflow, xorq, inspect_evals; **PostHog** as a
detection-only exploratory case kept apart; openedx-platform as an example source only.

## 2. Step 1b — mining

`sarms.mining.first_parent` walked the default branch's first-parent chain of every
shortlisted repository, reading each merge as what it added to the branch (PyDriller reports no
files for merges, which is why the walk is our own). Author e-mails were replaced by a salted
hash before anything was written (`docs/ethics.md`). Sizes: kedro 1,957 commits · wemake 3,148 ·
sqlfluff 4,593 · checkov 13,941 · faststream 1,624 · ramses_rf 4,699 · qiskit-serverless 1,866 ·
gt4py 1,811 · airflow 40,198 · PostHog 66,957. Outputs `data/<repo>/commits.parquet`.

## 3. Step 1c — the awareness-gap baseline

For each contract-track repository the import-linter record at HEAD was frozen
(`sarms.rules.record_history`: contract introduction dates, every exception added or removed),
then applied to **every** first-parent commit with the exceptions removed
(`sarms.replay.proxy_lint --every 1`, the strict record), and the resulting series was turned
into violation episodes — introduced at, repaired at, or still open (`sarms.replay.baseline`).
Large histories were windowed from a month before the first contract.

| Repository | Commits replayed | Violating edges | Episodes after the contract | Repaired | Median gap (commits / days) | Drops (criterion 4) | Exception removals | Standing at HEAD |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| kedro-org/kedro | 1957 | 16 | 28 | 19 | 92 / 156 | 4 | 3 | 9 |
| bridgecrewio/checkov | 2695 | 25 | 1 | 0 | – | 6 | 5 | 5 |
| wemake-services/wemake-python-styleguide | 3148 | 5 | 1 | 1 | 32 / 14 | 3 | 3 | 2 |
| sqlfluff/sqlfluff | 1986 | 8 | 3 | 0 | – | 1 | 0 | 5 |
| ag2ai/faststream | 1624 | 80 | 0 | 0 | – | 3 | 0 | 20 |
| ramses-rf/ramses_rf, Qiskit/qiskit-serverless | replay in progress at packaging time; rows appended by the follow-up patch | | | | | | | |

What the series say (`reports/awareness-gap-baseline.md`):

1. **Enforced contracts keep violations off the default branch; what stands is acknowledged
   debt.** Every repository has violating edges at HEAD under the strict record — the imports its
   team listed in `ignore_imports`. In kedro the oldest has stood since 16 Jul 2020.
2. **Repair is rare and slow.** kedro, the richest history: 28 episodes, 19 repaired, median 92
   commits / 156 days, p90 430 days, 9 never. The three longest gaps are 623, 469 and 420 days.
3. **The contract's arrival is itself a repair event.** checkov removed 24 violating edges nine
   days after its first contract (2023-08-15); sqlfluff on 2023-08-29 and 2023-10-25. After
   that, almost nothing: checkov 1 episode, sqlfluff 3, wemake 1.
4. **A fresh record legalises the existing structure.** faststream's contracts (2026-09-20)
   arrived with 17 exceptions; the strict record shows 80 violating edges before that date and
   none after — documentation lag by construction.
5. **Criterion 4 (≥ 20 drops) is met by no one**, so it is reported, not selected on
   (amendment of 21 Oct), and PostHog — 481 exceptions added and 292 removed in 59 commits in six
   months — is kept as the detection-only case where repair is frequent
   (`reports/exploratory/posthog.md`).

ADR track (`reports/adr-track/`): gt4py 51 ADRs, 21 structural by keyword; airflow 49 / 35;
openedx-platform 143 / 42; xorq 21 / 19; inspect_evals 10 / 7; climate_indices 24 / 18. The
structural flag is a keyword screen (≥ 2 of import, dependency, layer, module, boundary, must
not, only through …); Week 2's rule compiler decides which of those compile.

## 4. Step 2 — the specification (autonomous apply)

Point 7 changed the design on 21 Oct: the verdict `accept` means the kernel applies the
correction as its own commit; no human is asked, and humans audit afterwards. The spec says so
in every file it touches:

| File | What it fixes | Real examples in it |
| --- | --- | --- |
| `docs/spec/vocabulary.md` | 4 Differ labels, 3 drift indicators, 5 root causes, verdicts and outcomes (`applied, left_standing, amended_by_human, reverted, escalated`) | kedro's `runner → config` (ADDITIONAL, 623 days), `runner → framework.session` (INVERTED), openedx ADR 0002 (MISSING), kedro HEAD: 7 unassigned packages, one 30-module cycle, hubs by fan-in |
| `docs/spec/rules.schema.yaml` | one compiled rule, with provenance | a kedro contract rule, an ADR rule from openedx 0002 |
| `docs/spec/ledger.sql`, `ledger.md` | the deviation ledger and the awareness-gap view | — |
| `docs/spec/decision-record.schema.json` | the signed record the kernel executes; `applied_commit` | — |
| `docs/spec/gate.md` | G0–G8 in execution order, the apply policy, the hard lines G0 and G7 | kedro Nov 2024 relocation (reduce, never relocate) |
| `docs/spec/evaluation-protocol.md` | replay rule, metrics and targets, fault injection, post-hoc audit; amendment of 21 Oct | — |
| `docs/spec/fault-injection.md` | 10 injections per subject, what must happen with no human action, measures | — |
| `docs/spec/failure-modes.md` | 17 failure modes with detection and mitigation | 9 found in the 19–21 Oct runs |
| `docs/spec/pilot-sheet.csv` | the 50 root-cause cases with empty rater columns | drawn with seed 2569 |

`tools/validate_spec.py` checks the set and prints the protocol hash recorded in
`reports/p1-pack.md`.

## 5. What changed in the tooling this week (all found by running it)

- Contract introduction is read from the import-linter section, not from the config file's
  first commit (kedro: file 2019-05-16, first contract 2019-08-13).
- The replay uses the strict record; with the record as written, CI-enforced repositories
  show no violations after the contract date.
- Monorepo configs (`--config`), optional layers on old commits, `error` status instead of
  false violations, one reused worktree and grimp's cache.
- A subject line with a control character (PostHog, U+001D) split a git log record; the reader
  now uses NUL-separated records.
- The GitHub API is not reachable from the build machine; stars fall back to the team's sheet,
  licence to the LICENSE text, Python share to file sizes (marked "~").

## 6. Still open before Friday

- Criterion 3: run `tools/check_tests.sh` for the four primaries on a laptop (needs Git Bash or
  WSL on Windows); a failure swaps the primary with reserve 1.
- Re-check sqlfluff's Python share with `gh api repos/sqlfluff/sqlfluff/languages`.
- Advisor's confirmation of the selected set and of the detection-only PostHog case.
- Precision sample: the five finished replays hold 148 episodes (33 after a contract; faststream's 80 pre-contract edges dominate), so `data/samples/precision_100.csv` has its 100 cases and `rootcause_50.csv` has 29 post-contract cases, not 50; the PostHog and reserve replays top the pool up when they finish (same seed, re-drawn and re-committed before labelling starts).

# Repository selection (Step 1a, draft for A)

Criteria fixed on 19 Oct 2026, before any repository was chosen (copied from the Week 1–2
runbook). A repository is selected only if it meets 1–3 and 5–8 today and 4 after the proxy
run. Changes are appended under *Amendments*, never edited in place.

| # | Criterion | Threshold | Evidence column in data/candidates.csv |
| --- | --- | --- | --- |
| 1 | Intent is recorded | ≥ 2 import-linter contracts, or ≥ 10 MADR-style ADRs | contracts, adrs |
| 2 | History | ≥ 2 years and ≥ 1,500 first-parent commits | first_commit, n_first_parent |
| 3 | Tests | a documented pytest suite that runs on a laptop in under 10 minutes | tests_min (data/tests.csv) |
| 4 | Repairs exist | ≥ 20 sampled commits where the violation count drops | drops_c4 (reports/awareness-gap-baseline/summary.csv) |
| 5 | Language | ≥ 90% Python by bytes | python_share_pct (gh api …/languages; "~" = estimate from file sizes) |
| 6 | Size | 20k–400k lines of Python | loc_py |
| 7 | Licence | OSI-approved: MIT, Apache-2.0, BSD | licence |
| 8 | Alive | a commit on the default branch in the last 6 months; not archived | last_commit, archived |

## The team's own numbering

The Step 1 sheets the team built (`data/Step1_usable_repos_230.csv`, `data/Step1_near_miss_203.csv`)
number the criteria C1–C5. They are the same criteria; the mapping is fixed here so both
numberings can be used: C1 = Python repository (criterion 5 above, measured there as a share),
C2 = intent recorded (1), C3 = years of history (2; the sheet has no commit count, so 2's
≥ 1,500 first-parent commits is measured by `tools/screen.py`), C4 = tests (3), C5 =
violation-reducing commits (4). Licence (7), size (6) and liveness (8) are not on the sheet and
are measured at screening.

## From 230 to the screening list (R1–R5, 21 Oct 2026)

`tools/reduce_longlist.py` reads the 230-row sheet and drops rows by five rules, in this
order, writing one reason per row to `data/longlist_decisions.csv`. The sheet's own columns
are used; every kept row is re-measured afterwards. No repository is chosen here.

| Rule | Drops a row when | Dropped | Left |
| --- | --- | --- | --- |
| R3 fork / duplicate / the checker itself | the row is a fork or copy of a repository already on the list (two airflow forks, two dify copies, one iris fork), or is import-linter / grimp | 6 | 224 |
| R1 intent too thin | fewer than 2 import-linter contracts and fewer than 10 ADRs (criterion 1 as frozen) | 82 | 142 |
| R2 history too short | under 2 years or under 1,000 commits on the sheet (criterion 2's floor; the exact first-parent count is measured next) | 60 | 82 |
| R4 no team behind it | under 50 stars — a proxy for "a team maintains this", which the practitioner study [1] the project rests on is about; personal and student repositories are not the population | 44 | 38 |
| R5 tach-only rules | the only rules are `tach.toml` and there are < 10 ADRs; the replay tooling reads import-linter | 0 | 38 |

(The rules are applied in the order R3, R1, R2, R4, R5 so that a fork is recorded as a fork
even when it would also fail R1.) The 38 survivors are in `data/longlist.txt` and were cloned
and screened by `tools/screen.py` on 21 Oct (`data/candidates.csv`); the three largest
(openedx-platform, airflow, truenas/middleware) were screened without a checkout, so their
line counts come from the GitHub language bytes only.

The near-miss sheet (203 rows) is the reserve pool: it is not screened unless the shortlist
falls below three primaries.

## Seed screening, 19 Oct 2026 (data/candidates_seed.csv)

| Repository | Contracts (exceptions) / ADRs | First-parent commits | Python LOC, share | Licence | Contract since | Exception removals | Criteria |
| --- | --- | --- | --- | --- | --- | --- | --- |
| kedro-org/kedro | 4 (6) / 0 | 1,957 | 57k, ~94% | Apache-2.0 | 2019-08 | 3 commits | meets 1,2,5,6,7,8; **4 fails: 4 drops over every commit**; 3 pending |
| napari/napari | 4 (3) / 0 | 4,724 | 208k, ~100% | BSD-3 | 2021-05 | 5 | meets 1,2,5,6,7,8; 3, 4 pending |
| bridgecrewio/checkov | 6 (13) / 0 | 13,938 | 247k, ~95% | Apache-2.0 | 2023-08 | 5 | meets 1,2,5,6,7,8; 3, 4 pending |
| sqlfluff/sqlfluff | 4 (4) / 0 | 4,588 | 194k, ~86% (check with gh) | MIT | 2023-08 | 0 | 5 borderline; 3, 4 pending |
| PostHog/posthog | 6 (189) / 2 | 66,382 | not counted (very large) | MIT | 2026-04 | **58** (290 exceptions removed) | 5, 6 likely fail; strongest repair evidence |
| openedx/edx-platform | 4 (42) / 143 | 17,663 | 755k, ~40% | AGPL-3.0 | 2022-12 | 9 | fails 5, 6, 7; the only seed with both contracts and ADRs |
| feast-dev/feast | 0 / 13 | 4,382 | 276k, ~40% | Apache-2.0 | – | – | fails 5 (ADR track only) |
| microsoft/semantic-kernel | 0 / 78 | 4,744 | 198k, ~36% | MIT | – | – | fails 5 (ADR track only) |
| open-metadata/OpenMetadata | 0 / 107 | 19,464 | not counted | Apache-2.0 | – | – | Java-first; 5 likely fails |
| great-expectations/great_expectations | 0 / 6 | 7,737 | 360k, ~94% | Apache-2.0 | – | – | fails 1 (6 ADRs < 10) |
| mozilla/kitsune | 0 / 6 | 8,127 | 173k, ~79% | BSD-3 | – | – | fails 1, 5 |
| google/langextract | 3 (0) / 0 | 185 | 44k, ~97% | Apache-2.0 | 2025-08 | – | fails 2 |
| poliastro/poliastro | 1 (0) / 0 | 1,019 | 32k | MIT | 2021-11 | – | fails 1, 2, 8 (archived 2023) |
| seddonym/import-linter | 2 (0) / 0 | 367 | 14k | BSD-2 | 2019-04 | – | fails 2; is the tool itself |
| seddonym/grimp | 1 (4) / 0 | 323 | 11k | BSD-2 | 2025-08 | – | fails 1, 2; cannot be replayed (name clash with the checker) |

Reading: three repositories pass every criterion that can be checked today (kedro, napari,
checkov), sqlfluff is borderline on 5, and criterion 4 is the binding one. kedro, checked on
every commit, has only 4 drops in seven years plus 3 commits that removed an exception: its
contracts run in CI (pre-commit), so violations rarely reach main. That is likely to hold for
every repository that enforces its contracts.

## Decision taken 21 Oct 2026: criterion 4

The every-commit replays (strict HEAD record, `reports/awareness-gap-baseline.md`) settle it
with exact numbers. Drops in the violation count after the contract: kedro 4, checkov 6,
wemake-python-styleguide 3, sqlfluff 1, faststream 3; exception-removal commits 3, 5, 3, 0, 0.
No repository on the longlist reaches 20, and the mechanism is clear from the series: once a
contract runs in CI, violations rarely reach the default branch at all — what stands for years
is the *acknowledged* debt in `ignore_imports` (kedro: 9 violating edges at HEAD behind 6
exceptions, the oldest since July 2020), and the repair events are the few commits that remove
an exception or the clean-up that accompanies the contract's arrival (checkov: 24 edges
removed on 2023-08-15, nine days after the first contract; sqlfluff: the same on 2023-08-29
and 2023-10-25).

Option taken: **C — report, don't select on it**, plus one **detection-only** subject that
fails criteria 5–7 (PostHog, option A's candidate) so that RQ1 and RQ3 have enough deviations to
judge. Criterion 4 stays in the table as a measured finding and is the first result of Part 2 of
the paper: human repairs of recorded architectural debt are rare and slow (kedro median 92
commits / 156 days; 9 of 28 episodes never repaired).

Criterion 3 (tests under 10 minutes) is still pending for every repository: `tools/check_tests.sh`
installs and runs each suite, which this week's machine time went to the replays instead. It
runs on a team laptop before Friday; a primary that fails it swaps with the first reserve.

## Selected (21 Oct 2026; confirm with the advisor on Friday 23 Oct)

| Repository | Role | Rationale |
| --- | --- | --- |
| kedro-org/kedro | primary (contracts) | 4 contracts since 2019-08, enforced in pre-commit; 1,957 first-parent commits, 57k lines, Apache-2.0, ~94% Python. The richest repair history on the list: 16 violating edges, 28 episodes, 19 repaired, median gap 92 commits / 156 days, 9 still open. Replay of every commit takes 5 minutes. |
| bridgecrewio/checkov | primary (contracts) | 6 contracts since 2023-08 (13 exceptions at HEAD), 13,941 commits, 247k lines, Apache-2.0, ~95% Python. Shows the contract-adoption pattern: 24 violating edges cleaned up nine days after the first contract, 5 exception-removal commits since; large enough that a per-push loop is tested at scale. Replayed from 2023-06 (2,695 commits, ~1 hour). |
| wemake-services/wemake-python-styleguide | primary (contracts) | 6 contracts since 2019-07 — the longest-enforced record on the list — 3,148 commits, 57k lines, MIT, ~100% Python; a linter whose own layering is a contract. Few violations (5 edges; 1 post-contract episode, repaired in 14 days) make it the clean control: the system should mostly stay silent here. |
| sqlfluff/sqlfluff | reserve 1 (contracts) | 4 contracts since 2023-08, 4,593 commits, 195k lines, MIT; criterion 5 borderline (~86% Python by file size — dialect SQL fixtures; re-check with `gh api .../languages` on a laptop). 8 edges, 3 post-contract episodes, none repaired yet (5 standing at HEAD). |
| ag2ai/faststream | reserve 2 (contracts) | 8 contracts, but written 2026-09-20 with 17 exceptions, so there is one month of post-contract history; 80 violating edges before that date under the strict record. Useful for the "record written to legalise the existing structure" case (documentation lag), not for the awareness gap yet. |
| ramses-rf/ramses_rf, Qiskit/qiskit-serverless | reserve 3, 4 (contracts) | pass criteria 1, 2, 5–8; contracts since 2026-06 and 2026-02; replays in progress at the time of writing (`data/<repo>/timings.csv`). |
| GridTools/gt4py | primary (ADR track) | 51 ADRs, 21 flagged structural by the keyword screen (imports, circular dependencies, module boundaries), 1,811 commits, 187k lines, BSD-3, ~93% Python. The repository on which the rule compiler's compilable fraction (RQ1) is measured against ADR text rather than contracts. |
| apache/airflow | reserve (ADR track) | 49 ADRs since 2021-11, 35 structural; 40,198 commits — too large to replay this term, used for the compilable-fraction study only. |
| xorq-labs/xorq, UKGovernmentBEIS/inspect_evals | reserve (ADR track) | 21 and 10 ADRs, young records (2026); pass 1, 2, 5–8. |
| PostHog/posthog | detection-only, exploratory | fails 5–7 (TypeScript-heavy monorepo, 585k+ lines, MIT + `ee/` licence) and is kept apart (`reports/exploratory/`); 6 contracts since 2026-04-15 with 189 exceptions standing at HEAD (481 added, 292 removed in 59 commits in six months) — the repair-rich history the primaries lack, for RQ1/RQ3 statistics only, never for drafts. |
| openedx/openedx-platform | example source only | 143 ADRs and 4 contracts, AGPL-3.0; fails 5–7. Not a subject; ADR 0002 "Inter-app APIs" supplies the vocabulary's MISSING example. |

## Rejected

Every rejected longlist row keeps its rule and reason in `data/longlist_decisions.csv`; every
screened repository keeps its measured criteria in `data/candidates.csv` (`criteria_met`).
Notable near misses: nolar/kopf (11 contracts since 2021, but a rebased history of 564
first-parent commits fails criterion 2); LibrePhotos, endurain, geti, blueking-* (contracts in a
backend sub-package of a TypeScript-heavy monorepo: criterion 5); mixle (714k lines: 6); PyTCP,
Carvera (GPL: 7); the 44 personal repositories under R4.

## Amendments

- 2026-10-21 — Criterion 4 (≥ 20 violation-reducing commits) is reported, not selected on
  (option C above); a detection-only subject that fails 5–7 is admitted for RQ1/RQ3 statistics.
  Reason: no repository with enforced contracts reaches 20; the mechanism is recorded above.
- 2026-10-21 — Criterion 1's ADR arm is measured as "ADR files in a decisions folder at HEAD",
  dated by the first-parent commit that added the file (a folder move resets the date: gt4py's
  51 ADRs all date from the 2025-04-11 move to `docs/development/ADRs/`).

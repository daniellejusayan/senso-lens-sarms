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

## Decision for Wednesday 21 Oct: criterion 4

Run `proxy_lint --every 1` on napari, checkov and sqlfluff on Tuesday so the call has exact
numbers, then choose one, and record it below as an amendment:

| Option | What changes | Effect on the seed set |
| --- | --- | --- |
| A. Keep ≥ 20 | add one repair-rich subject for detection only (RQ1, RQ3), relaxing 5–7 for it | PostHog (58 exception-removal commits since Apr 2026) or edx-platform (9, and 143 ADRs) joins kedro/napari/checkov |
| B. Count both kinds of repair, ≥ 10 | drops in the strict violation count (every commit) + commits that remove an exception | kedro 4 + 3 = 7 still fails; napari and checkov unknown until Tuesday |
| C. Report, don't select on it | criterion 4 becomes a measured finding; selection uses 1–3, 5–8 | kedro, napari, checkov selected; the low repair counts become a result |

Recommendation: C for the three primary subjects plus A's detection-only subject, because
the evaluation needs deviations to judge (100 for precision), and enforced contracts produce
few. Ask Ajarn on Wednesday whether a detection-only subject that fails 5–7 is acceptable.

## Selected (fill on Wednesday, confirm on Friday)

| Repository | Role (primary / reserve / detection-only) | One paragraph of rationale |
| --- | --- | --- |

## Rejected

Every rejected candidate keeps its reason in data/candidates.csv (column `reason`).

## Amendments

(none yet)

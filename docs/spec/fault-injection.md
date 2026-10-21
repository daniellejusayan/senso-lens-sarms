# Fault-injection protocol (spec v0, point 7)

The replay measures the past; it cannot show the live post-push path, where the system acts
with no human in the loop. Fault injection does. Written on 21 Oct 2026, before the system
exists, so the targets are on record; changes are appended under *Amendments*.

## Setup

1. Clone the subject at its current default-branch head into a throwaway working copy
   (`data/raw/REPO` is never used for this; the kernel must be free to commit).
2. Create a branch `sarms/fi-<run-id>`. The "developer" is a fixed test author
   (`SARMS Test Author <fi@sarms.invalid>`); the system commits as
   `sarms[bot] <bot@sarms.invalid>`. Author identity is how the ledger tells the two apart.
3. Freeze the record: compile the subject's contracts and ADRs at that head into
   `.rms/rules/` and commit them to the branch first, so every injection is judged against
   the same rules.

## Injections — 10 per subject, drawn with `numpy.random.default_rng(2569)` and committed before the run

Each injection is one commit by the test author that breaks exactly one known rule and
nothing else, and carries a small functional change (a new function with a test) so that G0
has something to keep. The ten are balanced across the Differ labels and classes:

| # | Kind | What the commit does | Differ label expected | Correction class expected |
| --- | --- | --- | --- | --- |
| 1–3 | layer skip | a module in a lower layer imports a module from a higher layer (the layers contract) | INVERTED | move_to_layer or route_through_port |
| 4–5 | forbidden import | a `source_modules` module imports a `forbidden_modules` module | ADDITIONAL | route_through_port |
| 6 | independence break | one of two independent packages imports the other | ADDITIONAL | extract_shared_types |
| 7 | acknowledged exception re-used | an import that is in `ignore_imports` is used from a new module | ADDITIONAL (acknowledged = false, new module) | move_to_layer |
| 8 | documentation lag | the commit also edits the ADR/contract text to allow the new import, with a PR text that says so | ADDITIONAL + stale record | record_amendment |
| 9 | requirement realization | the PR text describes a new capability; no conforming path exists | ADDITIONAL | escalate (decision record) |
| 10 | clean control | a functional change that breaks no rule | none | none — the system must do nothing |

Subjects whose record has no contract of a kind (no independence contract, say) get a second
injection of another kind in its place; the substitution is written in the run's README.

## What must happen, with no human action

For every injection 1–8 the system, on its own, (a) detects the deviation on the pushed tree,
(b) produces a draft, (c) passes G0–G8 and (d) commits the correction as a follow-up commit on
the same branch with the decision record attached; the test author's commit is untouched
(G0) and `git revert <system commit>` is clean (G7). Injection 9 ends in a decision record
and no commit. Injection 10 ends in a ledger row with no deviation and no commit.

## Measures (Axis A, controlled)

| Measure | Definition | Target |
| --- | --- | --- |
| Corrected | injections 1–8 that end with a system commit and the Differ at zero new violations | 8/8 per subject (100% corrected or escalated, 0 left standing, over all subjects) |
| Escalated correctly | injection 9 ends in a decision record, no commit | 1/1 |
| Silent on clean | injection 10: no draft, no commit, one ledger row | 1/1 |
| Author untouched | the test author's diff is byte-identical after the system commit (G0) | 100% |
| Revert clean | `git revert` of each system commit applies without conflict (G7) | 100% |
| Time to correction | seconds from the injected commit to the system commit | report median and max |
| False action | any system commit on injection 10, or any second system commit on 1–9 | 0 |

An injection the system cannot correct is a finding, not a failure of the protocol: it is
recorded with the gate line that failed and goes to the paper's limitations.

## Audit link

The 10 applied corrections in the post-hoc audit (evaluation-protocol.md) are drawn half
from the replay and half from these runs, so the auditors see the live path too.

## Amendments

(none)

# Gate G0–G8 (spec v0, draft for D)

A checklist run by tools; no LLM. Lines run in this order, static lines first, and the first
failing line stops the run: the draft is not returned as verified, the deviation is still
reported, and the failure is counted as a verifier rejection. Each line names the evidence
the decision record must carry; a line without evidence is a fail. Thresholds live in
`.rms/policy.yaml` (owned by the architects through CODEOWNERS).

| Line | Passes when | Evidence field | Tool | Stage |
| --- | --- | --- | --- | --- |
| G0 | the author's functional change is still in the diff and their added tests pass | diff_hunks_kept, author_tests | diff against the author's diff; pytest -k on their tests | static |
| G1 | the Differ on the candidate shows strictly fewer violations and none new | differ_before, differ_after | import-linter, grimp, the Differ | static |
| G2 | no new cycle, no hub fan-in growth, no new unassigned module | indicators_before, indicators_after | networkx; PyExamine as second opinion | static |
| G5 | no protected path touched; files and lines changed under the class cap | paths_touched, blast_radius | path filter, diff stats | static |
| G6 | the draft names the rule or ADR it serves and that rule is the one violated | rule_id | lookup in .rms/rules/ | static |
| G7 | one commit that git revert undoes cleanly | revert_dry_run | git | static |
| G3 | full suite green | pytest_run_id | pytest, pytest-testmon first | trial |
| G4 | mutation score on the moved code not below the policy floor | mutmut_before, mutmut_after | mutmut, diff-scoped | trial |
| G8 | contracts compile and pass in a clean CI run | ci_run_id | import-linter in a fresh job | trial |

The table is in execution order (all static lines, then the trials); the record still lists
G0 to G8 in numeric order.

## Decisions to write into .rms/policy.yaml this week

| Setting | Draft value | Why |
| --- | --- | --- |
| G4 mutation floor | not below the score at the author's commit, and at least 0.60 | the moved code must stay at least as well tested as it was |
| G5 protected paths | `.github/**`, `.rms/policy.yaml`, `CODEOWNERS`, the contract files (except for class record_amendment) | the system may not edit its own fence |
| G5 class caps | move_to_layer ≤ 10 files / 300 lines; route_through_port ≤ 15 / 500; record_amendment ≤ 3 / 120 | a conforming version should be a small, reviewable change |
| G3 flaky tests | a test in the flakiness registry is re-run up to 2 times and is not G3 evidence on its own | same sha passing and failing is noise, not evidence |
| Relocation (G1) | any new ADDITIONAL or INVERTED edge fails, even if the total falls | reduce, never relocate (kedro, Nov 2024: an exception moved from `parallel_runner` to `task`) |

# Gate G0–G8 (spec v0, draft for D)

A checklist run by tools; no LLM. Lines run in this order, static lines first, and the first
failing line stops the run: nothing is applied, the deviation is still reported, and the
failure is counted as a verifier rejection. Each line names the evidence
the decision record must carry; a line without evidence is a fail. Thresholds live in
`.rms/policy.yaml` (owned by the architects through CODEOWNERS).

**Point 7 (21 Oct 2026): no human after the push.** The verdict `accept` means the kernel
applies the correction itself, as a follow-up commit of its own on the same branch, with the
decision record attached. No one is asked to accept, edit or re-visit anything; the author is
notified. Two lines make acting without asking safe and are never relaxed by policy: G0 (the
developer's change is kept) and G7 (one commit undoes the system's). Humans meet the system's
work afterwards, in `docs/architecture/log.md` and in the post-hoc audit
(evaluation-protocol.md); the audit can switch a correction class off in `policy.yaml`, which
is the only human control in the loop.

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
| G5 class caps | move_to_layer ≤ 10 files / 300 lines; route_through_port ≤ 15 / 500; record_amendment ≤ 3 / 120 | a conforming version should be a small, auditable change |
| G3 flaky tests | a test in the flakiness registry is re-run up to 2 times and is not G3 evidence on its own | same sha passing and failing is noise, not evidence |
| Apply | every correction class applies autonomously (`classes.<name>.enabled: true`); the audit may set a class to `false`, after which that class escalates instead of applying | point 7: no human in the post-push path; the audit is the only switch |
| Relocation (G1) | any new ADDITIONAL or INVERTED edge fails, even if the total falls | reduce, never relocate (kedro, Nov 2024: an exception moved from `parallel_runner` to `task`) |

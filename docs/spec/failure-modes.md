# Failure modes (spec v0, draft for D)

The runbook's eight rows first; the rows after them were found in the 19 Oct test runs.

| Failure | How we detect it | Mitigation |
| --- | --- | --- |
| An ADR cannot be compiled | the compiler writes `evaluable: false` | counted and reported as the uncompilable fraction (RQ1); routed to humans, never guessed |
| Flaky tests | the same sha fails and passes on rerun | flakiness registry; a flaky test is not G3 evidence |
| A draft relocates a violation | G1: the Differ on the candidate | rejected; counted as a verifier rejection |
| Prompt injection through PR or issue text | by construction | PR text enters the prompt as a fenced data field; output is schema-validated; Synthesize has no tools |
| Contracts changed over the history | `sarms.rules.record_history` (contract introduction from the import-linter section, not `git log --diff-filter=A`, which dates the file) | rules compiled from HEAD; pre-contract commits excluded from the gap |
| Test suite too slow for the trial | run time over 10 minutes | testmon selection; per-trial time cap; repository criterion 3 |
| Model nondeterminism | differing outputs for one prompt hash | pinned model, temperature 0, prompt hash logged; verifier rejections counted as the error signal |
| Graph extraction too slow on a large repository | over 60 s per commit | repository criterion 6; grimp cache; module-level graph only |
| Contracts enforced in CI hide the debt | proxy run with the record as written shows no violations after the contract date | strict record (exceptions removed) plus exception churn from `record_history` |
| Old commits lack the modules a contract names | import-linter raises "Missing layer" or "does not exist" | layers made optional; the contract is recorded as `error` for that commit, never as a violation |
| A violation is relocated by a human, not repaired (kedro, Nov 2024) | an exception disappears and a near-identical one appears in the same commit | not counted as a repair; reported separately |
| One import line creates many violating edges (kedro, Jan 2025: 13) | many episodes share one introducing commit | precision sampled and reported by incident |
| The subject's package shares a name with the checker's own packages (grimp, importlinter, click, rich) | the worker refuses with "same name as a module the checker itself uses" | such repositories cannot be subjects; excluded at screening |
| Module or package renamed (src layout move) | an edge disappears and an edge with a renamed endpoint appears in the same commit | pair them; neither a repair nor an introduction |
| A commit subject holds a control character (PostHog, U+001D) | `git log` text parsing splits one record in two | records are NUL-separated (`git log -z`) |
| A fresh contract legalises the existing structure (faststream, Sep 2026: 17 exceptions on day one) | the strict record shows many violating edges before the contract date and none after | counted as documentation lag at adoption, not as erosion; reported per repository |
| The system commits a correction the team did not want (point 7) | a human commit edits or reverts the system's commit inside the watch window (`amended_by_human`, `reverted`) | G0 keeps the developer's change; G5 caps blast radius; G7 one-commit revert; the audit switches the class off in `policy.yaml` |

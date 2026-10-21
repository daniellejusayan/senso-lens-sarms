# Evaluation protocol (spec v0, draft for D)

Written before any result exists. Put the SHA-256 of this file into the P1 pack
(`sha256sum docs/spec/evaluation-protocol.md`) so the targets are on record; later changes
are appended under *Amendments* with a date and a reason, never edited in place.

## History

The default branch's first-parent chain, oldest to newest. A merge commit is read as its
diff against `parents[0]` (what the push added). `idx` is the position on that chain.
Example of why this matters: kedro's `kedro.runner → kedro.config` violation was removed on
main by a merge commit (e6cfb423, develop → main, 31 Mar 2022), which a per-commit miner that
reports no files for merges would miss.

## Replay rule

At commit *t* the system sees only history before *t* (contracts and ADRs as they were at
*t*, PR text created before *t*); the later human commit that removed a deviation is the
ground truth and the comparison target for our draft.

The Week 1 proxy run is a different, labelled view: the HEAD record with every
`ignore_imports` entry removed ("strict"), applied to sampled commits. It measures how long
code that breaks today's record lived. The as-of view with exceptions kept is what CI saw;
for repositories that run lint-imports in CI it is nearly always clean (kedro: 160 of 160).

## Units

- Violating edge: (contract or rule, edge_from, edge_to) as reported.
- Episode: consecutive checked commits in which the edge is present; introduced_at = first,
  repaired_at = first later commit without it while the contract can still be checked.
- Pre-contract episode: began before its contract was written; in the series, not in the gap.
- Incident: episodes introduced by the same commit (one import line can create many edges;
  kedro, Jan 2025: 13). Precision is sampled by incident.

## Measures and targets

- Detection precision (RQ1): a stratified random sample of 100 flagged deviations
  (proportional per repository, at least 15 per label); two raters label independently,
  disagreements adjudicated; precision = agreed-true / 100; target ≥ 0.90; report Cohen's κ.
- Awareness gap (RQ1): for each repaired deviation, commits and days from introduced_at to
  repaired_at; report median, 90th percentile and the share never repaired. A measurement,
  no target.
- Verified-suggestion rate (RQ2): among implementation-choice deviations, the share with a
  draft passing G0–G8; target ≥ 70%. Gate soundness: verified drafts that add a violation or
  a smell, target 0.
- Root-cause agreement (RQ3): 50 cases, two raters, Cohen's κ ≥ 0.6; and the share routed to
  the right action (code, record, escalate).
- Reviewer study (RQ2): 3–6 reviewers, 20 proposals with the evidence pack, items A1–A6 on
  anchored 1–5 scales plus the binary "would you merge this as-is?"; target ≥ 70%
  would-accept (4 or 5); report Krippendorff's α and medians.
- Comparison draft: every LLM draft is compared with the rule-based template draft under the
  same gate; report both rates.

Random draws use `numpy.random.default_rng(2569)`; the drawn ids are committed before anyone
looks at the cases.

## Threats reported with every number

Survivorship (changes nobody attempted cannot be scored); label noise in "repairing" commits
(a removal can be a rename or a relocation); the strict HEAD view is retroactive for contracts
written late; repositories with enforced contracts are more disciplined than average
(selection bias); preprint status of several sources.

## Amendments

(none)

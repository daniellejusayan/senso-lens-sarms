# Build plan — the automated loop this semester (agreed 28 Oct 2026)

**This semester:** build the whole MSV-K loop on import-linter contracts (checkable Python rules
we have today), then add rules compiled from ADRs, each confirmed once by a person before it is
enforced. **Next semester:** repositories with no reference files (onboarding: mine the history,
flag risks, ask the architects, record every answer, then run autonomously).

**What the system guarantees:** no push leaves a recorded rule broken. Every violation a push
introduces is corrected automatically or escalated, without blocking the push, and no
correction sarms applies makes the structure worse. People own the rules; sarms owns the
enforcement. In the paper the rules are *architectural rules* or *adaptation goals*, not
requirements.

## Build order on kedro (a thin slice through every stage, then widen)

| Step | Component | What it does | Done when | Status (28 Oct) |
| --- | --- | --- | --- | --- |
| 1 | Rule compiler `sarms.rules.compile` | contracts at a commit → `.rms/rules/*.yaml` (schema-checked), `acknowledged.yaml`, `contracts.json` | kedro's 4 contracts compile and validate | **done**: 64 rules (36 forbidden, 28 allowed), 0 schema errors |
| 2 | Differ `sarms.differ` | labels edges CONFIRMED / ADDITIONAL / INVERTED (MISSING with ADR rules); acknowledged = gone under the contracts as written; direct vs indirect; drift indicators (unassigned, cycles, fan-in); SARIF | reproduces the replay's 16 violating edges and 28 episodes | **done**: `tools/check_against_replay.py` → ALL PASS; 1,957 commits in 3 min |
| 3 | Ledger `sarms.ledger` | DuckDB per `docs/spec/ledger.sql`; episodes; awareness-gap view; hub-growth rows | view gives 92 commits / 156 days | **done**: 96,455 rows; 92 / 156; 4 drops; 9 standing |
| 4 | Synthesize `sarms.synthesize` | one LLM call drafts FIND/REPLACE edits; applied in a copy; G1 (violation gone, none new) and G3 (tests) re-checked; retry ≤ 3 with the reason; template drafter; everything under `.rms/drafts/` | a valid draft for each kedro fault injection | **built, untested on a real model**: passes end to end with a fake model on a synthetic repo; the first real run is this week's task on the laptop (Ollama) |
| 5 | Gate + kernel `sarms.verify`, `sarms.kernel` | G0–G8 in order (static lines first), signed decision record, commit as `sensolens-sarms`, ledger outcome | 10 plants on kedro: 8 corrected, #9 escalated, #10 (drift) recorded only | Weeks 4–5 |

Then widen: all contract types (protected, acyclic_siblings) → checkov, wemake-python-styleguide →
full fault injection per primary → ADRs on gt4py (compilable fraction = RQ1's measure; a person
confirms each compiled rule once).

## Design decisions fixed so far

- **The Differ runs import-linter itself** for contract rules (the lint worker, one fresh process
  per commit), so indirect chains and optional layers keep import-linter's exact semantics. The
  rule files give every violation a rule id (G6, the ledger) and will carry the ADR rules
  import-linter cannot express (required edges → MISSING).
- **Acknowledged** = the violation disappears when the contract is checked as written. Only 1 of
  kedro's 6 `ignore_imports` entries is a direct exception; the other 5 are links that break
  indirect chains. The strict record (ignores removed) is what the Differ labels.
- **The model is a configuration, not code.** `sarms.synthesize.llm` speaks the OpenAI chat API to
  any endpoint: Ollama locally (default, `qwen2.5-coder:7b`), Gemini's free tier, or a paid API.
  One call per draft, temperature 0, no tools, no agent, no fine-tuning. Model, endpoint and
  prompt hash are stored with every draft.
- **Drafts are FIND/REPLACE blocks, not diffs.** Small local models get them right more often, and
  a block that does not match is rejected before anything runs.
- **Early gate lines in the draft step:** edits to tests, rule files or anything outside the
  source roots are refused (G0/G5), and the Differ re-runs on the copy (G1). The full gate,
  mutation testing, the signed record and the commit are step 5.
- **Bot identity** for step 5: `sensolens-sarms`. The CI attribution check blocks a plain `sarms@`
  author and lets `sensolens-sarms@` through.
- **Spec v0 limit found:** the ledger's primary key has no `rule_id`, so an edge that breaks two
  contracts at once keeps one row. None occurs in kedro; to be fixed by a dated amendment to
  `ledger.sql` before checkov/wemake, where it may.

## What the Differ replay added to the findings

- kedro's 29-module cycle first closed at commit `1ed504cf` (15 Jan 2025, chain position 1516),
  the same push that introduced 13 violating edges. Before it the largest cycle had 2–5 modules;
  after it 13–30. Drift and erosion arrived together.
- Unassigned top-level packages grew from 3 (2019) to 7 (today); no rule was ever added for them.

## Parallel human work (no code)

- Two-rater labelling: the 100 precision cases and the 46 root-cause cases (`data/samples/`).
- Test-suite timing for kedro (`tests/runner` first, then the full suite): G3's cost.
- The ADR hand-check on gt4py's 21 flagged ADRs, by two members independently.
- Recruit 3–6 maintainers for the post-hoc audit.
- Advisor's decisions: point 7, the selection change + PostHog, the four subjects.

## Team split

| Role | Owns | Spec files |
| --- | --- | --- |
| Monitor + Knowledge | rule compiler, Differ, ledger | vocabulary.md, rules.schema.yaml, ledger.md |
| Synthesize | prompts, output format, template drafts, root-cause labels | vocabulary.md (root causes) |
| Verify + kernel | gate G0–G8, decision records, kernel, fault-injection harness | gate.md, decision-record.schema.json, fault-injection.md |
| Evaluation + ADRs | labelling, ADR hand-check and compilation, audit recruitment | evaluation-protocol.md |

## 5 November (progress demo)

Show: `tools/check_against_replay.py` → ALL PASS (the live Monitor reproduces the history
analysis exactly); `sarms check` on kedro today; the ledger in DuckDB; the first real draft
(`sarms draft`, with its prompt, reply, patch and result); the first precision and κ numbers;
kedro's test timing. The fully automatic fix (gate + kernel) follows in weeks 4–5. Fallback: if
model drafts keep failing by 31 Oct, the template drafter carries the demo.

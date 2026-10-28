# sarms — Self-Adaptive Repository Management System (Senso-Lens)

Keeps code faithful to its recorded architecture after each push. After a push lands, the
system compares the change with the architecture recorded in the repository's ADRs and
dependency rules, drafts a conforming version where the change deviates, verifies the draft
with tools (gate G0–G8), and applies it itself; only real architecture decisions reach a human.

1305394 Seminar in Software Engineering, Mae Fah Luang University, 1/2569 · advisor Dr. Nacha
Chondamrongkul · team: Danielle Jerick M. Jusayan, Eaindray, Kanthi Phoosorn, Withuwit Ninphan.

## Layout

```
src/sarms/mining      first-parent history (Step 1b)            src/sarms/differ      the four labels; replay over a history (Week 2)
src/sarms/rules       record history; the rule compiler         src/sarms/ledger      episodes; DuckDB ledger (Week 2)
src/sarms/replay      proxy run and baseline (Step 1c)           src/sarms/synthesize  one LLM call -> a draft tried in a copy (Week 3)
src/sarms/graph       import graph of a commit (extract)         src/sarms/verify      gate G0–G8 (Week 4–5)
                                                                 src/sarms/kernel      executor (Week 5)
tools/                longlist reduction, screening, 1b+1c runner, samples, spec validation, demo,
                      check_against_replay (the Differ's correctness test on kedro)
docs/spec/            the frozen specification (Step 2)     docs/build-plan.md   the build order and its status
data/<repo>/          derived, pseudonymised data (git-ignored); data/<repo>/rms/ = rule bundle, Differ output, ledger, drafts
reports/              baselines, ADR track, exploratory, P1 pack, M1–M3 reports
```

`.importlinter` holds our own contracts (the Differ and the gate may never import the model
step); CI runs ruff, pytest, lint-imports and the spec validator on every push.

## Setup

```bash
uv sync --all-groups
cp .salt.example .salt          # or paste the team salt; .salt is git-ignored, never commit it
uv run lint-imports             # 3 contracts kept
uv run pytest -q
uv run sarms --help             # compile | check | replay | ledger | draft
```

The loop on kedro, end to end: `docs/runbook-commands.md`, section "Weeks 2–3".

Step-by-step commands: `docs/runbook-commands.md`.

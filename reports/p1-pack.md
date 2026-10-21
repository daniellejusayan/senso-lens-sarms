# P1 pack — Steps 1 and 2 frozen (week of 19–23 Oct 2026)

What this pack fixes before any result is used: the selection criteria, the subject
repositories, the vocabulary, the gate, the records and the evaluation protocol. Later changes
go into each file's *Amendments* section with a date and a reason; the hashes below are the
versions this pack refers to.

## Frozen files and their SHA-256

<!-- HASHES -->
| File | SHA-256 |
| --- | --- |
| `docs/repo-selection.md` | `9f5c3bdc17cf02ed61f975ae5d6058f95142440a4a22f26a7424a62d1424a6c2` |
| `docs/spec/vocabulary.md` | `3419154886c66e90ee9dd48aa48635d7b7cdb71eb15b93fd682f1936add502d5` |
| `docs/spec/rules.schema.yaml` | `e3d6da4385dfb7bcb1d725b79b08d9cb43e108990a4777d8a90ec87830fc9c4f` |
| `docs/spec/ledger.sql` | `2332bf40484032f93f172ff7316ed2b7f2ed8d38bc92a1ad1bdbc0d3f26898f4` |
| `docs/spec/ledger.md` | `a7a0b43b262b2f0dcf0e0cf6b1f1d2dbb2d03c12e37f4d7089a9d7944d79bbb5` |
| `docs/spec/decision-record.schema.json` | `e40b6a00e8ae69fe825fa317eaabca8a78299cb4fc5fb88ba08733019d4c7a0e` |
| `docs/spec/gate.md` | `8886f929553be22447c6c1eb3ab000ae57b70a49db473e1880874a70627f7a32` |
| `docs/spec/evaluation-protocol.md` | `b0e2de5cba4bc9985fe566eccd7d1496e75bca79c4aa14e9ec85f49b3f760065` |
| `docs/spec/fault-injection.md` | `8805525c0c550b138439acd4f37123cd2ba701767e379f12ddd03b164ad257b9` |
| `docs/spec/failure-modes.md` | `8f5c12728437bc04f305cee912c2eee2fa4c8c1aac00daada5d5eb49bf5154f5` |
| `docs/ethics.md` | `c2bcb4c7b3b4c6c0a6178b79ea2bd10eed9659ea8124ac6e54eb8407b9bbedff` |
| `data/longlist_decisions.csv` | `83cc1c83fda0864eee5d22c99a93c6513c0e66d793c6caa793d4169efe0cbc3b` |
| `data/candidates.csv` | `96b8f706ee775cb0529cb9a0f860f3d18d081075f729ba9a6a4985b5b1b1d26c` |

## Step 1 — data and evidence

- Criteria 1–8 (and the team's C1–C5 numbering): `docs/repo-selection.md`.
- Longlist 230 → 38 with one reason per row: `data/longlist_decisions.csv` (R3 forks 6, R1 intent
  82, R2 history 60, R4 team 44). Screening of the 38: `data/candidates.csv`.
- Selected subjects, reserves and the detection-only case: `docs/repo-selection.md` § Selected.
- Awareness-gap baseline, every commit, strict HEAD record: `reports/awareness-gap-baseline.md`
  and `reports/awareness-gap-baseline/<repo>.md`.
- ADR track: `reports/adr-track/<repo>.md` (dates, titles, structural flag).
- Exploratory, detection only: `reports/exploratory/posthog.md`.
- Labelling samples, drawn with seed 2569 before anyone looked: `data/samples/`.

## Step 2 — specification (autonomous apply, point 7)

`docs/spec/vocabulary.md` (4 Differ labels, 3 drift indicators, 5 root causes, each with a
real example), `rules.schema.yaml`, `ledger.sql` + `ledger.md`, `decision-record.schema.json`,
`gate.md` (G0–G8, apply policy), `evaluation-protocol.md`, `fault-injection.md`,
`failure-modes.md`, `pilot-sheet.csv`. `uv run python tools/validate_spec.py` passes.

## Checks run on this pack

<!-- CHECKS -->
| Check | Result |
| --- | --- |
| `uv run lint-imports` | Contracts: 3 kept, 0 broken. |
| `uv run ruff check .` | All checks passed! |
| `uv run pytest -q` | 4 passed in 1.07s |
| `uv run python tools/validate_spec.py` | ALL PASS |

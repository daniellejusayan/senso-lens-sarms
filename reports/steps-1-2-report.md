# Steps 1 and 2 — how the system works, what we measured, what we found, what is still open

Written 21 Oct 2026 for the team and the advisor. Every section is explained twice: first in
full, then **in plain words**. A box marked *Where it lives* names the file, column or report
the explanation refers to, so you can open the thing being talked about. Section 8 is a lookup
table of every term and the concrete instance it refers to in our data.

---

## 1. The system in one pass

**In full.** The managed system is a repository: its code, tests, CI and its *recorded intent*
— the architecture its team wrote down as import-linter contracts (`pyproject.toml`,
`.importlinter`, `setup.cfg`) or as architecture decision records (ADRs, Markdown files in a
`decisions/` or `adr/` folder). The managing system attaches to it and treats every push, once
it has landed, as an event. A non-adaptive **kernel** (this term a replay driver; in Term 2 a job
in the repository's own CI) routes the event into one MSV-K loop:

- **Monitor** (deterministic, no model) builds the import graph of the pushed tree, loads the
  rules compiled from the record, and the **Differ** labels every intended edge CONFIRMED /
  MISSING / ADDITIONAL / INVERTED and computes three drift indicators.
- **Synthesize** (the LLM) reads a labelled deviation, the rule's text and the pull-request text
  as quarantined data, and returns a schema-validated root-cause label plus a draft: a
  conforming version of the author's own change, or an amendment of the record when the record
  is what lagged.
- **Verify** (deterministic, tools only) runs the gate G0–G8 on the draft: the developer's
  change is kept, strictly fewer violations and none new, no new smells, tests green, mutation
  floor on moved code, protected paths untouched, traceability to the rule, one-commit revert,
  clean contract compile.
- **Knowledge** is the compiled rules, the deviation ledger, the signed decision records, the
  architecture log and the policy, all versioned inside the repository under `.rms/`.

Four rules govern the loop. (1) The push always lands — never blocked, never reverted.
(2) Erosion is never left standing — a broken rule always yields a verified correction or a
record amendment. (3) Drift is allowed for now — structure that moves without breaking a rule
is recorded and trended, and architects get a decision record when a trend appears. (4)
Everything is recorded — ledger, decision record, ADR amendment, architecture log. **Point 7
(21 Oct)**: the verdict `accept` means the kernel *applies* the correction as its own commit on
the same branch. Nobody is asked to click; the author is told; humans audit afterwards. G0 and
G7 are the two lines that make acting without asking safe.

**In plain words.** A team writes down "module A must never import module B". Developers
push code anyway. After each push, our system checks whether the new code broke any written
rule. If it did, it asks a language model for a version of the same change that respects the
rule, checks that version with ordinary tools (does it still do what the developer wanted, does
it break fewer rules, do the tests pass), and then commits that version itself. The developer
never has to come back and fix architecture. If the rule itself is what's out of date, the
system fixes the document instead. If the problem is a real architecture decision, it writes a
note for the architects and leaves the code alone.

> *Where it lives:* the proposal (Part 7, Figure 1); `docs/spec/gate.md`;
> `docs/spec/vocabulary.md`; the design note in Part 7.4 of the proposal (point 7).

---

## 2. The words everything else is built on

**Intended vs implemented architecture.** The intended architecture is what the team wrote
down; the implemented one is what the code actually does. For Python the implemented
architecture we can read mechanically is the **import graph**: a node per module, an **edge**
from module X to module Y when X imports Y. The intended architecture, once compiled, is a set
of statements about edges: this edge is allowed, this one forbidden, this one required.

**In plain words.** The code is a map of who-calls-whom. The rules say which roads are
allowed. We compare the two.

**The four Differ labels.** For each edge a rule speaks about, at a given commit:

| Label | Meaning | Erosion? |
| --- | --- | --- |
| CONFIRMED | an allowed/required edge is present | no — conformance |
| MISSING | a required edge is absent | yes, if it used to be there |
| ADDITIONAL | a forbidden edge is present | yes |
| INVERTED | under a layers rule, a lower layer imports a higher one | yes |

A **violating edge** is an ADDITIONAL or INVERTED edge (or a MISSING one that used to exist):
one concrete import line in one file that breaks one written rule. It is the atom of the whole
project: the Differ labels it, the ledger stores it, the awareness gap is measured on it,
Synthesize drafts a fix for it, and the gate's G1 asks "are there fewer of them and none new".

**In plain words.** A violating edge is one line `from kedro.config import …` sitting in a
file under `kedro/runner/`, when the team's rule says runner must not import config. That one
line is what we count, time, and later fix.

**Why edges and not something fuzzier.** Because the system must act without a human, its
detection has to be something two runs agree on exactly. An import edge either exists in the
tree or it doesn't; a rule either names it or it doesn't. There is no judgement in Monitor, so
the only place a model's opinion enters is the draft — and the gate re-checks that draft
mechanically.

**Acknowledged exceptions and the strict record.** import-linter lets a team list imports it
knows break a contract but tolerates (`ignore_imports`). The checker then stays green. We call
those **acknowledged** violations. The **strict record** is the HEAD configuration with every
`ignore_imports` entry removed: it asks "what does the code do against the rule as written",
not "what does the team currently tolerate". We replay the strict record because a repository
that enforces its contracts in CI shows *zero* violations after the contract date under the
record as written — the exceptions hide exactly the debt we want to see.

**In plain words.** Teams keep a list of "yes, we know, ignore it". We take that list away for
the measurement, because the ignored imports are the architectural debt.

**Episode.** A violating edge appears at one commit and (maybe) disappears at a later one.
That span is an episode: introduced-at, repaired-at (or still open), gap in commits and days.
If the edge was already there when the contract was written, the episode is **pre-contract**:
it is in the series but not in the awareness gap, because nobody could have been "unaware" of
a rule that did not exist yet.

**First-parent history.** We walk the default branch's first-parent chain, so a merge commit
is read as "what the merge added to the branch". A per-commit miner that reports no files for
merges (PyDriller does) misses repairs that landed by merge — kedro's `runner → config` repair
did.

**In plain words.** We read the main branch's history the way the branch itself experienced
it, one landing at a time.

**Erosion vs drift.** Erosion = a written rule is broken (a violating edge). Drift = the
structure moves without breaking a rule: a new module no layer claims, a new import cycle, a
module everyone starts depending on. The system corrects erosion and only records drift.

> *Where it lives:* `docs/spec/vocabulary.md` (labels, indicators, root causes);
> `data/<repo>/violations_sample.parquet` (one row per violating edge per commit: `contract`,
> `edge_from`, `edge_to`, `edges` = the import lines); `data/<repo>/episodes.csv`;
> `data/<repo>/record/importlinter.HEAD.*` (the record) and `record/events.parquet`
> (every exception added or removed).

---

## 3. The awareness gap — where it comes from and why we baseline it

**In full.** The proposal rests on Anthony et al.'s 2024 study of how developers deal with
architectural drift (the proposal's reference [1]): teams detect deviations mainly by
reviewing each other's code and by talking; 89% sometimes do not discuss architectural
decisions; and when developers were asked when they become aware of a deviation, the answer
was "at some other time in the future". Our research questions turn that sentence into a
number. RQ1 asks, among other things, "how much earlier than the human repair does the system
detect a deviation?" To answer it we need to know how long humans took. The **awareness gap**
of a violating edge is the distance, in commits and in days, between the commit that
introduced it and the human commit that removed it. The **baseline** is that distribution,
measured on the subject repositories *before* the system exists (Part 3, evidence row 6 of the
proposal; reported at checkpoint M1 on 6 Nov).

It does three jobs. First, it is the problem's existence proof in our own data, not only in
the literature. Second, it is the yardstick: a system that checks every push detects at a gap
of zero commits, so the baseline's median is the detection lead we claim. Third, it feeds
selection: a repository where nobody ever repairs anything, or where there is nothing to
repair, teaches us less.

**How we compute it.** Freeze the record at HEAD (`record_history`), strip the exceptions,
check every first-parent commit against it (`proxy_lint --every 1`), and read the resulting
series into episodes (`baseline`). A rise in the count of violating edges is an introduction;
a drop is a human repair. Criterion 4 in our selection criteria ("≥ 20 violation-reducing
commits") was meant to make sure there were enough drops to study.

**In plain words.** The literature says developers notice architecture problems "some time
later". We measured how much later, in the real histories of real projects: for each broken
rule, how many commits and days passed before somebody fixed it. We did this before building
anything, so that when the system later catches a problem on the very push that created it,
we can say exactly how much earlier that is.

> *Where it lives:* proposal Part 3 row 6, RQ1, Appendix D replay protocol;
> `reports/awareness-gap-baseline.md` (summary table + one section per repository);
> `reports/awareness-gap-baseline/summary.csv` (columns `episodes_after_contract`, `repaired`,
> `median_gap_commits`, `median_gap_days`, `drops`, `exception_removal_commits`).

---

## 4. Step 1 in order — what we did and why

### 4a. Selection

**In full.** Eight criteria were frozen on 19 Oct before any repository was looked at: intent
recorded (≥ 2 contracts or ≥ 10 ADRs), history (≥ 2 years, ≥ 1,500 first-parent commits),
tests under 10 minutes, repairs exist (≥ 20 drops), ≥ 90% Python, 20k–400k lines, OSI licence,
alive. The team's own sheet numbers them C1–C5; the mapping is recorded (C1 = Python, C2 =
intent, C3 = years, C4 = tests, C5 = repairs). The 230-row sheet was reduced by five rules in a
fixed order, each row keeping its reason: forks/duplicates/the checker itself (6), intent too
thin (82), history too short (60), under 50 stars — no team behind it (44), tach-only rules
(0). The 38 survivors were cloned (partial clones) and measured from the repository itself.
Then the subjects were chosen with the baseline numbers in front of us.

**In plain words.** We wrote the rules for choosing projects before looking, so we could not
pick projects that flatter us. Then we threw out copies, toy projects and projects with too
little written architecture or too little history, and measured the rest.

**Why 50 stars.** The problem statement is about *teams* losing architectural knowledge through
communication. A one-person repository has no communication to lose. Stars are a crude proxy
for "more than one person depends on this"; we say so in the amendments.

> *Where it lives:* `docs/repo-selection.md` (criteria, C1–C5 map, R1–R5, selected table,
> amendments); `data/longlist_decisions.csv` (`decision`, `rule`, `reason` per row);
> `data/longlist.txt`; `data/candidates.csv` (`criteria_met`, `contracts`, `adrs`,
> `n_first_parent`, `loc_py`, `python_share_pct`, `licence`, `config_path`).

### 4b. Mining

**In full.** `sarms.mining.first_parent` walks each repository's default branch and writes one
row per first-parent commit: position, sha, committer and author time, a salted hash of the
author e-mail, merge flag, files and Python files touched, subject, PR number. Author e-mails
never reach disk; the hash uses a secret team salt (`.salt`, git-ignored) so the same author
gets the same hash across our repositories and nobody else can reverse it.

**In plain words.** We copied each project's history into a table, one line per landing on
the main branch, with the authors replaced by codes.

> *Where it lives:* `data/<repo>/commits.parquet`; `docs/ethics.md`; `src/sarms/mining/`.

### 4c. The baseline run

**In full.** For each contract-track repository: `record_history` reads the import-linter
section at every commit that touched a config file and records contract added/removed/changed
and every exception added/removed (this is also where the contract's true introduction date
comes from — not the config file's first commit); `proxy_lint --every 1` applies the strict
HEAD record to every commit, with layers made optional and missing modules recorded as `error`
rather than as violations; `baseline` turns the series into episodes and the report. For the
ADR track, `adr_history` lists every ADR at HEAD, dates it, and flags the ones whose text
names imports, dependencies, layers, modules or boundaries — the candidates the rule compiler
will try in Week 2.

**In plain words.** We took each project's current rulebook, removed the "ignore this" list,
and checked every single historical version of the code against it, then noted when each
broken rule appeared and when (if ever) a person fixed it. For projects that have decision
documents instead of rules, we listed the documents and marked the ones that talk about
dependencies.

> *Where it lives:* `tools/run_step1.py` (runs all four stages, `data/<repo>/timings.csv`);
> `data/<repo>/checks_sample.parquet` (one row per commit × contract, `status` ∈ kept, broken,
> error, package_missing, graph_error); `reports/adr-track/<repo>.md`; `data/<repo>/adrs.csv`.

---

## 5. What we found

### The table

| Repository | Commits replayed (window) | Contracts (since) | Violating edges ever | Episodes after the contract | Repaired | Median gap commits / days | Drops | Exception removals | Standing at HEAD (strict) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| kedro-org/kedro | 1,957 (all) | 4 (2019-08) | 16 | 28 | 19 (68%) | 92 / 156 | 4 | 3 | 9 |
| bridgecrewio/checkov | 2,695 (since 2023-06) | 6 (2023-08) | 25 | 1 | 0 | – | 6 | 5 | 5 |
| sqlfluff/sqlfluff | 1,986 (since 2023-06) | 4 (2023-08) | 8 | 3 | 0 | – | 1 | 0 | 5 |
| wemake-services/wemake-python-styleguide | 3,148 (all) | 6 (2019-07) | 5 | 1 | 1 | 32 / 14 | 3 | 3 | 2 |
| ag2ai/faststream | 1,624 (all) | 8 (2026-09) | 80 | 0 | – | – | 3 | 0 | 20 |
| ramses-rf/ramses_rf | 4,699 (all) | 4 (2026-06) | 21 | 6 | 1 | 143 / 25 | 13 | 0 | 15 |
| Qiskit/qiskit-serverless | 1,868 (all) | 3 (2026-02) | 2 | 0 | – | – | 1 | 0 | 0 |
| PostHog/posthog (exploratory, stride 50) | 663 of ~33,000 since 2026-03 | 6 (2026-04) | 111 | 101 | 22 (22%) | 1,200 / 5 | 30 | 59 | 189 exceptions |

### Finding 1 — enforced rules keep violations off main; what stands is acknowledged debt

**In full.** Every repository has violating edges at HEAD under the strict record, and they are
almost exactly the imports its team listed in `ignore_imports`. kedro's oldest standing edge,
`kedro.runner → kedro.config`, was introduced on 16 Jul 2020 together with its own exception
and has stood, with one 13-month break, ever since. Under the record *as written* these
repositories are green.

**In plain words.** The projects that take architecture seriously don't let new violations
through — their checker blocks them. But each has a short list of "known violations we live
with", and those sit there for years. That list is the architectural debt.

**What it means for the design.** The system's first job on a real repository is not to
catch new violations (CI already does) but to work off the acknowledged list — and to keep
the record honest when a developer adds a new exception instead of a fix.

### Finding 2 — human repair is rare and slow

**In full.** kedro, the richest history: 28 episodes after the contract, 19 repaired, median
92 commits / 156 days, 90th percentile 285 commits / 430 days, 9 never. The three longest
repaired gaps were 623, 469 and 420 days. Across the seven repositories, 21 of 39 post-contract
episodes were ever repaired, 19 of them in kedro.

**In plain words.** When a rule was broken, half the time it took more than five months and
ninety-odd pushes before someone fixed it — and nearly half were never fixed.

### Finding 3 — the contract's arrival is itself the repair event

**In full.** checkov's 24 pre-contract violating edges were all removed on 15 Aug 2023, nine
days after its first contract was written (6 Aug); sqlfluff's on 29 Aug and 25 Oct 2023, the
days its contracts arrived; wemake's four pre-contract episodes end at or before the 2019
contract. After that, there is almost nothing to repair.

**In plain words.** The moment a team writes the rule down is the moment it cleans up. After
that the checker holds the line and humans rarely have to.

### Finding 4 — a fresh record legalises the existing structure

**In full.** faststream's eight contracts (20 Sep 2026) came with 17 exceptions on day one;
the strict record shows 80 violating edges before that date and none after. ramses_rf (June
2026) shows the same shape: 19 pre-contract episodes, 15 edges standing at HEAD behind
exceptions. This is documentation lag by construction: the record was written to describe the
structure, exceptions included.

**In plain words.** New rulebooks are often written around the mess that already exists, with
the mess listed as exceptions. Our root-cause label *documentation lag* is for exactly this.

### Finding 5 — criterion 4 is met by nobody

**In full.** Drops in the violation count after the contract: kedro 4, checkov 6, wemake 3,
sqlfluff 1, faststream 3, ramses_rf 13 (mostly before its contract), qiskit 1. The ≥ 20
threshold assumed repairs would be frequent; findings 1–3 say why they are not. We took option
C — criterion 4 is reported as a finding, not used for selection — and admitted PostHog as a
detection-only case because it is the one repository where repair is frequent: 101 post-contract
episodes in six months, 22 repaired, 30 drops, 59 exception-removal commits — and a median gap
of 5 days, because PostHog lands ~150 commits a day (1,200 commits) and runs the checker in CI
(`reports/exploratory/posthog.md`, sampled every 50th commit).

**In plain words.** We expected to find lots of "someone fixed an architecture violation"
commits. We found a handful per project, because the checker stops most violations before
they land. That is itself the result, so we kept the criterion as a number to report and
dropped it as a filter.

> *Where it lives:* `reports/awareness-gap-baseline.md`; `docs/repo-selection.md` § Decision
> taken 21 Oct and § Amendments; `reports/exploratory/posthog.md` (when the run finishes).

### The ADR track

gt4py: 51 ADRs, 21 flagged structural by the keyword screen; airflow 49 / 35; openedx 143 /
42; xorq 21 / 19; inspect_evals 10 / 7; climate_indices 24 / 18. The flag means the text uses
at least two of: import, dependency, layer, module, package, boundary, must not, only through,
circular, coupling, interface. It is a screen, not a judgement; Week 2's compiler decides which
sentences become rules, and the share that cannot is RQ1's "compilable fraction".

**In plain words.** We found the decision documents and marked the ones that sound like rules
about who may import whom. Whether they really can be turned into rules is next week's work.

---

## 6. Step 2 — the specification, and why it exists before any code

**In full.** The spec is the contract between the team members building the four parts and
the contract with the evaluation: it fixes what every label means, what a rule looks like,
what the ledger stores, what the gate checks and in what order, what the decision record
carries, how the evaluation will be run and scored, and how fault injection works. It is
written before the build so that the results cannot bend the definitions; later changes go
under *Amendments* with a date and a reason, and `reports/p1-pack.md` records every file's
hash. Point 7 is written into every file it touches: `accept` = the kernel applies the
correction; outcomes are `applied / left_standing / amended_by_human / reverted / escalated`;
the reviewer study became a post-hoc audit; fault injection measures the live path.

| File | Fixes | Real example inside |
| --- | --- | --- |
| `vocabulary.md` | the 4 labels, 3 drift indicators, 5 root causes, verdicts, outcomes | kedro `runner → config` (ADDITIONAL, 623 days); `runner → framework.session` (INVERTED); openedx ADR 0002 (MISSING); kedro HEAD: 7 unassigned packages, one 29-module cycle, hubs by fan-in |
| `rules.schema.yaml` | one compiled rule with provenance | a kedro contract rule; an ADR-derived required rule |
| `ledger.sql` / `ledger.md` | the deviation ledger, the awareness-gap view | — |
| `decision-record.schema.json` | the signed record the kernel executes; `applied_commit` | — |
| `gate.md` | G0–G8 in execution order, apply policy, the hard lines G0 and G7 | kedro Nov 2024: an exception moved, not fixed (reduce, never relocate) |
| `evaluation-protocol.md` | replay rule, metrics, targets, post-hoc audit, amendments | — |
| `fault-injection.md` | 10 injections per subject, what must happen with no human | — |
| `failure-modes.md` | 17 failure modes, detection, mitigation | 9 found in our own runs |
| `pilot-sheet.csv` | the root-cause cases with empty rater columns | drawn with seed 2569 |

**In plain words.** Before building, we wrote the rulebook for ourselves: what each word
means, what "pass" means, how we will score the result. We did it now so that later we can't
quietly move the goalposts, and we recorded a fingerprint of each file to prove it.

> *Where it lives:* `docs/spec/*`; `tools/validate_spec.py` (checks the set, prints the
> protocol hash `b0e2de5c…0065`); `reports/p1-pack.md`.

---

## 7. What else we need to confirm

| Open item | Why it matters | Who / when |
| --- | --- | --- |
| **Criterion 3 — each primary's test suite runs in under 10 minutes** (kedro, checkov, wemake, gt4py) | G3 runs the suite on every draft; a slow suite makes the loop unusable. Not yet measured: `tools/check_tests.sh` needs a laptop with Git Bash/WSL. A failure swaps the primary with reserve 1 (sqlfluff). | team laptop, before Friday 23 Oct |
| **sqlfluff's Python share** (~86% by file size; criterion 5 says ≥ 90%) | decides whether sqlfluff is a reserve or a primary candidate; SQL fixture files may be inflating the non-Python share | `gh api repos/sqlfluff/sqlfluff/languages` on a laptop |
| **Advisor's confirmation** of the selected set, of option C for criterion 4, and of PostHog as a detection-only subject that fails criteria 5–7 | selection is frozen on his nod; the amendments are dated for that | Friday 23 Oct |
| **Labelling starts** on the committed samples | 100 precision cases across 7 repositories (14 per repository, the rest to the largest), 46 post-contract root-cause cases among them — 4 short of 50 because the precision draw is stratified; the protocol allows topping up from PostHog (PostHog included, as RQ3 is detection-side); two raters, independently | Week 2 |
| **Hand-check of the ADR structural flag** on gt4py's 21 | a keyword screen over-selects; the compilable fraction (RQ1) needs a human read first | Week 2, two members independently |
| **Pre-contract vs window** | checkov and sqlfluff were replayed from 2023-06; episodes that start at the window edge are "already there", not introduced then. The paper must say so. | writing, Week 2 |
| **Fault-injection fit** | injections 1–3 need a layers contract; checkov has only forbidden contracts, so it gets substitutes (allowed by the protocol, must be written in the run README) | Week 5 |
| **One import line, many edges** | kedro Jan 2025: one line created 13 violating edges; precision must be sampled by incident, not by edge, or it is inflated | protocol already says so; check when labelling |

---

## 8. Which ones they are referring to — a lookup table

| When the text says… | It means this concrete thing | Open it here |
| --- | --- | --- |
| "the record", "the HEAD record" | the import-linter section of the repository's config at the newest commit, e.g. kedro's `[tool.importlinter]` in `pyproject.toml` with 4 contracts | `data/kedro/record/importlinter.HEAD.toml` |
| "the strict record" | the same, with every `ignore_imports` entry removed (kedro: 6 entries) | `proxy_lint` default; `--keep-ignores` gives the record as written |
| "a contract" | one named rule in that section, e.g. kedro **"Runner et al cannot import Config"** (type forbidden), **"CLI > Context > Library, Runner > Extras > IO & Pipeline"** (type layers), **"Pipeline and IO are independent"** (independence) | `data/kedro/record/contracts.csv` |
| "a violating edge" | one `edge_from → edge_to` pair that breaks a contract, e.g. `kedro.runner → kedro.config` | `data/kedro/violations_sample.parquet`, columns `edge_from`, `edge_to`, `edges` (the actual import lines) |
| "the kedro example" (ADDITIONAL) | `kedro.runner → kedro.config`, introduced 2020-07-16 (9039f82a), gone 2022-03-31 (merge e6cfb423), back 2022-05-09 (7c5b55f7), still open | `data/kedro/episodes.csv` rows 2–3 |
| "the INVERTED example" | `kedro.runner → kedro.framework.session`: runner is a lower layer importing a higher one, 2020-12-17 to 2022-03-31 | `data/kedro/episodes.csv` row 4 |
| "the relocation" (reduce, never relocate) | kedro, Nov 2024: an exception on `parallel_runner` disappeared and a near-identical one on `task` appeared in the same commit — not a repair | `data/kedro/record/events.parquet`, `debt_removed`/`debt_added` same sha |
| "the MISSING example" | openedx-platform ADR 0002 "Inter-app APIs": other apps may reach an app only through its `api.py`; a cross-app import landing on `<app>.models` is a MISSING `→ <app>.api` plus an ADDITIONAL `→ <app>.models` | `docs/spec/vocabulary.md`; `reports/adr-track/openedx-platform.md` |
| "drops", "criterion 4", "C5" | commits where the strict count of violating edges went down with the same contracts in force — our proxy for a human repair | `summary.csv` column `drops` |
| "exception removals" | commits that deleted an `ignore_imports` entry while the contract stayed — the other kind of repair | `summary.csv` column `exception_removal_commits`; `events.parquet` event `debt_removed`, cause `entry_removed` |
| "episodes after the contract / pre-contract" | 28 / 0 for kedro; 1 / 24 for checkov (the 24 were there when the window opened and vanished nine days after the contract) | `episodes.csv` column `pre_contract` |
| "standing at HEAD" | violating edges present at the newest commit under the strict record — kedro 9, faststream 20, ramses_rf 15 | last `idx` in `violations_sample.parquet` |
| "the awareness gap" | per repaired episode, `gap_commits` and `gap_days`; kedro median 92 / 156 | `episodes.csv`; `summary.csv` |
| "contract since / introduced" | the first first-parent commit whose config has an import-linter section with that contract (kedro 2019-08-13, not the file's 2019-05-16) | `contracts.csv` column `introduced_at` |
| "the window" | `--since 2023-06-01` for checkov and sqlfluff: replay starts a month before the first contract | `data/<repo>/timings.csv`, `reports/logs/step1-<repo>.log` |
| "statuses kept / broken / error / package_missing / graph_error" | per commit × contract: rule held / rule broken / the contract names a module that did not exist yet / the package was not in the tree / grimp could not build the graph (e.g. qiskit before its `gateway/` layout) | `checks_sample.parquet` column `status` |
| "the import graph", "the implemented architecture" | grimp's module-level graph of one commit — the thing the contracts are checked on. Not kept by the replay (only its violating edges are); `sarms.graph.extract` writes the whole graph for a commit: `edges.csv` (importer, imported, line number, the import line), `modules.csv` (fan-in/out, package, is_unassigned, cycle id), `packages.csv` + `packages.dot` (package roll-up, drawable with Graphviz), `summary.json` | `data/<repo>/graph/<sha12>/`; kedro HEAD and the 2020 commit 9039f82a are stored |
| "drift indicators on kedro HEAD" | 7 of 12 top-level packages named by no rule (`inspection, ipython, logging, server, utils, validation, __main__`); one 29-module strongly connected component; hubs `framework.project` (16), `utils` (14), `io.core` (14) | `docs/spec/vocabulary.md` § Drift indicators |
| "the ADR track", "structural" | ADR files under a decisions folder at HEAD, dated by the commit that added the file; "structural" = ≥ 2 keyword hits | `data/<repo>/adrs.csv`, `reports/adr-track/<repo>.md` |
| "primaries / reserves / detection-only" | kedro, checkov, wemake, gt4py / sqlfluff, faststream, ramses_rf, qiskit-serverless, airflow, xorq, inspect_evals / PostHog | `docs/repo-selection.md` § Selected |
| "R1–R5" and "C1–C5" | our reduction rules; the team's criteria numbering | `docs/repo-selection.md`; `data/longlist_decisions.csv` column `rule` |
| "the four rules" | push always lands; erosion never left standing; drift allowed for now; everything recorded | proposal Part 1; `docs/spec/gate.md` |
| "point 7" | the 21 Oct design change: no human after the push; the kernel applies | proposal Part 7.4 design note; `evaluation-protocol.md` § Amendments |
| "G0 … G8" | keep the developer's change; fewer violations, none new; no new smells; tests green; mutation floor; protected paths and blast radius; rule link; one-commit revert; clean CI compile | `docs/spec/gate.md` |
| "the samples", "seed 2569" | 100 precision cases (pre-contract allowed) and the post-contract root-cause cases, drawn before anyone looks | `data/samples/precision_100.csv`, `rootcause_50.csv`, `docs/spec/pilot-sheet.csv` |
| "the protocol hash" | SHA-256 of `evaluation-protocol.md` as frozen: `b0e2de5cba4bc9985fe566eccd7d1496e75bca79c4aa14e9ec85f49b3f760065` | `reports/p1-pack.md` |

---

## 9. What changed this week, and why

- **Point 7.** A suggestion the author has to click still sends the developer back to the
  code. The design now has no human in the post-push path; the spec and the proposal say so
  (the slide deck and the interactive page are still to be updated), and the audit moved to
  after the fact.
- **Criterion 4.** Reported, not selected on (option C), with PostHog admitted as a
  detection-only case. Reason: findings 1–3.
- **Tooling, found by running it.** Contract dates come from the config's *content*, not the
  file's first commit (kedro: 3 months apart). The replay uses the strict record. Monorepo
  configs are found and replayed (`--config`, `--src`). Old commits produce `error`, not false
  violations. One reused worktree and grimp's cache make every-commit replay affordable (kedro
  5 min alone, 15 min when sharing two cores). A commit subject with a control character
  (PostHog) split a git-log record; records are NUL-separated now, with a test. The GitHub API
  is unreachable from the build machine, so stars fall back to the team's sheet.

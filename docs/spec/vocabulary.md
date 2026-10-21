# Vocabulary (spec v0, draft for C)

Every label the system or a rater may use, each with a decision rule a program can apply
and one real example from a subject repository. Definitions follow the Week 1–2 runbook;
changes after Friday 23 Oct go through a pull request with a reason.

## Differ labels — one per intended edge per commit

| Label | Decision rule | Counts as | Real example |
| --- | --- | --- | --- |
| CONFIRMED | an edge a rule allows (or requires) is present in the import graph | conformance | kedro: `kedro.framework.session.session → kedro.io.core` (session sits above io in the layers contract; line 28) |
| MISSING | a required edge is absent | erosion if the edge was present at an earlier commit; otherwise a documentation question for the record | import-linter contracts state no required edges; ADRs do. openedx-platform [ADR 0002 "Inter-app APIs"](https://github.com/openedx/openedx-platform/blob/master/docs/decisions/0002-inter-app-apis.rst) (accepted 2019-05-06): "Python clients outside of an app will interface only through declared APIs in api.py" — compiled, every Django app that other apps import must expose `<app>.api`, and every cross-app edge must land on it. An app imported from outside with no `api.py` module, or a cross-app edge that lands on `<app>.models` instead, is the MISSING edge `<client> → <app>.api` (and the latter also an ADDITIONAL `<client> → <app>.models`) |
| ADDITIONAL | an edge is present that a forbidden or layers rule disallows, including indirect chains, as import-linter counts them | erosion | kedro: `kedro.runner → kedro.config` under "Runner et al cannot import Config": introduced 16 Jul 2020 by [9039f82a](https://github.com/kedro-org/kedro/commit/9039f82a31c5826672758d19d00d14feb9349e8c) (which also listed it as an exception), gone 31 Mar 2022 with the merge [e6cfb423](https://github.com/kedro-org/kedro/commit/e6cfb42373398bef2dc0c19d24e62373e34780e3), back on 9 May 2022 ([7c5b55f7](https://github.com/kedro-org/kedro/commit/7c5b55f7edbfa57b48014f89b93a2cc9cf1ba8c6)), still open |
| INVERTED | under a layers rule an edge points from a lower layer to a higher one; or where A→B is required, B→A exists instead | erosion | kedro: `kedro.runner → kedro.framework.session` (runner sits below framework.session): 17 Dec 2020, merge [1bb5f4be](https://github.com/kedro-org/kedro/commit/1bb5f4be6fc4e6ef7a5a9480131cbce4582385c9), to 31 Mar 2022, merge [e6cfb423](https://github.com/kedro-org/kedro/commit/e6cfb42373398bef2dc0c19d24e62373e34780e3) |

Mapping from import-linter contract types (used by the rule compiler in Week 2):

| Contract type | Produces |
| --- | --- |
| layers | lower → higher import = INVERTED; import between independent siblings (`a \| b`) = ADDITIONAL |
| forbidden | source → forbidden import = ADDITIONAL |
| independence | import between any two listed modules = ADDITIONAL |
| protected | import of a protected module from outside the allow-list = ADDITIONAL |
| acyclic_siblings | the edge that closes a cycle between siblings = ADDITIONAL |

An edge listed in `ignore_imports` is still labelled, with `acknowledged = true`, so known
exceptions are counted apart from unacknowledged violations.

## Drift indicators — no rule broken

Initial thresholds; calibrated in Week 3 on the subject repositories. Examples computed on 21 Oct 2026 with grimp 3.17 on kedro's default branch at 738830bb; the full graph is stored by `sarms.graph.extract` under `data/kedro/graph/738830bbf026/` (edges, modules, packages, summary.json).

| Indicator | Definition | Initial threshold | Real example |
| --- | --- | --- | --- |
| Unassigned module | a top-level module matched by no layer and no rule | count per commit; any increase is reported | kedro HEAD (21 Oct 2026, grimp): 7 of 12 top-level packages are named by no layer or rule — `inspection`, `ipython`, `logging`, `server`, `utils`, `validation`, `__main__`; the contracts name only `config`, `framework.*`, `io`, `pipeline`, `runner` |
| New cycle | a strongly connected component of ≥ 2 modules absent at the parent commit (`networkx.strongly_connected_components` on the module graph) | any | kedro HEAD (738830bb) has one SCC of 29 modules spanning `kedro.framework.{cli,context,hooks,project,session,startup}`, `kedro.runner.*`, `kedro.pipeline`, `kedro.validation.*` and `kedro.ipython`; at package level the cycle joins 9 of 12 packages. No rule forbids it, so it is drift, not erosion — and the kind the weekly tick is for. The first commit that closed it is found in Week 2 by walking the replay |
| Hub fan-in growth | a module whose in-degree grows by ≥ 3 edges and ≥ 20% within a 4-week window | reported on the weekly tick | kedro HEAD hubs by fan-in: `kedro.framework.project` 16, `kedro.utils` 14, `kedro.io.core` 14, `kedro.framework.startup` 12; the growth series comes from the Week 3 per-commit graphs |

## Root-cause labels — one per deviation (Synthesize, and independently two raters)

Apply in this order; the first that fits wins, then the tie-break below.

| Label | Evidence that selects it | Action |
| --- | --- | --- |
| requirement realization | the PR or issue describes a new capability and no conforming path exists under the current rules | decision record with options to the architects; never forced back |
| documentation lag | the code is right and the record is stale: the PR text says the rule or the module moved, or the same pattern already exists in ≥ 3 other places | ADR amendment + rule update, committed by the system with the author named in the log entry |
| implementation choice | the rule stands and a conforming path exists (an allowed layer, a port or adapter the ADR prescribes) | conforming version of the author's change |
| behavioral defect | the deviation co-occurs with failing tests or a linked bug report | escalate this term (Generation loop in Term 2) |
| mixed | evidence for two of the above | escalate with both halves |

Tie-break: any evidence for requirement realization wins; between documentation lag and
implementation choice, choose implementation choice unless the text evidence for a stale
record is explicit.

How a rater applies it: read the introducing commit, its PR and the contract or ADR text;
pick the first label that fits; write one sentence of evidence with a link. A case the rater
cannot decide is labelled mixed, never skipped.

## Outcomes and verdicts

- Verdict (gate): accept (the kernel applies the verified correction as its own commit; no human
  is asked — point 7), escalate, defer, reject.
- Outcome (ledger): none, applied, left_standing, amended_by_human, reverted, escalated.
  `left_standing` is set when the applied commit survives the watch window (default 30 days)
  untouched; `amended_by_human` / `reverted` when a later human commit edits or undoes it.
- System correction: a first-parent commit authored by the system that applies a verified
  draft; always one commit, always revertable (G7).
- Human repair: a first-parent commit, not by the system, after which a violating edge is
  absent while its contract can still be checked.

# Onboarding repositories without references (proposal, 28 Oct 2026)

Status: proposal for the team and the advisor. Nothing here changes the spec until it goes
through a pull request with a reason. An earlier draft lives in the team's Claude Doc
([link](https://claude.ai/artifact/BnsVKK2hSDvQT5X2Vxkvsm)). This file supersedes it.

## 1. Summary

sarms only works where the architecture is written down. We propose an **onboarding mode** for
repositories that have no contracts and no ADRs. sarms mines the repository's history and
proposes a reference: a layer order, binding invariants and a list of exceptions. Developers and
architects confirm it, and their answers become ordinary rule files. People are involved only
until the reference covers the dependencies the code actually uses. After that, the repository
is a normal sarms subject and the autonomous loop applies.

The plan is to build the whole loop this term (Term 1), on repositories with written rules, and
to dedicate Term 2 to onboarding. Term 2 already plans a CI job and a live pilot with consenting
maintainers, which is exactly what onboarding needs.

## 2. Why: sarms needs recorded intent

Selection criterion 1 requires at least two import-linter contracts or at least ten ADRs. Gate
lines G1 and G6 check every repair against those rules. Without them, sarms has nothing to
detect violations of and nothing to verify a repair against.

On 27 October 2026 we tested whether rules recovered from the import graph alone could replace
written ones. We hid the contracts of nine repositories, recovered rules from their graphs, and
compared the two. "Forbid everything" is the baseline that forbids every import between
components; its precision is the share of the contracts' verdicts that are "forbidden".

| Repository | Forbid everything: precision | Layer order: precision | Layer order: recall |
| --- | --- | --- | --- |
| kedro | 0.57 | 0.93 | 0.81 |
| openedx-platform | 0.58 | 0.80 | 0.69 |
| wemake-python-styleguide | 0.60 | 0.90 | 0.75 |
| sqlfluff | 0.74 | 0.99 | 0.94 |
| ramses_rf | 0.50 | 0.80 | 0.80 |

The other four repositories are not informative: checkov, qiskit-serverless and faststream have
only "forbidden" verdicts, and PostHog is excluded because of a scorer bug.

Recovered rules are good drafts and poor judges:

- The pairs above are only 4 to 38% of what the recovered rules forbid in most repositories.
  Nobody has judged the rest.
- On imports that actually appeared over history, the best method was right on 6 of the 9
  alarms we could judge. The history-based methods were right on about one in four.
- Adopted as is, the layer order would flag 5 to 24 existing imports per repository for
  automatic repair, most of which no contract forbids.

**Why people are needed, in one example.** kedro's push of 15 January 2025, "Add support for
%load_ext kedro" (#4406), added one line: `import kedro.ipython` at line 42 of
`kedro/__init__.py`. Before the push, kedro had three dependency cycles of two modules each.
After it, one cycle spanned 29 modules, and removing that line alone breaks it up again. A
before/after comparison of the import graph finds this in seconds, with no rules at all. But the
same push recorded the import as an exception in kedro's contracts. The maintainers made the
structure worse on purpose, to ship a feature. Only a person could say that.

## 3. The idea: people build the reference, then step back

sarms does the mining and proposing. Developers and architects answer questions about what it
found. Their answers become written rules.

| Reference | Mined from | Confirmed by | Example |
| --- | --- | --- | --- |
| Layer order | trophic levels or a feedback-arc order of the import graph | an architect, once | kedro: the framework packages sit above runner, which sits above io |
| Binding invariants | general design principles, checked against the parent commit | an architect, once, as policy | no new dependency cycle between top-level packages |
| Recorded exceptions | deliberate departures, at the push that makes them | the developer who made the push | kedro's `kedro -> kedro.ipython`, recorded in the same push that added it |

Nothing mined is enforced until a person has confirmed it.

## 4. The four phases

| Phase | Who is involved | What happens | Gate to the next phase |
| --- | --- | --- | --- |
| 1. Mine | no people | sarms builds import graphs over the history and proposes a layer order, binding invariants and a decay report | proposals ready |
| 2. Confirm | architects, once | they review the proposed rules one by one, with the evidence for each; existing imports that break a proposed rule become questions, not repairs | rules committed |
| 3. Ask | developers, per new crossing | each first-time import between two components asks its author whether the direction is allowed; answers become rules or recorded exceptions; sarms reports and never repairs unconfirmed rules | exit criterion met |
| 4. Autonomous | no one per push | confirmed rules run the normal loop: detect, draft, gate G0 to G8, apply; post-hoc audit as today | none; a new uncovered crossing goes back to phase 3 |

Violations of rules that are already confirmed never wait for anyone, in any phase.

**Exit criterion, draft:** no new question for four consecutive weeks, and every pair of
components that import each other is covered by a confirmed rule. The team sets the final value.

## 5. How the questions work inside the system

People answer where they already work, in the pull request. Every answer is stored as a rule file
in the repository, so it is versioned and reviewed like code.

**Phase 2 is a pull request from sarms.** sarms opens one onboarding pull request with the
proposed rules as files and an evidence report per rule: which imports support it and which go
against it. Architects review it like any pull request, edit rules inline, delete wrong ones and
comment. Merging it is the "rules committed" gate.

**Phase 3 is a comment on the import line.** On every push, the Differ already knows which import
edges no rule covers. When a push adds the first import from one component to another, sarms
comments on that line. The evidence numbers below are illustrative:

```
sarms · onboarding question
kedro/io/core.py:12 adds the first import from kedro.io to kedro.framework.session.
No confirmed rule covers this direction.
Evidence: 0 imports this way so far, 6 the other way.
Proposed: forbidden, because io sits below framework.session in the mined layer order.

Reply with one of:
  /sarms allow       this direction is fine from now on
  /sarms forbid      this direction is wrong
  /sarms exception   only this import is fine; give a reason
```

**Each answer becomes a rule commit.** sarms commits a rule to `.rms/rules/` on the pull
request's branch, with the source marked as confirmed, who confirmed it and when.

- `allow` writes an allowed rule.
- `forbid` writes a forbidden rule, and the author fixes their own import before merging.
- `exception` writes an exception entry with the reason, as import-linter's `ignore_imports` does.

**Architects keep oversight through the code-owners file.** The rules folder is protected the same
way `.rms/policy.yaml` is. A pull request that adds a rule cannot merge without an architect's
approval, so developers answer and architects approve, with no new tool to learn.

**Further rules:**

- Each pair is asked once. The answer covers every future import in that direction.
- Questions never block merging (loop rule 1: the push always lands). The check shows as needing
  attention, not failed.
- Unanswered questions roll into a weekly digest issue for the architects, on the weekly tick the
  spec already has for drift.
- Every question and answer goes into the ledger. Author identities are salted hashes, as in the
  mining.
- The hand-over is a pull request too. When the exit criterion is met, sarms opens a pull request
  that switches the policy file from onboarding to autonomous, and an architect merges it.
- Repositories not hosted on GitHub fall back to a question file in the repository that people
  edit.

## 6. Fit with the MSV-K loop

Onboarding is the same loop, started with an empty Knowledge base that people's answers fill.

| Loop part | Its job today | During onboarding |
| --- | --- | --- |
| Monitor | builds the graph and labels edges against rules, with no model | unchanged; also lists uncovered edges and mines the proposals, still with no model |
| Synthesize | the LLM writes the root cause and the draft | mostly idle, since questions come from a template; it runs only if we later let it read README text to propose rules |
| Verify | gate G0 to G8 on every draft | checks each rule commit as it checks a record amendment |
| Knowledge | rules, ledger, decision records, policy under `.rms/` | starts empty; every answer becomes a rule and every question a ledger row |
| Kernel | routes events and executes only decision records | each answer becomes a decision record of class `record_amendment`, and the kernel commits the rule |

The spec already has the slot for answers. The draft class `record_amendment` exists for when the
record rather than the code lagged. Gate line G5 already lets that class touch the contract files,
within its cap of 3 files and 120 lines.

**The four loop rules still hold.**

1. The push always lands: questions never block merging.
2. Erosion is never left standing: without a rule there is no erosion; once an answer confirms a
   rule, its violations take the normal correction path.
3. Drift is allowed for now: uncovered edges are drift; sarms asks about each one instead of only
   trending them.
4. Everything is recorded: questions and answers go into the ledger.

**In the code, the layering contract gets one sibling.** sarms's own `.importlinter` orders the
layers kernel, verify, synthesize, differ. A new `sarms.onboard` sits beside synthesize
(`sarms.synthesize | sarms.onboard`), with a forbidden contract like the two that keep the model
out of the Differ and the gate, so question generation stays deterministic.

**Spec amendments needed,** each through a pull request with a reason:

- `rules.schema.yaml`: an `invariant` source type, and fields for who confirmed a rule and when.
- `ledger.md`: the question and answer records.
- `gate.md`: G1 and G6 may name a binding invariant instead of a rule. G8 ("contracts compile and
  pass in a clean CI run") needs wording for a rule commit that forbids a direction existing code
  already uses; such a commit carries those imports as recorded exceptions.
- Point 7: a clarification that it covers corrections, not onboarding questions.
- The kernel: a second event type, an answer on a pull request, beside a landed push.

## 7. Evaluation

**Simulation, no people needed.** On the nine contract repositories, we hide the contracts and
let them play the maintainer:

1. Mine proposals from the history before the first contract was written.
2. Answer every question from the hidden contracts: "allowed", "forbidden", or "no rule" where
   they are silent.
3. Replay the history forward, with the answers accumulating.

| Measure | Definition |
| --- | --- |
| Effort | questions asked until the exit criterion is met, per repository and per 100 commits |
| Quality | agreement of the final confirmed reference with the hidden contracts |
| Detection | violations caught after the exit point, compared with the contracts' violation episodes |
| Noise | false alarms after the exit point |

The simulated maintainer is perfect and consistent, so these are best-case numbers.

**Real study, in the Term 2 pilot.** The pilot's maintainers answer the questions for their
repository. We record their time and how often they disagree with the proposal.

## 8. Timeline

| Term | Focus | Outcome |
| --- | --- | --- |
| Term 1 | the full loop on repositories with written rules: rule compiler, Differ, ledger, Synthesize, gate, kernel; labelling; fault injection | RQ1 to RQ3 answered; the paper states the limitation, with the 27 October measurement as evidence |
| Term 2 | the CI job, the live pilot, onboarding | onboarding evaluated by simulation, then with the pilot's maintainers |

Term 2 already holds two related plans. The Steps 1-2 report says the kernel becomes "a job in the
repository's own CI" in Term 2, which is where onboarding questions appear. `docs/ethics.md` plans
a Term 2 live pilot on a repository "whose maintainers agree in writing", which supplies the
people. Term 2 also holds the Generation loop for behavioral defects (`vocabulary.md`), so the team
must decide how the two share the term.

**Cheap things to do in Term 1 so Term 2 starts unblocked:**

- Have the Differ output uncovered edges, the imports no rule speaks about.
- Commit the four scoring scripts and fix their two known bugs: PostHog's exception lists, and
  each layer pair being counted twice.
- Start recruiting the pilot repository early, and ask about onboarding questions in the same
  request.
- Amend `docs/ethics.md` so the consent wording covers developers who answer questions.

**One Term 1 risk to watch: the ADR track is not solid yet.** The contract repositories are
selected and replayed, and their baselines exist. The ADR repositories are not at that point:

- The rule compiler does not exist yet, and whether ADR sentences compile into import rules at
  all is RQ1's "compilable fraction". That is a research result still to be found, not only code
  to write.
- gt4py's 51 ADRs have 21 flagged structural by a keyword screen, which over-selects. The
  hand-check by two members is still pending.
- Judging by titles alone, many of airflow's 35 flagged ADRs are about Docker images, installers
  or the Go, Java and TypeScript SDKs, not Python import structure.
- No ADR repository has a replay, episodes or an awareness-gap baseline, because those need
  compiled rules.
- gt4py's ADRs all date from a 2025-04-11 folder move, so when each decision was made is lost.

## 9. Risks and limits

| Risk | What could go wrong | Mitigation |
| --- | --- | --- |
| Anchoring | architects accept the proposal as shown, mistakes included | show the evidence per rule and ask for confirmation rule by rule, never a blanket accept |
| Question fatigue | developers stop answering if asked too often | ask only on first-time crossings between components, never twice about the same pair; kedro gained about 70 such imports over six years of sampled history, roughly ten a year |
| Deliberate restructuring | during a planned reorganisation, mined rules describe the old structure | pause questions and invariants while a reorganisation is declared in the policy file |
| Unjudged pairs | most mined rules cover pairs nobody has ruled on | they stay proposals until someone answers; only confirmed rules are enforced |
| Biased evidence | our nine repositories enforce contracts in CI, so their layering is cleaner than typical | report it as a threat; the simulation gives best-case numbers |
| Unminable rules | rules on external packages or custom contract types cannot come from the internal import graph | state the scope: internal layering and dependency rules only |

## 10. Decisions for the team

- [ ] Onboarding as RQ4 in Term 2, or discussion plus future work only?
- [ ] How onboarding and the Generation loop share Term 2.
- [ ] Exit criterion (draft in section 4).
- [ ] Default binding invariants. Draft: only "no new dependency cycle between top-level packages".
- [ ] Who may answer a question: only the pull request's author, or any code owner.
- [ ] Who files the spec amendments in section 6, and by when.

## References

- [Maffort et al., Mining Architectural Violations from Version History](https://www.llp.dcc.ufmg.br/Publications/Journal2016/2015_emse.pdf), Empirical Software Engineering 2016. Rule-free violation mining, 54 to 63% precision.
- [MacKay, Johnson and Sansom, How Directed Is a Directed Network?](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7540772/), Royal Society Open Science 2020. The trophic levels behind the proposed layer order.
- [Engler et al., Bugs as Deviant Behavior](https://www.sosp.org/2001/papers/yu-chen.pdf), SOSP 2001. Rules inferred from what most code does.
- [Savarimuthu et al., Identifying Prohibition Norms in Agent Societies](https://ourarchive.otago.ac.nz/esploro/outputs/journalArticle/Identifying-prohibition-norms-in-agent-societies/9926516664201891), Artificial Intelligence and Law 2013. Rules learned from observed decisions.
- [Xiao et al., Identifying and Quantifying Architectural Debt](https://personal.stevens.edu/~lxiao6/papers/ICSE-16-Debt.pdf), ICSE 2016. Smells as a risk signal when no rules exist.
- [Resende, Durelli and Terra, ArchLintor](https://sol.sbc.org.br/index.php/sbes/article/view/37076), SBES 2025. A rules-first checker for TypeScript, which still needs written rules.

Our own material: `tools/score_recovery.py`, `tools/replay_recovery.py`, `tools/sample_graphs.py`
and `tools/alert_precision.py` (uncommitted); results in `data/<repo>/recovery/` (not in git);
the kedro cycle example in `data/kedro/graph/1ed504cf5206/`.

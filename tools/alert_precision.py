"""False alarms as a developer would see them: recovered rules checked against the imports that
actually appeared over the history, not against every possible pair.

    uv run python tools/alert_precision.py REPO [REPO ...]

Walks the sampled graphs of data/REPO/graph/ in history order (tools/sample_graphs.py). At each
step it recovers rules from the earlier graph alone (and, for the history methods, every graph
before it), takes the unit edges that are new in the next graph, and asks each method whether it
would have raised an alert. Every new edge is then judged by the written HEAD contracts:
  violation  the contracts forbid the unit pair            -> an alert here is a true alarm
  allowed    the contracts allow it (a permitted layer direction, an acknowledged exception)
                                                            -> an alert here is a false alarm
  silent     the contracts say nothing about the pair       -> unknown; reported apart
  new unit   one side did not exist before                  -> no rule could cover it; reported apart
Only steps after the first contract was written count. Units: the contract scheme of
tools/score_recovery.py. Writes data/REPO/recovery/alerts.json.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from score_recovery import (  # noqa: E402
    compile_contracts,
    decide,
    load_graph,
    load_record,
    project,
    roots_of,
    unit_graph,
    units_contract,
)

METHODS = ["observed", "trophic", "fas", "both", "never", "removed"]


def main():
    out_all = {}
    for name in sys.argv[1:]:
        data = Path("data") / name
        opts = load_record(data)
        roots = roots_of(opts)
        commits = pd.read_parquet(data / "commits.parquet", columns=["idx", "sha"])
        idx_of = dict(zip(commits.sha, commits.idx, strict=True))
        cc = pd.read_csv(data / "record" / "contracts.csv")
        first_contract = min((idx_of[s] for s in cc.introduced_sha if s in idx_of), default=0)
        graphs = []
        for p in (data / "graph").iterdir():
            if (p / "summary.json").exists():
                sha = json.loads((p / "summary.json").read_text())["sha"]
                if sha in idx_of:
                    graphs.append((idx_of[sha], p))
        graphs.sort()
        seen_before = set()
        prev = None
        steps = 0
        truth_count = Counter()
        alerts = {m: Counter() for m in METHODS}
        examples = {m: [] for m in METHODS}
        for idx, p in graphs:
            modules, edges, sha = load_graph(p)
            contracts, named, _, _ = compile_contracts(opts, modules)
            unit = units_contract(named, modules, roots)
            units = sorted(set(unit.values()))
            W = unit_graph(unit, edges)
            if prev is not None and idx >= first_contract:
                p_units, p_W, p_seen = prev
                D, _, _, _ = decide(p_units, p_W, 0.0, p_seen)
                truth, _ = project(contracts, units)
                pu = set(p_units)
                steps += 1
                for pair in W:
                    if pair in p_W:
                        continue
                    U, V = pair
                    if U not in pu or V not in pu:
                        kind = "new unit"
                    else:
                        kind = {"forbidden": "violation", "allowed": "allowed"}.get(truth.get(pair), "silent")
                    truth_count[kind] += 1
                    for m in METHODS:
                        if kind != "new unit" and D[m].get(pair) == "forbidden":
                            alerts[m][kind] += 1
                            if kind == "allowed" and len(examples[m]) < 6:
                                examples[m].append(f"{U} -> {V} @ {sha[:8]}")
            if prev is not None:
                seen_before |= set(prev[1])
            prev = (units, W, set(seen_before))
        res = {"repo": name, "graphs": len(graphs), "steps_after_contract": steps, "new_edges": dict(truth_count), "methods": {}}
        print(f"\n{name}: {len(graphs)} sampled graphs, {steps} steps after the first contract; new unit edges: {dict(truth_count)}")
        print(f"  {'method':9s} {'alerts':>6s} {'true':>5s} {'false':>5s} {'silent':>6s}  {'alarm precision':>15s}  {'violations caught':>17s}")
        for m in METHODS:
            a = alerts[m]
            t, f, s = a["violation"], a["allowed"], a["silent"]
            prec = t / (t + f) if t + f else float("nan")
            caught = f"{t} of {truth_count['violation']}"
            res["methods"][m] = {"alerts": t + f + s, "true": t, "false": f, "silent": s, "alarm_precision": prec, "false_examples": examples[m]}
            print(f"  {m:9s} {t + f + s:6d} {t:5d} {f:5d} {s:6d}  {prec:15.2f}  {caught:>17s}")
        (data / "recovery").mkdir(parents=True, exist_ok=True)
        (data / "recovery" / "alerts.json").write_text(json.dumps(res, indent=1, default=float))
        out_all[name] = res


if __name__ == "__main__":
    main()

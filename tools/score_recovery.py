"""Rule recovery scored against the written contracts: hide a repository's import-linter contracts,
recover rules from its import graph alone, and compare them with what the maintainers wrote.

    uv run python tools/score_recovery.py REPO                                  # HEAD graph, static methods
    uv run python tools/score_recovery.py REPO --history "data/REPO/graph/*"    # adds the history methods
    uv run python tools/score_recovery.py REPO --graph data/REPO/graph/<sha12>  # another commit's graph

Writes data/REPO/recovery/static.json (every number) and prints the summary table.

Ground truth: the contracts of data/REPO/record/importlinter.HEAD.*, compiled to one verdict per
ordered pair of units — forbidden, allowed (the permitted direction of a layers contract), or
unconstrained. A forbidden pair whose whole unit pair is whitelisted by an ignore_imports
expression counts as allowed (acknowledged). Contracts on external packages and contract types
other than layers / forbidden / independence are reported as unscorable.

Units (the rules are recovered between units; the written rules are projected onto them):
  contract  the modules the contracts name, plus each root's depth-2 packages for the rest.
            ArchLint's assumption (Maffort et al. 2016): the components are known, the rules are not.
  auto      each root's depth-2 packages, a package holding >= 25% of its root's modules split one
            level. No knowledge of the contracts at all.

Methods (each decides forbidden / allowed / abstain per ordered unit pair, from the graph alone):
  forbid_all  baseline: everything is forbidden (precision = the base rate)
  trophic     MacKay, Johnson & Sansom 2020: a level per unit from the import graph; importing a
              unit with a higher level is forbidden. --margin abstains on near-equal levels.
  fas         Eades, Lin & Smyth 1993: a greedy feedback-arc-set order; importing against it is forbidden
  observed    drift / Engler et al. 2001: a pair with no module edge at this commit is forbidden
  majority    Maffort et al. 2016, heuristic #3: of two units importing each other, the minority
              direction is forbidden; one direction only: the reverse is forbidden; neither: abstain
  both        trophic and observed agree, else abstain
  removed     (--history) had a module edge at an earlier sampled commit and has none now: forbidden;
              has one now: allowed; never seen: abstain          (ArchLint's deletion signal)
  never       (--history) no module edge at any sampled commit: forbidden; has one now: allowed
"""
from __future__ import annotations

import argparse
import glob
import json
import re
import sys
from collections import defaultdict
from itertools import permutations
from pathlib import Path

import numpy as np
import pandas as pd

from sarms.mining.common import as_list, read_il_options

SPLIT_SHARE = 0.25
METHODS = ["forbid_all", "trophic", "fas", "observed", "majority", "both"]
HISTORY_METHODS = ["removed", "never"]


# ----------------------------------------------------------------------------- inputs
def load_record(data_dir: Path):
    rec = data_dir / "record"
    f = next(p for p in sorted(rec.iterdir()) if p.name.startswith("importlinter.HEAD"))
    opts = read_il_options("x" + f.suffix, f.read_text(encoding="utf-8", errors="replace"))
    if opts is None:
        sys.exit(f"cannot parse {f}")
    return opts


def roots_of(opts):
    so = opts.session_options
    return [r for r in (as_list(so.get("root_packages")) or [so.get("root_package")]) if r]


def load_graph(gdir: Path):
    """(modules: set, module_edges: set of (importer, imported), sha)"""
    e = pd.read_csv(gdir / "edges.csv")
    m = pd.read_csv(gdir / "modules.csv")
    sha = json.loads((gdir / "summary.json").read_text())["sha"]
    return set(m.module), set(e[["importer", "imported"]].drop_duplicates().itertuples(index=False, name=None)), sha


# ----------------------------------------------------------------------------- module expressions
def expr_regex(expr: str) -> re.Pattern:
    return re.compile("^" + re.escape(expr.strip()).replace(r"\*\*", ".*").replace(r"\*", r"[^.]+") + "$")


def expand(expr: str, modules: set) -> list[str]:
    """Modules of the graph matching an import-linter module expression (* one level, ** any depth).
    A plain name is kept when it is a module or a package of the graph."""
    expr = expr.strip()
    if not expr:
        return []
    if "*" not in expr:
        return [expr] if (expr in modules or any(m.startswith(expr + ".") for m in modules)) else []
    rx = expr_regex(expr)
    return sorted(m for m in modules if rx.match(m))


def covers(name: str, unit: str) -> bool:
    """The named module is the unit or an ancestor of it."""
    return name == unit or unit.startswith(name + ".")


# ----------------------------------------------------------------------------- the written rules
def compile_contracts(opts, modules: set):
    """-> contracts: [{name, type, verdicts: {(a,b): 'forbidden'|'allowed'}, ignores: [(rxA, rxB)]}],
          named: set of module names the contracts name, layer_orders: [(contract, [[names]...])],
          unscorable: [(contract, item, why)]"""
    contracts, named, layer_orders, unscorable = [], set(), [], []
    for c in opts.contracts_options:
        t, name = c.get("type"), c.get("name", "?")
        verdicts = {}

        def forbid(a, b, verdicts=verdicts):  # a nested pair (posthog: presentation -> its own backend) is kept; project() drops U == V
            if a != b:
                verdicts[(a, b)] = "forbidden"

        def allow(a, b, verdicts=verdicts):
            if a != b:
                verdicts.setdefault((a, b), "allowed")

        if t == "layers":
            containers = as_list(c.get("containers")) or [""]
            for pre in containers:
                groups = []
                for layer in as_list(c.get("layers")):
                    group = []
                    for part in str(layer).split("|"):
                        full = part.strip().strip("()").strip()
                        full = f"{pre}.{full}" if pre else full
                        ex = expand(full, modules)
                        if not ex:
                            unscorable.append((name, full, "layer not in the graph"))
                        group += ex
                    groups.append(group)
                for i in range(len(groups)):
                    for a, b in permutations(groups[i], 2):
                        forbid(a, b)  # independent siblings on one level
                    for j in range(i + 1, len(groups)):
                        for a in groups[i]:
                            for b in groups[j]:
                                forbid(b, a)
                                allow(a, b)
                named.update(n for g in groups for n in g)
                layer_orders.append((name, [g for g in groups if g]))
        elif t == "forbidden":
            srcs = [m for s in as_list(c.get("source_modules")) for m in expand(s, modules)]
            tgts = []
            for f in as_list(c.get("forbidden_modules")):
                ex = expand(f, modules)
                if ex:
                    tgts += ex
                elif f.strip():
                    unscorable.append((name, f, "forbidden module not in the graph (external?)"))
            for s in srcs:
                for f in tgts:
                    forbid(s, f)
            named.update(srcs + tgts)
        elif t == "independence":
            mods = [m for s in as_list(c.get("modules")) for m in expand(s, modules)]
            for a, b in permutations(mods, 2):
                forbid(a, b)
            named.update(mods)
        else:
            unscorable.append((name, t, "contract type not compiled"))
            continue
        ignores = []
        for ig in as_list(c.get("ignore_imports")):
            ig = ig.split("#")[0].strip().strip('"').strip("'").rstrip(",")
            if "->" in ig:
                a, b = (x.strip() for x in ig.split("->", 1))
                ignores.append((expr_regex(a), expr_regex(b), ig))
        contracts.append({"name": name, "type": t, "verdicts": verdicts, "ignores": ignores})
    return contracts, named, layer_orders, unscorable


def project(contracts, units: list[str]):
    """Written verdicts projected onto ordered unit pairs; forbidden > allowed. A pair takes a verdict
    only from a named pair at least as coarse as the units (finer contracts are below the units'
    granularity). A pair whitelisted wholesale by an ignore_imports expression is allowed for that
    contract. -> (truth: {(U,V): verdict}, n_below_granularity)"""
    truth = {}
    below = 0
    uset = set(units)
    for c in contracts:
        own = {}
        for (a, b), v in c["verdicts"].items():
            ua = [u for u in uset if covers(a, u)]
            ub = [u for u in uset if covers(b, u)]
            if not ua or not ub:
                below += 1
                continue
            for U in ua:
                for V in ub:
                    if U == V:
                        continue
                    if v == "forbidden" or (U, V) not in own:
                        own[(U, V)] = v
        for (U, V), v in own.items():
            if v == "forbidden" and any(ra.match(U + ".x") and rb.match(V + ".x") for ra, rb, _ in c["ignores"]):
                v = "allowed"
            if v == "forbidden" or (U, V) not in truth:
                truth[(U, V)] = v
    return truth, below


# ----------------------------------------------------------------------------- units
def depth2(m: str, roots: list[str]) -> str:
    for r in sorted(roots, key=len, reverse=True):
        if m == r:
            return r
        if m.startswith(r + "."):
            rest = m[len(r) + 1:].split(".")
            return f"{r}.{rest[0]}"
    return m.split(".")[0]


def units_contract(named: set, modules: set, roots: list[str]):
    """unit(m) = the longest named module that is m or an ancestor of m, else its depth-2 package."""
    names = sorted(named, key=len, reverse=True)
    unit = {}
    for m in modules:
        for n in names:
            if covers(n, m):
                unit[m] = n
                break
        else:
            unit[m] = depth2(m, roots)
    return unit


def units_auto(modules: set, roots: list[str]):
    """Depth-2 packages per root; a package with >= SPLIT_SHARE of its root's modules is split one level."""
    unit = {m: depth2(m, roots) for m in modules}
    per_root = defaultdict(int)
    per_unit = defaultdict(int)
    for u in unit.values():
        per_root[u.split(".")[0]] += 1
        per_unit[u] += 1
    split = {u for u, n in per_unit.items() if "." in u and n >= SPLIT_SHARE * per_root[u.split(".")[0]]}
    for m in modules:
        u = unit[m]
        if u in split and m != u and m.startswith(u + "."):
            rest = m[len(u) + 1:].split(".")
            unit[m] = f"{u}.{rest[0]}"
    return unit, sorted(split)


def unit_graph(unit: dict, module_edges: set):
    W = defaultdict(int)
    for a, b in module_edges:
        if a in unit and b in unit and unit[a] != unit[b]:
            W[(unit[a], unit[b])] += 1
    return dict(W)


# ----------------------------------------------------------------------------- recovery methods
def trophic_levels(units: list[str], W: dict):
    """MacKay, Johnson & Sansom 2020, eq. (2.4)-(2.7): Lambda h = v, flow runs imported -> importer,
    so a unit imported by many sits low and one that imports many sits high. Returns (levels, F0)."""
    ix = {u: i for i, u in enumerate(units)}
    n = len(units)
    A = np.zeros((n, n))
    for (a, b), w in W.items():  # importer a, imported b: flow b -> a
        A[ix[b], ix[a]] += w
    if A.sum() == 0:
        return dict.fromkeys(units, 0.0), float("nan")
    win, wout = A.sum(0), A.sum(1)
    lam = np.diag(win + wout) - A - A.T
    h = np.linalg.pinv(lam) @ (win - wout)
    h -= h.min()
    F0 = float((A * (h[None, :] - h[:, None] - 1) ** 2).sum() / A.sum())
    return dict(zip(units, map(float, h), strict=True)), F0


def fas_order(units: list[str], W: dict):
    """Eades, Lin & Smyth 1993 greedy: sinks to the back, sources to the front, else the node with the
    largest out-minus-in weight to the front. Importers come first; an import against the order is
    a back edge. Returns {unit: position}, 0 = highest."""
    out, inn = defaultdict(dict), defaultdict(dict)
    for (a, b), w in W.items():
        out[a][b] = w
        inn[b][a] = w
    left, right, alive = [], [], set(units)
    while alive:
        sinks = [u for u in alive if not any(v in alive for v in out[u])]
        if sinks:
            for u in sorted(sinks):
                right.append(u)
                alive.discard(u)
            continue
        sources = [u for u in alive if not any(v in alive for v in inn[u])]
        if sources:
            for u in sorted(sources):
                left.append(u)
                alive.discard(u)
            continue
        u = max(sorted(alive), key=lambda x: sum(w for v, w in out[x].items() if v in alive) - sum(w for v, w in inn[x].items() if v in alive))
        left.append(u)
        alive.discard(u)
    order = left + right[::-1]
    return {u: i for i, u in enumerate(order)}


def decide(units: list[str], W: dict, margin: float = 0.0, seen_before: set | None = None):
    """-> decisions {method: {(U,V): 'forbidden'|'allowed'|None}}, levels, fas positions, F0"""
    levels, F0 = trophic_levels(units, W)
    pos = fas_order(units, W)
    D = {m: {} for m in METHODS + (HISTORY_METHODS if seen_before is not None else [])}
    for U, V in permutations(units, 2):
        w, back = W.get((U, V), 0), W.get((V, U), 0)
        D["forbid_all"][(U, V)] = "forbidden"
        d = levels[V] - levels[U]
        D["trophic"][(U, V)] = "forbidden" if d > margin else ("allowed" if d < -margin else None)
        D["fas"][(U, V)] = "forbidden" if pos[V] < pos[U] else "allowed"
        D["observed"][(U, V)] = "forbidden" if w == 0 else "allowed"
        if w and back:
            D["majority"][(U, V)] = "forbidden" if w < back else ("allowed" if w > back else None)
        elif w:
            D["majority"][(U, V)] = "allowed"
        elif back:
            D["majority"][(U, V)] = "forbidden"
        else:
            D["majority"][(U, V)] = None
        t, o = D["trophic"][(U, V)], D["observed"][(U, V)]
        D["both"][(U, V)] = t if t == o else None
        if seen_before is not None:
            if w:
                D["removed"][(U, V)] = D["never"][(U, V)] = "allowed"
            else:
                D["removed"][(U, V)] = "forbidden" if (U, V) in seen_before else None
                D["never"][(U, V)] = None if (U, V) in seen_before else "forbidden"
    return D, levels, pos, F0


# ----------------------------------------------------------------------------- scoring
def score(truth: dict, decisions: dict, W: dict):
    constrained = {p: v for p, v in truth.items()}
    n_f = sum(v == "forbidden" for v in constrained.values())
    n_a = len(constrained) - n_f
    rows = {}
    for m, D in decisions.items():
        tp = fp = fn = tn = abst = 0
        for p, v in constrained.items():
            d = D.get(p)
            if d is None:
                abst += 1
                if v == "forbidden":
                    fn += 1
            elif d == "forbidden":
                tp += v == "forbidden"
                fp += v == "allowed"
            else:
                fn += v == "forbidden"
                tn += v == "allowed"
        prec = tp / (tp + fp) if tp + fp else float("nan")
        rec = tp / n_f if n_f else float("nan")
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        extra = sum(1 for p, d in D.items() if d == "forbidden" and p not in constrained)
        rows[m] = {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "abstain": abst, "precision": prec, "recall": rec, "f1": f1,
                   "coverage": (len(constrained) - abst) / len(constrained) if constrained else float("nan"),
                   "forbids_on_unconstrained": extra}
    present_forbidden = sum(1 for p, v in constrained.items() if v == "forbidden" and W.get(p, 0) > 0)
    return {"n_constrained": len(constrained), "n_forbidden": n_f, "n_allowed": n_a,
            "base_rate": n_f / len(constrained) if constrained else float("nan"),
            "forbidden_pairs_with_edges_now": present_forbidden, "methods": rows}


def kendall(layer_orders, unit: dict, levels: dict, pos: dict):
    """Per layers contract: agreement of the recovered order with the written one over pairs of named
    modules on different layers (tau = (concordant - discordant) / pairs)."""
    out = []
    for name, groups in layer_orders:
        units_of = lambda names: sorted({unit[m] for m in unit if any(covers(n, m) for n in names)})  # noqa: E731
        G = [units_of(g) for g in groups]
        res = {"contract": name, "layers": len(G)}
        for label, key, higher_is in (("trophic", levels, "greater"), ("fas", pos, "smaller")):
            conc = disc = 0
            for i in range(len(G)):
                for j in range(i + 1, len(G)):
                    for a in G[i]:
                        for b in G[j]:
                            if a == b or a not in key or b not in key:
                                continue
                            ok = key[a] > key[b] if higher_is == "greater" else key[a] < key[b]
                            conc += ok
                            disc += not ok
            res[f"tau_{label}"] = (conc - disc) / (conc + disc) if conc + disc else float("nan")
            res[f"pairs_{label}"] = conc + disc
        out.append(res)
    return out


def run_scheme(scheme, unit, modules, module_edges, contracts, layer_orders, margin, history):
    units = sorted(set(unit.values()))
    W = unit_graph(unit, module_edges)
    truth, below = project(contracts, units)
    seen = None
    hist_note = None
    if history:
        seen = set()
        for _, edges_s in history:
            for a, b in edges_s:
                # a module of an older commit maps by the HEAD unit table when it still exists, else by name prefix
                ua = unit.get(a) or next((u for u in sorted(units, key=len, reverse=True) if covers(u, a)), None)
                ub = unit.get(b) or next((u for u in sorted(units, key=len, reverse=True) if covers(u, b)), None)
                if ua and ub and ua != ub:
                    seen.add((ua, ub))
        hist_note = {"samples": len(history), "pairs_seen_before": len(seen)}
    D, levels, pos, F0 = decide(units, W, margin, seen)
    res = {"scheme": scheme, "n_units": len(units), "n_unit_edges": len(W), "trophic_incoherence_F0": F0,
           "named_pairs_below_granularity": below, "history": hist_note,
           "score": score(truth, D, W), "layer_order": kendall(layer_orders, unit, levels, pos),
           "levels": dict(sorted(levels.items(), key=lambda kv: -kv[1])),
           "disagreements": {m: sorted([f"{U} -> {V}" for (U, V), v in truth.items() if D[m].get((U, V)) and D[m][(U, V)] != v])
                             for m in D if m != "forbid_all"},
           "truth_forbidden": sorted(f"{U} -> {V}" for (U, V), v in truth.items() if v == "forbidden"),
           "truth_allowed": sorted(f"{U} -> {V}" for (U, V), v in truth.items() if v == "allowed")}
    return res, D, units


def fmt(x):
    return "  -  " if x != x else f"{x:5.2f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("repo", help="repository name under data/")
    ap.add_argument("--graph", help="graph folder (default: data/REPO/graph/<HEAD sha> per commits.parquet, else the newest)")
    ap.add_argument("--history", help="glob of graph folders of earlier commits (history methods)")
    ap.add_argument("--margin", type=float, default=0.0, help="trophic: abstain when the level gap is within this")
    ap.add_argument("--out")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    data = Path("data") / a.repo
    opts = load_record(data)
    roots = roots_of(opts)
    commits = pd.read_parquet(data / "commits.parquet", columns=["idx", "sha", "ts"]) if (data / "commits.parquet").exists() else None
    idx_of = dict(zip(commits.sha, commits.idx, strict=True)) if commits is not None else {}
    gdirs = sorted(p for p in (data / "graph").iterdir() if (p / "summary.json").exists()) if (data / "graph").is_dir() else []
    if a.graph:
        gdir = Path(a.graph)
    else:
        gdir = max(gdirs, key=lambda p: idx_of.get(json.loads((p / "summary.json").read_text())["sha"], -1))
    modules, module_edges, sha = load_graph(gdir)
    contracts, named, layer_orders, unscorable = compile_contracts(opts, modules)
    history = []
    if a.history:
        for p in sorted(glob.glob(a.history)):
            p = Path(p)
            if p.resolve() == gdir.resolve() or not (p / "summary.json").exists():
                continue
            m_s, e_s, s_s = load_graph(p)
            if idx_of and idx_of.get(s_s, 10**9) >= idx_of.get(sha, 10**9):
                continue  # not earlier than the scored commit
            history.append((s_s, e_s))
    unit_c = units_contract(named, modules, roots)
    unit_a, split = units_auto(modules, roots)
    out = {"repo": a.repo, "sha": sha, "graph": str(gdir), "roots": roots, "n_modules": len(modules), "n_module_edges": len(module_edges),
           "contracts": [{"name": c["name"], "type": c["type"], "named_pairs": len(c["verdicts"])} for c in contracts],
           "named_modules": sorted(named), "unscorable": unscorable, "auto_split": split, "margin": a.margin, "schemes": {}}
    for scheme, unit in (("contract", unit_c), ("auto", unit_a)):
        res, _, _ = run_scheme(scheme, unit, modules, module_edges, contracts, layer_orders, a.margin, history)
        out["schemes"][scheme] = res
    outp = Path(a.out) if a.out else data / "recovery" / "static.json"
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps(out, indent=1, default=float))
    if not a.quiet:
        print(f"{a.repo}@{sha[:8]}: {len(modules)} modules, {len(module_edges)} module edges; {len(contracts)} contracts compiled, "
              f"{len(unscorable)} items unscorable; history samples: {len(history)}")
        for scheme, res in out["schemes"].items():
            s = res["score"]
            print(f"\n[{scheme}] {res['n_units']} units, {res['n_unit_edges']} unit edges, F0={fmt(res['trophic_incoherence_F0'])}; "
                  f"constrained pairs {s['n_constrained']} (forbidden {s['n_forbidden']}, allowed {s['n_allowed']}, base rate {fmt(s['base_rate'])}); "
                  f"{s['forbidden_pairs_with_edges_now']} forbidden pairs have edges now; {res['named_pairs_below_granularity']} named pairs below granularity")
            print(f"  {'method':10s} {'prec':>5s} {'rec':>5s} {'f1':>5s} {'cover':>5s}   tp  fp  fn  tn  abst  extra")
            for m, r in s["methods"].items():
                print(f"  {m:10s} {fmt(r['precision'])} {fmt(r['recall'])} {fmt(r['f1'])} {fmt(r['coverage'])}  {r['tp']:3d} {r['fp']:3d} {r['fn']:3d} {r['tn']:3d}  {r['abstain']:4d}  {r['forbids_on_unconstrained']:5d}")
            for lo in res["layer_order"]:
                print(f"  layers '{lo['contract'][:50]}': tau trophic {fmt(lo['tau_trophic'])} ({lo['pairs_trophic']} pairs), fas {fmt(lo['tau_fas'])}")
        print(f"-> {outp}")


if __name__ == "__main__":
    main()

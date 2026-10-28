"""Fault injection, setup half (docs/spec/fault-injection.md): plant rule-breaking pushes on a branch.

    uv run python tools/fault_injection.py data/raw/kedro --rules data/kedro/rms/rules --out data/kedro/rms/fi
    uv run python tools/fault_injection.py data/raw/kedro --rules ... --out ... --kinds unused,helper,constant,control --per-kind 2

Creates the worktree <repo>.fi and, for every injection, one branch sarms/fi-<run-id>-<n> holding
a single planted push on top of the current head (siblings, not a stack, so each plant is judged
against a clean parent), committed by the fixed test author `SARMS Test Author <fi@sarms.invalid>`. Each push breaks exactly one compiled rule (chosen with
numpy.random.default_rng(2569), balanced over layer skip / forbidden import / independence break)
and carries a small functional change with a test, so the gate has something to keep (G0).

Kinds — what the push does, and the fix a developer would make:
  unused     adds `from <to> import <name>` to a module under <from>, plus a new function that does
             not use it            -> delete the import (strategy 1)
  helper     adds a tiny helper to a module under <to> and a function under <from> that uses it
             -> move the helper to a module both may import (strategy 3)
  constant   a function under <from> uses an existing public name of <to>
             -> pass it in or move it (strategies 2/3); the hardest kind, may end in escalate
  control    a functional change that breaks no rule (injection 10) -> the system must do nothing

Writes <out>/plants.json: one record per plant with its sha, kind, rule, the edge the Differ should
report (as `edge_from -> edge_to`), the expected label and the files touched. tools/eval_drafts.py
reads it. data/raw/REPO itself is never modified; the worktree can be deleted with
`git -C data/raw/REPO worktree remove --force <repo>.fi`.
"""
from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

from sarms.differ.diff import VIOLATION_LABELS, diff_commit
from sarms.mining.common import git, module_matches, resolve_ref, worktree_path
from sarms.replay.proxy_lint import pythonpath
from sarms.rules.compile import load_bundle, load_rules

AUTHOR = ["-c", "user.name=SARMS Test Author", "-c", "user.email=fi@sarms.invalid"]


def modules_under(tree: Path, roots_paths, pattern: str):
    """[(module name, path)] of .py files (not __init__, not tests) under a rule pattern."""
    out = []
    for base in roots_paths:
        base = Path(base)
        top = pattern.replace("*", "").strip(".").split(".")[0]
        for f in sorted((base / top).rglob("*.py")) if (base / top).is_dir() else []:
            rel = f.relative_to(base).with_suffix("")
            if f.name == "__init__.py" or "test" in f.parts or "templates" in f.parts:
                continue
            mod = ".".join(rel.parts)
            if module_matches(pattern, mod):
                out.append((mod, f))
    return out


def public_names(path: Path):
    """Top-level functions and UPPER_CASE constants a module defines (not starting with _)."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return []
    names = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
            names.append(node.name)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id.isupper():
                    names.append(t.id)
    return names


def rule_kind(rule):
    s = rule["source"].get("sentence", "")
    return "layer skip" if s.startswith("layers:") else "independence break" if s.startswith("independence:") else "forbidden import"


def plant(copy: Path, roots_paths, rule, kind, n, rng):
    """Write the planted change into the worktree. Returns the plant record (without sha) or None."""
    src = modules_under(copy, roots_paths, rule["from"])
    dst = modules_under(copy, roots_paths, rule["to"])
    if not src or not dst:
        return None
    s_mod, s_path = src[int(rng.integers(len(src)))]
    cands = [(m, p) for m, p in dst if public_names(p)] if kind == "constant" else dst
    if not cands:
        return None
    t_mod, t_path = cands[int(rng.integers(len(cands)))]
    tag = f"sarms_fi_{n}"
    files = [str(s_path.relative_to(copy)).replace("\\", "/")]
    if kind == "unused":
        names = public_names(t_path)
        name = names[int(rng.integers(len(names)))] if names else None
        imp = f"from {t_mod} import {name}" if name else f"import {t_mod}"
        import_line = f"{imp}  # noqa: F401  (planted: {tag})"
        s_path.write_text(s_path.read_text(encoding="utf-8") +
                          f"\n\n{import_line}\n\n\n"
                          f"def {tag}():\n    \"\"\"Planted functional change {n}: returns a fixed marker.\"\"\"\n    return {n!r}\n",
                          encoding="utf-8")
    elif kind == "helper":
        helper = f"{tag}_helper"
        t_path.write_text(t_path.read_text(encoding="utf-8") +
                          f"\n\ndef {helper}():\n    \"\"\"Planted helper {n}.\"\"\"\n    return {n!r}\n", encoding="utf-8")
        import_line = f"from {t_mod} import {helper}  # planted: {tag}"
        s_path.write_text(s_path.read_text(encoding="utf-8") +
                          f"\n\n{import_line}\n\n\n"
                          f"def {tag}():\n    \"\"\"Planted functional change {n}: uses a helper from {t_mod}.\"\"\"\n    return {helper}()\n",
                          encoding="utf-8")
        files.append(str(t_path.relative_to(copy)).replace("\\", "/"))
        name = helper
    elif kind == "constant":
        names = public_names(t_path)
        name = names[int(rng.integers(len(names)))]
        import_line = f"from {t_mod} import {name}  # planted: {tag}"
        s_path.write_text(s_path.read_text(encoding="utf-8") +
                          f"\n\n{import_line}\n\n\n"
                          f"def {tag}():\n    \"\"\"Planted functional change {n}: refers to {name} from {t_mod}.\"\"\"\n    return {name}\n",
                          encoding="utf-8")
    else:
        raise ValueError(kind)
    test_dir = copy / "tests" / "sarms_fi"
    test_dir.mkdir(parents=True, exist_ok=True)
    (test_dir / "__init__.py").touch()
    expect = f"{tag}() == {n!r}" if kind in ("unused", "helper") else f"{tag}() is not None"
    (test_dir / f"test_{tag}.py").write_text(
        f"from {s_mod} import {tag}\n\n\ndef test_{tag}():\n    assert {expect}\n", encoding="utf-8")
    files.append(f"tests/sarms_fi/test_{tag}.py")
    return {"n": n, "kind": kind, "rule_id": rule["id"], "rule_kind": rule_kind(rule), "contract": rule["source"]["id"],
            "edge": f"{rule['from']} -> {rule['to']}", "expected_label": "INVERTED" if rule_kind(rule) == "layer skip" else "ADDITIONAL",
            "importer": s_mod, "imported": t_mod, "name": name, "import_line": import_line,
            "importer_file": files[0], "imported_file": str(t_path.relative_to(copy)).replace("\\", "/"),
            "files": files, "test": f"tests/sarms_fi/test_{tag}.py"}


def plant_control(copy: Path, roots_paths, bundle, n, rng):
    root = bundle["session"]["root_packages"][0].split(".")[0]
    mods = [(m, p) for base in roots_paths for p in sorted((Path(base) / root).rglob("*.py"))
            if p.name != "__init__.py" and "test" not in p.parts and "templates" not in p.parts
            for m in [".".join(p.relative_to(base).with_suffix("").parts)]]
    s_mod, s_path = mods[int(rng.integers(len(mods)))]
    tag = f"sarms_fi_{n}"
    s_path.write_text(s_path.read_text(encoding="utf-8") +
                      f"\n\ndef {tag}():\n    \"\"\"Planted clean control {n}: breaks no rule.\"\"\"\n    return {n!r}\n", encoding="utf-8")
    test_dir = copy / "tests" / "sarms_fi"
    test_dir.mkdir(parents=True, exist_ok=True)
    (test_dir / "__init__.py").touch()
    (test_dir / f"test_{tag}.py").write_text(f"from {s_mod} import {tag}\n\n\ndef test_{tag}():\n    assert {tag}() == {n!r}\n", encoding="utf-8")
    return {"n": n, "kind": "control", "rule_id": None, "rule_kind": "clean control", "contract": None, "edge": None,
            "expected_label": None, "importer": s_mod, "imported": None, "name": None,
            "files": [str(s_path.relative_to(copy)).replace("\\", "/"), f"tests/sarms_fi/test_{tag}.py"], "test": f"tests/sarms_fi/test_{tag}.py"}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("repo_dir")
    ap.add_argument("--rules", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--kinds", default="unused,helper,constant,control")
    ap.add_argument("--per-kind", type=int, default=1)
    ap.add_argument("--seed", type=int, default=2569)
    ap.add_argument("--src", nargs="*")
    ap.add_argument("--run-id", default=time.strftime("%Y%m%d-%H%M"))
    a = ap.parse_args()
    repo = Path(a.repo_dir).resolve()
    rules_dir, out = Path(a.rules), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    bundle, rules = load_bundle(rules_dir), load_rules(rules_dir)
    head = git(repo, "rev-parse", resolve_ref(repo)).strip()
    rng = np.random.default_rng(a.seed)

    copy = worktree_path(repo, "fi")
    branch = f"sarms/fi-{a.run_id}"
    if copy.exists():
        git(repo, "worktree", "remove", "--force", str(copy), check=False)
    git(repo, "worktree", "add", "--detach", str(copy), head)
    roots_paths, _ = pythonpath(copy, bundle["session"]["root_packages"], a.src)

    # rules not already broken at head (so each plant is a NEW violation), balanced by kind
    base = diff_commit(repo, head, rules_dir, None, a.src, tree=copy, write_files=False)
    broken = {(r["edge_from"], r["edge_to"]) for r in base["rows"] if r["label"] in VIOLATION_LABELS}
    pool = {k: [] for k in ("layer skip", "forbidden import", "independence break")}
    for r in rules:
        if r["kind"] == "forbidden" and r.get("evaluable", True) and "*" not in r["from"] + r["to"] \
                and (r["from"], r["to"]) not in broken:
            pool[rule_kind(r)].append(r)
    for k in pool:
        rng.shuffle(pool[k])
    cycle = [k for k in ("layer skip", "forbidden import", "independence break") if pool[k]]

    plants, n = [], 0
    for kind in a.kinds.split(","):
        for _ in range(a.per_kind):
            n += 1
            if kind == "control":
                rec = plant_control(copy, roots_paths, bundle, n, rng)
            else:
                rec = None
                for _try in range(20):
                    rk = cycle[(n + _try) % len(cycle)]
                    if not pool[rk]:
                        continue
                    rule = pool[rk].pop()
                    rec = plant(copy, roots_paths, rule, kind, n, rng)
                    if rec:
                        break
                    git(copy, "checkout", "-q", "--force", "--detach", head)
                    git(copy, "clean", "-fdq")
                if rec is None:
                    print(f"  could not plant kind {kind} (#{n}); skipped")
                    continue
            git(copy, "add", "-A")
            msg = (f"fi-{n}: {rec['kind']} — {rec['rule_kind']} {rec['edge'] or '(no rule broken)'}\n\n"
                   f"Planted push {n} for fault injection (docs/spec/fault-injection.md). "
                   f"Adds {rec['importer']}.sarms_fi_{n} with a test.")
            subprocess.run(["git", "-C", str(copy), *AUTHOR, "commit", "-q", "-m", msg], check=True)
            rec["sha"] = git(copy, "rev-parse", "HEAD").strip()
            rec["parent"] = head
            rec["branch"] = f"{branch}-{n}"
            git(copy, "branch", "-f", rec["branch"], rec["sha"])
            plants.append(rec)
            git(copy, "checkout", "-q", "--detach", head)   # the next plant starts from the clean head again
            git(copy, "clean", "-fdq")
            print(f"  planted #{n} {rec['kind']:8s} {rec['rule_kind']:18s} {rec['edge'] or '-':55s} {rec['sha'][:12]}")
    meta = {"repo": str(repo), "head": head, "branch": branch, "worktree": str(copy), "seed": a.seed,
            "run_id": a.run_id, "rules_dir": str(rules_dir), "plants": plants}
    (out / "plants.json").write_text(json.dumps(meta, indent=1))
    print(f"{len(plants)} plants on {branch}-1..{n} (one branch each, all from {head[:12]}) -> {out / 'plants.json'}")


if __name__ == "__main__":
    sys.exit(main())

"""Synthesize: one violation -> one drafted fix, tried in a copy, never committed here.

    uv run python -m sarms.synthesize.draft data/raw/kedro --rules data/kedro/rms/rules --rms data/kedro/rms --pick direct
    uv run python -m sarms.synthesize.draft data/raw/kedro ... --edge "kedro.runner -> kedro.framework.project" --tests "python -m pytest tests/runner -q -x --no-cov -p no:cacheprovider"
    uv run python -m sarms.synthesize.draft data/raw/kedro ... --template          # the rule-based draft, no model

What happens, in order (our code does everything except writing the edit):
  1. the Differ labels the commit; the violation is chosen (--edge, or --pick direct = the first
     violation one import line explains, unacknowledged first)
  2. a fresh worktree <repo>.draft is checked out at the commit: the copy the draft is tried in
  3. the prompt is built (sarms.synthesize.prompt) and the model answers once (sarms.synthesize.llm)
     — or, with --template, the rule-based drafter answers (delete an unused import) or gives up
  4. the answer is parsed into FIND/REPLACE blocks and applied to the copy; edits outside the
     source roots, or to tests or rule files, are refused (the gate's G0/G5 lines, early)
  5. the Differ runs on the copy: the violation must be gone and no new violation may appear (G1);
     with --tests, the command runs in the copy and must exit 0 (G3)
  6. a failure is sent back to the model with the reason, up to --tries times; then: escalate
Everything is written to <rms>/drafts/<sha12>-<n>/: prompt.txt, reply.txt, patch.diff, result.json.
The full gate (G0-G8), the signed decision record and the kernel commit are Weeks 4-5.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path

from sarms.differ.diff import VIOLATION_LABELS, diff_commit
from sarms.mining.common import git, resolve_ref
from sarms.replay.proxy_lint import pythonpath
from sarms.rules.compile import load_bundle, load_rules
from sarms.synthesize import llm
from sarms.synthesize import prompt as P

BLOCK = re.compile(r"FILE:\s*(?P<path>\S+)\s*\n<{7} FIND\n(?P<find>.*?)\n?={7}\n(?P<repl>.*?)\n?>{7} REPLACE", re.S)
REASON = re.compile(r"^REASON:\s*(.+)$", re.M)
PROTECTED = re.compile(r"(^|/)(tests?|testing|conftest\.py|pyproject\.toml|setup\.cfg|\.importlinter|tox\.ini|\.github/)", re.I)


def parse(reply: str):
    """-> (blocks [(path, find, replace)], reason, problems)."""
    text = reply.replace("\r\n", "\n")
    text = re.sub(r"```[a-z]*\n?", "", text)  # tolerate fences
    blocks = [(m.group("path").strip(), m.group("find"), m.group("repl")) for m in BLOCK.finditer(text)]
    reason = (REASON.search(text) or [None, ""])[1].strip()
    problems = [] if blocks else ["no FIND/REPLACE block found in the reply"]
    return blocks, reason, problems


def apply(tree: Path, blocks, allowed_roots):
    """Apply blocks to the copy. -> problems (empty = applied)."""
    problems = []
    for path, find, repl in blocks:
        rel = Path(path.lstrip("./"))
        if rel.is_absolute() or ".." in rel.parts:
            problems.append(f"{path}: refused, path escapes the repository")
            continue
        if PROTECTED.search(rel.as_posix()):
            problems.append(f"{path}: refused, tests and rule files may not be edited (G0/G5)")
            continue
        if not any(rel.as_posix().startswith(r) for r in allowed_roots):
            problems.append(f"{path}: refused, outside the source roots {sorted(allowed_roots)}")
            continue
        f = tree / rel
        if find.strip() == "":
            if f.exists():
                problems.append(f"{path}: empty FIND but the file exists")
                continue
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(repl.rstrip("\n") + "\n", encoding="utf-8")
            continue
        if not f.exists():
            problems.append(f"{path}: file does not exist")
            continue
        src = f.read_text(encoding="utf-8")
        n = src.count(find)
        if n == 0:
            # second chance: ignore trailing whitespace differences
            cand = "\n".join(line.rstrip() for line in find.split("\n"))
            srcn = "\n".join(line.rstrip() for line in src.split("\n"))
            if srcn.count(cand) == 1:
                src, find = srcn, cand
                n = 1
        if n == 0:
            problems.append(f"{path}: FIND text not found (copy the lines exactly; first line was {find.splitlines()[0]!r})")
            continue
        if n > 1:
            problems.append(f"{path}: FIND text occurs {n} times; include more context lines")
            continue
        f.write_text(src.replace(find, repl, 1), encoding="utf-8")
    return problems


def template_draft(tree: Path, violation, roots_paths):
    """The rule-based drafter: delete each violating import line whose names are unused in
    the file. Returns (blocks, reason) or (None, why not)."""
    blocks = []
    for ln in violation.get("lines", []):
        mod = ln["edge"].split("->")[0]
        p = P.module_path(tree, mod, roots_paths)
        if not p:
            return None, f"cannot locate {mod}"
        line = ln["line_contents"]
        src = p.read_text(encoding="utf-8")
        m = re.match(r"\s*from\s+\S+\s+import\s+(.+)", line) or re.match(r"\s*import\s+(.+)", line)
        if not m:
            return None, f"unrecognised import form: {line.strip()}"
        names = [n.split(" as ")[-1].strip() for n in m.group(1).strip("()").split(",") if n.strip()]
        rest = src.replace(line, "", 1)
        used = [n for n in names if re.search(rf"\b{re.escape(n)}\b", rest)]
        if used:
            return None, f"{', '.join(used)} still used in {p.relative_to(tree).as_posix()}: a real refactor is needed"
        blocks.append((p.relative_to(tree).as_posix(), line, ""))
    if not blocks:
        return None, "no direct import line to delete (indirect violation)"
    return blocks, "template: the imported names are unused, so the import lines are deleted"


def pick(result, edge=None):
    viol = [r for r in result["rows"] if r["label"] in VIOLATION_LABELS]
    if edge:
        a, b = [x.strip() for x in edge.split("->")]
        hit = [r for r in viol if r["edge_from"] == a and r["edge_to"] == b]
        if not hit:
            sys.exit(f"no violation {a} -> {b} at this commit; present: " + ", ".join(f"{r['edge_from']} -> {r['edge_to']}" for r in viol))
        return hit[0]
    direct = sorted((r for r in viol if r["direct"]), key=lambda r: (r["acknowledged"], r["edge_from"]))
    if not direct:
        sys.exit("no direct violation at this commit (all are indirect chains); choose one with --edge")
    return direct[0]


def fresh_copy(repo_dir: Path, sha: str):
    wt = Path(f"{repo_dir}.draft").resolve()
    if not wt.exists():
        git(repo_dir, "worktree", "add", "--detach", "-f", str(wt.resolve()), sha)
    else:
        git(wt, "checkout", "-q", "--force", sha)
        git(wt, "clean", "-fdq")
    return wt


def run_tests(tree: Path, cmd: str, timeout: int):
    t0 = time.time()
    try:
        p = subprocess.run(cmd, shell=True, cwd=tree, capture_output=True, text=True, timeout=timeout)
        out = (p.stdout + p.stderr)
        return {"command": cmd, "exit": p.returncode, "pass": p.returncode == 0, "seconds": round(time.time() - t0, 1),
                "tail": out[-3000:]}
    except subprocess.TimeoutExpired:
        return {"command": cmd, "exit": None, "pass": False, "seconds": timeout, "tail": "timeout"}


def draft_one(repo_dir, sha=None, rules_dir=None, rms_dir=None, edge=None, pick_mode="direct", tests=None,
              tries=3, template=False, model=None, base_url=None, src=None, test_timeout=3600, log=print):
    repo_dir = Path(repo_dir).resolve()
    sha = git(repo_dir, "rev-parse", sha or resolve_ref(repo_dir)).strip()
    rules_dir = Path(rules_dir) if rules_dir else repo_dir / ".rms" / "rules"
    rms = Path(rms_dir) if rms_dir else repo_dir / ".rms"
    rules = {r["id"]: r for r in load_rules(rules_dir)}
    bundle = load_bundle(rules_dir)

    before = diff_commit(repo_dir, sha, rules_dir, rms, src)
    v = pick(before, edge)
    rule = rules.get(v["rule_id"])
    before_set = {(r["contract"], r["edge_from"], r["edge_to"]) for r in before["rows"] if r["label"] in VIOLATION_LABELS}
    log(f"target: {v['label']} {v['edge_from']} -> {v['edge_to']}  [{v['rule_id']}]  "
        f"{'direct' if v['direct'] else 'indirect'}{' (acknowledged)' if v['acknowledged'] else ''}")

    copy = fresh_copy(repo_dir, sha)
    roots_paths, _ = pythonpath(copy.resolve(), bundle["session"]["root_packages"], src)
    allowed_roots = set()
    for p in roots_paths:
        rel = Path(p).resolve().relative_to(copy.resolve()).as_posix()
        prefix = "" if rel in ("", ".") else rel + "/"
        for r in bundle["session"]["root_packages"]:
            allowed_roots.add(prefix + r.split(".")[0])

    n = 1 + len(list((rms / "drafts").glob(f"{sha[:12]}-*"))) if (rms / "drafts").exists() else 1
    out = rms / "drafts" / f"{sha[:12]}-{n}"
    out.mkdir(parents=True, exist_ok=True)
    result = {"sha": sha, "violation": {k: v[k] for k in ("rule_id", "contract", "edge_from", "edge_to", "label", "acknowledged", "direct", "edges")},
              "class": "template" if template else "llm_draft", "attempts": [], "verdict": None}
    feedback, t0 = None, time.time()
    for attempt in range(1, (1 if template else tries) + 1):
        if attempt > 1:
            copy = fresh_copy(repo_dir, sha)
        att = {"n": attempt}
        if template:
            blocks, reason = template_draft(copy, v, roots_paths)
            if blocks is None:
                att.update({"problems": [reason]})
                result["attempts"].append(att)
                break
            reply, rec = "", {"model": "template"}
        else:
            text, importers = P.build(v, rule, copy, roots_paths, feedback=feedback)
            (out / f"prompt{attempt}.txt").write_text(text)
            try:
                reply, rec = llm.complete(text, P.SYSTEM, model=model, base_url=base_url, call_no=attempt - 1)
            except llm.LLMError as e:
                att.update({"problems": [str(e)]})
                result["attempts"].append(att)
                log(f"  attempt {attempt}: {e}")
                break
            (out / f"reply{attempt}.txt").write_text(reply)
            blocks, reason, problems = parse(reply)
            att.update({"model": rec, "reason": reason})
            if problems:
                att["problems"] = problems
                feedback = "\n".join(problems)
                result["attempts"].append(att)
                log(f"  attempt {attempt}: {problems[0]}")
                continue
        problems = apply(copy, blocks, allowed_roots)
        att["files"] = sorted({b[0] for b in blocks})
        if problems:
            att["problems"] = problems
            feedback = "\n".join(problems)
            result["attempts"].append(att)
            log(f"  attempt {attempt}: {problems[0]}")
            continue
        patch = git(copy, "diff", "--", ".", check=False) + git(copy, "ls-files", "--others", "--exclude-standard", check=False)
        (out / f"patch{attempt}.diff").write_text(patch)
        after = diff_commit(repo_dir, sha, rules_dir, None, src, tree=copy, write_files=False)
        after_set = {(r["contract"], r["edge_from"], r["edge_to"]) for r in after["rows"] if r["label"] in VIOLATION_LABELS}
        gone = (v["contract"], v["edge_from"], v["edge_to"]) not in after_set
        new = sorted(after_set - before_set)
        att["g1"] = {"violation_gone": gone, "new_violations": [f"{a} -> {b} ({c})" for c, a, b in new],
                     "violations_before": len(before_set), "violations_after": len(after_set), "pass": gone and not new}
        if tests and att["g1"]["pass"]:
            att["g3"] = run_tests(copy, tests, test_timeout)
        ok = att["g1"]["pass"] and (att.get("g3", {"pass": True})["pass"])
        att["pass"] = ok
        result["attempts"].append(att)
        if ok:
            result["verdict"] = "draft_passes"
            (out / "patch.diff").write_text(patch)
            log(f"  attempt {attempt}: PASS — violation gone, {len(after_set)} violations left (was {len(before_set)})"
                + (f"; tests pass in {att['g3']['seconds']}s" if "g3" in att else ""))
            break
        why = []
        if not gone:
            why.append(f"the violation {v['edge_from']} -> {v['edge_to']} is still reported after your change")
        if new:
            why.append("your change created new violations: " + "; ".join(att["g1"]["new_violations"]))
        if "g3" in att and not att["g3"]["pass"]:
            why.append("the tests failed:\n" + att["g3"]["tail"][-1500:])
        feedback = "\n".join(why)
        log(f"  attempt {attempt}: rejected — {why[0][:160]}")
    if result["verdict"] is None:
        result["verdict"] = "escalate"
    result["seconds"] = round(time.time() - t0, 1)
    result["tries"] = len(result["attempts"])
    prompts = sorted(out.glob("prompt*.txt"))
    result["prompt_hash"] = hashlib.sha256(prompts[0].read_bytes()).hexdigest() if prompts else None
    (out / "result.json").write_text(json.dumps(result, indent=1, default=str))
    log(f"verdict: {result['verdict']} after {result['tries']} attempt(s), {result['seconds']}s -> {out}")
    return result, out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("repo_dir")
    ap.add_argument("--sha")
    ap.add_argument("--rules")
    ap.add_argument("--rms")
    ap.add_argument("--edge", help='"a.b -> c.d" as the Differ prints it')
    ap.add_argument("--pick", default="direct")
    ap.add_argument("--tests", help="test command to run in the copy after a draft passes G1 (e.g. pytest ...)")
    ap.add_argument("--tries", type=int, default=3)
    ap.add_argument("--template", action="store_true", help="rule-based draft, no model")
    ap.add_argument("--model")
    ap.add_argument("--base-url")
    ap.add_argument("--src", nargs="*")
    ap.add_argument("--test-timeout", type=int, default=3600)
    a = ap.parse_args()
    draft_one(a.repo_dir, a.sha, a.rules, a.rms, a.edge, a.pick, a.tests, a.tries, a.template, a.model, a.base_url, a.src,
              a.test_timeout, log=lambda s: print(s, flush=True))


if __name__ == "__main__":
    main()

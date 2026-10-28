"""Fault injection, measurement half: detect every plant, draft a fix with each model, one table.

    uv run python tools/eval_drafts.py data/kedro/rms/fi/plants.json --models ollama:qwen2.5-coder:latest
    uv run python tools/eval_drafts.py data/kedro/rms/fi/plants.json --models ollama:qwen2.5-coder:latest gemini:gemini-2.5-flash template
    uv run python tools/eval_drafts.py data/kedro/rms/fi/plants.json --models oracle          # hand-written ideal replies: proves the harness
    ... --tests "python -m pytest tests/sarms_fi -q -p no:cacheprovider --no-cov"             # also run the planted tests on each draft (G3)

For every plant (tools/fault_injection.py):
  detection   the Differ on the planted commit minus the Differ on its parent must contain the
              planted edge with the expected label; a control must add nothing   (recall on plants)
  drafting    sarms.synthesize.draft on the planted edge, once per model; a control is never drafted
Model presets: ollama:<name> (localhost:11434), gemini:<name> (needs GEMINI_API_KEY or SARMS_LLM_API_KEY),
openai:<name> (OPENAI_API_KEY), anthropic:<name> (ANTHROPIC_API_KEY), url:<base>|<name>, fake:<dir>,
template (rule-based drafter), oracle (an ideal reply built from the plant record, for unused/helper).
Writes <plants dir>/results-<run>.md and .csv. Nothing here touches data/raw/REPO or its main branch.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import textwrap
import time
from pathlib import Path

from sarms.differ.diff import VIOLATION_LABELS, diff_commit
from sarms.synthesize.draft import draft_one, fresh_copy

PRESETS = {"ollama": ("http://localhost:11434/v1", None),
           "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai", "GEMINI_API_KEY"),
           "openai": ("https://api.openai.com/v1", "OPENAI_API_KEY"),
           "anthropic": ("https://api.anthropic.com/v1", "ANTHROPIC_API_KEY")}


def preset(spec):
    """-> (label, kwargs for draft_one, env to set)"""
    if spec in ("template", "oracle"):
        return spec, {"template": spec == "template"}, {}
    kind, _, rest = spec.partition(":")
    if kind == "fake":
        return spec, {"base_url": f"fake:{rest}", "model": "fake"}, {}
    if kind == "url":
        base, _, model = rest.partition("|")
        return spec, {"base_url": base, "model": model}, {}
    if kind in PRESETS:
        base, key_env = PRESETS[kind]
        env = {}
        if key_env and os.environ.get(key_env):
            env["SARMS_LLM_API_KEY"] = os.environ[key_env]
        return spec, {"base_url": base, "model": rest}, env
    sys.exit(f"unknown model preset {spec!r}")


def oracle_reply(p, root):
    """The edit a careful developer would make, from the plant record. None when no generic fix exists."""
    tag = f"sarms_fi_{p['n']}"
    if p["kind"] == "unused":
        return textwrap.dedent(f"""\
            PLAN: strategy 1, the imported name is unused, delete the import.

            FILE: {p['importer_file']}
            <<<<<<< FIND
            {p['import_line']}
            =======
            >>>>>>> REPLACE

            REASON: strategy 1: nothing in the file uses the import.
            """)
    if p["kind"] == "helper":
        shared = f"{root}/{tag}_shared.py"
        helper = p["name"]
        return textwrap.dedent(f"""\
            PLAN: strategy 3, move {helper} into a module neither rule constrains and import it from there on both sides.

            FILE: {shared}
            <<<<<<< FIND
            =======
            def {helper}():
                \"\"\"Planted helper {p['n']}.\"\"\"
                return {p['n']!r}
            >>>>>>> REPLACE

            FILE: {p['importer_file']}
            <<<<<<< FIND
            {p['import_line']}
            =======
            from {root}.{tag}_shared import {helper}
            >>>>>>> REPLACE

            FILE: {p['imported_file']}
            <<<<<<< FIND


            def {helper}():
                \"\"\"Planted helper {p['n']}.\"\"\"
                return {p['n']!r}
            =======
            >>>>>>> REPLACE

            REASON: strategy 3: the helper now lives in a shared module, so the importer no longer depends on {p['imported']}.
            """)
    return None


def detect(repo, sha, parent, rules_dir, p, src):
    copy = fresh_copy(Path(repo), sha)
    here = diff_commit(repo, sha, rules_dir, None, src, tree=copy, write_files=False)
    copy = fresh_copy(Path(repo), parent)
    before = diff_commit(repo, parent, rules_dir, None, src, tree=copy, write_files=False)
    key = lambda r: (r["contract"], r["edge_from"], r["edge_to"])  # noqa: E731
    old = {key(r) for r in before["rows"] if r["label"] in VIOLATION_LABELS}
    added = [r for r in here["rows"] if r["label"] in VIOLATION_LABELS and key(r) not in old]
    if p["kind"] == "control":
        return {"detected": not added, "added": len(added), "label": None, "direct": None}
    a, b = [x.strip() for x in p["edge"].split("->")]
    hits = [r for r in added if (r["edge_from"], r["edge_to"]) == (a, b)]
    labels = sorted({r["label"] for r in hits})
    return {"detected": p["expected_label"] in labels, "added": len(added), "label": "+".join(labels) or None,
            "direct": any(r["direct"] for r in hits) if hits else None,
            "acknowledged": all(r["acknowledged"] for r in hits) if hits else None}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("plants_json")
    ap.add_argument("--models", nargs="*", default=[])
    ap.add_argument("--tests", help="test command run in the copy after G1 passes")
    ap.add_argument("--tries", type=int, default=3)
    ap.add_argument("--only", help="comma-separated plant numbers")
    ap.add_argument("--src", nargs="*")
    ap.add_argument("--rms", help="where drafts go (default: the plants' .rms = parent of the plants dir)")
    ap.add_argument("--run-id", default=time.strftime("%Y%m%d-%H%M"))
    a = ap.parse_args()
    pj = Path(a.plants_json)
    meta = json.loads(pj.read_text())
    repo, rules_dir = Path(meta["repo"]), Path(meta["rules_dir"])
    rms = Path(a.rms) if a.rms else pj.parent.parent
    root = json.loads((rules_dir / "contracts.json").read_text())["session"]["root_packages"][0].split(".")[0]
    plants = meta["plants"]
    if a.only:
        keep = {int(x) for x in a.only.split(",")}
        plants = [p for p in plants if p["n"] in keep]
    models = [preset(m) for m in a.models]

    rows = []
    for p in plants:
        print(f"\n#{p['n']} {p['kind']} {p['rule_kind']} {p['edge'] or ''}  ({p['sha'][:12]})", flush=True)
        d = detect(repo, p["sha"], p["parent"], rules_dir, p, a.src)
        print(f"  detection: {'OK' if d['detected'] else 'MISSED'}  (+{d['added']} new violation(s), label {d['label']}, direct {d['direct']})")
        row = {"n": p["n"], "kind": p["kind"], "rule_kind": p["rule_kind"], "edge": p["edge"] or "", "sha": p["sha"][:12],
               "detected": d["detected"], "new_violations": d["added"]}
        for label, kw, env in models:
            if p["kind"] == "control":
                row[label] = "silent" if d["detected"] else "FALSE ACTION"
                continue
            old_env = {k: os.environ.get(k) for k in env}
            os.environ.update(env)
            try:
                if label == "oracle":
                    reply = oracle_reply(p, root)
                    if reply is None:
                        row[label] = "n/a"
                        print(f"  {label}: no generic ideal fix for kind {p['kind']}")
                        continue
                    fdir = rms / "fi" / "oracle" / str(p["n"])
                    fdir.mkdir(parents=True, exist_ok=True)
                    (fdir / "1.txt").write_text(reply)
                    kw = {"base_url": f"fake:{fdir}", "model": "oracle"}
                t0 = time.time()
                res, out = draft_one(repo, p["sha"], rules_dir, rms, edge=p["edge"], tests=a.tests, tries=a.tries,
                                     src=a.src, log=lambda s: print("   ", s, flush=True), **kw)
                last = res["attempts"][-1] if res["attempts"] else {}
                g3 = last.get("g3", {}).get("pass")
                row[label] = f"{res['verdict']} ({res['tries']} tries, {time.time() - t0:.0f}s" + (f", tests {'pass' if g3 else 'FAIL'}" if g3 is not None else "") + ")"
                row[label + "_dir"] = str(out)
            finally:
                for k, v in old_env.items():
                    if v is None:
                        os.environ.pop(k, None)
                    else:
                        os.environ[k] = v
        rows.append(row)

    labels = [m[0] for m in models]
    n_det = sum(r["detected"] for r in rows)
    lines = [f"# Fault injection results — {meta['branch']} — run {a.run_id}", "",
             f"Subject `{repo.name}` at `{meta['head'][:12]}`; {len(rows)} plants; models: {', '.join(labels) or 'none'}."
             + (f" Tests: `{a.tests}`" if a.tests else " No tests run (G1 only)."), "",
             f"**Detection: {n_det}/{len(rows)}** plants detected with the expected label (controls: nothing new).", "",
             "| # | kind | rule kind | edge | detected | " + " | ".join(labels) + " |",
             "| --- | --- | --- | --- | --- | " + " | ".join("---" for _ in labels) + " |"]
    for r in rows:
        lines.append(f"| {r['n']} | {r['kind']} | {r['rule_kind']} | `{r['edge']}` | {'yes' if r['detected'] else 'NO'} | "
                     + " | ".join(str(r.get(m, "")) for m in labels) + " |")
    for m in labels:
        done = [r for r in rows if r["kind"] != "control" and r.get(m, "") not in ("", "n/a")]
        passed = [r for r in done if str(r[m]).startswith("draft_passes")]
        if done:
            lines.append(f"\n**{m}: {len(passed)}/{len(done)} drafts pass** ({len(done) - len(passed)} escalated).")
    md = "\n".join(lines) + "\n"
    out_md = pj.parent / f"results-{a.run_id}.md"
    out_md.write_text(md)
    with open(pj.parent / f"results-{a.run_id}.csv", "w", newline="") as fh:
        keys = sorted({k for r in rows for k in r}, key=lambda k: (k not in ("n", "kind", "rule_kind", "edge", "sha", "detected", "new_violations"), k))
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)
    print("\n" + md)
    print(f"-> {out_md}")


if __name__ == "__main__":
    main()

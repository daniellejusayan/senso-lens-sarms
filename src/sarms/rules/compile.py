"""The rule compiler (Knowledge): import-linter contracts -> the rule bundle in .rms/rules/.

    uv run python -m sarms.rules.compile data/raw/kedro                       # HEAD of the default branch
    uv run python -m sarms.rules.compile data/raw/kedro --sha 9039f82a --out data/kedro/rms/rules
    uv run python -m sarms.rules.compile . --config .importlinter             # our own contracts

Writes into the output directory (default <repo>/.rms/rules; for subjects use data/REPO/rms/rules):

  <contract-slug>.yaml   the rules compiled from that contract: a list of entries that each
                         validate against docs/spec/rules.schema.yaml (id, kind, from, to,
                         source, compiled_at, severity, evaluable, acknowledged)
  acknowledged.yaml      every ignore_imports entry, the rule ids it belongs to, and the ones
                         that match no rule (kedro's "kedro -> kedro.ipython")
  contracts.json         the machine record: session options and the contracts both strict
                         (ignore_imports removed) and as written, which the Differ feeds to
                         import-linter so that its exact semantics (indirect chains, optional
                         layers) are kept

How a contract becomes rules (vocabulary.md, "Mapping from import-linter contract types"):
  forbidden      one forbidden rule per source x forbidden pair                 -> ADDITIONAL
  independence   one forbidden rule per ordered pair of the listed modules     -> ADDITIONAL
  layers         for every lower/higher pair: one forbidden rule lower -> higher (sentence
                 starts with "layers:", the Differ labels it INVERTED) and one allowed rule
                 higher -> lower (CONFIRMED); independent siblings (a | b) get a forbidden
                 rule each way (ADDITIONAL); containers prefix every layer
  anything else  one rule with evaluable: false, so the gap is reported, never silent
Each ignore_imports entry is attached (acknowledged) to the rules whose from/to it falls under.
"""
from __future__ import annotations

import argparse
import itertools
import json
import re
import sys
from pathlib import Path

import jsonschema
import yaml

from sarms.mining.common import (
    IL_FILES,
    as_list,
    find_il_config,
    git,
    module_matches,
    norm_ignore,
    normalize_contracts,
    read_il_options,
    resolve_ref,
)

SCHEMA = Path(__file__).resolve().parents[3] / "docs" / "spec" / "rules.schema.yaml"


def slug(s: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-")
    return s[:48] or "contract"


def _layers(c):
    """[[names of one layer line]] bottom -> top is NOT guaranteed by import-linter: the list is
    written top (highest) first. Returns (lines, independent) where each line is a list of names
    and independent says whether the siblings on that line are independent (|) or not (:)."""
    lines = []
    for raw in as_list(c.get("layers")):
        raw = str(raw).strip()
        sep = "|" if "|" in raw else ":" if ":" in raw else None
        names = [n.strip().strip("()").strip() for n in (raw.split(sep) if sep else [raw])]
        lines.append((names, sep == "|"))
    return lines


def _containers(c):
    cs = as_list(c.get("containers"))
    return cs or [None]


def _q(container, name):
    return f"{container}.{name}" if container else name


def compile_contract(c, repo: str, sha: str):
    """Rules for one normalised contract (as written, so ignore_imports is present)."""
    name, ctype = c["name"], c.get("type", "?")
    base = f"R-{slug(repo)}-{slug(name)}"
    src = {"type": "contract", "id": name}
    rules = []
    n = itertools.count(1)

    def add(kind, frm, to, sentence, severity="high", evaluable=True):
        rules.append({"id": f"{base}-{next(n)}", "kind": kind, "from": frm, "to": to,
                      "source": {**src, "sentence": sentence}, "compiled_at": sha[:12],
                      "severity": severity, "evaluable": evaluable})

    if ctype == "forbidden":
        for s in as_list(c.get("source_modules")):
            for f in as_list(c.get("forbidden_modules")):
                add("forbidden", s, f, f"source_modules = {s}; forbidden_modules = {f}")
    elif ctype == "independence":
        mods = as_list(c.get("modules"))
        for a, b in itertools.permutations(mods, 2):
            add("forbidden", a, b, f"independence: {a} | {b}")
    elif ctype == "layers":
        lines = _layers(c)
        for cont in _containers(c):
            for i, (higher, _) in enumerate(lines):
                for lower, _ in lines[i + 1:]:
                    for h in higher:
                        for lo in lower:
                            hq, lq = _q(cont, h), _q(cont, lo)
                            add("forbidden", lq, hq, f"layers: {lq} is below {hq}")
                            add("allowed", hq, lq, f"layers: {hq} is above {lq}", "medium")
            for names, independent in lines:
                if independent and len(names) > 1:
                    for a, b in itertools.permutations(names, 2):
                        add("forbidden", _q(cont, a), _q(cont, b), f"siblings: {a} | {b}")
    else:
        add("forbidden", "?", "?", f"type = {ctype}: not compiled by this version", "medium", False)

    # acknowledged: each ignore entry goes to every rule whose from/to it falls under
    entries = [norm_ignore(e) for e in as_list(c.get("ignore_imports"))]
    unmatched = []
    for e in entries:
        a, b = [x.strip() for x in e.split("->", 1)]
        hit = False
        for r in rules:
            if r["kind"] == "forbidden" and r["evaluable"] and module_matches(r["from"], a) and module_matches(r["to"], b):
                r.setdefault("acknowledged", []).append(e)
                hit = True
        if not hit:
            unmatched.append(e)
    return rules, entries, unmatched


def compile_all(opts, repo: str, sha: str, config_file: str):
    session, strict = normalize_contracts(opts, strict=True)
    _, asis = normalize_contracts(opts, strict=False)
    files, ack = {}, {"compiled_at": sha[:12], "entries": []}
    for c in asis:
        rules, entries, unmatched = compile_contract(c, repo, sha)
        files[slug(c["name"]) + ".yaml"] = rules
        for e in entries:
            ack["entries"].append({"contract": c["name"], "entry": e,
                                   "rules": [r["id"] for r in rules if e in r.get("acknowledged", [])],
                                   "matched": e not in unmatched})
    bundle = {"repo": repo, "compiled_at": sha, "config_file": config_file, "session": session,
              "contracts_strict": strict, "contracts_asis": asis}
    return files, ack, bundle


def validate(rules, schema_path=SCHEMA):
    """[(rule id, error message)] — empty when every rule validates."""
    schema = yaml.safe_load(Path(schema_path).read_text())
    v = jsonschema.Draft202012Validator(schema)
    return [(r.get("id"), e.message) for r in rules for e in v.iter_errors(r)]


def write(out_dir, files, ack, bundle):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*.yaml"):
        old.unlink()
    for fname, rules in files.items():
        (out / fname).write_text(yaml.safe_dump(rules, sort_keys=False, allow_unicode=True))
    (out / "acknowledged.yaml").write_text(yaml.safe_dump(ack, sort_keys=False, allow_unicode=True))
    (out / "contracts.json").write_text(json.dumps(bundle, indent=1, default=str))
    return out


def load_rules(rules_dir):
    """Every compiled rule in a directory, in file order."""
    rules = []
    for f in sorted(Path(rules_dir).glob("*.yaml")):
        if f.name == "acknowledged.yaml":
            continue
        rules.extend(yaml.safe_load(f.read_text()) or [])
    return rules


def load_bundle(rules_dir):
    return json.loads((Path(rules_dir) / "contracts.json").read_text())


def compile_repo(repo_dir, sha=None, config=None, out_dir=None, repo_label=None):
    """Compile the contracts of a git repository at a commit. Returns (out_dir, rules, errors)."""
    repo_dir = Path(repo_dir)
    sha = git(repo_dir, "rev-parse", sha or resolve_ref(repo_dir)).strip()
    fname, text = find_il_config(repo_dir, sha, [config] if config else IL_FILES)
    if not fname:
        sys.exit(f"no import-linter configuration at {sha[:12]} in {repo_dir}")
    opts = read_il_options(fname, text)
    if not opts:
        sys.exit(f"import-linter could not parse {fname} at {sha[:12]}")
    label = repo_label or repo_dir.resolve().name
    files, ack, bundle = compile_all(opts, label, sha, fname)
    rules = [r for rs in files.values() for r in rs]
    errors = validate(rules)
    out = write(out_dir or repo_dir / ".rms" / "rules", files, ack, bundle)
    return out, rules, errors


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("repo_dir")
    ap.add_argument("--sha", help="commit to compile at (default: HEAD of the default branch)")
    ap.add_argument("--config", help="config path inside the repo when it is not at the root")
    ap.add_argument("--out", help="output directory (default <repo>/.rms/rules)")
    ap.add_argument("--repo", help="label used in rule ids (default: the folder name)")
    a = ap.parse_args()
    out, rules, errors = compile_repo(a.repo_dir, a.sha, a.config, a.out, a.repo)
    kinds = {}
    for r in rules:
        kinds[r["kind"]] = kinds.get(r["kind"], 0) + 1
    ack = sum(len(r.get("acknowledged", [])) for r in rules)
    print(f"{len(rules)} rules ({', '.join(f'{v} {k}' for k, v in sorted(kinds.items()))}), "
          f"{ack} acknowledged exceptions attached -> {out}")
    for rid, msg in errors:
        print(f"  SCHEMA ERROR {rid}: {msg}")
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()

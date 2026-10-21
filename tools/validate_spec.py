"""Check docs/spec before Friday's review (the runbook's "done when" for the spec files).

    uv run python tools/validate_spec.py

vocabulary.md names 4 Differ labels, 3 drift indicators and 5 root causes; gate.md has
G0-G8; rules.schema.yaml and decision-record.schema.json are valid JSON Schemas and their
examples validate; ledger.sql loads into DuckDB; evaluation-protocol.md has an Amendments
section; and its SHA-256 is printed for the P1 pack.
"""
import hashlib
import json
import re
from pathlib import Path

import duckdb
import jsonschema
import yaml

S = Path("docs/spec")
ok = True


def check(name, cond, detail=""):
    global ok
    print(("PASS " if cond else "FAIL ") + name + ("" if cond or not detail else f" — {detail}"))
    ok &= bool(cond)


voc = (S / "vocabulary.md").read_text()
for words, n, what in ((["CONFIRMED", "MISSING", "ADDITIONAL", "INVERTED"], 4, "Differ labels"),
                       (["Unassigned module", "New cycle", "Hub fan-in growth"], 3, "drift indicators"),
                       (["requirement realization", "documentation lag", "implementation choice",
                         "behavioral defect", "mixed"], 5, "root causes")):
    missing = [w for w in words if w not in voc]
    check(f"vocabulary.md: {n} {what}", not missing, f"missing {missing}")
rows = [line for line in voc.splitlines() if line.startswith("| ") and re.match(r"\| (CONFIRMED|MISSING|ADDITIONAL|INVERTED) \|", line)]
check("vocabulary.md: every Differ label has an example column filled",
      all(line.rstrip(" |").split("|")[-1].strip() for line in rows))

gate = (S / "gate.md").read_text()
lines = sorted(set(re.findall(r"^\| (G[0-8]) \|", gate, re.M)))
check("gate.md: G0..G8 present", lines == [f"G{i}" for i in range(9)], str(lines))

rs = yaml.safe_load((S / "rules.schema.yaml").read_text())
jsonschema.Draft202012Validator.check_schema(rs)
check("rules.schema.yaml is a valid schema", True)
for ex in rs.get("examples", []):
    errs = [e.message for e in jsonschema.Draft202012Validator(rs).iter_errors(ex)]
    check(f"example rule {ex.get('id')} validates", not errs, "; ".join(errs))

dr = json.loads((S / "decision-record.schema.json").read_text())
jsonschema.Draft202012Validator.check_schema(dr)
check("decision-record.schema.json is a valid schema", True)
sample = {"sha": "0" * 40, "verdict": "accept", "class": "move_to_layer",
          "gate": [{"line": f"G{i}", "pass": True, "evidence": {"ref": f"runs/{i}"}} for i in range(9)],
          "differ_before": "a.sarif", "differ_after": "b.sarif", "trial_runs": ["ci/1"],
          "prompt_hash": "p", "policy_version": "0", "verifier_version": "0", "signature": "s"}
errs = [e.message for e in jsonschema.Draft202012Validator(dr).iter_errors(sample)]
check("a sample decision record validates", not errs, "; ".join(errs))

try:
    con = duckdb.connect()
    con.execute((S / "ledger.sql").read_text())
    t = {r[0] for r in con.execute("select table_name from information_schema.tables").fetchall()}
    check("ledger.sql loads (table ledger + view awareness_gap)", {"ledger", "awareness_gap"} <= t, str(t))
except Exception as e:
    check("ledger.sql loads", False, str(e))

ep = (S / "evaluation-protocol.md").read_bytes()
check("evaluation-protocol.md has an Amendments section", b"## Amendments" in ep)
print(f"\nevaluation-protocol.md sha256 (for the P1 pack): {hashlib.sha256(ep).hexdigest()}")
print("ALL PASS" if ok else "FIX THE FAILURES ABOVE")
raise SystemExit(0 if ok else 1)

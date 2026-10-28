"""The thin slice end to end on a tiny repository: compile -> Differ -> ledger -> draft (fake model).

No network, no model: the fake backend replies from files. The replay data for kedro is not in
CI, so the kedro reproduction check lives in tools/check_against_replay.py.
"""
import json
import subprocess
import textwrap
from pathlib import Path

import pytest

from sarms.mining.common import module_matches

CONFIG = """\
[importlinter]
root_package = app

[importlinter:contract:ui-db]
name = UI must not import the database layer
type = forbidden
source_modules = app.ui
forbidden_modules = app.db

[importlinter:contract:layers]
name = Service above DB
type = layers
layers =
    app.service
    app.db
"""


def g(repo, *a):
    return subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", *a],
                          check=True, capture_output=True, text=True).stdout


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "subject"
    (r / "app").mkdir(parents=True)
    (r / "tests").mkdir()
    (r / ".importlinter").write_text(CONFIG)
    (r / "app" / "__init__.py").write_text("")
    (r / "app" / "db.py").write_text("def connect():\n    return 'db'\n")
    (r / "app" / "service.py").write_text("from app.db import connect\n\n\ndef run():\n    return connect()\n")
    (r / "app" / "ui.py").write_text("import os\nfrom app.db import connect\n\n\ndef show():\n    return os.getcwd()\n")
    (r / "tests" / "test_app.py").write_text("from app.service import run\n\n\ndef test_run():\n    assert run() == 'db'\n")
    g(r, "init", "-q", "-b", "main")
    g(r, "add", "-A")
    g(r, "commit", "-q", "-m", "first: ui imports db (unused)")
    return r


def test_module_matches():
    assert module_matches("kedro.runner", "kedro.runner.task")
    assert module_matches("kedro.runner", "kedro.runner")
    assert not module_matches("kedro.runner", "kedro.runners")
    assert module_matches("app.*", "app.ui") and not module_matches("app.*", "app.ui.widgets") or module_matches("app.*", "app.ui.widgets")
    assert module_matches("lms.djangoapps.*.api", "lms.djangoapps.grades.api")
    assert module_matches("a.**", "a.b.c.d")


def test_compile_differ_ledger_and_draft(repo, tmp_path):
    from sarms.differ.diff import diff_commit
    from sarms.differ.replay import replay
    from sarms.ledger.build import build
    from sarms.rules.compile import compile_repo, load_rules
    from sarms.synthesize.draft import draft_one

    rules_dir = tmp_path / "rms" / "rules"
    out, rules, errors = compile_repo(repo, out_dir=rules_dir, repo_label="app")
    assert not errors
    kinds = sorted(r["kind"] for r in rules)
    assert kinds == ["allowed", "forbidden", "forbidden"]           # layers -> one allowed + one forbidden; forbidden -> one
    assert {r["id"] for r in load_rules(rules_dir)} == {r["id"] for r in rules}

    res = diff_commit(repo, rules_dir=rules_dir, out_dir=tmp_path / "rms")
    viol = [r for r in res["rows"] if r["label"] != "CONFIRMED"]
    conf = [r for r in res["rows"] if r["label"] == "CONFIRMED"]
    assert [(v["edge_from"], v["edge_to"], v["label"], v["acknowledged"], v["direct"]) for v in viol] == \
        [("app.ui", "app.db", "ADDITIONAL", False, True)]
    assert viol[0]["lines"][0]["line_number"] == 2
    assert [(c["edge_from"], c["edge_to"]) for c in conf] == [("app.service", "app.db")]
    assert Path(res["paths"]["sarif"]).exists()

    # the draft: first reply edits a test (refused), second deletes the unused import (passes)
    replies = tmp_path / "replies"
    replies.mkdir()
    (replies / "1.txt").write_text(textwrap.dedent("""\
        FILE: tests/test_app.py
        <<<<<<< FIND
        assert run() == 'db'
        =======
        assert True
        >>>>>>> REPLACE
        REASON: weaken the test
        """))
    (replies / "2.txt").write_text(textwrap.dedent("""\
        FILE: app/ui.py
        <<<<<<< FIND
        from app.db import connect
        =======
        >>>>>>> REPLACE
        REASON: strategy 1, connect is unused
        """))
    result, d = draft_one(repo, rules_dir=rules_dir, rms_dir=tmp_path / "rms", base_url=f"fake:{replies}",
                          tests="python -m pytest -q -p no:cacheprovider tests", log=lambda s: None)
    assert result["verdict"] == "draft_passes" and result["tries"] == 2
    assert "G0/G5" in result["attempts"][0]["problems"][0]
    assert result["attempts"][1]["g1"] == {"violation_gone": True, "new_violations": [], "violations_before": 1,
                                           "violations_after": 0, "pass": True}
    assert result["attempts"][1]["g3"]["pass"]
    assert "from app.db import connect" not in (d / "patch.diff").read_text().split("\n-")[0]
    assert json.loads((d / "result.json").read_text())["prompt_hash"]
    # the subject itself was never touched
    assert "from app.db import connect" in (repo / "app" / "ui.py").read_text()

    # the template drafter reaches the same fix without a model
    t, _ = draft_one(repo, rules_dir=rules_dir, rms_dir=tmp_path / "rms", template=True, log=lambda s: None)
    assert t["verdict"] == "draft_passes" and t["class"] == "template"

    # history: a second commit repairs it; the Differ replay + ledger see one repaired episode of 1 commit
    (repo / "app" / "ui.py").write_text("import os\n\n\ndef show():\n    return os.getcwd()\n")
    g(repo, "commit", "-qam", "repair")
    replay(repo, "main", tmp_path / "rms", rules_dir, log=lambda s: None)
    led = build(tmp_path / "rms", "t/app")
    ep = led["episodes"]
    assert len(ep) == 1 and bool(ep.repaired.iloc[0]) and ep.gap_commits.iloc[0] == 1
    assert led["drops"] == 1


def test_fault_injection_and_eval_on_the_tiny_repo(repo, tmp_path):
    """tools/fault_injection.py plants pushes on sibling branches; tools/eval_drafts.py detects every
    plant, drafts with the template and the oracle, stays silent on the control."""
    import subprocess
    import sys

    from sarms.rules.compile import compile_repo

    rules_dir = tmp_path / "rms" / "rules"
    compile_repo(repo, out_dir=rules_dir, repo_label="app")
    # the first commit already breaks ui -> db; repair it so every plant is a new violation
    (repo / "app" / "ui.py").write_text("import os\n\n\ndef show():\n    return os.getcwd()\n")
    g(repo, "commit", "-qam", "repair")
    env = {**__import__("os").environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
    root = Path(__file__).resolve().parents[1]
    p = subprocess.run([sys.executable, str(root / "tools" / "fault_injection.py"), str(repo), "--rules", str(rules_dir),
                        "--out", str(tmp_path / "rms" / "fi"), "--kinds", "unused,helper,control", "--run-id", "t"],
                       capture_output=True, text=True, env=env)
    assert p.returncode == 0, p.stderr
    plants = json.loads((tmp_path / "rms" / "fi" / "plants.json").read_text())["plants"]
    assert [x["kind"] for x in plants] == ["unused", "helper", "control"]
    assert len({x["parent"] for x in plants}) == 1                      # siblings, all from the same head
    assert g(repo, "log", "-1", "--format=%an", plants[0]["sha"]).strip() == "SARMS Test Author"
    p = subprocess.run([sys.executable, str(root / "tools" / "eval_drafts.py"), str(tmp_path / "rms" / "fi" / "plants.json"),
                        "--models", "template", "oracle", "--run-id", "t",
                        "--tests", f"{sys.executable} -m pytest tests -q -p no:cacheprovider"],
                       capture_output=True, text=True, env=env)
    assert p.returncode == 0, p.stderr
    md = (tmp_path / "rms" / "fi" / "results-t.md").read_text()
    assert "**Detection: 3/3**" in md
    assert "**template: 1/2 drafts pass**" in md and "**oracle: 2/2 drafts pass**" in md
    assert "| silent | silent |" in md
    assert g(repo, "status", "--short").strip() == ""                   # the subject's own checkout is untouched

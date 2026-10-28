"""The first real model replies (tests/fixtures/kedro_task_replies) must be rejected for the right reasons."""
import textwrap
from pathlib import Path

from sarms.synthesize.draft import apply, parse, still_imports

FIX = Path(__file__).parent / "fixtures" / "kedro_task_replies"

TASK_PY = textwrap.dedent("""\
    from __future__ import annotations

    import inspect
    from kedro.framework.project import settings


    class Task:
        def _run(self):
            if self.parallel:
                from kedro.framework.project import LOGGING, PACKAGE_NAME
                return LOGGING, PACKAGE_NAME

        def _bootstrap(self):
            from kedro.framework.project import configure_logging, configure_project
            return configure_logging, configure_project, settings.HOOKS
    """)


def make_tree(tmp_path):
    tree = tmp_path / "copy"
    (tree / "kedro" / "runner").mkdir(parents=True)
    (tree / "kedro" / "runner" / "task.py").write_text(TASK_PY)
    return tree


def test_joined_non_adjacent_lines_are_rejected(tmp_path):
    tree = make_tree(tmp_path)
    for name in ("reply1.txt", "reply3.txt"):
        blocks, reason, problems = parse((FIX / name).read_text())
        assert len(blocks) == 1 and not problems and reason.startswith("Strategy 3")
        assert apply(tree, blocks, {"kedro"})[0].endswith("first line was 'from kedro.framework.project import settings')")
        assert (tree / "kedro" / "runner" / "task.py").read_text() == TASK_PY  # nothing changed


def test_swapping_names_from_the_same_module_is_caught_statically(tmp_path):
    tree = make_tree(tmp_path)
    blocks, reason, problems = parse((FIX / "reply2.txt").read_text())
    assert not problems and apply(tree, blocks, {"kedro"}) == []
    left = still_imports(tree, ["kedro/runner/task.py"], "kedro.framework.project")
    assert len(left) == 3 and left[0].startswith("kedro/runner/task.py line 4: from kedro.framework.project import LOGGING")


def test_still_imports_sees_submodules_and_plain_imports(tmp_path):
    tree = tmp_path
    (tree / "m.py").write_text("import kedro.framework.project.settings as s\nfrom kedro.framework import project\nimport os\n")
    hits = still_imports(tree, ["m.py"], "kedro.framework.project")
    assert len(hits) == 1 and "line 1" in hits[0]

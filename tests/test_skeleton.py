"""Smoke tests that run in CI without network: the package imports and the spec validates."""
import importlib
import subprocess
import sys


def test_modules_import():
    for m in ("sarms.mining.common", "sarms.mining.first_parent", "sarms.rules.record_history",
              "sarms.replay.proxy_lint", "sarms.replay.baseline"):
        importlib.import_module(m)


def test_pseudonym_is_salted(monkeypatch, tmp_path):
    from sarms.mining import common
    monkeypatch.setenv("RMS_SALT", "a")
    one = common.pseudonym("dev@example.org")
    monkeypatch.setenv("RMS_SALT", "b")
    two = common.pseudonym("dev@example.org")
    assert one != two and len(one) == 16 and "example" not in one


def test_spec_validates():
    r = subprocess.run([sys.executable, "tools/validate_spec.py"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_first_parent_survives_control_characters_in_subjects(tmp_path):
    """PostHog has a commit subject with U+001D, which str.splitlines() treats as a line break."""
    import subprocess

    from sarms.mining.common import first_parent

    def g(*a):
        subprocess.run(["git", "-C", str(tmp_path), *a], check=True, capture_output=True)

    g("init", "-q", "-b", "main")
    g("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "first")
    g("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "fix: colo\x1drs (#1)")
    g("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "third")
    rows = first_parent(tmp_path, "main")
    assert [r[0] for r in rows] == [0, 1, 2]
    assert rows[1][3].startswith("fix: colo")

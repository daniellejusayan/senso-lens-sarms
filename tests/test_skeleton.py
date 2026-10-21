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

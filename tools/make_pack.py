"""Fill reports/p1-pack.md with the frozen files' hashes and the check results.

    uv run python tools/make_pack.py

Run after validate_spec, lint-imports, ruff and pytest; the pack records what they printed.
"""
from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

FROZEN = ["docs/repo-selection.md", "docs/spec/vocabulary.md", "docs/spec/rules.schema.yaml", "docs/spec/ledger.sql",
          "docs/spec/ledger.md", "docs/spec/decision-record.schema.json", "docs/spec/gate.md",
          "docs/spec/evaluation-protocol.md", "docs/spec/fault-injection.md", "docs/spec/failure-modes.md",
          "docs/ethics.md", "data/longlist_decisions.csv", "data/candidates.csv"]


def sh(cmd):
    p = subprocess.run(cmd, text=True, capture_output=True)
    return (p.stdout + p.stderr).strip().splitlines()[-1] if (p.stdout + p.stderr).strip() else f"exit {p.returncode}"


def main():
    pack = Path("reports/p1-pack.md")
    t = pack.read_text()
    rows = ["| File | SHA-256 |", "| --- | --- |"]
    for f in FROZEN:
        if Path(f).exists():
            rows.append(f"| `{f}` | `{hashlib.sha256(Path(f).read_bytes()).hexdigest()}` |")
    checks = ["| Check | Result |", "| --- | --- |",
              f"| `uv run lint-imports` | {sh(['uv', 'run', '--quiet', 'lint-imports'])} |",
              f"| `uv run ruff check .` | {sh(['uv', 'run', '--quiet', 'ruff', 'check', '.'])} |",
              f"| `uv run pytest -q` | {sh(['uv', 'run', '--quiet', 'pytest', '-q'])} |",
              f"| `uv run python tools/validate_spec.py` | {sh([sys.executable, 'tools/validate_spec.py'])} |"]
    import re
    t = re.sub(r"<!-- HASHES -->.*?(?=\n## )", "<!-- HASHES -->\n" + "\n".join(rows) + "\n", t, flags=re.S)
    t = re.sub(r"<!-- CHECKS -->.*$", "<!-- CHECKS -->\n" + "\n".join(checks) + "\n", t, flags=re.S)
    pack.write_text(t)
    print(f"-> {pack}")


if __name__ == "__main__":
    main()

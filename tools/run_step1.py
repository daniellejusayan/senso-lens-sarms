"""Steps 1b and 1c for one repository, in order, with timings (works on Windows, macOS, Linux).

    uv run python tools/run_step1.py kedro-org/kedro --every 1
    uv run python tools/run_step1.py LibrePhotos/librephotos --config apps/backend/pyproject.toml --src apps/backend
    uv run python tools/run_step1.py PostHog/posthog --since 2026-03-01 --every 1          # exploratory

Runs: first_parent (1b) -> record_history (1c) -> proxy_lint (1c, strict HEAD record) ->
baseline (1c). The clone is data/raw/REPO (made by tools/screen.py; made here if missing).
Each stage is skipped when its output exists unless --force. Timings go to data/REPO/timings.csv.
Use --since for very large repositories (a month before the first contract; record_history
prints that date).
"""
from __future__ import annotations

import argparse
import csv
import subprocess
import sys
import time
from pathlib import Path

from sarms.mining.common import ensure_clone, repo_name, resolve_ref


def run(label, cmd, log):
    t0 = time.time()
    print(f"== {label}: {' '.join(cmd)}", flush=True)
    p = subprocess.run(cmd, text=True, capture_output=True)
    dt = time.time() - t0
    (log.parent / f"{label}.log").write_text(p.stdout + p.stderr)
    tail = (p.stdout.strip().splitlines() or [""])[-1]
    print(f"   {dt:.0f}s  {tail}" + ("" if p.returncode == 0 else f"  [exit {p.returncode}] see {log.parent / (label + '.log')}"), flush=True)
    with open(log, "a", newline="") as fh:
        csv.writer(fh).writerow([label, f"{dt:.1f}", p.returncode])
    return p.returncode


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("owner_repo")
    ap.add_argument("--every", type=int, default=25)
    ap.add_argument("--since")
    ap.add_argument("--config", help="import-linter config path inside the repo (monorepos)")
    ap.add_argument("--src", nargs="*", help="source roots relative to the repo")
    ap.add_argument("--match", help="proxy_lint --match (message regex adding commits to the sample; '' = none)")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--skip-proxy", action="store_true", help="1b + record only (ADR-track repositories)")
    a = ap.parse_args()
    name = repo_name(a.owner_repo)
    d = ensure_clone(a.owner_repo, checkout=False)
    branch = resolve_ref(d).split("/", 1)[1]
    out = Path("data") / name
    out.mkdir(parents=True, exist_ok=True)
    log = out / "timings.csv"
    py = [sys.executable, "-m"]
    since = ["--since", a.since] if a.since else []
    cfg = ["--config", a.config] if a.config else []
    rc = 0
    if a.force or not (out / "commits.parquet").exists():
        rc |= run("first_parent", [*py, "sarms.mining.first_parent", str(d), branch, str(out / "commits.parquet")], log)
    if a.force or not (out / "record" / "events.parquet").exists():
        rc |= run("record_history", [*py, "sarms.rules.record_history", str(d), branch, str(out / "record"), *since, *cfg], log)
    if not a.skip_proxy and (a.force or not (out / "checks_sample.parquet").exists()):
        src = ["--src", *a.src] if a.src else []
        match = ["--match", a.match] if a.match is not None else []
        rc |= run("proxy_lint", [*py, "sarms.replay.proxy_lint", str(d), branch, str(out), "--every", str(a.every), *since, *cfg, *src, *match], log)
    if not a.skip_proxy and (out / "checks_sample.parquet").exists():
        rc |= run("baseline", [*py, "sarms.replay.baseline", str(out), a.owner_repo], log)
    sys.exit(1 if rc else 0)


if __name__ == "__main__":
    main()

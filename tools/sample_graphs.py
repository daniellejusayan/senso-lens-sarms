"""Import graphs at commits spread evenly over the first-parent history (for the history methods).

    uv run python tools/sample_graphs.py OWNER/REPO --n 20 [--config PATH] [--src DIR ...] [--root PKG ...] [--since YYYY-MM-DD]

Picks n commits evenly spaced over data/REPO/commits.parquet (after --since if given) and runs
sarms.graph.extract on each; a commit whose graph cannot be built (the package did not exist yet,
say) is logged to data/REPO/recovery/extract_failures.log and skipped. Existing graphs are kept.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from score_recovery import load_record, roots_of  # noqa: E402

from sarms.mining.common import repo_name  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("owner_repo")
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--since")
    ap.add_argument("--config")
    ap.add_argument("--src", nargs="*")
    ap.add_argument("--root", nargs="*")
    a = ap.parse_args()
    name = repo_name(a.owner_repo)
    data = Path("data") / name
    repo_dir = Path("data") / "raw" / name
    roots = a.root or roots_of(load_record(data))
    c = pd.read_parquet(data / "commits.parquet", columns=["idx", "sha", "ts"]).sort_values("idx")
    if a.since:
        c = c[c.ts >= pd.Timestamp(a.since, tz="UTC")]
    if len(c) > a.n:
        step = len(c) / a.n
        c = c.iloc[[int(i * step) for i in range(a.n)]]
    ok = fail = 0
    for r in c.itertuples(index=False):
        out = data / "graph" / r.sha[:12]
        if (out / "summary.json").exists():
            ok += 1
            continue
        t0 = time.time()
        cmd = [sys.executable, "-m", "sarms.graph.extract", str(repo_dir), "--sha", r.sha, "--root", *roots]
        if a.config:
            cmd += ["--config", a.config]
        if a.src:
            cmd += ["--src", *a.src]
        p = subprocess.run(cmd, capture_output=True, text=True)
        if p.returncode == 0:
            ok += 1
            print(f"  {r.sha[:8]} {str(r.ts)[:10]} {time.time() - t0:5.0f}s  {(p.stdout.strip().splitlines() or [''])[-1][:100]}", flush=True)
        else:
            fail += 1
            (data / "recovery").mkdir(parents=True, exist_ok=True)
            with open(data / "recovery" / "extract_failures.log", "a") as fh:
                fh.write(f"== {r.sha} {r.ts}\n{p.stdout}\n{p.stderr}\n")
            print(f"  {r.sha[:8]} {str(r.ts)[:10]} {time.time() - t0:5.0f}s  FAILED ({(p.stderr.strip().splitlines() or [''])[-1][:100]})", flush=True)
    print(f"{name}: {ok} graphs available, {fail} commits failed")


if __name__ == "__main__":
    main()

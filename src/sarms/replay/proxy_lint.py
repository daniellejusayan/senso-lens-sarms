"""Step 1c, part 2: the proxy run. Apply the frozen HEAD record to sampled commits.

    uv run python -m sarms.replay.proxy_lint data/raw/REPO "$BRANCH" data/REPO
    uv run python -m sarms.replay.proxy_lint data/raw/REPO "$BRANCH" data/REPO --every 1     # exact count

Sample (runbook): every 25th first-parent commit, plus every commit whose first message line
matches --match (default import|layer|architect|depend|circular|cycle|boundar|refactor),
plus the last commit. Written to data/REPO/sample.csv.

Three things this does that a `lint-imports` shell loop cannot:
  * strict record (default): every `ignore_imports` entry is removed, so the exceptions the
    team listed count as violations. Repositories that run lint-imports in CI otherwise show
    no violations at all after the contract date (kedro, as-of rules: 160 of 160 checks kept).
    --keep-ignores checks the contracts exactly as written.
  * old commits: layers are made optional (import-linter's "(layer)" syntax), and a contract
    whose modules do not exist yet is recorded as status `error`, not as a violation.
  * structured results: import-linter's own result objects, not its printed text; one worktree
    and grimp's cache are reused, so only changed files are re-parsed (kedro: 1,957 commits
    in 5 minutes).

Outputs (data/REPO/):
  checks_sample.parquet      one row per commit x contract, passes included: status
                             kept | broken | error | package_missing | graph_error, n_routes
  violations_sample.parquet  one row per violation: sha, ts, contract, edge_from (the module
                             that must not import) -> edge_to, n_routes, edges (import lines)
--rules asof checks each commit against the contracts as they were at that commit (the
replay rule of Appendix D); outputs then carry the suffix _asof.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd

from sarms.mining.common import IL_FILES, find_il_config, first_parent, git, read_il_options, resolve_ref

WORKER = Path(__file__).with_name("_lint_worker.py")
DEFAULT_MATCH = r"import|layer|architect|depend|circular|cycle|boundar|refactor"


def optional_layers(layers):
    out = []
    for line in layers:
        parts = re.split(r"(\s*[|:]\s*)", line.strip())
        out.append("".join(p if re.fullmatch(r"\s*[|:]\s*", p) or p.startswith("(") or not p
                           else f"({p})" for p in parts))
    return out


def prepare(opts, strict: bool):
    contracts = []
    for c in opts.contracts_options:
        c = dict(c)
        if strict:
            c.pop("ignore_imports", None)
        c["unmatched_ignore_imports_alerting"] = "none"
        if c.get("type") == "layers" and c.get("layers"):
            lay = c["layers"] if isinstance(c["layers"], list) else [x for x in str(c["layers"]).splitlines() if x.strip()]
            c["layers"] = optional_layers(lay)
        c.setdefault("name", c.get("id", "?"))
        contracts.append(c)
    session = dict(opts.session_options)
    if "root_packages" not in session:
        session["root_packages"] = [session.pop("root_package")]
    return session, contracts


def pythonpath(wt: Path, roots, override=None):
    if override:
        return [str(wt / p) for p in override]
    paths = []
    for r in roots:
        top = r.split(".")[0]
        for base in (wt / "src", wt, wt / "python", wt / "lib"):
            if (base / top).is_dir() or (base / f"{top}.py").exists():
                paths.append(str(base))
                break
        else:
            return None
    return list(dict.fromkeys(paths))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("repo_path")
    ap.add_argument("branch")
    ap.add_argument("out_dir")
    ap.add_argument("--every", type=int, default=25)
    ap.add_argument("--match", default=DEFAULT_MATCH, help="also sample commits whose message matches ('' = none)")
    ap.add_argument("--rules", choices=["head", "asof"], default="head")
    ap.add_argument("--keep-ignores", action="store_true")
    ap.add_argument("--since", help="YYYY-MM-DD: start of the window")
    ap.add_argument("--src", nargs="*", help="source roots relative to the repo, if auto-detection fails")
    ap.add_argument("--timeout", type=int, default=600, help="seconds per commit")
    ap.add_argument("--config", help="path of the import-linter config inside the repo when it is not at the root (monorepos)")
    a = ap.parse_args()
    strict = not a.keep_ignores
    files = [a.config] if a.config else IL_FILES
    suffix = ("" if a.rules == "head" else "_asof") + ("" if strict else "_asis")
    repo, out = Path(a.repo_path), Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    ref = resolve_ref(repo, a.branch or None)
    chain = first_parent(repo, ref, since=a.since)
    rx = re.compile(a.match, re.I) if a.match else None
    sample = [c for n, c in enumerate(chain) if n % a.every == 0 or (rx and rx.search(c[3]))]
    if sample[-1] != chain[-1]:
        sample.append(chain[-1])
    pd.DataFrame(sample, columns=["idx", "sha", "ts", "msg"]).to_csv(out / f"sample{suffix}.csv", index=False)

    if a.rules == "head":
        fname, text = find_il_config(repo, chain[-1][1], files)
        if not fname:
            sys.exit("no import-linter configuration at HEAD; this repository has no checkable record")
        session, contracts = prepare(read_il_options(fname, text), strict)
    wt = Path(f"{repo}.wt")
    if not wt.exists():
        git(repo, "worktree", "add", "--detach", "-f", str(wt.resolve()), sample[0][1])
    cache = Path(f"{repo}.ilcache").resolve()
    checks, viols, t0 = [], [], time.time()
    for n, (idx, sha, ts, _msg) in enumerate(sample, 1):
        git(wt, "checkout", "-q", "--force", sha)
        git(wt, "clean", "-fdq")
        if a.rules == "asof":
            fname, text = find_il_config(repo, sha, files)
            if not fname:
                continue
            o = read_il_options(fname, text)
            if not o:
                checks.append({"idx": idx, "sha": sha, "ts": ts, "contract": "", "type": "", "status": "config_unparseable",
                               "error": "", "n_violations": 0, "n_routes": 0})
                continue
            session, contracts = prepare(o, strict)
        base = {"idx": idx, "sha": sha, "ts": ts}
        pp = pythonpath(wt.resolve(), session["root_packages"], a.src)
        if pp is None:
            for c in contracts:
                checks.append({**base, "contract": c["name"], "type": c["type"], "status": "package_missing",
                               "error": "", "n_violations": 0, "n_routes": 0})
            continue
        spec = {"pythonpath": pp, "session_options": session, "contracts": contracts, "cache_dir": str(cache)}
        try:
            p = subprocess.run([sys.executable, str(WORKER)], input=json.dumps(spec), capture_output=True,
                               text=True, timeout=a.timeout, cwd=wt)
            res = json.loads(p.stdout.strip().splitlines()[-1]) if p.stdout.strip() else {"graph_error": p.stderr[-400:]}
        except subprocess.TimeoutExpired:
            res = {"graph_error": "timeout"}
        if "graph_error" in res:
            for c in contracts:
                checks.append({**base, "contract": c["name"], "type": c["type"], "status": "graph_error",
                               "error": res["graph_error"], "n_violations": 0, "n_routes": 0})
        else:
            for r in res["results"]:
                checks.append({**base, "contract": r["contract"], "type": r["type"], "status": r["status"],
                               "error": r["error"], "n_violations": len(r["violations"]),
                               "n_routes": sum(v["n_routes"] for v in r["violations"])})
                for v in r["violations"]:
                    viols.append({**base, "contract": r["contract"], "type": r["type"], "edge_from": v["importer"],
                                  "edge_to": v["imported"], "n_routes": v["n_routes"], "edges": v["edges"]})
        if n % 25 == 0 or n == len(sample):
            el = time.time() - t0
            print(f"  {n}/{len(sample)} commits ({el:.0f}s, ~{el / n * (len(sample) - n):.0f}s left)", flush=True)
    cdf = pd.DataFrame(checks)
    vdf = pd.DataFrame(viols, columns=["idx", "sha", "ts", "contract", "type", "edge_from", "edge_to", "n_routes", "edges"])
    for df in (cdf, vdf):
        if len(df):
            df["ts"] = pd.to_datetime(df["ts"], utc=True)
    cdf.to_parquet(out / f"checks_sample{suffix}.parquet", index=False)
    vdf.to_parquet(out / f"violations_sample{suffix}.parquet", index=False)
    st = cdf["status"].value_counts().to_dict() if len(cdf) else {}
    print(f"{len(sample)} sampled commits (every {a.every}"
          f"{', plus message matches' if rx else ''}), statuses {st}, {len(vdf)} violation rows -> {out}")


if __name__ == "__main__":
    main()

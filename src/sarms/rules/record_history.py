"""Step 1c, part 1: freeze the record and read how it changed over time.

    uv run python -m sarms.rules.record_history data/raw/REPO "$BRANCH" data/REPO/record [--since YYYY-MM-DD]

Writes into data/REPO/record/:
  importlinter.HEAD.<ext>   the HEAD configuration, copied verbatim (the frozen record)
  contracts.csv             each HEAD contract: type, introduced_sha, introduced_at
  events.parquet            every change to the record on the first-parent chain

Why not `git log --diff-filter=A`: when contracts live in pyproject.toml or setup.cfg, that
returns the day the FILE was created, not the day the contract was written. This reads the
import-linter section at every commit that touched a config file instead.

Events: contract_added / contract_removed / contract_renamed (same type and options, new
name) / contract_changed, and on the union of all `ignore_imports` entries:
debt_added and debt_removed (cause = entry_removed, usually a human repair, or
contract_removed, not a repair). Moving an entry between contracts is neither.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import pandas as pd

from sarms.mining.common import (
    IL_FILES,
    as_list,
    find_il_config,
    first_parent,
    git,
    norm_ignore,
    read_il_options,
    resolve_ref,
)


def state_at(d, sha, files=IL_FILES):
    fname, text = find_il_config(d, sha, files)
    if not fname:
        return None, {}
    opts = read_il_options(fname, text)
    if not opts:
        return fname, None
    st = {}
    for c in opts.contracts_options:
        name = c.get("name") or c.get("id") or "?"
        rest = {k: v for k, v in c.items() if k not in ("ignore_imports", "name", "id")}
        st[name] = {"type": c.get("type", "?"), "opts": json.dumps(rest, sort_keys=True, default=str),
                    "ignores": {norm_ignore(e) for e in as_list(c.get("ignore_imports"))}}
    return fname, st


def pair_renames(prev, st):
    added, removed, pairs = set(st) - set(prev), set(prev) - set(st), {}
    for r in sorted(removed):
        free = sorted(added - set(pairs.values()))
        same = [a for a in free if st[a]["type"] == prev[r]["type"] and st[a]["opts"] == prev[r]["opts"]]
        if not same:
            same = [a for a in free if st[a]["type"] == prev[r]["type"]]
            same = same if len(same) == 1 else []
        if same:
            pairs[r] = same[0]
    return pairs


def history(repo_path, branch, out_dir, since=None, extra_paths=(), config=None):
    files = [config] if config else IL_FILES
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    ref = resolve_ref(repo_path, branch)
    chain = first_parent(repo_path, ref)
    order = {sha: (idx, ts) for idx, sha, ts, _ in chain}
    head = chain[-1][1]
    fname, text = find_il_config(repo_path, head, files)
    if fname:
        ext = "toml" if fname.endswith(".toml") else "cfg"
        (out / f"importlinter.HEAD.{ext}").write_text(text)
    window = [f"--since={since}"] if since else []
    touched = git(repo_path, "log", "--first-parent", "--reverse", "--format=%H", *window, ref, "--",
                  *files, *extra_paths).split()
    events, prev, prev_union = [], {}, set()
    intro = {}
    for sha in touched:
        f, st = state_at(repo_path, sha, files)
        i, ts = order[sha]
        base = {"idx": i, "sha": sha, "ts": ts, "config_file": f or ""}
        if st is None:
            events.append({**base, "event": "config_unparseable", "contract": "", "contract_type": "", "detail": "", "cause": ""})
            continue
        ren = pair_renames(prev, st)
        for old, new in ren.items():
            events.append({**base, "event": "contract_renamed", "contract": new, "contract_type": st[new]["type"], "detail": f"was: {old}", "cause": ""})
            intro[new] = intro.pop(old, (sha, ts))
        added = set(st) - set(prev) - set(ren.values())
        removed = set(prev) - set(st) - set(ren)
        for n in sorted(added):
            events.append({**base, "event": "contract_added", "contract": n, "contract_type": st[n]["type"], "detail": "", "cause": ""})
            intro.setdefault(n, (sha, ts))
        for n in sorted(removed):
            events.append({**base, "event": "contract_removed", "contract": n, "contract_type": prev[n]["type"], "detail": "", "cause": ""})
        for n in sorted(set(st) & set(prev)):
            if st[n]["opts"] != prev[n]["opts"]:
                events.append({**base, "event": "contract_changed", "contract": n, "contract_type": st[n]["type"], "detail": "", "cause": ""})
        union = set().union(*(c["ignores"] for c in st.values())) if st else set()
        lost = set().union(*(prev[n]["ignores"] for n in removed)) if removed else set()
        owner = {e: n for n, c in st.items() for e in c["ignores"]}
        prev_owner = {e: n for n, c in prev.items() for e in c["ignores"]}
        for e in sorted(union - prev_union):
            events.append({**base, "event": "debt_added", "contract": owner.get(e, ""), "contract_type": st[owner[e]]["type"], "detail": e, "cause": ""})
        for e in sorted(prev_union - union):
            n = prev_owner.get(e, "")
            events.append({**base, "event": "debt_removed", "contract": n, "contract_type": prev.get(n, {}).get("type", ""),
                           "detail": e, "cause": "contract_removed" if e in lost else "entry_removed"})
        prev, prev_union = st, union
    df = pd.DataFrame(events, columns=["idx", "sha", "ts", "config_file", "event", "contract",
                                       "contract_type", "detail", "cause"])
    if len(df):
        df["ts"] = pd.to_datetime(df["ts"], utc=True)
    df.to_parquet(out / "events.parquet", index=False)
    with open(out / "contracts.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["contract", "type", "introduced_sha", "introduced_at"])
        for n, c in (prev or {}).items():
            s, t = intro.get(n, ("", ""))
            w.writerow([n, c["type"], s, t])
    fixed = df[(df.event == "debt_removed") & (df.cause == "entry_removed")] if len(df) else df
    first = min((t for _, t in intro.values()), default="")
    print(f"record: {fname or 'no import-linter config at HEAD'}; {len(touched)} commits touched a config file; "
          f"first contract {first[:10] if first else '-'}; exceptions added "
          f"{int((df.event == 'debt_added').sum()) if len(df) else 0}, removed {len(fixed)} "
          f"in {fixed.sha.nunique() if len(fixed) else 0} commits -> {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("repo_path")
    ap.add_argument("branch")
    ap.add_argument("out_dir")
    ap.add_argument("--since", help="YYYY-MM-DD, at least a month before the first contract")
    ap.add_argument("--extra-path", action="append", default=[], help="a config passed to lint-imports with --config")
    ap.add_argument("--config", help="path of the import-linter config inside the repo when it is not at the root (monorepos)")
    a = ap.parse_args()
    history(a.repo_path, a.branch or None, a.out_dir, a.since, a.extra_path, a.config)

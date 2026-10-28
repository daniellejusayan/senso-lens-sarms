"""Episodes: the life of one violating edge, from the commit it appears to the first later
commit without it (docs/spec/evaluation-protocol.md). Shared by the Step 1c baseline and the
ledger, so both compute the awareness gap the same way.

  violating edge   (contract, edge_from, edge_to) as import-linter reports it
  episode          consecutive checkable commits in which the edge is present
  introduced_at    first commit of the episode;  repaired_at  first later commit without it
  gap              repaired_at - introduced_at, in first-parent commits and in days
  pre-contract     the episode began before its contract was written: flagged, kept out of the gap
"""
from __future__ import annotations

import pandas as pd

OK_STATUS = ("kept", "broken")


def episodes(checks, viols, intro=None):
    """checks: one row per commit x contract with status; viols: one row per violation
    (contract, edge_from, edge_to, idx); intro: {contract: introduced timestamp}."""
    intro = intro or {}
    ok = checks[checks.status.isin(OK_STATUS)][["contract", "idx", "ts", "sha"]].sort_values("idx")
    present = set(zip(viols.contract, viols.edge_from, viols.edge_to, viols.idx, strict=True))
    rows = []
    for c, f, t in viols[["contract", "edge_from", "edge_to"]].drop_duplicates().itertuples(index=False):
        cur = None
        for idx, ts, sha in zip(*(ok[ok.contract == c][k] for k in ("idx", "ts", "sha")), strict=True):
            here = (c, f, t, idx) in present
            if here and cur is None:
                cur = (idx, ts, sha)
            elif not here and cur is not None:
                rows.append((c, f, t, *cur, idx, ts, sha))
                cur = None
        if cur is not None:
            rows.append((c, f, t, *cur, None, None, None))
    ep = pd.DataFrame(rows, columns=["contract", "edge_from", "edge_to", "start_idx", "start_ts", "start_sha",
                                     "end_idx", "end_ts", "end_sha"])
    if ep.empty:
        ep = pd.DataFrame(columns=[*ep.columns, "repaired", "gap_commits", "gap_days", "pre_contract"])
        return ep.astype({"repaired": bool, "pre_contract": bool})
    ep["start_ts"] = pd.to_datetime(ep.start_ts, utc=True)
    ep["end_ts"] = pd.to_datetime(ep.end_ts, utc=True)
    ep["end_idx"] = pd.to_numeric(ep.end_idx)
    ep["repaired"] = ep.end_idx.notna()
    ep["gap_commits"] = ep.end_idx - ep.start_idx
    ep["gap_days"] = (ep.end_ts - ep.start_ts).dt.total_seconds() / 86400
    ep["pre_contract"] = [s < intro[c] if c in intro else False for c, s in zip(ep.contract, ep.start_ts, strict=True)]
    return ep


def drops_and_rises(checks, n_routes_col="n_routes"):
    """(rises, drops): sampled intervals where the illegal-route count over the contracts
    checkable at both ends rose / fell (the old criterion 4; drops = proxy for human repair)."""
    ok = checks[checks.status.isin(OK_STATUS)]
    if n_routes_col not in ok.columns or ok.empty:
        return 0, 0
    routes = ok.groupby("idx")[n_routes_col].sum().sort_index()
    same = ok.groupby("idx").contract.nunique().sort_index()
    same = same.eq(same.shift())
    return int(((routes.diff() > 0) & same).sum()), int(((routes.diff() < 0) & same).sum())

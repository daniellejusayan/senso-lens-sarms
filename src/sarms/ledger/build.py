"""The ledger (Knowledge): one row per labelled edge per commit, in DuckDB, per docs/spec/ledger.sql.

    uv run python -m sarms.ledger.build data/kedro/rms --repo kedro-org/kedro --record data/kedro/record/contracts.csv
    uv run python -m sarms.ledger.build data/kedro/rms --repo kedro-org/kedro --from-replay data/kedro

Input is either the Differ's replay output (<rms>/differ/*.parquet) or, with --from-replay, the
Step 1c proxy run (checks_sample / violations_sample.parquet), so the ledger can be built on a
laptop without re-running the Differ over the whole history.

Writes <rms>/ledger/ledger.duckdb (table `ledger` from the spec DDL, view `awareness_gap`, plus a
supplementary `episodes` table) and <rms>/ledger/ledger.parquet. introduced_at / repaired_at come
from the episode logic in sarms.ledger.episodes, so the awareness gap here equals the Step 1c
baseline's when the input is the same. Hub-growth indicator rows (fan-in +3 and +20% within 28
days) are computed from the per-commit fan-in series when the Differ output provides it.

Known limit (spec v0): the primary key has no rule_id, so an edge that breaks two contracts
at once keeps one row (the first); none occurs in kedro. Noted for a dated amendment.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import duckdb
import pandas as pd

from sarms.ledger.episodes import drops_and_rises, episodes

DDL = Path(__file__).resolve().parents[3] / "docs" / "spec" / "ledger.sql"
VIOLATION = ("ADDITIONAL", "INVERTED", "MISSING")


def read_intro(record_csv):
    intro = {}
    if record_csv and Path(record_csv).exists():
        for r in csv.DictReader(open(record_csv)):
            if r.get("introduced_at"):
                intro[r["contract"]] = pd.Timestamp(r["introduced_at"]).tz_convert("UTC")
    return intro


def from_differ(rms_dir):
    d = Path(rms_dir) / "differ"
    edges = pd.read_parquet(d / "edges.parquet")
    checks = pd.read_parquet(d / "checks.parquet")
    inds = pd.read_parquet(d / "indicators.parquet") if (d / "indicators.parquet").exists() else pd.DataFrame()
    graphs = pd.read_parquet(d / "graphs.parquet") if (d / "graphs.parquet").exists() else pd.DataFrame()
    # n_routes per commit x contract, for drops/rises
    if len(edges):
        nr = edges[edges.label.isin(VIOLATION)].groupby(["idx", "contract"]).n_routes.sum().rename("n_routes").reset_index()
        checks = checks.merge(nr, on=["idx", "contract"], how="left").fillna({"n_routes": 0})
    else:
        checks["n_routes"] = 0
    return edges, checks, inds, graphs


def from_replay(data_dir, suffix=""):
    d = Path(data_dir)
    checks = pd.read_parquet(d / f"checks_sample{suffix}.parquet")
    v = pd.read_parquet(d / f"violations_sample{suffix}.parquet")
    edges = v.rename(columns={}).copy()
    edges["rule_id"] = None
    edges["label"] = ["INVERTED" if t == "layers" else "ADDITIONAL" for t in v["type"]]
    edges["acknowledged"] = False
    edges["direct"] = [len(e) == 1 for e in v["edges"]]
    edges["n_lines"] = 0
    return edges, checks, pd.DataFrame(), pd.DataFrame()


def hub_rows(graphs, min_gain=3, min_share=0.20, window_days=28):
    """Modules whose fan-in grew by >= min_gain and >= min_share within window_days: one row at
    the commit where the growth crossed the line (vocabulary.md, 'Hub fan-in growth')."""
    if graphs is None or graphs.empty or "fan_in" not in graphs:
        return []
    g = graphs.sort_values("idx")
    series = [(r.idx, r.sha, pd.Timestamp(r.ts), json.loads(r.fan_in)) for r in g.itertuples()]
    rows, flagged = [], set()
    for i, (idx, sha, ts, fan) in enumerate(series):
        # the earliest commit inside the window
        j = i
        while j > 0 and (ts - series[j - 1][2]).days <= window_days:
            j -= 1
        if j == i:
            continue
        base = series[j][3]
        for m, d in fan.items():
            b = base.get(m, 0)
            if d - b >= min_gain and (b == 0 or (d - b) / b >= min_share) and (m, series[j][0]) not in flagged:
                flagged.add((m, series[j][0]))
                rows.append({"idx": idx, "sha": sha, "ts": ts, "indicator": "hub", "edge_from": m,
                             "edge_to": f"fan_in:{b}->{d}", "n": d})
    return rows


def build(rms_dir, repo, record_csv=None, from_replay_dir=None, suffix=""):
    rms = Path(rms_dir)
    if from_replay_dir:
        edges, checks, inds, graphs = from_replay(from_replay_dir, suffix)
    else:
        edges, checks, inds, graphs = from_differ(rms)
    intro = read_intro(record_csv)
    viol = edges[edges.label.isin(VIOLATION)].copy()
    ep = episodes(checks, viol, intro)
    ep.insert(0, "repo", repo)
    # attach each violation row to its episode (start_idx <= idx < end_idx or open)
    ep_rows = []
    for r in ep.itertuples(index=False):
        ep_rows.append((r.contract, r.edge_from, r.edge_to, r.start_idx, r.end_idx, r.start_ts, r.end_ts))
    def episode_of(c, f, t, idx):
        for ec, ef, et, s, e, sts, ets in ep_rows:
            if (ec, ef, et) == (c, f, t) and s <= idx and (pd.isna(e) or idx < e):
                return sts, ets
        return pd.NaT, pd.NaT
    intro_at, rep_at = [], []
    for r in edges.itertuples(index=False):
        if r.label in VIOLATION:
            s, e = episode_of(r.contract, r.edge_from, r.edge_to, r.idx)
        else:
            s, e = pd.NaT, pd.NaT
        intro_at.append(s)
        rep_at.append(e)
    gh = dict(zip(graphs.sha, graphs.graph_hash, strict=True)) if len(graphs) else {}
    led = pd.DataFrame({
        "repo": repo, "sha": edges.sha, "ts": pd.to_datetime(edges.ts, utc=True),
        "graph_hash": [gh.get(s, "") or "" for s in edges.sha],
        "rule_id": edges.rule_id, "edge_from": edges.edge_from, "edge_to": edges.edge_to, "label": edges.label,
        "indicator": "none", "acknowledged": edges.acknowledged.astype(bool),
        "introduced_at": pd.to_datetime(intro_at, utc=True), "detected_at": pd.to_datetime(intro_at, utc=True),
        "repaired_at": pd.to_datetime(rep_at, utc=True), "root_cause": None, "outcome": "none", "decision_id": None})
    ind_rows = []
    if len(inds):
        ind_rows.extend(inds.to_dict("records"))
    ind_rows.extend(hub_rows(graphs))
    if ind_rows:
        idf = pd.DataFrame(ind_rows)
        led_i = pd.DataFrame({
            "repo": repo, "sha": idf.sha, "ts": pd.to_datetime(idf.ts, utc=True),
            "graph_hash": [gh.get(s, "") or "" for s in idf.sha], "rule_id": None,
            "edge_from": idf.edge_from, "edge_to": idf.edge_to.fillna(""), "label": None, "indicator": idf.indicator,
            "acknowledged": False, "introduced_at": pd.NaT, "detected_at": pd.to_datetime(idf.ts, utc=True),
            "repaired_at": pd.NaT, "root_cause": None, "outcome": "none", "decision_id": None})
        led = pd.concat([led, led_i], ignore_index=True)
    before = len(led)
    led = led.drop_duplicates(["repo", "sha", "edge_from", "edge_to", "indicator"], keep="first")
    dropped = before - len(led)

    out = rms / "ledger"
    out.mkdir(parents=True, exist_ok=True)
    led.to_parquet(out / "ledger.parquet", index=False)
    ep.to_csv(out / "episodes.csv", index=False)
    db = out / "ledger.duckdb"
    if db.exists():
        db.unlink()
    con = duckdb.connect(str(db))
    con.execute(DDL.read_text())
    con.register("led_df", led)
    con.execute("INSERT INTO ledger SELECT * FROM led_df")
    con.register("ep_df", ep)
    con.execute("CREATE TABLE episodes AS SELECT * FROM ep_df")
    con.register("checks_df", checks)
    con.execute("CREATE TABLE checks AS SELECT * FROM checks_df")
    con.close()
    rises, drops = drops_and_rises(checks)
    return {"db": str(db), "rows": len(led), "pk_collisions_dropped": dropped, "episodes": ep, "rises": rises, "drops": drops,
            "checks": checks, "edges": edges}


def summary(result, repo):
    ep = result["episodes"]
    post = ep[~ep.pre_contract.astype(bool)]
    rep = post[post.repaired.astype(bool)]
    con = duckdb.connect(result["db"], read_only=True)
    view = con.execute("""SELECT median(gap_days) FROM (SELECT DISTINCT repo, edge_from, edge_to, rule_id, introduced_at, repaired_at, gap_days
                          FROM awareness_gap WHERE repo = ?)""", [repo]).fetchone()[0]
    standing = con.execute("""SELECT count(*) FROM ledger WHERE repo = ? AND label IN ('ADDITIONAL','INVERTED','MISSING')
                              AND sha = (SELECT sha FROM ledger WHERE repo = ? ORDER BY ts DESC LIMIT 1)""", [repo, repo]).fetchone()[0]
    n_ind = con.execute("SELECT indicator, count(DISTINCT sha) FROM ledger WHERE repo = ? AND indicator <> 'none' GROUP BY 1", [repo]).fetchall()
    con.close()
    lines = [f"ledger {result['db']}: {result['rows']:,} rows",
             f"  distinct violating edges: {ep[['contract', 'edge_from', 'edge_to']].drop_duplicates().shape[0]}",
             f"  episodes after the contract: {len(post)} ({int(ep.pre_contract.sum())} pre-contract)",
             f"  repaired by a person: {len(rep)} of {len(post)}; still open: {len(post) - len(rep)}",
             f"  median gap: {rep.gap_commits.median():.0f} commits / {rep.gap_days.median():.0f} days"
             + (f" (awareness_gap view: {view:.0f} days)" if view is not None else "") if len(rep) else "  median gap: –",
             f"  rises / drops in the violation count: {result['rises']} / {result['drops']}",
             f"  violations standing at the last commit: {standing}",
             f"  drift indicator rows (commits with any): {dict(n_ind)}"]
    if result["pk_collisions_dropped"]:
        lines.append(f"  NOTE {result['pk_collisions_dropped']} rows dropped by the spec v0 primary key (edge under two rules)")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("rms_dir", help="the .rms directory (data/REPO/rms for subjects)")
    ap.add_argument("--repo", required=True, help="owner/name")
    ap.add_argument("--record", help="record/contracts.csv, for pre-contract flagging")
    ap.add_argument("--from-replay", help="data/REPO: build from the Step 1c proxy run instead of the Differ output")
    ap.add_argument("--suffix", default="")
    a = ap.parse_args()
    r = build(a.rms_dir, a.repo, a.record, a.from_replay, a.suffix)
    print(summary(r, a.repo))


if __name__ == "__main__":
    main()

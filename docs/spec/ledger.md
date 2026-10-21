# Ledger (spec v0, draft for C)

`.rms/ledger/*.parquet`, queried with DuckDB. One row per intended edge per commit, passes
included, deduplicated by `graph_hash` when the import graph did not change between commits.
The evaluation in Part 7.3 is a set of queries over this table. DDL: `docs/spec/ledger.sql`.

| Column | Type | Meaning |
| --- | --- | --- |
| repo | VARCHAR | owner/name |
| sha | VARCHAR(40) | first-parent commit |
| ts | TIMESTAMPTZ | committer time |
| graph_hash | VARCHAR | hash of the module graph; equal hash = identical graph, rows reused |
| rule_id | VARCHAR | `.rms/rules` id, NULL for an indicator row |
| edge_from, edge_to | VARCHAR | the module that imports, the module imported |
| label | VARCHAR | CONFIRMED, MISSING, ADDITIONAL, INVERTED (NULL for an indicator row) |
| indicator | VARCHAR | none, unassigned, cycle, hub |
| acknowledged | BOOLEAN | the edge matches an `ignore_imports` exception |
| introduced_at | TIMESTAMPTZ | first commit of this deviation's episode |
| detected_at | TIMESTAMPTZ | when the system reported it (equals introduced_at in replay) |
| repaired_at | TIMESTAMPTZ | first later commit without it; NULL while open |
| root_cause | VARCHAR | one of the five root-cause labels, NULL until Synthesize runs |
| outcome | VARCHAR | none, applied, left_standing, amended_by_human, reverted, escalated (point 7: the system applies; humans audit afterwards) |
| decision_id | VARCHAR | `.rms/decisions/<sha>.json` that decided it |

Example queries:

```sql
-- awareness gap (days) of repaired, unacknowledged erosion
SELECT repo, median(date_diff('day', introduced_at, repaired_at)) AS median_gap_days
FROM ledger
WHERE label IN ('ADDITIONAL', 'INVERTED') AND NOT acknowledged AND repaired_at IS NOT NULL
GROUP BY repo;

-- commits that reduced the violation count (criterion 4)
WITH v AS (SELECT repo, sha, ts, count(*) FILTER (WHERE label IN ('ADDITIONAL','INVERTED','MISSING')) AS n
           FROM ledger GROUP BY repo, sha, ts)
SELECT repo, count(*) FROM (SELECT repo, n - lag(n) OVER (PARTITION BY repo ORDER BY ts) AS d FROM v) WHERE d < 0 GROUP BY repo;
```

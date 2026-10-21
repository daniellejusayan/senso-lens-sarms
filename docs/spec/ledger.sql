-- Ledger DDL (spec v0). Load: duckdb ledger.duckdb < docs/spec/ledger.sql
CREATE TABLE ledger (
  repo           VARCHAR NOT NULL,
  sha            VARCHAR NOT NULL,
  ts             TIMESTAMPTZ NOT NULL,
  graph_hash     VARCHAR NOT NULL,
  rule_id        VARCHAR,
  edge_from      VARCHAR NOT NULL,
  edge_to        VARCHAR NOT NULL,
  label          VARCHAR CHECK (label IN ('CONFIRMED', 'MISSING', 'ADDITIONAL', 'INVERTED')),
  indicator      VARCHAR NOT NULL DEFAULT 'none' CHECK (indicator IN ('none', 'unassigned', 'cycle', 'hub')),
  acknowledged   BOOLEAN NOT NULL DEFAULT FALSE,
  introduced_at  TIMESTAMPTZ,
  detected_at    TIMESTAMPTZ,
  repaired_at    TIMESTAMPTZ,
  root_cause     VARCHAR CHECK (root_cause IN ('requirement realization', 'documentation lag',
                                               'implementation choice', 'behavioral defect', 'mixed')),
  outcome        VARCHAR NOT NULL DEFAULT 'none'
                 CHECK (outcome IN ('none', 'applied', 'left_standing', 'amended_by_human', 'reverted', 'escalated')),
  decision_id    VARCHAR,
  CHECK (label IS NOT NULL OR indicator <> 'none'),
  PRIMARY KEY (repo, sha, edge_from, edge_to, indicator)
);

CREATE VIEW awareness_gap AS
SELECT repo, edge_from, edge_to, rule_id, introduced_at, repaired_at,
       date_diff('day', introduced_at, repaired_at) AS gap_days
FROM ledger
WHERE label IN ('ADDITIONAL', 'INVERTED', 'MISSING') AND repaired_at IS NOT NULL;

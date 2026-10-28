"""sarms — the command line (Stage 1). Each subcommand is one stage of the MSV-K loop.

    uv run sarms compile REPO [--sha S] [--out DIR]          contracts -> rule bundle (.rms/rules)
    uv run sarms check   REPO [--sha S] [--rules DIR] [--out DIR]   the Differ on one commit, in plain words
    uv run sarms replay  REPO BRANCH OUT [--rules DIR] [--every K]  the Differ over the history -> parquet
    uv run sarms ledger  RMS --repo OWNER/NAME [--record CSV] [--from-replay DATA]
    uv run sarms draft   REPO [--rules DIR] [--rms DIR] [--edge "a -> b" | --pick direct] [--tests CMD] [--template]

Subjects keep their bundle and outputs under data/REPO/rms (never inside data/raw); a repository
that runs sarms on itself (Term 2) keeps them in its own .rms/.
"""
from __future__ import annotations

import sys


def main() -> None:
    argv = sys.argv[1:]
    cmds = {"compile": "sarms.rules.compile", "check": "sarms.differ.diff", "replay": "sarms.differ.replay",
            "ledger": "sarms.ledger.build", "draft": "sarms.synthesize.draft"}
    if not argv or argv[0] in ("-h", "--help") or argv[0] not in cmds:
        print(__doc__)
        sys.exit(0 if argv and argv[0] in ("-h", "--help") else 2)
    import importlib
    mod = importlib.import_module(cmds[argv[0]])
    sys.argv = [f"sarms {argv[0]}", *argv[1:]]
    mod.main()

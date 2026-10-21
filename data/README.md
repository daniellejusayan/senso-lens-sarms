# data/ — what is here and what is not in git

| Path | Written by | In git? | Contents |
| --- | --- | --- | --- |
| `Step1_usable_repos_230.csv`, `Step1_near_miss_203.csv` | the team (Step 1 sheets, 20 Oct) | yes | the 230-row longlist and the 203-row reserve pool, as received |
| `longlist_decisions.csv`, `longlist.txt` | `tools/reduce_longlist.py` | yes | every longlist row with kept/dropped and the rule (R1–R5); the kept rows in screen.py's input format |
| `candidates_seed.csv` | `tools/screen.py`, 19 Oct | yes | the 15 seed repositories screened before the longlist existed |
| `candidates.csv` | `tools/screen.py`, 21 Oct | yes | the 38 longlist survivors measured on criteria 1–8 (3 and 4 filled from tests.csv and the baseline summary when they exist) |
| `tests.csv` | `tools/check_tests.sh` | yes | criterion 3: install + test wall time per repository |
| `samples/precision_100.csv`, `samples/rootcause_50.csv` | `tools/draw_sample.py` | yes | the drawn labelling cases (committed before anyone looks at them) |
| `raw/<repo>/` | `tools/screen.py` / `ensure_clone` | **no** | partial clones (`--filter=blob:none`); re-created by running screen.py |
| `raw/<repo>.wt`, `raw/<repo>.ilcache` | `sarms.replay.proxy_lint` | **no** | one reused worktree and grimp's cache per replayed repository |
| `<repo>/commits.parquet` | `sarms.mining.first_parent` | **no** (Parquet is ignored) | the first-parent chain: idx, sha, ts, author_ts, author_hash (salted), is_merge, n_files, py_files, msg, pr_number |
| `<repo>/record/` | `sarms.rules.record_history` | **no** | `importlinter.HEAD.*`, `contracts.csv`, `events.parquet` (contract added/removed/changed, exceptions added/removed) |
| `<repo>/checks_sample*.parquet`, `violations_sample*.parquet`, `sample*.csv` | `sarms.replay.proxy_lint` | **no** | one row per commit × contract; one row per violating edge |
| `<repo>/episodes*.csv`, `timings.csv` | `sarms.replay.baseline`, `tools/run_step1.py` | **no** | violation episodes (introduced → repaired) and stage timings |

Everything marked **no** is reproduced from the clone by `tools/run_step1.py OWNER/REPO`; the
Steps 1–2 data pack (`sarms-steps-1-2-data.zip`) carries a snapshot of it for the team.
Author e-mails appear nowhere: `author_hash` is a salted SHA-256 (see `docs/ethics.md`).

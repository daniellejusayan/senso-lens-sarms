# Awareness-gap baseline (proxy run, Step 1c)

Strict HEAD record applied to first-parent commits (every commit where the table says stride 1; otherwise every 25th plus commits whose message names imports, layers, dependencies, cycles or refactoring). Exceptions in `ignore_imports` count as violations. Pre-contract episodes are in the series but not in the gap. Windowed runs (--since) start a month before the first contract.

| Repository | Sampled | Edges | Episodes | Repaired | Median gap (commits / days) | Drops (C4) | Exception removals |
| --- | --- | --- | --- | --- | --- | --- | --- |
| kedro-org/kedro  | 1957 | 16 | 28 | 19 | 92.0 / 155.8 | 4 | 3 |
| wemake-services/wemake-python-styleguide  | 3148 | 5 | 1 | 1 | 32.0 / 13.6 | 3 | 3 |
| bridgecrewio/checkov  | 2695 | 25 | 1 | 0 | – / – | 6 | 5 |
| sqlfluff/sqlfluff  | 1986 | 8 | 3 | 0 | – / – | 1 | 0 |
| ag2ai/faststream  | 1624 | 80 | 0 | 0 | – / – | 3 | 0 |
| Qiskit/qiskit-serverless  | 1868 | 2 | 0 | 0 | – / – | 1 | 0 |
| ramses-rf/ramses_rf  | 4699 | 21 | 6 | 1 | 143.0 / 25.3 | 13 | 0 |

## bridgecrewio/checkov

Record: 6 contracts, first written 2023-08-06.
Sampled 2695 first-parent commits, 2023-06-01 to 2026-10-20, median stride 1 (resolution ±1 commits). Statuses: {'kept': 12863, 'broken': 2695, 'error': 612}.

| Measure | Value |
| --- | --- |
| Distinct violating edges seen | 25 |
| Episodes (after the contract / pre-contract) | 1 / 24 |
| Share later repaired (after the contract) | 0 of 1 (0%) |
| Gap, commits: median (p90) | – |
| Gap, days: median (p90) | – |
| Rises / drops in the violation count (criterion 4 = drops) | 3 / 6 |
| Commits that removed an `ignore_imports` exception | 5 |

Longest repaired gaps:

- none repaired in the window
Caveat: resolution is the sampling stride (±1 commits); Weeks 2–3 recompute per commit with the Differ.

## ag2ai/faststream

Record: 8 contracts, first written 2026-09-20.
Sampled 1624 first-parent commits, 2022-12-01 to 2026-10-19, median stride 1 (resolution ±1 commits). Statuses: {'broken': 7151, 'package_missing': 2320, 'error': 1927, 'kept': 1594}.

| Measure | Value |
| --- | --- |
| Distinct violating edges seen | 80 |
| Episodes (after the contract / pre-contract) | 0 / 80 |
| Share later repaired (after the contract) | 0 of 0 (0%) |
| Gap, commits: median (p90) | – |
| Gap, days: median (p90) | – |
| Rises / drops in the violation count (criterion 4 = drops) | 30 / 3 |
| Commits that removed an `ignore_imports` exception | 0 |

Longest repaired gaps:

- none repaired in the window
Caveat: resolution is the sampling stride (±1 commits); Weeks 2–3 recompute per commit with the Differ.

## kedro-org/kedro

Record: 4 contracts, first written 2019-08-13.
Sampled 1957 first-parent commits, 2019-05-16 to 2026-10-19, median stride 1 (resolution ±1 commits). Statuses: {'broken': 4174, 'kept': 3650, 'package_missing': 4}.

| Measure | Value |
| --- | --- |
| Distinct violating edges seen | 16 |
| Episodes (after the contract / pre-contract) | 28 / 0 |
| Share later repaired (after the contract) | 19 of 28 (68%) |
| Gap, commits: median (p90) | 92 (p90 285) |
| Gap, days: median (p90) | 156 (p90 430) |
| Rises / drops in the violation count (criterion 4 = drops) | 7 / 4 |
| Commits that removed an `ignore_imports` exception | 3 |

Longest repaired gaps:

- `kedro.runner → kedro.config` (Runner et al cannot import Config): introduced [9039f82a](https://github.com/kedro-org/kedro/commit/9039f82a31c5826672758d19d00d14feb9349e8c) 2020-07-16, gone at [e6cfb423](https://github.com/kedro-org/kedro/commit/e6cfb42373398bef2dc0c19d24e62373e34780e3) 2022-03-31, 492 commits / 623 days
- `kedro.runner → kedro.framework.session` (CLI > Context > Library, Runner > Extras > IO & Pipeline): introduced [1bb5f4be](https://github.com/kedro-org/kedro/commit/1bb5f4be6fc4e6ef7a5a9480131cbce4582385c9) 2020-12-17, gone at [e6cfb423](https://github.com/kedro-org/kedro/commit/e6cfb42373398bef2dc0c19d24e62373e34780e3) 2022-03-31, 355 commits / 469 days
- `kedro.pipeline → kedro.framework.session` (CLI > Context > Library, Runner > Extras > IO & Pipeline): introduced [1ed504cf](https://github.com/kedro-org/kedro/commit/1ed504cf52067d516490e8118a7b602a498cd856) 2025-01-15, gone at [257c2bd3](https://github.com/kedro-org/kedro/commit/257c2bd3e2cdc5707c413392abbb7bd08059dedf) 2026-03-11, 267 commits / 420 days

Caveat: resolution is the sampling stride (±1 commits); Weeks 2–3 recompute per commit with the Differ.

## Qiskit/qiskit-serverless

Record: 3 contracts, first written 2026-02-16.
Sampled 1868 first-parent commits, 2022-09-15 to 2026-10-21, median stride 1 (resolution ±1 commits). Statuses: {'graph_error': 3591, 'kept': 1971, 'broken': 42}.

| Measure | Value |
| --- | --- |
| Distinct violating edges seen | 2 |
| Episodes (after the contract / pre-contract) | 0 / 2 |
| Share later repaired (after the contract) | 0 of 0 (0%) |
| Gap, commits: median (p90) | – |
| Gap, days: median (p90) | – |
| Rises / drops in the violation count (criterion 4 = drops) | 1 / 1 |
| Commits that removed an `ignore_imports` exception | 0 |

Longest repaired gaps:

- none repaired in the window
Caveat: resolution is the sampling stride (±1 commits); Weeks 2–3 recompute per commit with the Differ.

## ramses-rf/ramses_rf

Record: 4 contracts, first written 2026-06-27.
Sampled 4699 first-parent commits, 2019-11-25 to 2026-10-20, median stride 1 (resolution ±1 commits). Statuses: {'package_missing': 11404, 'broken': 4915, 'error': 1328, 'kept': 1145, 'graph_error': 4}.

| Measure | Value |
| --- | --- |
| Distinct violating edges seen | 21 |
| Episodes (after the contract / pre-contract) | 6 / 19 |
| Share later repaired (after the contract) | 1 of 6 (17%) |
| Gap, commits: median (p90) | 143 (p90 143) |
| Gap, days: median (p90) | 25 (p90 25) |
| Rises / drops in the violation count (criterion 4 = drops) | 27 / 13 |
| Commits that removed an `ignore_imports` exception | 0 |

Longest repaired gaps:

- `ramses_rf.models → ramses_rf.protocol` (ramses_rf CQRS Architecture Layers): introduced [7cfc9e59](https://github.com/ramses-rf/ramses_rf/commit/7cfc9e59f4f3d6e4cc1a2faa60ace969b4d85d7b) 2026-06-27, gone at [1542d396](https://github.com/ramses-rf/ramses_rf/commit/1542d3969cc2b39ef8cc9e3f56e665b3d22ab7a2) 2026-07-22, 143 commits / 25 days

Caveat: resolution is the sampling stride (±1 commits); Weeks 2–3 recompute per commit with the Differ.

## sqlfluff/sqlfluff

Record: 4 contracts, first written 2023-08-29.
Sampled 1986 first-parent commits, 2023-06-03 to 2026-10-20, median stride 1 (resolution ±1 commits). Statuses: {'kept': 5425, 'broken': 2250, 'error': 269}.

| Measure | Value |
| --- | --- |
| Distinct violating edges seen | 8 |
| Episodes (after the contract / pre-contract) | 3 / 7 |
| Share later repaired (after the contract) | 0 of 3 (0%) |
| Gap, commits: median (p90) | – |
| Gap, days: median (p90) | – |
| Rises / drops in the violation count (criterion 4 = drops) | 4 / 1 |
| Commits that removed an `ignore_imports` exception | 0 |

Longest repaired gaps:

- none repaired in the window
Caveat: resolution is the sampling stride (±1 commits); Weeks 2–3 recompute per commit with the Differ.

## wemake-services/wemake-python-styleguide

Record: 6 contracts, first written 2019-07-28.
Sampled 3148 first-parent commits, 2018-03-09 to 2026-10-19, median stride 1 (resolution ±1 commits). Statuses: {'kept': 13846, 'broken': 3208, 'error': 1816, 'package_missing': 18}.

| Measure | Value |
| --- | --- |
| Distinct violating edges seen | 5 |
| Episodes (after the contract / pre-contract) | 1 / 4 |
| Share later repaired (after the contract) | 1 of 1 (100%) |
| Gap, commits: median (p90) | 32 (p90 32) |
| Gap, days: median (p90) | 14 (p90 14) |
| Rises / drops in the violation count (criterion 4 = drops) | 3 / 3 |
| Commits that removed an `ignore_imports` exception | 3 |

Longest repaired gaps:

- `wemake_python_styleguide → dataclasses` (Forbids to import anything from dependencies): introduced [7354cb0d](https://github.com/wemake-services/wemake-python-styleguide/commit/7354cb0dc51d5ffad4a4b9fd87efef903b1ba2fd) 2021-01-27, gone at [f246606e](https://github.com/wemake-services/wemake-python-styleguide/commit/f246606ef2a9428042fbf156e553588a0cdc282c) 2021-02-10, 32 commits / 14 days

Caveat: resolution is the sampling stride (±1 commits); Weeks 2–3 recompute per commit with the Differ.

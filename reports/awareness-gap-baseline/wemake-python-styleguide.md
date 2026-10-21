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

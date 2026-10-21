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

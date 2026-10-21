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

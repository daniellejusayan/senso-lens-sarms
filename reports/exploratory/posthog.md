## PostHog/posthog


Exploratory, detection only: this repository fails selection criteria 5–7 and is not a subject; its numbers are reported for what they show about repair behaviour, never used for drafts.

Record: 6 contracts, first written 2026-04-15.
Sampled 663 first-parent commits, 2026-03-01 to 2026-10-21, median stride 50 (resolution ±50 commits). Statuses: {'broken': 1817, 'kept': 1641, 'package_missing': 520}.

| Measure | Value |
| --- | --- |
| Distinct violating edges seen | 111 |
| Episodes (after the contract / pre-contract) | 101 / 22 |
| Share later repaired (after the contract) | 22 of 101 (22%) |
| Gap, commits: median (p90) | 1200 (p90 5305) |
| Gap, days: median (p90) | 5 (p90 27) |
| Rises / drops in the violation count (criterion 4 = drops) | 82 / 30 |
| Commits that removed an `ignore_imports` exception | 59 |

Longest repaired gaps:

- `products.logs.backend.presentation → products.cdp.backend` (presentation must use facade): introduced [c87eae49](https://github.com/PostHog/posthog/commit/c87eae496b43013e7629b772c0ffacefbbe4b58e) 2026-06-18, gone at [efc0b0d8](https://github.com/PostHog/posthog/commit/efc0b0d8dd99c7724fc4c900541e154807d4961f) 2026-08-26, 10950 commits / 69 days
- `products.product_analytics.backend.presentation → products.annotations.backend` (presentation must use facade): introduced [4100cddc](https://github.com/PostHog/posthog/commit/4100cddce34b21894e2fb94d03e883f516f6fe08) 2026-08-20, gone at [6d129743](https://github.com/PostHog/posthog/commit/6d129743e835fc052b64770d6a7800e4c2a33e1e) 2026-09-18, 5350 commits / 29 days
- `products.data_warehouse.backend.presentation → products.revenue_analytics.backend` (presentation must use facade): introduced [c42a91ed](https://github.com/PostHog/posthog/commit/c42a91edcad7edd3aa830db51c4b7cd93fb7f774) 2026-06-25, gone at [8fb5a830](https://github.com/PostHog/posthog/commit/8fb5a83091e8c7ef0949887156446f03f8b7e1cf) 2026-07-22, 4300 commits / 27 days

Caveat: resolution is the sampling stride (±50 commits); Weeks 2–3 recompute per commit with the Differ.

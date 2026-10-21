# ADR track: monocongo/climate_indices

24 ADR files at `d8a5f133`; first added 2026-08-08, last 2026-10-18; 18 flagged structural by keyword screen (≥ 2 distinct terms) — the candidates for rule compilation.

| Added | Title | Status | Structural terms |
| --- | --- | --- | --- |
| 2026-08-08 | [Dual numpy and xarray public APIs](https://github.com/monocongo/climate_indices/blob/d8a5f133ba88/docs/adr/0001-dual-numpy-xarray-api.md) |  | depend interface layer module package |
| 2026-08-08 | [Multiprocessing for the CLI, Dask for the xarray API](https://github.com/monocongo/climate_indices/blob/d8a5f133ba88/docs/adr/0002-multiprocessing-cli-dask-xarray.md) |  | dependency importing layer layers |
| 2026-09-13 | [Fire APIs are namespaced in the `fire` package](https://github.com/monocongo/climate_indices/blob/d8a5f133ba88/docs/adr/0005-fire-module-api.md) |  | import module modules package |
| 2026-09-13 | [Recursive fire indices use explicit state and a pure-NumPy baseline](https://github.com/monocongo/climate_indices/blob/d8a5f133ba88/docs/adr/0006-fire-recursive-state-and-execution.md) |  | boundary depend dependency layer |
| 2026-09-15 | [Recursive fire indices never bridge missing days by default](https://github.com/monocongo/climate_indices/blob/d8a5f133ba88/docs/adr/0007-fire-missing-data-policy.md) |  | boundary package |
| 2026-09-17 | [Seasonal carry is an explicit in-season mask](https://github.com/monocongo/climate_indices/blob/d8a5f133ba88/docs/adr/0010-seasonal-carry-is-an-explicit-mask.md) |  | boundaries boundary package should not |
| 2026-09-18 | [The xarray DataArray API stays Beta through 3.0.0 and is promoted no earlier than 3.1.0](https://github.com/monocongo/climate_indices/blob/d8a5f133ba88/docs/adr/0012-xarray-api-stays-beta-through-3.0.0.md) |  | boundaries interface |
| 2026-09-23 | [Flood APIs are namespaced in the `flood` package, with `edi` also at the package root](https://github.com/monocongo/climate_indices/blob/d8a5f133ba88/docs/adr/0013-flood-module-api-and-naming.md) |  | import interface module modules package |
| 2026-09-23 | [Flood-family scientific conventions, and what stays out of scope](https://github.com/monocongo/climate_indices/blob/d8a5f133ba88/docs/adr/0014-flood-family-scientific-conventions.md) |  | boundary circular dependencies layer must not package |
| 2026-09-28 | [Zero handling in standardized indices](https://github.com/monocongo/climate_indices/blob/d8a5f133ba88/docs/adr/0015-zero-handling-in-standardized-indices.md) |  | package packages |
| 2026-10-08 | [Rust core as an acceleration backend](https://github.com/monocongo/climate_indices/blob/d8a5f133ba88/docs/adr/0017-rust-core-acceleration-backend.md) |  | boundary import importing imports module |
| 2026-10-08 | [Optional-Rust packaging: hatchling artifacts beside maturin binary wheels](https://github.com/monocongo/climate_indices/blob/d8a5f133ba88/docs/adr/0018-optional-rust-packaging.md) |  | boundaries boundary dependencies dependency import imports package |
| 2026-10-15 | [Energy APIs are namespaced in the `energy` package, and the standardize seam gains an aggregation](https://github.com/monocongo/climate_indices/blob/d8a5f133ba88/docs/adr/0019-energy-module-api-and-aggregation.md) |  | boundary dependencies dependency import layer module modules package |
| 2026-10-15 | [The generic standardization seam ships recipes, one neutral CF entry, and a wired xarray path](https://github.com/monocongo/climate_indices/blob/d8a5f133ba88/docs/adr/0020-standardized-index-public-surface.md) |  | module package |
| 2026-10-16 | [The crate publishes to crates.io as `climate-indices` on an independent 0.x track](https://github.com/monocongo/climate_indices/blob/d8a5f133ba88/docs/adr/0021-climate-indices-crate-identity.md) |  | boundary depend dependency import module package |
| 2026-10-17 | [Compound-analysis contracts](https://github.com/monocongo/climate_indices/blob/d8a5f133ba88/docs/adr/0022-compound-analysis-contracts.md) |  | boundaries boundary circular depend dependencies dependency import layer module modules must not package should not |
| 2026-10-17 | [The Rust API retains borrowed ndarray views and typed, extensible errors](https://github.com/monocongo/climate_indices/blob/d8a5f133ba88/docs/adr/0023-rust-public-api.md) |  | boundary depend dependencies dependency import imports modules package |
| 2026-10-18 | [Beta distribution for a bounded series](https://github.com/monocongo/climate_indices/blob/d8a5f133ba88/docs/adr/0024-beta-distribution-for-bounded-series.md) |  | boundaries boundary module package |

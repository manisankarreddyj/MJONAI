# ENGINE TRIAGE — File-by-File Disposition Plan

**Date:** 2026-08-22
**Scope:** every file in `mjonai-build/engine/` (113 files, ~9,700 lines)
**Goal:** dissolve `engine/` into `mjonai-build/` — one codebase, build conventions, no drift.
**Method:** every file gets exactly one verdict:

| Verdict | Meaning |
|---|---|
| **ABSORB** | Build has no equivalent; logic is useful → move into build, renamed to build conventions. Tests move with it. |
| **PORT→ARCHIVE** | Build already has similar logic → port any engine-only *fix* into the build file, then archive engine's copy. |
| **ARCHIVE** | Dead, stale, or superseded → move to archive (never hard-delete). |
| **FLATTEN** | Part of an over-layered group → merge into one module during absorption. |

**Iron rule:** the 2026-08-22 measurement fixes (next-open entries, gap fills, slippage, real Sharpe/Sortino, embargo, one-position rule, coverage-aware cache) are pinned by 53 passing tests and MUST survive the merge. No verdict may discard them.

---

## Summary

| Verdict | Files | ~Lines | Notes |
|---|---|---|---|
| ABSORB (into build) | 54 | ~5,100 | backtest core, analytics math, research/walk-forward/optimization, storage, market-data research path, instruments |
| PORT→ARCHIVE | 19 | ~1,300 | strategies (8+registry+dummy), Strategy ABC, broker cost models, indicators (compare first) |
| ARCHIVE | 22 | ~3,000 | portfolio pretense, 4 root experiment scripts, 12 network "tests", misc |
| FLATTEN | 6 | ~250 | composition layers (bootstrap/factory/context/pipeline/data_loader) → one builder |
| **Total** | **113** | **~9,700** | End state: `engine/` directory ceases to exist |

---

## 1. `engine/analytics/` — 6 files, 753 lines

| File | Lines | What it does | Verdict | Destination / Notes |
|---|---|---|---|---|
| `metrics.py` | 231 | Per-trade stats (win rate, PF on gross P&L, expectancy, streaks). Fixed 2026-08-22: breakeven excluded, gross PF. | **ABSORB** | → `analytics/trade_metrics.py`. Compare with build `analytics/strategy_metrics.py` at merge time; port corrections there if it duplicates. |
| `performance_metrics.py` | 231 | Risk-adjusted stats from daily equity series (Sharpe, Sortino, CAGR, Calmar, MAR). Today's flagship fix. | **ABSORB** | → `analytics/risk_metrics.py`. Build's `analytics/performance_metrics.py` (250 ln, Supabase-dict-based live reporting) is a *different* data model — keep both, do not merge blindly. |
| `equity.py` | 107 | Equity curve + drawdown from closed trades. | **ABSORB** | → `analytics/equity_curve.py` |
| `models.py` | 82 | TradeStatistics / EquityStatistics / PerformanceStatistics / PerformanceReport dataclasses. | **ABSORB** | → `analytics/models.py` (build has no analytics models file) |
| `performance.py` | 49 | PerformanceAnalyzer composition of the three calculators. | **ABSORB** | → `analytics/analyzer.py` |
| `report.py` | 23 | Console pretty-printer. | **ARCHIVE** | Superseded by runner table output. |

## 2. `engine/backtest/` — 5 files + 5 test files, ~1,120 lines

| File | Lines | What it does | Verdict | Destination / Notes |
|---|---|---|---|---|
| `trade_simulator.py` | 264 | Single-trade fill simulation. Gap-aware exits (2026-08-22 fix). | **ABSORB** | → `research/backtest/trade_simulator.py` |
| `backtest_engine.py` | 129 | Orchestrates signals → trades. Next-open entry + one-position-per-symbol (2026-08-22 fixes). | **ABSORB** | → `research/backtest/engine.py` |
| `models.py` | 133 | TradeResult / BacktestResult / EquityCurve / EquityPoint. | **ABSORB** | → `research/backtest/models.py` |
| `test_trade_simulator.py` | 230 | Fill-semantics regression tests. | **ABSORB** (with module) | pytest, keep green |
| `test_backtest_engine.py` | 93 | Pipeline end-to-end test. | **ABSORB** (with module) | |
| `test_no_lookahead.py` | 119 | Entry-timing regression test. | **ABSORB** (with module) | |
| `test_gap_fills.py` | 81 | Gap-fill regression test. | **ABSORB** (with module) | |
| `test_one_position.py` | 80 | Overlap-skip regression test. | **ABSORB** (with module) | |

## 3. `engine/common/` — 3 files, 77 lines

| File | Lines | What it does | Verdict | Destination / Notes |
|---|---|---|---|---|
| `enums.py` | 65 | Provider / Exchange / AssetType / Direction / OrderType / ProductType enums. | **ABSORB** | → `core/enums.py` (new). Build currently scatters these (e.g. `DataProvider` inside `data/angelone/historical.py`) — consolidate carefully, one enum set. |
| `constants.py` | 8 | 5 trivial constants (project name, tz, storage root). | **ABSORB** | Fold into build `core/constants.py` (already a god module — P2-1; add, don't grow further) |
| `types.py` | 4 | `PathLike` alias. | **ARCHIVE** | Inline where needed. |

## 4. `engine/core/` — 2 files, 180 lines

| File | Lines | What it does | Verdict | Destination / Notes |
|---|---|---|---|---|
| `strategy.py` | 107 | Research `Strategy` ABC + `StrategyResult`. | **PORT→ARCHIVE** | Duplicate of build `strategy/registry/base.py` (`BaseStrategy` + `StrategySignalResult`, richer: validation, execute_safe, asset-class gating). Research will target the **registry** ABC via a thin adapter. Archive after rewire. |
| `strategy_runner.py` | 73 | Historical replay loop (expanding windows, 200-bar warmup). | **ABSORB** | → `research/runner.py`. Build has no equivalent. |

## 5. `engine/execution/` — 9 files, 324 lines

| File | Lines | What it does | Verdict | Destination / Notes |
|---|---|---|---|---|
| `brokers/zerodha.py` | 104 | Zerodha delivery cost model + slippage_bps (2026-08-22). | **PORT→ARCHIVE** | Build `execution/tax.py` (242 ln) is richer (STT intraday/delivery/F&O, CTT, stamp, GST, turnover charges). Port the **slippage_bps parameter** into build's cost layer; archive. |
| `brokers/angel_one.py` | 41 | Stub model (slippage only). | **ARCHIVE** | Build tax.py already covers Angel charges properly. |
| `brokers/shoonya.py` | 41 | Stub model (slippage only). | **ARCHIVE** | Same. |
| `brokers/base.py` | 24 | BrokerCostModel ABC. | **ARCHIVE** | With registry. |
| `brokers/registry.py` | 28 | Name→model registry. | **ARCHIVE** | Over-abstraction for 3 models. |
| `brokers/enums.py` | 11 | Broker enum. | **ARCHIVE** | |
| `costs.py` | 55 | TransactionCostCalculator facade. | **ARCHIVE** | After slippage port. |
| `models.py` | 14 | `TransactionCost` dataclass. | **ABSORB** | → `execution/costs.py` (new; build has breakdown functions but no cost DTO). |
| `enums.py` | 17 | Order side enums. | **ARCHIVE** | Build `core/constants.py` covers these. |

## 6. `engine/indicators/` — 1 file, 97 lines

| File | Lines | What it does | Verdict | Destination / Notes |
|---|---|---|---|---|
| `momentum.py` | 97 | ema, rsi (Wilder), atr, sma, bollinger, donchian, vwap. | **PORT→ARCHIVE** | Build `strategy/registry/indicators.py` is the canonical indicator module. Diff the two; port any missing function (donchian, vwap likely) into registry's file; archive. **Do not keep two indicator libraries.** |

## 7. `engine/instruments/` — 5 files, 488 lines

| File | Lines | What it does | Verdict | Destination / Notes |
|---|---|---|---|---|
| `models.py` | 76 | Provider-neutral `Instrument` dataclass (symbol/token/exchange/asset_type/lot/tick/expiry/strike). | **ABSORB** | → `data/instruments/models.py`. Build's token_map is Angel-CSV-specific; this is the neutral model. |
| `master.py` | 157 | In-memory catalog with symbol/token/exchange/asset-type indexes + search. | **ABSORB** | → `data/instruments/master.py`. Supersedes ad-hoc lookups in token_map.py over time (do not rip out token_map in this pass). |
| `normalizer.py` | 140 | Angel scrip-master row → Instrument (instrumenttype mapping, option/future/index classification). | **ABSORB** | → `data/angelone/normalize.py` (next to its data source). |
| `providers/angel_provider.py` | 93 | Downloads Angel public scrip-master JSON (~10MB, no auth). | **ABSORB** | → `data/angelone/scrip_master.py`. |
| `base_provider.py` | 22 | InstrumentProvider ABC. | **ABSORB** | With models. |

## 8. `engine/market_data/` — 9 files, 466 lines

| File | Lines | What it does | Verdict | Destination / Notes |
|---|---|---|---|---|
| `service.py` | 161 | Coverage-aware cache service (2026-08-22 fix: serves only ranges the cache spans; prints HIT/MISS). | **ABSORB** | → `research/data/market_data.py` (research data path; build's `data/angelone/historical.py` remains the live path). |
| `providers/yahoo_provider.py` | 92 | yfinance fetch, auto_adjust=True (2026-08-22 fix), MultiIndex flatten. | **ABSORB** | → `research/data/providers/yahoo.py` |
| `base_provider.py` | 21 | HistoricalDataProvider ABC. | **ABSORB** | With service. |
| `models.py` | 35 | Candle / HistoricalData. | **ABSORB** | With service. |
| `requests.py` | 23 | HistoricalDataRequest. | **ABSORB** | |
| `responses.py` | 18 | HistoricalDataResponse. | **ABSORB** | |
| `timeframe.py` | 31 | TimeFrame enum (tick→monthly). | **ABSORB** | → `core/timeframe.py` or keep in research/data. |
| `downloader/historical_downloader.py` | 89 | Bulk download loop with per-symbol progress. | **ABSORB** | → `research/data/downloader.py` (prefills the parquet cache for a universe). |
| `downloader/jobs.py` + `update_service.py` | 71 | DownloadJob/Result DTOs; daily-update convenience. | **ABSORB** (flatten) | Fold jobs DTOs into downloader module; drop update_service wrapper. |

## 9. `engine/optimization/` — 6 files, 355 lines

| File | Lines | What it does | Verdict | Destination / Notes |
|---|---|---|---|---|
| `models.py` | 72 | ParameterDefinition / ParameterSet / OptimizationResult / Summary. | **ABSORB** | → `research/optimization/models.py` |
| `parameters.py` | 72 | Cartesian grid generator. | **ABSORB** | → `research/optimization/grid.py` |
| `grid_search.py` | 72 | Sharpe ranking + min_trades gate (2026-08-22). | **ABSORB** | → `research/optimization/grid_search.py` |
| `engine.py` | 56 | Runs→results summarizer. | **FLATTEN** | Merge into grid_search module. |
| `optimizer.py` | 18 | Single-method ABC. | **ARCHIVE** | Useless abstraction (one impl). |
| `research_optimizer.py` | 65 | Pipeline-driving optimizer. | **ABSORB** | → `research/optimization/optimizer.py` |

## 10. `engine/portfolio/` — 6 files, 462 lines

| File | Lines | What it does | Verdict | Destination / Notes |
|---|---|---|---|---|
| `trade_processor.py` | 137 | Post-simulation sizing + cost application + affordability clamp (2026-08-22 fix lives here). | **PORT→ARCHIVE** | Port the clamp + cost application **into** `research/backtest/engine.py` during absorption (removes the simulate-then-size convolution); archive. |
| `capital.py` | 99 | CapitalManager (allocate/release/apply P&L). | **ARCHIVE** | Backtests don't need a treasury; live capital belongs to build `risk/` + `execution/`. |
| `models.py` | 93 | Capital/Position dataclasses. | **ARCHIVE** | With capital.py. |
| `portfolio.py` | 87 | Portfolio aggregate. | **ARCHIVE** | With capital.py. |
| `position.py` | 2 | Re-export. | **ARCHIVE** | |
| `position_sizer.py` | 44 | Fixed-risk sizer. | **ARCHIVE** | If risk-based sizing is wanted in backtests later, implement inline (~15 lines) at portfolio level in build `risk/`. |

## 11. `engine/research/` — 14 files, 876 lines

| File | Lines | What it does | Verdict | Destination / Notes |
|---|---|---|---|---|
| `walk_forward_windows.py` | 68 | Window generator with embargo_days (2026-08-22 fix). | **ABSORB** | → `research/walk_forward/windows.py` |
| `walk_forward_models.py` | 28 | Window/Result/Summary dataclasses. | **ABSORB** | → `research/walk_forward/models.py` |
| `walk_forward_engine.py` | 117 | Per-window optimize→validate with deepcopy isolation (2026-08-22 fix). | **ABSORB** | → `research/walk_forward/engine.py` |
| `research_engine.py` | 85 | Data→signals→trades→report orchestrator. | **ABSORB** (flatten) | → `research/pipeline.py` (single module) |
| `pipeline.py` | 43 | Thin data_loader+engine wrapper. | **FLATTEN** | Into the above. |
| `data_loader.py` | 52 | Per-instrument fetch loop. | **FLATTEN** | Into the above. |
| `factory.py` | 41 | Composition factory + back-compat wrapper. | **FLATTEN** | Into one `research/builder.py`. |
| `bootstrap.py` | 70 | Wires Angel instruments + Yahoo + storage + pipeline. | **FLATTEN** | Into builder. |
| `context.py` | 19 | ResearchContext DTO. | **ABSORB** | Into config module. |
| `config.py` | 20 | ResearchConfig DTO. | **ABSORB** | → `research/config.py` |
| `models.py` | 23 | ResearchResult DTO. | **ABSORB** | With pipeline. |
| `dynamic_exits.py` | 75 | ATR stop + R:R target (signal-bar ATR, entry-anchored — 2026-08-22 contract). | **ABSORB** | → `research/exits.py` |
| `universe.py` | 41 | Symbol→Instrument resolution over master. | **ABSORB** | → `research/universe.py` |
| `universe_loader.py` | 99 | Nifty 50/Bank/IT/Auto/Pharma/500 lists. **BUG: NIFTY500_CSV_PATH points to `mjonai-build/mjonai-build/data/...` (double path segment) → NIFTY_500 tier silently falls back to the hardcoded Nifty 50 list.** | **ABSORB** | → `research/universe.py` (merge with above) + **fix path** (the CSV already lives inside build). |

## 12. `engine/strategies/` — 10 files, 894 lines

| File | Lines | What it does | Verdict | Destination / Notes |
|---|---|---|---|---|
| `s01_momentum_rsi.py` … `s08_intraday_all_day.py` | 894 total | Research reimplementations of S01–S08. **All drift from the live `strategy/registry/` versions (e.g. registry S01 is v6.0, research copy is v1.0 — different logic).** | **PORT→ARCHIVE** | Research must run the **registry** strategies via a thin adapter (~100 lines, new file `research/registry_adapter.py`). After parity is documented, archive all 8. |
| `registry.py` | 63 | Research strategy registry. | **PORT→ARCHIVE** | Replaced by adapter over build `strategy/registry/__init__.py`. |
| `dummy_strategy.py` | 41 | Test fixture strategy. | **ABSORB** | → `research/testing/dummy.py` (used by pipeline tests). |

Registry strategies with **no** research copy (research never reached them): `macro_commodity_crypto`, `options_theta_decay`, `pairs_trading`, `volume_profile` (+ `intraday_all_day` exists on both sides). The adapter makes all of them researchable for the first time.

## 13. `engine/storage/` — 4 files, 230 lines

| File | Lines | What it does | Verdict | Destination / Notes |
|---|---|---|---|---|
| `parquet_store.py` | 127 | Parquet persistence with **merge-on-save** (2026-08-22 fix). | **ABSORB** | → `storage/parquet_store.py` (build `storage/` currently holds only runtime journals). |
| `service.py` | 49 | StorageService facade. | **ABSORB** | With store. |
| `models.py` | 24 | StorageKey / StorageRange. | **ABSORB** | With store. |
| `base.py` | 30 | StorageBackend ABC. | **ABSORB** | With store. |

## 14. Root-level experiment scripts — 4 files, 2,411 lines

| File | Lines | What it does | Verdict | Notes |
|---|---|---|---|---|
| `s01_1month_simulation.py` | 448 | One-off July-2026 bull-month S01 replay with its own tax/tranche logic. | **ARCHIVE** | Uncontrolled duplicate of backtest concerns; superseded by the fixed engine running registry strategies. |
| `s01_realtime_walkthrough.py` | 350 | Minute-by-minute narrative walkthrough for S01. | **ARCHIVE** | Same. |
| `simulation_harness.py` | 903 | 1-minute multi-strategy regime-adaptive orchestrator (own ADX, strike resolver, tranche logic). | **ARCHIVE** | Same — but note its regime-adaptive activation idea is worth re-considering *after* edges exist (park in docs). |
| `unconstrained_strategy_benchmark.py` | 710 | 12-strategy isolation benchmark with own MTM/taxes/Greeks. | **ARCHIVE** | Same. |

These four are the "duplicate backtests" problem the docs already flagged — they reimplement fills, taxes and sizing with no tests and no shared code.

## 15. `engine/tests/` — 20 files, ~1,076 lines

**Move with their modules (pytest, keep green):**
`test_analytics.py`, `test_metrics_corrections.py`, `test_performance_metrics.py`, `test_trade_processor.py`*, `test_walk_forward_embargo.py`, `test_grid_search_ranking.py`, `test_market_data_cache.py` (+ the 5 backtest tests in §2).
\* trade_processor tests get rewritten against the new inlined logic during Phase 4.

**Archive (execute live network calls at import time; not real tests):**
`test_angel_download.py`, `test_angel_instrument_provider.py`, `test_angel_profile.py`, `test_angel_raw_profile.py`, `test_angel_unknown_asset_types.py`, `test_angel_unknown_exchange.py`, `test_downloader.py`, `test_instrument_master.py`, `test_market_data.py`, `test_s01_strategy.py`, `test_strategy_registry.py`, `test_universe.py`.
Optionally convert the instrument/universe ones into proper mocked pytest tests in a later pass.

---

## Bugs & findings discovered during triage (beyond the 2026-08-22 log)

1. **`universe_loader.py` broken NIFTY_500 path** — resolves to `mjonai-build/mjonai-build/data/angelone/nifty500_tokens.csv` (double segment); silently falls back to hardcoded Nifty 50. Fix during absorption.
2. **Research never covered 4 of the live strategies** (macro_commodity_crypto, options_theta_decay, pairs_trading, volume_profile) — the registry adapter closes this gap.
3. **The four root scripts are uncontrolled backtest duplicates** (~2,400 lines of untested fill/tax/sizing logic) — the exact pattern that produced the invalid-results era.
4. **The old `engine/tests` "suite" was mostly smoke scripts**, giving false confidence — real coverage existed only for the pieces added on 2026-08-22.

---

## Merge plan (phases, each ending green tests + commit)

**Phase 0 — Clean base (prerequisite, user action):** commit or branch the uncommitted runtime refactor in `mjonai-build`. Merging into a dirty tree tangles two changes.

**Phase 1 — New home:** create `research/` package in build (`research/backtest/`, `research/data/`, `research/optimization/`, `research/walk_forward/`), `storage/parquet_store.py`, `analytics/` additions, `data/instruments/`, `core/enums.py`. Move ABSORB files + their tests. Rewire `run_research.py` / `run_walk_forward.py` / `run_optimization.py` imports. Engine untouched and still working at phase end.

**Phase 2 — Strategies:** write `research/registry_adapter.py`; run parity diff (engine S01 vs registry S01 v6.0 on same data — document the divergence); rewire research to registry strategies; archive `engine/strategies/`.

**Phase 3 — Costs:** port `slippage_bps` into build `execution/tax.py` cost path; archive `engine/execution/brokers/` + `costs.py`.

**Phase 4 — Portfolio removal:** inline affordability clamp + cost application into the backtest engine; archive `engine/portfolio/`.

**Phase 5 — Cleanup:** flatten composition layers; archive root scripts + network tests + `engine/core/strategy.py` + `engine/indicators` (after diff); fix universe_loader path; final sweep → `engine/` directory removed; update `MJONAI_DOCS.md` architecture section + `QUANTITATIVE_METHODOLOGY_FINDINGS.md` resolution log.

**Verification gate per phase:** full engine pytest suite green; `run_research.py` produces identical baseline numbers (where behavior is meant to be unchanged); explicit-path git commits only.

---

## Open questions (decide before/during execution)

1. **Destination naming**: `research/` package at build top level — OK? (Build's old `research/` scripts were deleted in your refactor, so the name is free.)
2. **Instrument layer**: absorb into new `data/instruments/` (proposed) vs folding into `data/angelone/` only?
3. **`simulation_harness.py`'s regime-adaptive activation idea** — archive now and re-evaluate later (recommended), or promote to a documented parked idea in MJONAI_DOCS.md?
4. **Intraday strategies** (S08, options/volume-profile/pairs): daily-bar research cannot validate them fairly — defer their research until an intraday data path exists (recommended), or invest in Angel historical 1-min data pipeline first?

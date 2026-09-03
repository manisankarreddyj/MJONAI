# F&O Spike 1+2 — Data Foundation Report

**Date:** 2026-08-25 · **Status:** WORKING DRAFT → merge key facts into MJONAI_DOCS §9 on acceptance
**Scope:** free historical F&O data sources (verified), minute-data validation vs exchange truth, EOD chain ingester build-out.

---

## 1. Verified source map

| Source | Role | Evidence |
|---|---|---|
| NSE UDiFF bhavcopy (`nsearchives.nseindia.com/content/fo/BhavCopy_NSE_FO_0_0_0_<date>_F_0000.csv.zip`) | **Exchange ground truth** + EOD warehouse backbone | HTTP-200 verified for current dates; legacy `archives.nseindia.com fo*bhav.csv.zip` works pre-UDiFF |
| HuggingFace `thetrademarkk/india-index-options-1m` | **Minute-level options research substrate** | Downloaded complete: **771 files / 1.84 GB** at `storage/temp/hf/` |
| jugaad-data | Legacy-era fetch tool only | Works ≤2024-05 era; **broken on UDiFF dates** ("not a zip"); license = YOLO (wrap-as-tool, never vendor) |
| Angel One SmartAPI | Forward-recorder ONLY | Admin-confirmed: no expired-contract history; tokens recycle |
| MoneyTicks / ZeroBrokerageClub / CloudTraderPro / ShoonyaTrader | Supplementary cross-checks / redundancy | Unaudited depth yet |
| PyZData | Kite enctoken scraper | ToS-gray; personal use at best |

## 2. Minute-data validation (HF dataset vs exchange)

Method: per contract-day, last 1-min bar close/OI vs same-day bhavcopy fields.

### Price validation — PASSED after reference correction
| Index | vs `ClsPric` | vs `LastPric` |
|---|---|---|
| NIFTY (50 contracts) | 62.0% | **100.0%** |
| BANKNIFTY (237) | 33.8% | **100.0%** |

`LastPric` sits inside the final bar's high/low in 100% of cases; mismatch timestamps cluster at 15:28–15:30.
**Root cause of apparent mismatch:** NSE's `ClsPric` is the computed closing price (closing-window VWAP), not the last trade. HF bars carry true last-trade prices. **Validation standard = LastPric.**

### OI validation — FAILED (do not trust HF `open_interest`)
3.6% match vs EOD OI on NIFTY sample. Field shows zeros mid-sequence, non-monotonic, uncorrelated with cumulative volume ⇒ semantics unknown/garbage.
**Rule: OI must come from bhavcopy (authoritative), never from the minute feed.**

### Known limitations (accepted for research use)
- Coverage bias: liquid/near strikes only (NIFTY day-sample: 55 of 152 bhav contracts)
- Freshness lag ≈ 7 weeks behind live
- "Educational use" license on HF set — fine for research phase, revisit before commercialization
- Zero duplicate keys, zero out-of-session bars (clean structure)

## 3. stocks_options census
284 files / **14 underlyings** (ADANIENT deepest: 43 expiries, 60 MB; sample window Jan→Feb 2023, full sessions). Partial and dated — index options are the strong asset; stock-option minute history remains a forward-record/vendor gap.

## 4. Ingester built (this wave)
- `research/data/fno_eod.py` — canonical schema (`trade_date, underlying, kind OPT/FUT, option_type CE/PE, strike, expiry, OHLC/last/settle/prev_close, underlying_price, volume, turnover, trades, oi, oi_change, lot_size`), UDiFF parser + legacy fallback, idempotent month-partitioned writer (`storage/parquet/fno_chain/eod/{YYYY-MM}.parquet`)
- `run_fno_backfill.py` — CLI (`--start --end [--underlying]`)
- **Bug caught by self-audit before trust:** modern UDiFF ships `CE/PE` directly; my CA/PA-only map nulled every option_type and dedupe collapsed strike pairs (~50% silent row loss). Fixed identity-preserving; smoke re-verified (Aug 18–19: 35,433 + 35,588 rows; NIFTY lots=65, CE/PE balanced).
- 12-month backfill (2025-08-01 → 2026-08-22): **COMPLETE** — 260 trading days ingested, 16 exchange-closed days skipped, **10,092,514 rows / 240 underlyings / 241 MB** across 13 month-partitions (`storage/parquet/fno_chain/eod/`), verified by independent disk re-read (the run's `rows_total=105,504,693` console figure is the superseded cumulative-months metric — disk truth is authoritative). Per-month rows grow Aug-25 594k → Mar-26 917k (chain breadth expanding).

## 5. Deferred / next waves
1. Backfill completion + DuckDB convenience view over `fno_chain`
2. IV/Greeks/spread enrichment (port logic from darshkale/sajal pipelines after license check)
3. Factor wiring: PCR / max-pain / OI-buildup / premium-decay → Gate 1 honest factors
4. ~~SENSEX/BSE ground-truth source~~ — **DESCOPED by owner (2026-08-25): NSE-only universe.** HF set still carries usable SENSEX minute files if ever needed
5. Margin engine study before any selling strategy; forward-recorder decision post-PAPER

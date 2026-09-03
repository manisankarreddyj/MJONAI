# F&O Spike 1 — Historical Index-Options Data Quality Report

**Date:** 2026-08-25 · **Dataset:** HuggingFace `thetrademarkk/india-index-options-1m` · **Status:** COMPLETE — dataset adopted with usage rules

---

## 1. What was pulled

Full archive to `mjonai-build/storage/temp/hf/` (gitignored): **771 parquet files / 1.84 GB**, integrity-passed (size-checked re-pull = 0 missing).

| Section | Files | Size | Content |
|---|---|---|---|
| `index/` | 3 | 24 MB | NIFTY (from 2021-05-24), BANKNIFTY (2021-05-27), SENSEX (2022-09-01) — 1-min OHLCV |
| `options/` | 477 | 1.60 GB | Per-expiry chains: NIFTY ×267, SENSEX ×148, BANKNIFTY ×62 expiries |
| `stocks_options/` | 284 | 0.21 GB | Stock-option expiries (coverage depth TBD in spike 2) |
| `mcx/` | 7 | <10 MB | Commodities spot |

Options schema verified as advertised: `timestamp` (IST tz-aware), OHLCV, `open_interest`, `trading_day`, `symbol`, `strike`, `option_type` (CE/PE), `expiry`.

## 2. Exchange ground-truth reconciliation (NIFTY expiry 2026-08-04 vs UDiFF bhavcopy, session 2026-07-02)

| Check | Result | Interpretation |
|---|---|---|
| Contract coverage | **55 of 152** bhav contracts present (36%) | Confirmed liquid-strike bias — far/illiquid strikes absent |
| Price accuracy | median err **₹0.000**; 65.5% within ±(0.1%+5p); worst ≈ ₹6 on ₹510 (~1.2%) | Minute closes are trade-print based; last print ≠ official close on thin names. Exact when liquid |
| **`open_interest` field** | **UNRELIABLE — DISCARD.** Sample contract: mostly zeros, non-monotonic, negatively correlated with cumulative volume | Do not use for any OI analytics; EOD OI must come from bhavcopy instead |
| Structure | 0 duplicate keys · 0 pre-open/post-close bars · no contract-day exceeds 380 bars · median 331 bars/day (~88% minute fill) | Clean session discipline |

## 3. Known limitations

1. **Freshness lag:** dataset snapshot trails its own expiry labels by ~4–7 weeks (file `2026-08-04` ends at session 2026-07-02).
2. **Coverage survivorship:** only liquid strikes recorded; unusable for far-strike/wings research.
3. **OI unusable** (above); **stock-option depth** not yet profiled (spike 2).
4. License: "educational use" — acceptable for research phase; revisit before commercialization.
5. Community provenance: no SLA; mitigated by bhavcopy cross-validation (this report's method).

## 4. Ground-truth tooling proven during spike

- **UDiFF bhavcopy (current era):** `https://nsearchives.nseindia.com/content/fo/BhavCopy_NSE_FO_0_0_0_YYYYMMDD_F_0000.csv.zip` — works with plain UA header. This becomes our EOD chain ingester AND validator.
- **Pre-UDiFF eras:** `jugaad-data.bhavcopy_fo_save()` works (installed in venv; YOLO license → dev-tool only, never vendored).
- Resumable downloader: `planning/fno/_hf_pull.py`; file inventory: `planning/supabase/_hf_inventory.json`.

## 5. Usage rules going forward (binding for research)

1. Prices: usable for near-ATM strategies; any study depending on closing values must re-validate sampled contract-days against bhavcopy.
2. OI: source exclusively from bhavcopy ingester output; ignore HF `open_interest`.
3. Far strikes: treat as nonexistent in this dataset.
4. Freshness: append newer sessions via own nightly recorder before trusting "current" research windows.

## 6. Next steps proposed

- Spike 2: profile `stocks_options/` depth + BANKNIFTY/SENSEX reconciliation spot-checks
- Build the bhavcopy ingester (both era patterns proven) → EOD chain + OI warehouse in `storage/parquet/fno_chain/`
- Then factor wiring: PCR / max-pain / OI-buildup / premium-decay into Gate 1 evidence

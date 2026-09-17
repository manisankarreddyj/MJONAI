# NIFTY 50 PIT membership ledger — provenance

This directory is the point-in-time (PIT) universe source for research
backtests. It is a **curated, hard-scoped** reference: NIFTY 50 only, as of
the vendoring date.

## Data file

`nifty50_membership_history.csv` — half-open membership intervals
`[valid_from, valid_to)` per NSE index constituent.

- 83 rows, 82 distinct symbols, 50 open legs (null `valid_to` = still a member).
- Coverage: 2014-01-01 → present. **Nothing before 2014-01-01 is claimable** —
  the loader fails closed if asked for an `asof` earlier than coverage starts.
- Sources: `snapshot_floor` (50 rows, pre-2017 baseline) + `press_release`
  (33 rows, 2017+ — each with the linked NSE press release PDF).
- One re-introduction is present (GRASIM: 2014–2017, exited, re-added 2018) —
  the loader returns **all** legs per symbol, never a single span.

## Upstream

- Dataset: `aditya-jha/nse-historical-membership`
  <https://github.com/aditya-jha/nse-historical-membership>
  — CSV in `index_history/data/index_membership_history.csv`.
- **License: CC BY 4.0 (data)** / MIT (code). Attribution must be preserved;
  see the repository's LICENSE. This file is derived from that dataset with
  no modifications beyond subsetting to Nifty 50 rows.
- Primary sources used upstream: NSE index press releases
  (<https://www.nseindia.com/regulations/listing-compliance/index-surveillance/index-constituent-shareholding>)
  and NSE published constituent CSV files.

## Why this exists (Decision 6 Phase 3)

Phase 3 = point-in-time universe. The prior hardcoded `SECTOR_UNIVERSES`
lists in `research/universe_loader.py` are a **today-snapshot** — using them
for a 2018→2026 backtest lets symbols that joined the index in 2024 trade in
2018 bars (survivorship bias). The PIT ledger routes `load_universe_symbols`
through true membership as-of a date and masks signals to membership
intervals inside the walk-forward / backtest engines.

## Refresh procedure

Re-download the upstream CSV, subset to the desired `index_name`, and commit
both files together plus any expectation changes in
`tests/research/test_pit_universe.py`. The loader is data-driven over the
file, so a refresh is a data-only change unless a new index is added.
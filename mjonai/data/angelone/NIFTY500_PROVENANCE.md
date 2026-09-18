# NIFTY 500 token file — provenance

`nifty500_tokens.csv` is the **today-snapshot** universe backing the
`NIFTY_500` research tier (`mjonai/research/universe_loader.py`). It is the
file the H1 fix (2026-08-24) demanded before the tier could be run, and it is
now vendored (2026-09-17).

## Data file

`nifty500_tokens.csv` — one `name` column (the NSE symbol), 499 rows, sorted
alphabetically. Read by `load_universe_symbols(tier=NIFTY_500)`; `max_count`
caps how many are returned.

## Upstream

- Dataset: `aditya-jha/nse-historical-membership`
  <https://github.com/aditya-jha/nse-historical-membership>
  — CSV in `index_history/data/index_membership_history.csv`, subset to
  `index_name = "Nifty 500"` rows whose `valid_to` is empty (open legs).
- **License: CC BY 4.0 (data)** / MIT (code). Attribution must be preserved;
  see the repository's LICENSE and the Nifty 50 ledger's PROVENANCE
  (`mjonai/data/pit/PROVENANCE.md`), which uses the same upstream.
- Extraction date: 2026-09-17. The file's newest membership entry is
  `valid_from = 2026-03-31`, so the snapshot reflects index changes through
  that quarter's press releases (includes 360ONE, AADHARHFC, ACMESOLAR —
  names absent from older third-party lists).

## Honesty caveat (must be stated in any report)

This is a **current-snapshot** universe, NOT point-in-time. A backtest over
2018→2026 using this file lets a symbol that joined the index in 2025 trade in
2018 bars — survivorship bias. The Nifty 50 ledger is the only PIT-capable
tier (Phase 3 hard-scope, `pit_universe.py`). NIFTY_500 PIT history is future
work; until then every NIFTY_500 result carries this caveat.

## Refresh procedure

Re-download the upstream CSV, subset to Nifty 500 open legs, and commit the
new file plus this note. The loader is data-driven over the file, so a refresh
is a data-only change.
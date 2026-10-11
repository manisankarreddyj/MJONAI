# Vendored: shiyu-coder/Kronos — ADR-0012 adoption record

- **Upstream:** https://github.com/shiyu-coder/Kronos (MIT, AAAI 2026 paper arXiv:2508.02739)
- **Adopted by:** ADR-0012 (research tier only — `docs/decisions/ADR-0012-kronos-tsfm.md`)
- **Fetched by:** `tools/scripts/fetch_kronos.py` (network-gated heredoc: `MJONAI_FETCH_KronOS=1`)
- **License:** MIT — vendoring + local modification permitted; this tree is the pinned snapshot of record.

## Layout
- `model.py`, `predictor.py`, `tokenizer.py` (+ examples) — upstream code, pinned
- Weights live OUTSIDE this tree at `storage/models/kronos/` (HuggingFace `NeoQuasar/Kronos-mini` + `NeoQuasar/Kronos-Tokenizer-2k`)

## MJONAI integration
- Adapter: `mjonai/research/forecasting/kronos_adapter.py` (ForecastModel port; Capitalized-OHLCV mapping; lazy load; fail-closed `ForecastUnavailableError` — never fabricates)
- Benchmark: `apps/research/run_forecast_benchmark.py --models kronos_mini` (both tables, net of canonical friction)
- Evidence: `storage/research_evidence/forecast_benchmark_*.json`

## Verdict (2026-10-11, mini tier): FAILED the ADR-0002 bar
Worst MAE (31.64), 42.0% dir-acc, 0.0% q10–q90 coverage, net −25.31% vs seasonal_naive −5.63% on RELIANCE daily, 60 origins. **Not a signal. Any UI surfacing this model must disclose the failed verdict.**

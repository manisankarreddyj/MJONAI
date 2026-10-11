# Forecast research ops — running the ADR-0002 benchmark

Owner-machine runbook for the forecasting layer (`mjonai/research/forecasting/`). Core venv/CI stay torch-free; every TSFM step here is research-opt-in.

## One-time setup (research venv)
```powershell
D:\MJONAI\.venv\Scripts\python.exe -m pip install -r requirements-research-ml.txt
$env:MJONAI_FETCH_KronOS=1
D:\MJONAI\.venv\Scripts\python.exe tools\scripts\fetch_kronos.py
```
Weights land in `storage/models/kronos/` (currently Kronos-mini + Kronos-Tokenizer-2k). Without torch or weights the adapters raise `ForecastUnavailableError` — fail-closed, never fabricated numbers.

## Classical baselines (always available, no torch)
```powershell
D:\MJONAI\.venv\Scripts\python.exe apps\research\run_forecast_benchmark.py `
  --symbol RELIANCE --tf 1d --start 2022-01-01 --max_origins 60 `
  --models seasonal_naive,rw_drift,exp_smoothing
```

## Kronos (or TimesFM) — research-opt-in tiers
```powershell
... --models seasonal_naive,rw_drift,exp_smoothing,kronos_mini
... --models kronos_small,kronos_base     # fails closed until those weights exist
... --timesfm                              # adapter present; verdict not yet recorded
```

## Reading the verdict (ADR-0002 bar)
- **Table 1 — accuracy:** MAE / directional accuracy / q10–q90 coverage per model on identical origins.
- **Table 2 — trading-edge gate:** the median path drives a long/flat policy, charged 11.42 bps round-trip friction derived from the canonical `execution/tax.py` (ADR-0003).
- **Adoption bar:** a TSFM must beat the baselines on **BOTH** tables; adoption itself additionally requires full-pipeline risk-adjusted improvement. Statistical floor: <30 pooled origins is a coin flip, not a verdict.
- Every run persists `storage/research_evidence/forecast_benchmark_<UTC>.json` (params + both tables + git revision).

## Current verdicts
- Classical (RELIANCE daily, 60 origins): every policy loses net of costs (−5.6% to −66.4%) — no daily-edge.
- Kronos-mini (2026-10-11, same run): FAILS the bar — see `docs/decisions/ADR-0012-kronos-tsfm.md`.

## Pitfalls
- Never chart a Kronos band without the failed-verdict disclosure inline (PWA strip included).
- Do not compute bands on intraday bars: mini was validated on daily bars only.
- Re-fetching a higher tier is a new experiment: run the benchmark, record the artifact, update ADR-0012.

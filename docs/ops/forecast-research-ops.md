# Forecast research ops — running the ADR-0002 benchmark

Owner-machine runbook for the forecasting layer (`mjonai/research/forecasting/`). Core venv/CI stay torch-free; every TSFM step here is research-opt-in.

## One-time setup (research venv)
```powershell
D:\MJONAI\.venv\Scripts\python.exe -m pip install -r requirements-research-ml.txt
$env:MJONAI_FETCH_KronOS=1
D:\MJONAI\.venv\Scripts\python.exe tools\scripts\fetch_kronos.py
```
Weights land in `storage/models/kronos/` (currently Kronos-mini + Kronos-Tokenizer-2k). Without torch or weights the adapters raise `ForecastUnavailableError` — fail-closed, never fabricated numbers.

### TimesFM 3.0 weights
```powershell
D:\MJONAI\.venv\Scripts\python.exe -m pip install timesfm
```
`google/timesfm-3.0-pytorch` is **1.32 GB** and must land in `storage/models/timesfm-3.0-pytorch/` (`config.json` + `model.safetensors`). huggingface.co is DNS-blocked on the owner machine — stream from the mirror instead:
```powershell
D:\MJONAI\.venv\Scripts\python.exe -c "import requests,os; d=r'storage\models\timesfm-3.0-pytorch'; os.makedirs(d,exist_ok=True); [open(os.path.join(d,n),'wb').write(requests.get('https://hf-mirror.com/google/timesfm-3.0-pytorch/resolve/main/'+n,timeout=60).content) for n in ('config.json','LICENSE')]; r=requests.get('https://hf-mirror.com/google/timesfm-3.0-pytorch/resolve/main/model.safetensors',stream=True,timeout=120); f=open(os.path.join(d,'model.safetensors'),'wb'); [f.write(c) for c in r.iter_content(1<<20)]; f.close()"
```
**Licensing:** the 3.0 weights are non-commercial/non-production — fine for MJONAI's personal paper-only posture; TimesFM ≤2.5 weights stay Apache-2.0 if commercial clearance is ever needed.

## Classical baselines (always available, no torch)
```powershell
D:\MJONAI\.venv\Scripts\python.exe apps\research\run_forecast_benchmark.py `
  --symbol RELIANCE --tf 1d --start 2022-01-01 --max_origins 60 `
  --models seasonal_naive,rw_drift,exp_smoothing
```

## Kronos / TimesFM — research-opt-in tiers
```powershell
... --models seasonal_naive,rw_drift,exp_smoothing,kronos_mini
... --models kronos_small,kronos_base     # fails closed until those weights exist
... --models seasonal_naive,rw_drift,exp_smoothing,timesfm   # local weights dir preferred
```

## Reading the verdict (ADR-0002 bar)
- **Table 1 — accuracy:** MAE / directional accuracy / q10–q90 coverage per model on identical origins.
- **Table 2 — trading-edge gate:** the median path drives a long/flat policy, charged 11.42 bps round-trip friction derived from the canonical `execution/tax.py` (ADR-0003).
- **Adoption bar:** a TSFM must beat the baselines on **BOTH** tables; adoption itself additionally requires full-pipeline risk-adjusted improvement. Statistical floor: <30 pooled origins is a coin flip, not a verdict.
- Every run persists `storage/research_evidence/forecast_benchmark_<UTC>.json` (params + both tables + git revision).

## Current verdicts
- Classical (RELIANCE daily, 60 origins): every policy loses net of costs (−5.6% to −66.4%) — no daily-edge.
- Kronos-mini (2026-10-11, same run): FAILS the bar — see `docs/decisions/ADR-0012-kronos-tsfm.md`.
- TimesFM 3.0 (2026-10-11, RELIANCE daily, 300 origins): FAILS the bar — net −15.00% (only negative vs classicals +41.97..+86.53%); artifact `storage/research_evidence/forecast_benchmark_20261011_182932.json`, §16.1 row 17.

## Pitfalls
- Never chart a Kronos band without the failed-verdict disclosure inline (PWA strip included).
- Do not compute bands on intraday bars: mini was validated on daily bars only.
- Re-fetching a higher tier is a new experiment: run the benchmark, record the artifact, update ADR-0012.

## SMC structure export (ADR-0013, snapshot channel for the PWA)
```powershell
D:\MJONAI\.venv\Scripts\python.exe apps\research\run_smc_structure_export.py --symbol RELIANCE --tf 1d
```
Writes `storage/research/smc_structure/{SYMBOL}_{tf}.json` (leakage-safe FVG zones + confirmed swings + current gap-hold state). The `/market` modal reads it through `/api/market/smc-structure` — a symbol with no snapshot renders "unavailable" with this command shown; markers are never fabricated. Supported `--tf`: 1m/5m/15m/1h/1d. Re-export after market data changes; the markers are causal, so re-running never rewrites history.

To re-verify the A8 family verdict:
```powershell
D:\MJONAI\.venv\Scripts\python.exe apps\research\run_discovery_sweep.py --underlying NIFTY --family A8_smc_structure
```

## Clean-room research readers (ADR registry #7 / #9)
```powershell
# Proximity-to-structure screener (SMC-Screener concept; CSV+JSON sinks + evidence artifact)
D:\MJONAI\.venv\Scripts\python.exe apps\research\run_smc_proximity_screener.py --symbols RELIANCE,INFY,TCS

# ATM-window option-chain reader (OI-Extractor concept) over the official warehouse
D:\MJONAI\.venv\Scripts\python.exe apps\research\run_chain_read.py --underlying NIFTY --date 2024-06-14 --strikes 5 --json --pretty
```
Both write a versioned artifact to `storage/research_evidence/` (`smc_proximity_*`, `chain_read_*`) in addition to their stdout/CSV sinks; both fail closed with a non-zero exit when their data is absent.

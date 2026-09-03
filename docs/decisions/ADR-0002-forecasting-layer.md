# ADR-0002: Forecasting layer — thin port, classical baselines mandatory, Kronos first

**Status:** ACCEPTED (owner-delegated 2026-08-24) — **EXECUTED**: `research/forecasting/` live (base, classical baselines, evaluate, kronos/timesfm adapters, pipeline_gate enforcing the full-pipeline evaluation discipline) · **Sequencing:** AFTER repair waves G1–G6 (ADR-0001)

## Context
The only genuine capability gap vs the blueprint. Evidence framework and confidence engine currently fabricate factor scores when data is absent (H3); a forecasting layer must NOT become another fabrication source. TSFM research consensus: forecast accuracy ≠ tradability.

## Decision
1. New `research/forecasting/` package behind a minimal `ForecastModel` protocol: `fit=None (zero-shot) / predict(df, horizon) -> quantiles|samples`.
2. **Mandatory classical baselines first**: seasonal-naive, ETS/ARIMA via statsmodels. Any TSFM claim requires beating these on our metrics before further spend.
3. Adapter order: Kronos (MIT, native OHLCV K-lines, open weights 4.1–102M params) → TimesFM 2.x → Chronos-2 (both Apache-2.0). All run on torch already present in venv.
4. Evaluation through the FULL pipeline: forward-return windows + cost-adjusted risk-adjusted backtest deltas per regime — never MAE/RMSE alone (blueprint §9.2 adopted).
5. Research-mode only; forecasts feed evidence/confidence as ONE factor with explicit data-quality tagging (existing CONFIDENT/STALE enum), never direct order triggers.

## Rejected
TimeGPT (API cost/lock-in), Lag-Llama (dormant), Toto-first (observability domain), TSLib training studies (premature without labeled edge).

## Consequences
GPU inference becomes a real dependency for TSFMs — acceptable: CUDA torch already installed; mini/small Kronos run on modest hardware. New failure surface isolated in research package; runtime untouched until a model survives full-pipeline evaluation.

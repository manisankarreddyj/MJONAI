# ADR-0012: Kronos TSFM — adopt for research; NO-GO as a signal (mini tier)

**Status:** ACCEPTED (research-only, owner-delegated) 2026-10-10 — **VERDICT RECORDED 2026-10-11: mini tier FAILED the ADR-0002 adoption bar**

## Context
ADR-0002 mandates a research forecasting layer in which a TSFM must beat the mandatory classical baselines on **BOTH** tables — the rolling-origin accuracy table AND the `pipeline_gate` trading-edge table, net of canonical friction — before any signal use. Kronos (MIT, native OHLCV K-lines, open weights 4.1–102M params) is the first-choice TSFM. The system must never present a failed model's output as a signal.

## Decision
1. **Adopt shiyu-coder/Kronos behind the ForecastModel port, research tier only.** Vendor pinned at `storage/vendor/kronos` via `tools/scripts/fetch_kronos.py` (network-gated heredoc). Local weights: **Kronos-mini + Kronos-Tokenizer-2k** (`storage/models/kronos`); small/base were never fetched. **Torch is a research opt-in** (`requirements-research-ml.txt`) — the core venv/CI stay torch-free (this supersedes ADR-0002's "torch already present in venv" line).
2. **Evaluation is one command:** `apps/research/run_forecast_benchmark.py` — both tables, 11.42 bps reference friction derived from the canonical `execution/tax.py` (ADR-0003); verdicts persisted to `storage/research_evidence/`.
3. **NOT wired into the 7-gate pipeline.** `pipeline_gate.py` is the evaluation seam only; no strategy may consume a forecast until a tier passes the bar (same boundary as the discovery fence — research primitives never reach the live path unreviewed).
4. **PWA research preview is permitted, disclosure mandatory.** The `/market` forecast strip may render a Kronos band as a clearly-labelled RESEARCH PREVIEW with the failed verdict disclosed inline. It is not a signal and cannot trigger orders (ADR-0007 read-only app unchanged).

## Verdict (mini tier, 2026-10-11)
RELIANCE daily, 60 origins, net of canonical friction — **FAILS the bar on both tables**: worst MAE of the field (31.64 vs rw_drift 21.32 / exp_smoothing 24.68 / seasonal_naive 26.36), 42.0% directional accuracy, **0.0% q10–q90 coverage** (its predictive intervals never contain the outcome), net **−25.31%** through the trading-edge gate vs seasonal_naive's −5.63%. Evidence: `storage/research_evidence/forecast_benchmark_20261011_023940.json`. A 20-origin 2024+ slice flipped to +9.8% net — n=20 is below the project's own ≥30 floor and does not reopen the question.

## Rejected
Kronos-small/base weight fetch (nothing clears the bar at mini; needs its own run + verdict) · fine-tuning on NSE bars (requires labeled edge + owner opt-in) · wiring forecasts into the live pipeline (bar not met) · LLM forecasts in the TradingAgents style (paid APIs, duplicates the deterministic debate room).

## Consequences
The forecasting layer remains a research instrument, consistent with the recorded no-edge findings. Re-opening the adoption question is a one-command repeatable test: fetch a higher tier (or a fine-tune) → run the benchmark → persist the evidence. Until then, any UI surface showing Kronos output must carry the failed-verdict disclosure.

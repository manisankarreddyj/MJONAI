# ARTHAI_CONTEXT.md

Last updated: 2026-04-20

## Spec baseline

Primary planning documents reviewed:
- `C:\Users\manis\Downloads\ARTHAI_MASTER_v4_1_CONSOLIDATED.docx`
- `C:\Users\manis\Downloads\ARTHAI_MASTER_SPECIFICATION_v4.docx`
- `C:\Users\manis\Downloads\ARTHAI_MASTER_SPECIFICATION_v4_Part2.docx`

These docs describe ArthAI as an AI-powered trading intelligence system built around:
- hardcoded capital-protection rules
- an 8-layer evidence framework
- a 5-agent debate room
- a signal engine with multiple risk and quality filters
- paper trading before live trading
- tax, scheduler, dashboard, alerts, and learning loops

## Honest current repo status

This repo is not a blank scaffold. A substantial implementation already exists across backend, frontend, AI debate, signal pipeline, market intelligence, paper trading, scheduler, and integrations.

Current date of this audit: 2026-04-20

## Verified on this machine

The current local status has been validated beyond static inspection:

- Local Python 3.11 exists at `C:\Users\manis\AppData\Local\Programs\Python\Python311\python.exe`.
- The existing `venv311` works and imports core packages successfully.
- `main.py` imports successfully.
- `dashboard/backend/app.py` imports successfully.
- The full startup chain was exercised by calling the real initialization functions in `main.py`.
- Startup verification passed for:
  - environment verification
  - connections
  - data pipeline
  - technical analysis
  - AI brain
  - knowledge base
  - risk guard
  - market intelligence
  - signal engine
  - paper trading
  - alerts
  - personal assistant
  - strategy lab
  - scheduler
  - dashboard
- Scheduler startup was verified with `16` jobs registered.
- Dashboard runtime health was verified with `GET http://127.0.0.1:8000/health` returning HTTP `200`.
- Personal Assistant and scheduler both shut down cleanly after smoke testing.
- `pytest` runs successfully after removing the unused `pytest-asyncio` plugin from the environment.
- `tests/test_technical_analysis.py` passes under `pytest` (`8 passed`).
- `tests/test_signal_engine.py` passes under `pytest` (`8 passed`).
- Rejected-signal storage was repaired to match the current Supabase schema and now writes successfully.
- Windows console logging was hardened in `main.py` so Unicode log messages no longer crash startup on the default code page.
- Psychology guard summary keys were aligned with `main.py` / scheduler expectations, so startup and heartbeat now report the real signal-count state.
- DB-backed signal-history tests now clean up their own `TEST_*` Supabase rows after execution.

## What is clearly built

### Platform and app shell
- `main.py` exists and wires together logging, env validation, integrations, data pipeline, technical analysis, AI brain, knowledge base, market intelligence, paper trading, assistant, scheduler, and dashboard startup hooks.
- FastAPI backend exists at `dashboard/backend/app.py`.
- Next.js frontend exists under `dashboard/frontend/src`.
- API route modules exist for signals, portfolio, performance, market mood, paper trading, assistant, watchlist, system, lessons, and options.

### Core trading engine
- `core/data_pipeline/` exists with market data, historical data, news, global markets, GIFT Nifty, and FII/DII tracking.
- `core/technical_analysis/` exists with indicators, volume analysis, support/resistance, chart patterns, multi-timeframe analysis, and a master technical analyzer.
- `core/signal_engine/` exists with signal generator, scorer, filter, formatter, history, correlation checker, volatility regime filter, and a large master `signal_manager.py`.
- `core/ai_brain/` exists with Bull, Bear, Economist, Devil, Supervisor, consensus engine, prompt manager, performance tracker, and a large `debate_room.py`.
- `core/options_engine/` exists with an options chain engine.

### Risk and trading operations
- `core/risk_management/` exists with circuit breaker, concentration limit checker, gap risk model, and portfolio Greeks aggregation.
- Top-level `risk_management/` also exists with position sizing, stop loss, drawdown protection, capital protection, portfolio risk, and black swan detection.
- `paper_trading/` exists with paper trading manager, simulator, virtual portfolio, performance analyzer, and accuracy tracker.
- `special_modes/` exists with crisis, election, expiry day, and budget day modes plus a manager.
- `scheduler/task_scheduler.py` exists with APScheduler-based recurring jobs, including market scan, pre-market, re-debate, EOD, health check, and data collection jobs.

### Intelligence, assistant, and integrations
- `market_intelligence/` exists with regime analysis, correlation engine, sector rotation, anomaly detection, sentiment index, options analytics, and manager modules.
- `knowledge_base/` exists and appears intended for RAG / memory support.
- `strategy_lab/` exists with strategies, backtesting, performance metrics, walk-forward analysis, and continuous learning modules.
- `personal_assistant/` exists with assistant and multilingual components.
- `psychology_guard/` exists and depends on risk controls.
- Integrations exist for Supabase, Redis, Telegram, Discord, and AngelOne.
- Monitoring exists for Sentry.
- Alerts manager exists.

### Tax and reporting
- `tax/fifo_lot_tracker.py` is implemented and substantial.
- `reports/` exists but currently looks very light compared with the spec.

## What is partial, renamed, or architecturally drifted

These areas are present, but do not line up cleanly with the v4/v4.1 spec yet:

- `core/signal_engine/volatility_regime_classifier.py` from the spec does not exist, but likely maps to `core/signal_engine/volatility_regime_filter.py`.
- `scheduler/master_scheduler.py` from the spec does not exist, but likely maps to `scheduler/task_scheduler.py`.
- Signal circuit breaker logic exists in `core/risk_management/circuit_breaker.py`, not in `core/signal_engine/signal_circuit_breaker.py`.
- Risk logic is split across both `core/risk_management/` and top-level `risk_management/`.
- Tax support exists, but only the FIFO lot tracker is clearly implemented. A full tax engine layer is not yet present.
- The backend is real and startup-verified; the frontend codebase exists, but frontend runtime / browser-level verification has still not been done in this audit.

## What is clearly missing against the spec

The following spec items were not found in the repo:

- `core/signal_engine/time_of_day_filter.py`
- `core/signal_engine/signal_priority_queue.py`
- `core/signal_engine/signal_staleness_decay.py`
- `core/signal_engine/signal_circuit_breaker.py`
- `tax/tax_engine.py`
- `wealth_lifecycle/`
- `asset_engines/`

These may be future phases, but they are not yet represented as files or folders.

## Current blockers

### Environment integrity
- The repo environment itself is now usable: `venv311` works and local pytest runs pass.
- Running Python from the Codex sandbox is still restricted, so some commands only work when executed outside the sandbox.
- `main.py` now reconfigures console output to UTF-8 during logging setup, but standalone scripts that print emoji directly may still need `PYTHONIOENCODING=utf-8` or plain ASCII output.
- Supabase client warnings still appear about deprecated `timeout` and `verify` parameters during DB-backed tests.

### Project hygiene
- There are still multiple environment/dependency folders and filenames in the workspace: `venv`, `venv311`, `requirements.txt`, `requirements_working.txt`, `requirements_final.txt`, and `requirements_311.txt`.
- `pytest-asyncio` was unused in this repo and was removed from the working environment because it broke normal pytest collection with the installed pytest version.
- `requirements.txt` is now the canonical dependency file. `requirements_working.txt`, `requirements_final.txt`, and `requirements_311.txt` were reduced to compatibility shims that defer to it with `-r requirements.txt`.
- `dashboard/frontend/node_modules` and `dashboard/frontend/.next` are present in the workspace, which adds noise and makes codebase inspection harder.
- The project is not currently a git repo in this workspace, so normal change tracking is missing.
- Tests exist under `tests/`, and the technical analysis plus signal engine suites now run successfully.
- Older `TEST_*` Supabase rows created during validation were cleaned up so they no longer inflate the daily signal count.

### Architecture clarity
- Risk logic is currently split between `core/risk_management` and top-level `risk_management`.
- Live imports show that `core/risk_management` is used by the signal engine, paper trading, and options engine for core pipeline risk controls such as circuit breakers, concentration limits, gap risk, and greeks aggregation.
- The top-level `risk_management` package is currently the legacy/public execution-guard namespace used by `psychology_guard`, the scheduler, and older tests for position sizing, stop loss, capital protection, drawdown, and black-swan handling.
- The repo still mixes `core/...` modules with top-level functional modules, which increases the chance of silent drift and inconsistent imports.
- The practical architectural decision is now: treat `core.risk_management` as the canonical home for new risk code, and migrate the top-level `risk_management` package toward a compatibility layer over time.
- The first migration slice is complete: compatibility wrappers now exist under `core/risk_management`, and `psychology_guard`, the scheduler risk-condition path, and the Part 8 risk/psychology tests now import through the core namespace successfully.
- Supabase schema and code had already begun drifting in `signal_rejections`; code was adjusted to match the current schema, but schema discipline needs stronger ownership going forward.

## Best next milestone

Before building more spec features, do this in order:

1. Continue collapsing the legacy top-level `risk_management` package by moving implementations behind the new `core.risk_management` wrappers without changing runtime behavior.
2. Audit Supabase schema vs code paths beyond signals/rejections so drift is caught earlier.
3. Fill or formally remap the missing signal-engine files from the spec:
   - time-of-day filter
   - signal priority queue
   - signal staleness decay
4. Only after that, continue with larger unbuilt areas such as full tax engine, wealth lifecycle, and asset-engine expansion.

## Practical summary

ArthAI is already a serious multi-module codebase.

The main issue is not "nothing has been built."
The environment is now usable, the core technical and signal tests pass, and the repo has a working Python 3.11 setup.
The main remaining risk is architecture and schema drift away from the spec.

The safest path now is:
- consolidate environment and requirements
- choose canonical module boundaries
- run end-to-end startup smoke tests
- then resume feature expansion

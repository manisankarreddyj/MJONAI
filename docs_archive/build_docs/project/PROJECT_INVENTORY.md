# MJONAI — Project Inventory

> This document serves as the inventory of the MJONAI repository and should be updated whenever major components are added, removed, archived, or significantly refactored.

## Core Runtime System

### main.py
Main runtime entry point for MJONAI.

### agents/
Contains:
- bull.py
- bear.py
- supervisor.py

Purpose:
AI agent decision and validation layer.

### execution/
Contains:
- paper.py

Purpose:
Paper trade execution layer.

### risk/
Contains:
- devil_checks.py
- emergency_triggers.py
- trade_risk.py

Purpose:
Risk management and trade validation.

### communication/
Contains:
- telegram.py
- telegram_commands.py

Purpose:
Telegram alerts and command interface.

### core/
Contains:
- constants.py
- market_state.py
- mqi.py
- time_utils.py

Purpose:
Core shared utilities and market intelligence logic.

### db/
Contains:
- repository.py

Purpose:
Database access and persistence layer.

## Research System

### research/
Main quantitative research and analysis workspace.

Contains:
- run_research.py
- run_v2.py
- analyze_results.py
- analyze_v2.py
- deep_analysis.py
- grid_tester.py
- grid_tester_v2.py
- exit_simulator.py
- forward_returns.py
- sector_scanner.py
- cost_model.py
- quick_view.py
- debug_nan.py
- check_data.py
- fix_and_analyze.py

Purpose:
Research, backtesting, edge discovery, performance analysis, and strategy validation.

### research/research_data.duckdb
Local DuckDB database for research datasets and backtest results.

### Test/
Contains multiple standalone backtesting scripts.

Examples:
- backtest_all_7strategies.py
- backtest_s05_filtered.py
- backtest_s05_nifty500.py
- backtest_2years.py

Purpose:
Experimental and scenario-specific backtesting workflows.

## Strategy System

### strategy/signal_scanner.py
Primary signal scanning orchestration layer.

Purpose:
Runs strategies and generates trading signals.

### strategy/registry/
Contains modular strategy implementations.

Current strategies:
- bollinger_squeeze.py
- mean_reversion.py
- mean_reversion_short.py
- momentum_rsi.py
- momentum_short.py
- price_action.py
- turtle_breakout.py

### strategy/registry/base.py
Base strategy structure and shared interface.

Purpose:
Standardizes strategy implementation architecture.

### Current Strategy Direction
Project currently focuses on:
- backtesting first
- edge validation
- strategy comparison
- filtering and optimization

before paper trading or live deployment.

## Risk System

## AI / Agent System

### agents/
Contains:
- bull.py
- bear.py
- supervisor.py

Purpose:
AI-based signal evaluation and multi-agent decision architecture.

### Agent Roles

#### bull.py
Bullish validation agent.

Purpose:
Supports and validates bullish trade opportunities.

#### bear.py
Bearish validation agent.

Purpose:
Evaluates bearish or opposing market perspectives.

#### supervisor.py
Final supervisory decision layer.

Purpose:
Reviews agent outputs and provides final signal oversight.

### ask.py
Early internal AI interaction entry point.

### ask_ai.py
Experimental AI interaction layer.

### Current AI Reality
Current AI system is still early-stage and partially experimental.

Long-term direction:
- repo-aware AI assistant
- architecture-aware AI CTO
- autonomous debugging and analysis
- persistent project memory integration
- internal MJONAI operating intelligence

## Communication System

### communication/telegram.py
Telegram notification and alert delivery layer.

Purpose:
Sends:
- alerts
- trade notifications
- runtime messages
- system events

### communication/telegram_commands.py
Telegram command handling layer.

Purpose:
Provides command-based interaction with MJONAI through Telegram.

### Current Communication Reality
Telegram currently acts as:
- operational notification interface
- lightweight command interface
- early remote interaction layer

Future direction may include:
- AI interaction through Telegram
- monitoring dashboards
- command-driven orchestration
- runtime control system

## Data Layer

### data/angelone/
Contains:
- token_map.py
- websocket.py
- nifty500_tokens.csv
- nse_tokens.csv

Purpose:
Broker integration, token management, and live market connectivity.

### data/earnings/
Contains:
- earnings_check.py

Purpose:
Earnings event filtering and validation.

### data/macro/
Contains:
- macro_check.py

Purpose:
Macro market condition filtering and checks.

### Current Data Reality
Current project primarily depends on:
- historical/backtest datasets
- local research data
- AngelOne integration experiments

Live production-grade realtime data flow is not fully completed yet.

## Documentation Layer

### docs/current_state/PROJECT_REALITY.md
Tracks actual current state of MJONAI.

Purpose:
Maintains reality-based understanding of:
- active direction
- current priorities
- working systems
- incomplete systems
- architectural evolution

### docs/current_state/PROJECT_INVENTORY.md
Tracks actual project structure and functional system boundaries.

Purpose:
Acts as persistent project memory for:
- future AI sessions
- future developers
- architecture understanding
- onboarding
- system cognition

### MJONAI_MASTER_v2.0.md
Original master planning document.

Purpose:
Long-term architectural vision and system design reference.

Important:
Current project direction has evolved beyond parts of the original master document.

### MJONAI_HANDOVER_v2.0.md
Project handover and transition reference document.

## Experimental / Unstructured Files

### ask.py
Experimental AI interaction utility.

### ask_ai.py
Experimental AI interaction and query utility.

### logs/
Runtime logs and execution history.

### __pycache__/
Python cache files.

Purpose:
Generated automatically by Python runtime.

### venv/
Local Python virtual environment.

Purpose:
Dependency isolation and runtime environment.

### 5}
### 7.4f}%
Unknown / accidental files currently present in project root.

Likely:
- accidental terminal artifacts
- incomplete file creation
- corrupted filenames

Should likely be removed after verification.

### Current Reality
Project currently contains:
- production-intent components
- research experiments
- evolving architecture
- partially completed systems
- exploratory AI tooling

System boundaries are improving but still evolving.

## Current Reality Summary
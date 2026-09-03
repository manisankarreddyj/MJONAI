# Analytics Architecture

## Purpose

The Analytics subsystem transforms raw operational data collected by MJONAI into meaningful performance insights.

It measures, explains, and summarizes how the system is performing across trades, strategies, market conditions, agents, portfolio, and risk.

The Analytics subsystem does NOT:

- Generate trading signals.
- Execute trades.
- Place orders.
- Perform market research.
- Modify trading decisions.

Its responsibility is to answer one question:

> "How is MJONAI actually performing, and what can be learned from that performance?"

Analytics serves as the evidence layer of MJONAI, providing accurate measurements and insights that can later be consumed by Intelligence, Research, Reporting, and future AI agents.

---

## Responsibilities

The Analytics subsystem is responsible for:

- Measuring trading performance.
- Measuring portfolio performance.
- Measuring strategy performance.
- Measuring market regime performance.
- Measuring risk performance.
- Measuring AI agent performance.
- Producing daily, weekly, monthly, and overall performance summaries.
- Calculating portfolio and trading metrics.
- Providing structured analytics for other MJONAI subsystems.

The Analytics subsystem does NOT own:

- Signal generation.
- Risk enforcement.
- Order execution.
- Market data collection.
- Database persistence.
- Trade decision making.

---

## Inputs

The Analytics subsystem consumes data from existing MJONAI subsystems.

Primary data sources include:

- Trades
- Trade Tranches
- Signal Intelligence Log
- Daily Portfolio Snapshots
- Strategy Performance
- Market State History
- Pattern Memory
- Agent Logs
- Agent Weight Log
- Risk Events
- Scan Log
- System Health Log

Analytics reads data through the Repository layer only.

It never queries Supabase directly.

It never owns or modifies source data.

The Repository remains the single source of truth for all persistent data.

---

## Outputs

The Analytics subsystem produces structured performance information for consumption by other MJONAI subsystems.

Primary outputs include:

- Portfolio performance metrics.
- Trading performance metrics.
- Strategy performance summaries.
- Market regime analytics.
- Risk analytics.
- Agent performance analytics.
- Daily, weekly, monthly, and overall reports.
- Structured metrics for dashboards.
- Structured metrics for the Intelligence subsystem.

Analytics outputs are read-only.

Analytics never changes trading decisions directly.

Any subsystem consuming Analytics remains responsible for deciding how to use the information.

---

## Core Capabilities

The Analytics subsystem is composed of the following capabilities:

### 1. Performance Analytics

Responsible for calculating overall trading performance.

Examples:

- Win Rate
- Loss Rate
- Profit Factor
- Expectancy
- Average Risk/Reward
- Net Profit
- Gross Profit
- Gross Loss

---

### 2. Portfolio Analytics

Responsible for measuring portfolio health.

Examples:

- Portfolio Value
- Capital Utilization
- Daily Return
- Monthly Return
- Drawdown
- Peak Equity
- Recovery Factor

---

### 3. Strategy Analytics

Responsible for evaluating individual strategy performance.

Examples:

- Strategy Win Rate
- Strategy Profit Factor
- Strategy Expectancy
- Strategy Ranking
- Strategy Stability

---

### 4. Market Analytics

Responsible for measuring performance across different market conditions.

Examples:

- Performance by Market State
- Performance by MQI
- Performance by VIX
- Performance by Sector

---

### 5. Agent Analytics

Responsible for evaluating AI agent performance.

Examples:

- Bull Agent Accuracy
- Supervisor Accuracy
- Agent Agreement
- Agent Confidence Calibration

---

### 6. Risk Analytics

Responsible for measuring portfolio and trading risk.

Examples:

- Maximum Drawdown
- Consecutive Losses
- Daily Loss Distribution
- Risk per Trade
- Exposure Analysis

---

## Data Flow

The Analytics subsystem follows a one-way data flow.

```
Repository
        │
        ▼
Analytics Engines
        │
        ▼
Calculated Metrics
        │
        ▼
Reports & Insights
        │
        ├────────► Dashboard
        │
        ├────────► Intelligence
        │
        ├────────► Reporting
        │
        └────────► Future AI Agents
```

### Data Flow Principles

- Analytics only reads data.
- Analytics never modifies source data.
- Analytics produces calculated metrics.
- Analytics provides facts, not decisions.
- Other subsystems decide how analytics should be used.

---

# Analytics Modules

The Analytics subsystem will initially be implemented using the following modules.

## performance_engine.py

Responsibility:

- Calculate overall trading performance.
- Produce system-wide performance metrics.
- Act as the primary analytics engine.

Owns:

- Win Rate
- Profit Factor
- Expectancy
- Average R:R
- Gross Profit
- Gross Loss
- Net Profit

Does NOT own:

- Portfolio analysis
- Strategy comparison
- Risk calculations
- AI reasoning

---

## portfolio_analytics.py

Responsibility:

Measure portfolio health.

Owns:

- Portfolio Value
- Capital Utilization
- Drawdown
- Peak Equity
- Daily Return
- Monthly Return

---

## strategy_analytics.py

Responsibility:

Measure individual strategy performance.

Owns:

- Strategy Ranking
- Strategy Win Rate
- Strategy Expectancy
- Strategy Stability
- Strategy Comparison

---

## market_analytics.py

Responsibility:

Analyze performance under different market conditions.

Owns:

- Market State Analysis
- MQI Analysis
- VIX Analysis
- Sector Analysis

---

## agent_analytics.py

Responsibility:

Evaluate AI agent performance.

Owns:

- Bull Accuracy
- Supervisor Accuracy
- Agent Agreement
- Confidence Calibration

---

## risk_analytics.py

Responsibility:

Measure portfolio and trading risk.

Owns:

- Maximum Drawdown
- Consecutive Losses
- Risk Distribution
- Exposure Metrics

---

## report_generator.py

Responsibility:

Convert analytics into structured reports.

Produces:

- Daily Report
- Weekly Report
- Monthly Report
- Overall Performance Summary

Does NOT calculate analytics.

It only formats and presents results.

---

# Development Roadmap

Analytics will be implemented incrementally.

## Phase 1

Build the core analytics engine.

Module:

- performance_engine.py

Goal:

Produce reliable portfolio-wide trading metrics.

---

## Phase 2

Build portfolio analytics.

Module:

- portfolio_analytics.py

Goal:

Measure overall portfolio health and capital performance.

---

## Phase 3

Build strategy analytics.

Module:

- strategy_analytics.py

Goal:

Compare and rank trading strategies.

---

## Phase 4

Build market analytics.

Module:

- market_analytics.py

Goal:

Measure performance across different market environments.

---

## Phase 5

Build agent analytics.

Module:

- agent_analytics.py

Goal:

Measure AI decision quality and calibration.

---

## Phase 6

Build risk analytics.

Module:

- risk_analytics.py

Goal:

Measure portfolio and trading risk.

---

## Phase 7

Build reporting.

Module:

- report_generator.py

Goal:

Produce daily, weekly, monthly and overall reports using analytics generated by previous phases.

---

## Architecture Rule

Each phase must be fully tested before starting the next phase.

No module should duplicate responsibilities already owned by another analytics module.

---

# Design Principles

The Analytics subsystem follows these architectural principles:

1. Single Responsibility
   - Each module owns one capability only.

2. Read Only
   - Analytics never modifies production data.

3. Repository First
   - All data access must go through the Repository layer.

4. Deterministic
   - Given the same input data, Analytics must always produce the same results.

5. Explainable
   - Every calculated metric should be traceable to its source data.

6. Reusable
   - Analytics modules should expose reusable functions that can be consumed by Reporting, Intelligence, Dashboards, and future AI agents.

7. Testable
   - Every metric should be independently verifiable using historical data.

8. Extensible
   - New metrics should be added without changing existing module responsibilities.
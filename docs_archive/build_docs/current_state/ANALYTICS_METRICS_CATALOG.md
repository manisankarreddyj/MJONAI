# Analytics Metrics Catalog

## Purpose

This document defines every metric calculated by the Analytics subsystem.

Each metric has a single owner.

No metric should be calculated by multiple modules.

This document serves as the contract between Analytics and the rest of MJONAI.

---

# Performance Metrics

Owner:

- performance_metrics.py

These metrics describe the overall trading performance of MJONAI.

## Core Metrics

- Total Trades
- Winning Trades
- Losing Trades
- Breakeven Trades
- Win Rate (%)
- Loss Rate (%)
- Breakeven Rate (%)

---

## Profit Metrics

- Gross Profit
- Gross Loss
- Net Profit
- Average Profit per Trade
- Average Loss per Trade

---

## Risk / Reward Metrics

- Average Planned Risk/Reward
- Average Actual Risk/Reward
- Best Trade
- Worst Trade

---

## Consistency Metrics

- Consecutive Wins
- Consecutive Losses
- Average Holding Time
- Average Trade Duration

---

## Trade Quality Metrics

- Average Confidence
- Average Entry Score
- Average Technical Score
- Average Position Size

---

Status:

Planned

---

# Portfolio Metrics

Owner:

- portfolio_analytics.py

These metrics describe the health and performance of the overall portfolio.

## Capital Metrics

- Initial Capital
- Current Capital
- Peak Capital
- Lowest Capital
- Capital Growth (%)

---

## Return Metrics

- Daily Return (%)
- Weekly Return (%)
- Monthly Return (%)
- Yearly Return (%)
- Total Return (%)

---

## Portfolio Health

- Capital Utilization (%)
- Available Cash
- Capital at Risk
- Open Positions
- Closed Positions

---

## Portfolio Stability

- Best Trading Day
- Worst Trading Day
- Average Daily Profit
- Average Daily Loss

---

Status:

Planned

---

# Strategy Metrics

Owner:

- strategy_analytics.py

These metrics measure the effectiveness and consistency of each trading strategy.

## Strategy Performance

- Total Trades
- Winning Trades
- Losing Trades
- Breakeven Trades
- Win Rate (%)
- Profit Factor
- Net Profit
- Gross Profit
- Gross Loss

---

## Strategy Quality

- Average Planned Risk/Reward
- Average Actual Risk/Reward
- Average Holding Time
- Average Confidence
- Average Technical Score

---

## Strategy Consistency

- Best Performing Strategy
- Worst Performing Strategy
- Consecutive Wins
- Consecutive Losses
- Strategy Stability Score

---

## Strategy Comparison

Compare performance by:

- Market State
- MQI Level
- Sector
- Entry Day
- Entry Time
- System Mode

---

Status:

Planned

---

# Market Metrics

Owner:

- market_analytics.py

These metrics measure MJONAI performance under different market conditions.

## Market State Performance

Performance grouped by:

- Bull Market
- Bear Market
- Neutral Market

For each Market State calculate:

- Total Trades
- Win Rate (%)
- Profit Factor
- Net Profit
- Average Risk/Reward

---

## MQI Performance

Performance grouped by:

- HIGH MQI
- MEDIUM MQI
- LOW MQI

For each MQI level calculate:

- Total Trades
- Win Rate (%)
- Profit Factor
- Net Profit

---

## VIX Performance

Performance grouped by:

- Low VIX
- Medium VIX
- High VIX

For each VIX range calculate:

- Total Trades
- Win Rate (%)
- Profit Factor
- Average Holding Time

---

## Sector Performance

Performance grouped by sector.

Examples:

- Banking
- IT
- Pharma
- Auto
- FMCG
- Energy
- Metal
- Realty

For each sector calculate:

- Total Trades
- Win Rate (%)
- Net Profit
- Profit Factor

---

Status:

Planned

---

# Agent Metrics

Owner:

- agent_analytics.py

These metrics evaluate the quality, consistency, and effectiveness of MJONAI AI agents.

## Agent Performance

For each agent calculate:

- Total Decisions
- Approved Signals
- Rejected Signals
- Correct Decisions
- Incorrect Decisions
- Accuracy (%)

---

## Confidence Analysis

Measure:

- Average Confidence
- Confidence vs Actual Outcome
- High Confidence Win Rate
- Low Confidence Win Rate

---

## Agreement Analysis

Measure:

- Bull vs Supervisor Agreement
- Approval Rate
- Rejection Rate
- Conflict Rate

---

## Agent Calibration

Measure:

- Current Agent Weight
- Weight Change History
- Accuracy Trend
- Calibration Trend

---

## Learning Metrics

Track:

- Best Performing Agent
- Most Improved Agent
- Most Conservative Agent
- Most Aggressive Agent

---

Status:

Planned

---

# Risk Metrics

Owner:

- risk_analytics.py

These metrics measure capital protection, portfolio stability, and trading risk.

## Drawdown Metrics

Measure:

- Maximum Drawdown (%)
- Current Drawdown (%)
- Average Drawdown (%)
- Drawdown Duration

---

## Exposure Metrics

Measure:

- Capital at Risk
- Open Risk
- Capital Utilization (%)
- Sector Exposure
- Strategy Exposure

---

## Loss Metrics

Measure:

- Consecutive Losses
- Largest Losing Trade
- Average Losing Trade
- Daily Loss
- Weekly Loss
- Monthly Loss

---

## Risk Distribution

Measure:

- Risk per Trade
- Average Position Size
- Average Stop Loss Distance
- Planned Risk vs Actual Risk

---

## Portfolio Safety

Measure:

- Risk Limit Breaches
- Daily Stop Trigger Count
- Emergency Stop Trigger Count
- Kill Switch Events

---

Status:

Planned

---

# Reporting Metrics

Owner:

- report_generator.py

The Reporting module is responsible for presenting analytics in a clear, structured, and human-readable format.

It does not calculate metrics.

It only consumes metrics generated by other Analytics modules.

## Daily Report

Include:

- Portfolio Summary
- Trading Summary
- Performance Metrics
- Risk Summary
- Strategy Summary
- Market Summary
- Agent Summary

---

## Weekly Report

Include:

- Weekly Performance
- Best Strategy
- Worst Strategy
- Portfolio Growth
- Drawdown Summary
- Risk Summary
- Key Insights

---

## Monthly Report

Include:

- Monthly Performance
- Portfolio Performance
- Strategy Rankings
- Market Performance
- Agent Performance
- Risk Analysis
- Improvement Opportunities

---

## Lifetime Report

Include:

- Overall Portfolio Growth
- Lifetime Performance
- Strategy Rankings
- Market Condition Performance
- Agent Performance
- Risk Statistics
- Historical Insights

---

## Delivery Channels

Reports may be delivered through:

- Terminal Console
- Telegram
- Dashboard
- PDF (Future)
- Web UI (Future)
- Mobile App (Future)

---

Status:

Planned
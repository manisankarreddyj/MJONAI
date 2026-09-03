# ADR-0003: One canonical transaction-cost engine

**Status:** PROPOSED (2026-08-24) · **Resolves:** H8/N2

## Context
Two friction models exist: `execution/tax.py` (canonical, used by backtests post-unification) and `risk/trade_risk.calculate_*_costs` (parallel; feeds Gate-4 net-R:R validation AND RESEARCH-mode paper booking). Divergences: always-delivery exit STT, flat ₹20 brokerage, intraday/SWING mismatches. Trades are currently approved against non-canonical costs.

## Decision
`execution/tax.py` becomes the ONLY cost calculator. `risk/trade_risk` imports it for RR gating; `orders.open_paper_trade` books from it. The duplicate functions are removed after call-sites migrate. Regression test asserts both paths produce identical itemized costs for representative trades (delivery/intraday × long/short).

## Consequences
RR gate may reject some previously-approved trades (correct behavior). Research-mode P&L denominators shift slightly → note in next validity log entry.

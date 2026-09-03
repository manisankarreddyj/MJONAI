# MJONAI Research Engine - Quantitative Methodology Review

**Date:** August 22, 2026  
**Review Scope:** `D:\MJONAI\mjonai-build\engine\` and related strategy/risk modules

---

## Executive Summary

This review identifies **critical issues that invalidate research results** and **would cause live trading losses**. The most severe problems are:

1. **Look-ahead bias in backtest engine** — Entry at current bar's close (not next open), intra-bar High/Low used for stops/targets
2. **No transaction costs modeled** in trade simulator — All costs hardcoded to zero
3. **Missing Sharpe/Sortino/Calmar calculations** — All return 0.0 (stubs)
4. **No purged/embargoed walk-forward CV** — Training and validation windows are adjacent (data leakage)
5. **No multiple testing correction** in optimization — Single-split selection on total return only

---

## 1. Backtest Methodology Correctness

### CRITICAL: Look-Ahead Bias — Entry at Current Bar Close
**File:** `engine/backtest/backtest_engine.py:56-60`
```python
entry_price = float(df["Close"].iloc[entry_index])
```
**Issue:** Signals generated on bar `i` (using data up to and including bar `i`), but entry executed at **bar `i`'s close**. In reality, you only know the close *after* the bar completes, so execution must be at **bar `i+1` open**. This creates perfect hindsight — entering at a price you couldn't have known at signal generation time.

### CRITICAL: Look-Ahead Bias — Intra-Bar High/Low for Stop/Target
**File:** `engine/backtest/trade_simulator.py:45-121`
```python
for i in range(entry_index + 1, last_bar + 1):
    high = float(df["High"].iloc[i])
    low = float(df["Low"].iloc[i])
    if low <= stop_loss:  # Uses same-bar Low
```
**Issue:** The simulator checks intra-bar `High`/`Low` on the **same bar as entry/exit** to determine if stops/targets hit. At signal time (bar close), you don't know the next bar's High/Low. This is a second form of look-ahead bias — you're using future intra-bar information.

### CRITICAL: Zero Transaction Costs
**File:** `engine/backtest/trade_simulator.py:216-221` (also `engine/execution/brokers/angel_one.py`, `shoonya.py`)
```python
transaction_cost = TransactionCost(
    brokerage=0.0,
    slippage=0.0,
    taxes=0.0,
    total=0.0,
)
```
**Issue:** `TradeProcessor.process()` calls cost calculator, but `TradeSimulator.simulate()` hardcodes all costs to zero. No slippage, commission, STT, GST modeled. Only Zerodha broker model implements realistic costs. This inflates returns significantly (20-50%+ for high-frequency strategies).

### CRITICAL: Fixed Quantity = 1 (No Position Sizing Integration)
**File:** `engine/backtest/trade_simulator.py:139`
```python
quantity = 1  # Hardcoded
```
**Issue:** Trade simulator uses fixed quantity of 1 share regardless of capital/risk. Position sizing via `TradeProcessor` happens *after* simulation, not during.

### HIGH: No Portfolio-Level Risk Management
**File:** `engine/backtest/backtest_engine.py:49-54`
**Issue:** No max concurrent positions, sector limits, or capital allocation logic. Each signal traded independently.

### HIGH: Signal-to-Trade Conversion Uses Current Bar
**File:** `engine/core/strategy_runner.py:64-68`
```python
for i in range(start_index, len(data)):
    window = data.iloc[: i + 1]  # Includes current bar i
    result = self.strategy.generate_signal(window)
```
**Issue:** Strategy sees bar `i`'s full OHLC before generating signal for bar `i`. This is look-ahead bias. Signal should be generated on `data.iloc[:i]` (bars 0 to i-1) and executed at bar `i` open.

### MEDIUM: Optimization Selects on Training Data Only, But No Statistical Correction
**File:** `engine/optimization/grid_search.py:26-33`
```python
ranked = sorted(results, key=lambda result: (
    result.report.equity.total_return_pct,
    result.report.trade.profit_factor,
    result.report.trade.win_rate_pct,
), reverse=True)
```
**Issue:** Selects best parameters by total return only — no multiple testing correction (Bonferroni, Benjamini-Hochberg, or deflated Sharpe). With 50+ parameter combinations, ~5% will appear profitable by chance.

---

## 2. Statistical Validity

### CRITICAL: Sharpe, Sortino, Calmar All Return 0.0
**File:** `engine/analytics/performance_metrics.py:27-36`
```python
return PerformanceStatistics(
    cagr_pct=0.0,
    annualized_return_pct=0.0,
    sharpe_ratio=0.0,        # NOT CALCULATED
    sortino_ratio=0.0,       # NOT CALCULATED
    calmar_ratio=0.0,        # NOT CALCULATED
    recovery_factor=...,
    mar_ratio=0.0,
)
```
**Issue:** Core risk-adjusted metrics are **stubs returning zero**. Any research claiming "Sharpe > 1.5" is fabricated.

**Required Implementation:**
```python
# Sharpe = (mean_daily_return - risk_free) / std_daily_return * sqrt(252)
# Sortino = (mean_daily_return - risk_free) / downside_deviation * sqrt(252)
# Calmar = annualized_return / max_drawdown
```

### HIGH: Win Rate Calculation Treats Breakeven as Loss
**File:** `engine/analytics/metrics.py:43-47`
```python
losses = [trade for trade in trades if trade.net_return_pct <= 0]
```
**Issue:** Trades with exactly 0% return counted as losses. Should be `< 0` for losses, `> 0` for wins, `== 0` excluded or separate.

### MEDIUM: Profit Factor Uses Net Returns (Should Be Gross)
**File:** `engine/analytics/metrics.py:111-128`
```python
gross_profit = sum(trade.net_return_pct for trade in wins)
gross_loss = abs(sum(trade.net_return_pct for trade in losses))
```
**Issue:** Profit factor should use **gross** P&L (before costs), not net. Using net double-counts transaction costs.

### MEDIUM: Expectancy Calculation Is Just Average Return
**File:** `engine/analytics/metrics.py:139`
```python
expectancy = average_return
```
**Issue:** Expectancy should be: `win_rate * avg_win + loss_rate * avg_loss`. Current formula equals average return, which is not standard expectancy.

### HIGH: No Statistical Significance Testing
**File:** `engine/optimization/engine.py`
**Issue:** No t-tests, bootstrap confidence intervals, or Monte Carlo permutation tests for strategy validation.

---

## 3. Risk Model Correctness

### HIGH: Fixed Risk Position Sizer — No Kelly, No Volatility Scaling
**File:** `engine/portfolio/position_sizer.py:8-44`
```python
def calculate(self, *, capital, risk_percent, entry_price, stop_loss):
    risk_amount = capital * risk_percent / 100
    risk_per_share = abs(entry_price - stop_loss)
    quantity = max(1, int(risk_amount / risk_per_share))
```
**Issues:**
1. **No Kelly criterion** — fixed fractional only
2. **No volatility adjustment** — position size ignores ATR/volatility regime
3. **Integer quantity rounding** creates discretization bias (especially for low-priced stocks)
4. **No portfolio heat/correlation limits** — each position sized independently

### HIGH: Capital Manager — No Compounding for Position Sizing
**File:** `engine/portfolio/capital.py:80-95`
```python
def apply_trade_result(self, net_pnl: float) -> None:
    self._capital.realized_pnl += net_pnl
    self._capital.available += net_pnl
```
**Issue:** Updates available capital but **doesn't compound** for next position sizing. PositionSizer uses initial capital, not current equity. Breaks compounding logic.

### HIGH: Devil Checks — Correlation Check Uses Hardcoded Proxy
**File:** `risk/devil_checks.py:203-217`
```python
proxy_correlation = 0.85  # HARDCODED!
if proxy_correlation > correlation_threshold:
```
**Issue:** Correlation check **doesn't compute actual correlation** — uses hardcoded 0.85. This check is purely cosmetic.

### MEDIUM: GARCH Gap Risk Falls Back to Naive Calculation
**File:** `risk/devil_checks.py:102-131`
```python
# Fallback
if expected_overnight_move is None:
    expected_overnight_move = sl_dist * 0.5  # ARBITRARY
```
**Issue:** When GARCH model unavailable (import fails), uses arbitrary 50% of SL distance. No actual historical overnight gap distribution analysis.

### MEDIUM: Real R:R Uses `total_cost / qty` Assumption
**File:** `risk/devil_checks.py:268`
**Issue:** Assumes cost is known per-unit at signal time. In practice, slippage/fees vary.

---

## 4. Strategy Implementation Quality

### HIGH: S01 Momentum RSI — Signal Generation Uses Current Bar
**File:** `engine/strategies/s01_momentum_rsi.py:140-161`
```python
current = len(data) - 1
previous = current - 1
if rsi_values.iloc[previous] <= self._rsi_level and rsi_values.iloc[current] > self._rsi_level:
```
**Issue:** Uses `data` which includes current bar (per `StrategyRunner`). RSI crossover detected on **current incomplete bar**. In live trading, you only know previous bar's close.

### HIGH: S02 Mean Reversion — Same Look-Ahead Issue
**File:** `engine/strategies/s02_mean_reversion.py:75-87`
```python
curr = len(data) - 1
prev = curr - 1
oversold_bounce = (
    close.iloc[prev] <= lower.iloc[prev]
    and close.iloc[curr] > lower.iloc[curr]
    and rsi_vals.iloc[curr] <= self._rsi_oversold + 10
)
```
**Issue:** Uses current bar's `lower.iloc[curr]` and `close.iloc[curr]` which are not fully formed at signal time.

### MEDIUM: Indicators Use `adjust=False` EWM (Correct for TA)
**File:** `engine/indicators/momentum.py:7-10`
```python
return series.ewm(span=period, adjust=False).mean()
```
**Finding:** This is **correct** — `adjust=False` gives standard TA EMA (recursive), not pandas' default expanding window.

### MEDIUM: RSI Uses Wilder's Smoothing (Correct)
**File:** `engine/indicators/momentum.py:20-28`
```python
avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
```
**Finding:** Correct implementation of Wilder's RSI smoothing.

### MEDIUM: Bollinger Bands Use Rolling Std (Correct)
**File:** `engine/indicators/momentum.py:67-76`
```python
middle = close.rolling(period).mean()
std = close.rolling(period).std()
```
**Finding:** Standard implementation.

---

## 5. Market Data Quality

### HIGH: Yahoo Provider — `auto_adjust=False` But No Split/Dividend Handling
**File:** `engine/market_data/providers/yahoo_provider.py:46`
```python
auto_adjust=False,
```
**Issue:** With `auto_adjust=False`, you get raw unadjusted prices. **No split/dividend adjustment is applied anywhere**. This creates massive artificial gaps on split/ex-dividend dates, corrupting:
- Returns calculations
- Indicator values (EMA, RSI, BB)
- Stop loss / target levels

**Required:** Either use `auto_adjust=True` or implement manual adjustment using Yahoo's `actions` (splits, dividends).

### MEDIUM: Yahoo Provider — MultiIndex Handling Fragile
**File:** `engine/market_data/providers/yahoo_provider.py:71-76`
```python
open=float(row["Open"].iloc[0] if hasattr(row["Open"], "iloc") else row["Open"]),
```
**Issue:** Defensive coding for yfinance MultiIndex columns, but this masks potential data structure issues. Better to explicitly flatten columns: `df.columns = df.columns.get_level_values(0)`.

### LOW: Instrument Normalizer — No Yahoo Symbol Mapping
**File:** `engine/instruments/normalizer.py`
**Issue:** Only handles Angel One provider. No normalization for Yahoo symbols (e.g., `RELIANCE.NS` → `RELIANCE`). Symbol mapping between providers is missing.

---

## 6. Walk-Forward/Out-of-Sample Rigor

### CRITICAL: No Embargo Between Train/Validation
**File:** `engine/research/walk_forward_windows.py:35-36`
```python
validation_start = train_end  # Direct adjacency
```

### CRITICAL: Hyperparameters Selected on Training, But No Nested CV
**File:** `engine/research/walk_forward_engine.py:71-84`
```python
optimization = self._optimizer.optimize(..., config=training_config)
strategy.configure(optimization.best_result.parameters)
validation_results = self._optimizer._pipeline.run(..., config=validation_config)
```
**Issue:** Single train/validation split per window. No nested cross-validation within training window to select hyperparameters. This is **single-split optimization bias**.

### HIGH: Walk-Forward Windows Don't Account for Indicator Warmup
**File:** `engine/research/walk_forward_windows.py`
**Issue:** Training window starts at `config.start` but strategies need 200+ bars warmup (see `StrategyRunner:62`). First ~200 bars of each training window are wasted or produce no signals.

### MEDIUM: No Anchored Walk-Forward (Expanding Window)
**File:** `engine/research/walk_forward_windows.py`
**Issue:** Only sliding window (`step_years` moves both train and validation). No expanding window option (anchored start, growing train) which is more robust for regime change detection.

### HIGH: Strategy Mutated In-Place Across Windows
**File:** `engine/research/walk_forward_engine.py:82-84`
```python
strategy.configure(optimization.best_result.parameters)
```
**Issue:** Strategy object mutated in-place. If same strategy instance reused across windows, parameters leak between windows.

---

## 7. Architectural / Integration Gaps

| Issue | Severity |
|-------|----------|
| **No slippage model** — Trade simulator assumes perfect fill at stop/target price. Real markets have slippage, especially on stops. | 🔴 CRITICAL |
| **No partial fill / rejection modeling** — All orders fill completely at desired price. | 🟠 HIGH |
| **No overnight/weekend gap handling in backtest** — `trade_simulator` only checks intra-bar high/low. Gaps on open not modeled. | 🔴 CRITICAL |
| **Strategy parameters optimized on full training window** — No nested cross-validation (inner CV for hyperparameter selection, outer for evaluation). | 🔴 CRITICAL |
| **No benchmark comparison** — No buy-and-hold or index benchmark in performance report. | 🟠 HIGH |

---

## Priority Remediation Order

| Priority | Issue | File:Line | Impact |
|----------|-------|-----------|--------|
| **P0** | Entry at current bar close (look-ahead) | backtest_engine.py:56 | Invalidates all backtests |
| **P0** | Intra-bar High/Low for stops (look-ahead) | trade_simulator.py:45-121 | Invalidates all backtests |
| **P0** | Zero transaction costs | trade_simulator.py:216 | Inflates returns 20-50%+ |
| **P0** | Sharpe/Sortino/Calmar = 0.0 | performance_metrics.py:27-36 | No risk-adjusted metrics |
| **P0** | No embargo in walk-forward | walk_forward_windows.py:35 | Data leakage |
| **P0** | No multiple testing correction | grid_search.py:26 | Overfitting |
| **P1** | Signal generation on current bar | strategy_runner.py:66 | Look-ahead bias |
| **P1** | No split/dividend adjustment | yahoo_provider.py:46 | Corrupted price series |
| **P1** | Position sizer ignores compounding | capital.py:80 | Breaks equity growth |
| **P1** | Correlation check hardcoded | devil_checks.py:209 | Risk check non-functional |
| **P1** | No overnight gap modeling | trade_simulator.py | Misses gap risk |
| **P2** | Win rate treats 0 as loss | metrics.py:46 | Minor bias |
| **P2** | Profit factor uses net returns | metrics.py:111 | Double-counts costs |
| **P2** | No Kelly/vol sizing | position_sizer.py:8 | Suboptimal sizing |
| **P2** | No expanding walk-forward | walk_forward_windows.py | Limited validation |

---

## Files Requiring Immediate Fixes

1. **`engine/backtest/backtest_engine.py`** — Entry price logic (next bar open)
2. **`engine/backtest/trade_simulator.py`** — Transaction costs, intra-bar High/Low usage, slippage model
3. **`engine/analytics/performance_metrics.py`** — Risk metrics implementation (Sharpe, Sortino, Calmar)
4. **`engine/research/walk_forward_windows.py`** — Embargo gap, warmup handling
5. **`engine/optimization/grid_search.py`** — Multiple testing correction
6. **`engine/core/strategy_runner.py`** — Signal generation timing (previous bar only)
7. **`engine/market_data/providers/yahoo_provider.py`** — Split/dividend handling (`auto_adjust=True`)
8. **`engine/portfolio/capital.py`** — Compounding logic for position sizing
9. **`risk/devil_checks.py`** — Real correlation calculation, GARCH gap risk
10. **`engine/portfolio/position_sizer.py`** — Kelly/volatility-based sizing
11. **`engine/research/walk_forward_engine.py`** — Nested CV, strategy cloning (not mutation)
12. **`engine/execution/brokers/angel_one.py`** — Real cost model
13. **`engine/execution/brokers/shoonya.py`** — Real cost model

---

## Notes

- The **most damaging issues** are the look-ahead bias (same-bar High/Low/Close for entry/exit), zero transaction costs, no walk-forward embargo, and hardcoded zero risk-adjusted metrics. These alone would produce **severely overstated backtest results** that will not replicate in live trading.
- The strategy implementations in `strategy/registry/` use a different codebase than the `engine/strategies/` module. Ensure both are consistent.
- The `engine/` directory appears to be the primary research engine, while `strategy/registry/` and `risk/` are separate modules. Integration between them needs verification.

---

## Resolution Log

### Session: 2026-08-22 — P0 Remediation Pass (engine/)

All P0 items above were fixed and covered by new pytest regression tests (46 passing in `engine/backtest/` + `engine/tests/`). Per-item status:

| Finding | Status | Fix |
|---------|--------|-----|
| Entry at current bar close (look-ahead) | ✅ FIXED | `backtest_engine.py`: entry at `signal.index + 1` open; `stop_loss_func(df, signal_index, entry_price, direction)` contract |
| Intra-bar High/Low for stops | ✅ FIXED | `trade_simulator.py`: scans from entry bar (post-open movement); bars opening beyond SL/target fill at the OPEN (gap semantics); stop-before-target ambiguity kept conservative |
| Zero transaction costs / slippage | ✅ FIXED | 5 bps/side slippage default threaded through all broker cost models (`slippage_bps`); Zerodha taxes were already applied via `TradeProcessor` (finding overstated — costs were post-applied, slippage was genuinely zero) |
| Sharpe/Sortino/Calmar = 0.0 | ✅ FIXED | `performance_metrics.py`: real daily-return series from equity curve; Sharpe, Sortino, CAGR, annualized return, Calmar, MAR implemented; degenerate-input safe |
| No walk-forward embargo | ✅ FIXED | `walk_forward_windows.py`: `embargo_days=7` default gap between train/validation; strategies deep-copied per window (no parameter leakage) |
| No multiple testing correction | 🟡 PARTIAL | `grid_search.py`: ranks by Sharpe with `min_trades=30` gate on selection. Formal Deflated Sharpe Ratio deferred until per-run daily returns are persisted |
| Signal generation on current bar | ✅ NOT A BUG | Runner is correct once execution moves to next-bar open: bar `i`'s OHLC is fully known at its close; the fill is what must be next-bar. Strategies unchanged |
| No split/dividend adjustment | ✅ FIXED | `yahoo_provider.py`: `auto_adjust=True`, MultiIndex flattened once |
| Win rate treats breakeven as loss | ✅ FIXED | `metrics.py`: breakeven excluded from win/loss split; win rate over decided trades |
| Profit factor uses net returns | ✅ FIXED | PF now computed on gross rupee P&L |
| Position sizer ignores affordability | ✅ FIXED | `trade_processor.py`: quantity clamped to affordable shares; unaffordable trades skipped instead of crashing `CapitalManager.allocate` |

**Follow-up 2 (same day) — NEW CRITICAL BUG FOUND:** the parquet market-data cache keyed only on `(provider, instrument, timeframe)` and ignored date ranges, so **every walk-forward window silently backtested whichever slice was cached first** (all windows returned byte-identical results). Fixed in `MarketDataService` (coverage-aware serving: cache usable only when it spans the requested range; serves the exact slice) and `ParquetStore` (saves merge into full history instead of overwriting). Regression-tested. **Every WFE number produced before this fix was void** (on top of the earlier look-ahead void).

**Walk-forward verdict after all fixes (S01_MomentumRSI, NIFTY_50 ×5, 3y train / 1y OOS, 20 windows):** Avg IS return +5.54% vs Avg OOS **-1.94%**, WFE **-35.1%** (robustness bar: >50%). Only 3/20 windows profitable out-of-sample. Note: S01's parameter grid is currently degenerate (one value per parameter), so this measures pure OOS consistency, not selection overfitting — widening the search space comes before any real optimization claims. **Per project rules (OOS drop >30% → overfit): S01 is marked NO EDGE / overfit-class on this universe.**

Also fixed en route: `min_trades` gate defaulted to 30, which rejected every single-symbol 3-year training window (zero windows evaluated); now configurable (`--min_trades`, default 10).

**Not fixed here (still open):** multi-position portfolio constraints (sector limits, portfolio heat), overnight-gap entry modeling beyond stop gaps, AngelOne/Shoonya full tax models (stubbed with slippage only), formal multiple-testing correction, expanding-window walk-forward, non-degenerate parameter grids for real optimization studies, WFE display conflates "OOS>0" with efficiency when train return ≤ 0.

**All prior backtest results produced by this engine remain VOID** — re-run research only on the fixed engine.

---

## Resolution Log — Absorption Complete (2026-08-23)

The `engine/` codebase no longer exists. Final disposition (full per-file table in `ENGINE_TRIAGE.md`):

- **Absorbed into build:** `research/` package (backtest, data, optimization, walk_forward, runner, strategy, registry_adapter), `analytics/` additions (`risk_metrics.py` etc.), `storage/` parquet store, `data/instruments/`, `core/enums.py`.
- **Single source of truth for strategies:** `strategy/registry/`. Research runs those exact strategies via `research/registry_adapter.py`. Parity check proved the old research copies agreed with the live S01 on **0.7% of signal-days** — they were different strategies sharing a name. Copies archived in `research_archive/engine_strategies/`.
- **Costs unified:** backtests now price trades through build's `execution/tax.py` (`calculate_all_in_friction`: capped brokerage, buy+sell STT, DP charges, stamp, GST, SEBI/exchange fees) plus 5 bps slippage — replacing the undercharging duplicate Zerodha model.
- **Archived (preserved):** portfolio/capital layer, broker cost trio, root experiment scripts (~2,400 lines of untested duplicated backtest logic), network-hitting pseudo-tests, misc shims → `research_archive/`.
- **Verification at close:** 59 tests passing; consecutive research runs deterministic; real-S01 baseline stable at 47 trades / 34% WR across 5 Nifty large caps (2018+, daily bars).

**Standing caveats:** (1) real S01 v6.0 is a 15-minute-chart system — its fair evaluation requires a 1-minute data pipeline; daily-bar results are sample-starved; (2) walk-forward WFE display conflates "OOS > 0" with efficiency when train return ≤ 0; (3) formal Deflated Sharpe still pending per-run return-series persistence.
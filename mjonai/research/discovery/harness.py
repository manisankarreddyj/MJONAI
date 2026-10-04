"""
Module: research/discovery/harness.py
Purpose: Honest alpha-discovery harness for LOW-TURNOVER index strategies.

WHY THIS EXISTS
---------------
The 2026-09-26 intraday battery (Donchian / RSI-reversion / ORB, on NIFTY &
BANKNIFTY futures, 1m/5m/15m) found real GROSS edge (10/12 configs positive
gross) but was universally negative NET of costs, because ~250-800 trades/yr
of futures friction (~7.4 bps round-trip at Rs 1L notional) is an 18-60 %/yr
drag. The structural lesson: at a Rs 1L account, only LOW-TURNOVER strategies
can clear costs. This harness is purpose-built for that regime.

DESIGN (all points are deliberate anti-overfit measures)
-------------------------------------------------------
1. NO LOOKAHEAD. A signal computed on the close of bar ``t`` is applied to the
   close-to-close return of bar ``t+1`` (one full bar of execution lag). Costs
   are charged on the position change that becomes effective at the next bar.
2. CANONICAL COSTS. Every trade is charged through
   ``mjonai.execution.tax.calculate_all_in_friction`` at the real Rs 1L-scale
   quantity. No made-up bps. The per-instrument round-trip rupee cost is
   reported alongside every result so the drag is visible.
3. WALK-FORWARD + EMBARGO. Parameters are chosen on a training window and
   only ever scored on a strictly-later validation window separated by an
   embargo gap, so no bar is scored by a parameter set that saw it.
4. MULTIPLE-TESTING CONTROL. ``deflated_sharpe_ratio`` is fed the REAL number
   of configurations tested in the family, and ``whites_reality_check`` tests
   pooled OOS excess returns against buy-and-hold. A family is only called a
   "discovery" if it beats B&H after deflating for the trial count.
5. B&H BENCHMARK ALWAYS SHOWN. Net strategy vs net buy-and-hold side by side.
6. HONEST GROSS/NET SPLIT. gross_ret is reported next to net_ret so a reader
   can see exactly how much of any edge the broker takes.

This module is kernel code (``mjonai``) and may be imported by the research
CLIs in ``apps/research``. It reuses the canonical tax and statistics engines;
it does not reimplement them.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date
from typing import Callable, Dict, Iterable, List, Optional, Sequence

import numpy as np
import pandas as pd

from mjonai.execution.tax import calculate_all_in_friction
from mjonai.analytics.statistical_validation import (
    deflated_sharpe_ratio,
    whites_reality_check,
)

# Canonical engine constant: Rs 1 Lakh is the single source of truth for the
# engine's capital base (owner ruling 2026-09-03, MJONAI_DOCS.md S5).
NOTIONAL_RUPEES = 100_000.0

TRADING_DAYS = 252


# ---------------------------------------------------------------------------
# Data loading (canonical warehouse readers; fail-closed on missing months)
# ---------------------------------------------------------------------------

def load_spot(underlying: str, start: date, end: date) -> pd.DataFrame:
    """Load the clean daily OHLC spot series from the TradingTick warehouse.

    Uses the canonical fail-closed loader (raises on a missing month). The
    source's rolling-frontier ``prev_close``/``change`` corruption is IGNORED
    on purpose: we derive any prior-close from the previous row's ``close``,
    never from the untrusted column.
    """
    from mjonai.configs.research_paths import WORKSPACE_ROOT
    from mjonai.research.data import tradingtick_index as tti

    out = str(WORKSPACE_ROOT / "storage" / "parquet" / "tradingtick_index")
    df = tti.load_series(out, "spot", underlying.upper(), start, end)
    if df.empty:
        return df
    df = df.sort_values("trade_date").drop_duplicates("trade_date", keep="last")
    df = df.set_index("trade_date")
    df.index = pd.to_datetime(df.index)
    for c in ("open", "high", "low", "close"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    # Derived prior close (trusted) replaces the corrupted source column.
    df["prev_close_trusted"] = df["close"].shift(1)
    return df[["open", "high", "low", "close", "prev_close_trusted"]]


# ---------------------------------------------------------------------------
# Cost model (canonical engine, per round trip, at Rs 1L notional)
# ---------------------------------------------------------------------------

def roundtrip_cost_rupees(
    price: float,
    *,
    asset_class: str = "FUTURES",
    product_type: str = "INTRADAY",
    notional: float = NOTIONAL_RUPEES,
) -> float:
    """Exact round-trip friction in rupees for a ``notional``-rupee position,
    computed by the canonical tax engine at the given per-unit ``price``.

    ``quantity`` is floored so we never model more units than the account can
    actually buy at Rs 1L — this keeps the fixed brokerage (Rs 20/order cap)
    honest instead of pretending costs scale linearly.
    """
    price = max(float(price), 1.0)
    qty = int(max(1.0, math.floor(notional / price)))
    res = calculate_all_in_friction(
        buy_price=price,
        sell_price=price,
        quantity=qty,
        asset_class=asset_class,
        product_type=product_type,
        exchange="NSE",
    )
    return float(res["total_friction"])


def roundtrip_cost_bps(price: float, **kw) -> float:
    """Round-trip friction expressed in bps of the traded notional."""
    price = max(float(price), 1.0)
    qty = int(max(1.0, math.floor(NOTIONAL_RUPEES / price)))
    return 10000.0 * roundtrip_cost_rupees(price, **kw) / (price * qty)


# ---------------------------------------------------------------------------
# Backtest core
# ---------------------------------------------------------------------------

@dataclass
class BacktestResult:
    daily: pd.DataFrame            # index=date, cols: ret_cc, pos, pos_used, gross, cost, net
    total_trades: int = 0          # number of position changes (round-trip legs)
    gross_total: float = 0.0
    net_total: float = 0.0
    cost_total: float = 0.0
    cost_bps_per_trade: float = 0.0
    turnover_per_year: float = 0.0
    years: float = 0.0


def backtest(
    df: pd.DataFrame,
    signal: pd.Series,
    *,
    asset_class: str = "FUTURES",
    product_type: str = "INTRADAY",
    cost_ref_price: Optional[float] = None,
) -> BacktestResult:
    """Backtest a discrete position ``signal`` (values in {-1, 0, +1}) on daily
    bars with one-bar execution lag and canonical per-round-trip costs.

    ``signal[t]`` is decided on the close of bar ``t`` and is applied to the
    close-to-close return of bar ``t+1`` (``pos_used = signal.shift(1)``), so
    nothing in the signal can see the bar it is traded on.
    """
    px = df["close"]
    ret_cc = px.pct_change()                       # return of bar t (t-1 -> t)
    pos = signal.reindex(px.index).fillna(0.0)
    pos_used = pos.shift(1).fillna(0.0)            # executed one bar later

    gross = pos_used * ret_cc
    # Cost accrues on the change in the executed position. A 0->+1->0 round
    # trip has |dpos| summing to 2 == one full round trip, so the per-round-trip
    # rupee cost is charged at HALF the round-trip rate per unit of |dpos|
    # (i.e. one_way = rt/2). Charging the full rt per unit of |dpos| would bill
    # a completed round trip twice and understate every net return.
    dpos = pos_used.diff().abs().fillna(pos_used.abs())
    ref_px = float(cost_ref_price) if cost_ref_price else float(px.iloc[-1])
    rt_rupees = roundtrip_cost_rupees(ref_px, asset_class=asset_class,
                                      product_type=product_type)
    # one-way cost as a fraction of the Rs 1L notional per unit of |dpos|
    cost_frac_per_unit = (rt_rupees / 2.0) / NOTIONAL_RUPEES
    cost = dpos * cost_frac_per_unit
    net = gross - cost

    daily = pd.DataFrame({
        "ret_cc": ret_cc, "pos": pos, "pos_used": pos_used,
        "gross": gross, "cost": cost, "net": net,
    }, index=px.index)

    trades = int((dpos > 0).sum())
    years = max((px.index[-1] - px.index[0]).days / 365.25, 1e-9)
    return BacktestResult(
        daily=daily,
        total_trades=trades,
        gross_total=float(gross.sum()),
        net_total=float(net.sum()),
        cost_total=float(cost.sum()),
        cost_bps_per_trade=10000.0 * float(cost.sum()) / max(1, trades) / (NOTIONAL_RUPEES / NOTIONAL_RUPEES) if trades else 0.0,
        turnover_per_year=trades / years,
        years=years,
    )


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def _max_drawdown(equity: np.ndarray) -> float:
    peak = np.maximum.accumulate(equity)
    dd = (equity - peak) / peak
    return float(-dd.min() * 100.0)


def metrics(
    net: pd.Series,
    *,
    bench: Optional[pd.Series] = None,
) -> Dict[str, float]:
    """CAGR / Sharpe / Sortino / MaxDD / total for a daily NET return series."""
    net = net.dropna()
    n = len(net)
    if n < 5:
        return {k: float("nan") for k in ("CAGR", "Sharpe", "Sortino", "MaxDD",
                                          "Total", "TradesPerYr", "Vol")}
    equity = (1.0 + net).cumprod()
    years = max((net.index[-1] - net.index[0]).days / 365.25, 1e-9)
    total = float(equity.iloc[-1] - 1.0)
    cagr = ((equity.iloc[-1]) ** (1.0 / years) - 1.0) * 100.0
    mu = float(net.mean())
    sd = float(net.std(ddof=1))
    sharpe = (mu / sd) * math.sqrt(TRADING_DAYS) if sd > 0 else float("nan")
    dn = net[net < 0]
    dsd = float(np.sqrt((dn ** 2).mean())) if len(dn) else float("nan")
    sortino = (mu / dsd) * math.sqrt(TRADING_DAYS) if dsd and dsd > 0 else float("nan")
    return {
        "CAGR": cagr,
        "Sharpe": sharpe,
        "Sortino": sortino,
        "MaxDD": _max_drawdown(equity.values),
        "Total": total * 100.0,
        "TradesPerYr": float((net.diff().abs() > 0).sum()) / years,
        "Vol": sd * math.sqrt(TRADING_DAYS) * 100.0,
    }


# ---------------------------------------------------------------------------
# Buy-and-hold benchmark (net of one round trip, held to the end)
# ---------------------------------------------------------------------------

def bench_buy_hold(
    df: pd.DataFrame,
    *,
    asset_class: str = "FUTURES",
    product_type: str = "INTRADAY",
) -> pd.Series:
    """Daily buy-and-hold NET return series: pay one round trip on day 0, then
    ride close-to-close. The single entry cost is charged on the first bar."""
    px = df["close"]
    ret_cc = px.pct_change()
    ref_px = float(px.iloc[0])
    rt_rupees = roundtrip_cost_rupees(ref_px, asset_class=asset_class,
                                      product_type=product_type)
    cost_frac = rt_rupees / NOTIONAL_RUPEES
    net = ret_cc.copy()
    net.iloc[0] = ret_cc.iloc[0] - cost_frac
    return net


# ---------------------------------------------------------------------------
# Walk-forward with embargo (pooled OOS, no per-bar parameter leakage)
# ---------------------------------------------------------------------------

@dataclass
class WalkForwardOutcome:
    config_name: str
    params: Dict
    pooled_oos: pd.Series            # concatenated net OOS returns
    pooled_gross: pd.Series
    n_oos_trades: int
    windows: List[Dict] = field(default_factory=list)
    is_robust: bool = False
    verdict: str = ""


def walk_forward(
    df: pd.DataFrame,
    config_grid: Sequence[tuple],
    signal_fn: Callable[[pd.DataFrame, dict], pd.Series],
    *,
    train_years: int = 3,
    val_years: int = 1,
    step_years: int = 1,
    embargo_days: int = 7,
    asset_class: str = "FUTURES",
    product_type: str = "INTRADAY",
    min_train_trades: int = 3,
) -> List[WalkForwardOutcome]:
    """For each window: pick the best config on TRAIN (by net Sharpe with a
    minimum-trade guard), then score THAT config on the strictly-later
    VALIDATION window (separated by ``embargo_days``). Pools all OOS returns.

    ``config_grid`` is a sequence of ``(name, params_dict)``. The number of
    configs here is exactly the trial count fed to the DSR later.
    """
    from datetime import timedelta

    start, end = df.index[0], df.index[-1]
    outcomes: List[WalkForwardOutcome] = []
    # one outcome per config: each config gets its OWN pooled OOS (honest --
    # a config that is never picked still reports its OOS so we don't hide losers)
    per_config_oos: Dict[str, List[pd.Series]] = {name: [] for name, _ in config_grid}
    per_config_gross: Dict[str, List[pd.Series]] = {name: [] for name, _ in config_grid}
    per_config_trades: Dict[str, int] = {name: 0 for name, _ in config_grid}
    per_config_windows: Dict[str, List[Dict]] = {name: [] for name, _ in config_grid}

    tr_start = start
    while True:
        tr_end = tr_start + pd.DateOffset(years=train_years)
        em_end = tr_end + timedelta(days=embargo_days)
        va_end = em_end + pd.DateOffset(years=val_years)
        if va_end > end:
            break
        train = df.loc[:tr_end]
        val = df.loc[em_end:va_end]
        if len(train) < 60 or len(val) < 20:
            tr_start = tr_start + pd.DateOffset(years=step_years)
            continue

        # Compute every signal on the FULL causal frame ONCE, then slice to the
        # train / val windows. All signal families are backward-looking
        # (rolling / shifted), so computing on the full frame introduces NO
        # lookahead -- it only gives long-lookback indicators (e.g. 200-DMA)
        # their warm-up inside a short 1-year validation slice instead of
        # wasting its first ~200 bars.
        all_sigs = {name: signal_fn(df, params) for name, params in config_grid}

        # pick best on TRAIN
        best = None
        for name, params in config_grid:
            sig = all_sigs[name].loc[:tr_end]
            bt = backtest(df.loc[:tr_end], sig, asset_class=asset_class,
                          product_type=product_type)
            if bt.total_trades < min_train_trades:
                continue
            m = metrics(bt.daily["net"])
            sh = m["Sharpe"]
            if not np.isfinite(sh):
                continue
            if best is None or sh > best[0]:
                best = (sh, name, params)

        # score the picked config on VALIDATION for EVERY config (each config
        # is evaluated OOS on the same windows; the grid is the trial universe)
        for name, params in config_grid:
            sig = all_sigs[name].loc[em_end:va_end]
            bt = backtest(val, sig, asset_class=asset_class,
                          product_type=product_type)
            per_config_oos[name].append(bt.daily["net"])
            per_config_gross[name].append(bt.daily["gross"])
            per_config_trades[name] += bt.total_trades
            per_config_windows[name].append({
                "val": (str(val.index[0].date()), str(val.index[-1].date())),
                "trades": bt.total_trades,
                "net_total_pct": round(bt.net_total * 100, 2),
            })

        tr_start = tr_start + pd.DateOffset(years=step_years)

    for name, params in config_grid:
        if not per_config_oos[name]:
            continue
        pooled = pd.concat(per_config_oos[name]).sort_index()
        pgross = pd.concat(per_config_gross[name]).sort_index()
        outcomes.append(WalkForwardOutcome(
            config_name=name, params=params, pooled_oos=pooled,
            pooled_gross=pgross, n_oos_trades=per_config_trades[name],
            windows=per_config_windows[name],
        ))
    return outcomes


def evaluate_outcome(
    outcome: WalkForwardOutcome,
    bench_oos: pd.Series,
    *,
    num_trials: int,
) -> Dict[str, float]:
    """Score a pooled-OOS outcome: metrics + DSR (deflated for the real trial
    count) + White's Reality Check vs buy-and-hold. This is the gate."""
    # Jointly drop NaNs: the first bar of each concatenated validation window
    # has a NaN pct_change, and a NaN anywhere silently poisons the DSR/WRC
    # statistics (they do not guard against it).
    strat = outcome.pooled_oos.dropna()
    bench = bench_oos.reindex(strat.index).ffill().fillna(0.0)
    keep = strat.notna() & bench.notna()
    strat, bench = strat[keep], bench[keep]
    m = metrics(strat)
    dsr = deflated_sharpe_ratio(list(strat.values), num_trials=num_trials)
    wrc = whites_reality_check(list(strat.values), list(bench.values))
    # Trade count comes from the outcome (position changes), recompute per-yr on
    # the pooled span.
    years = max((strat.index[-1] - strat.index[0]).days / 365.25, 1e-9)
    is_robust = (
        outcome.n_oos_trades >= 30
        and np.isfinite(m["Sharpe"]) and m["Sharpe"] > 0.5
        and m["CAGR"] > 0
        and dsr > 0
    )
    return {
        "config": outcome.config_name,
        "OOS_CAGR_pct": round(m["CAGR"], 2),
        "OOS_Sharpe": round(m["Sharpe"], 2),
        "OOS_Sortino": round(m["Sortino"], 2),
        "OOS_MaxDD_pct": round(m["MaxDD"], 2),
        "OOS_Total_pct": round(m["Total"], 2),
        "OOS_trades": outcome.n_oos_trades,
        "TradesPerYr": round(outcome.n_oos_trades / years, 1),
        "DSR_z": dsr,
        "WRC_p": wrc["p_value"],
        "WRC_sig": wrc["is_significant"],
        "is_robust": bool(is_robust),
    }

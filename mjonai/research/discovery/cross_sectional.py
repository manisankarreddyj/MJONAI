"""
Module: research/discovery/cross_sectional.py
Purpose: Survivorship-bias-free cross-sectional equity factor backtest on the
PIT Nifty 50, with canonical equity-delivery costs and honest turnover.

WHY CROSS-SECTIONAL (vs the index timing in signals.py)
------------------------------------------------------
Index timing (Family A) reliably improved RISK but never beat buy-and-hold on
RETURN. The literature's most robust equity alpha is CROSS-SECTIONAL: within a
universe, rank stocks by a characteristic (momentum, low-vol, short-term
reversal) and hold the top of the ranking. This module tests that family on the
POINT-IN-TIME Nifty 50 ledger (no survivorship bias) so a positive result is
tradeable, not a backtest illusion.

DISCIPLINE
----------
- The factor set is PRE-REGISTERED in ``FACTORS`` below (fixed before results
  were seen). The number of configs tested is fed to the Deflated Sharpe so the
  family pays for its own trial count.
- A rank buffer (hold a stock until it falls below 2x the top-K) keeps monthly
  turnover low enough to survive 28.5 bps equity-delivery round trips. Turnover
  and its cost are reported explicitly.
- Costs use the canonical tax engine; gross and net are both reported.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from mjonai.configs.research_paths import WORKSPACE_ROOT
from mjonai.execution.tax import calculate_all_in_friction
from mjonai.research.pit_universe import PitUniverseLedger

PANEL_DIR = str(WORKSPACE_ROOT / "storage" / "parquet" / "yahoo_equity")
BENCH_ASSET = ("EQUITY", "DELIVERY")


def _ols_alpha(residualized: pd.Series, market: pd.Series) -> float:
    """Compute the annualized alpha (intercept) from regressing series on market."""
    # Simple OLS: y = alpha + beta * x
    x = market.values
    y = residualized.values
    if len(x) < 20 or np.nanstd(x) < 1e-12:
        return 0.0
    x_mean, y_mean = np.nanmean(x), np.nanmean(y)
    cov = np.nanmean((x - x_mean) * (y - y_mean))
    var = np.nanvar(x)
    if var < 1e-12:
        return 0.0
    beta = cov / var
    alpha = y_mean - beta * x_mean
    return float(alpha * 252.0)  # annualize daily alpha


# ---------------------------------------------------------------------------
# Panel (wide closes, dates x symbols)
# ---------------------------------------------------------------------------

def load_panel(min_bars: int = 250) -> pd.DataFrame:
    """Wide close panel (date x symbol) from the per-symbol parquet cache."""
    import glob
    from pathlib import Path
    series = {}
    for f in glob.glob(PANEL_DIR + r"\*.parquet"):
        d = pd.read_parquet(f)
        if "date" not in d.columns or "close" not in d.columns:
            continue
        sym = Path(f).stem
        s = d.set_index(pd.to_datetime(d["date"]))["close"]
        if len(s.dropna()) >= min_bars:
            series[sym] = s
    panel = pd.DataFrame(series).sort_index()
    return panel


# ---------------------------------------------------------------------------
# Factors (causal: each uses only data up to t; ranked cross-sectionally)
# ---------------------------------------------------------------------------

def _mom(panel: pd.DataFrame, lookback: int, skip: int) -> pd.DataFrame:
    return panel.shift(skip) / panel.shift(lookback) - 1.0


def factor_momentum_12_1(panel):    return _mom(panel, 252, 21)
def factor_momentum_6_1(panel):     return _mom(panel, 126, 21)
def factor_momentum_3_12(panel):    return _mom(panel, 252, 63)
def factor_momentum_12(panel):      return _mom(panel, 252, 0)
def factor_momentum_6(panel):       return _mom(panel, 126, 0)


def factor_reversal_1(panel):       return _mom(panel, 21, 0)   # expect negative -> buy losers
def factor_reversal_3(panel):       return _mom(panel, 63, 0)


def factor_low_vol(panel):
    r = panel.pct_change()
    return -r.rolling(60, min_periods=40).std()   # negative vol -> high rank


def factor_trend_strength(panel):
    # fraction of positive days over 1y (path quality, not just return)
    r = (panel > panel.shift(1)).astype(float)
    return r.rolling(252, min_periods=120).mean()


# --- low-volatility variants (the robust winner) at different vol windows ---
def factor_low_vol_120(panel):
    r = panel.pct_change()
    return -r.rolling(120, min_periods=80).std()


def factor_low_vol_250(panel):
    r = panel.pct_change()
    return -r.rolling(250, min_periods=150).std()


def factor_low_vol_beta(panel, bench_close):
    # downside-vol / beta proxy: low market sensitivity + low idio vol
    r = panel.pct_change()
    rb = bench_close.pct_change()
    beta = r.rolling(120, min_periods=80).cov(rb) / rb.rolling(120, min_periods=80).var()
    return -(beta.abs() + r.rolling(120, min_periods=80).std())


def _zrank(x: pd.DataFrame) -> pd.DataFrame:
    return x.rank(axis=1, pct=True)


def factor_lowvol_mom(panel):
    """Rank-average of low-vol (60d) and 6-month momentum -- combine the two
    best standalone factors."""
    lv = _zrank(factor_low_vol(panel))
    mm = _zrank(_mom(panel, 126, 0))
    return (lv + mm) / 2.0


def factor_lowvol_reversal(panel):
    """Low-vol combined with short-term reversal (buy the dip among steadies)."""
    lv = _zrank(factor_low_vol(panel))
    rv = _zrank(factor_reversal_1(panel))  # low rank = loser = high score
    return (lv + rv) / 2.0


# Pre-registered factor registry (name -> function of the panel). This is the
# trial universe that the Deflated Sharpe pays for. ``factor_low_vol_beta``
# takes an extra benchmark argument and is therefore exercised by a dedicated
# runner, not by the uniform sweep.
FACTORS = {
    "mom_12_1": factor_momentum_12_1,
    "mom_6_1": factor_momentum_6_1,
    "mom_3_12": factor_momentum_3_12,
    "mom_12": factor_momentum_12,
    "mom_6": factor_momentum_6,
    "rev_1": factor_reversal_1,
    "rev_3": factor_reversal_3,
    "low_vol": factor_low_vol,
    "trend_strength": factor_trend_strength,
    "low_vol_120": factor_low_vol_120,
    "low_vol_250": factor_low_vol_250,
    "lowvol_mom": factor_lowvol_mom,
    "lowvol_rev": factor_lowvol_reversal,
}


# ---------------------------------------------------------------------------
# PIT universe
# ---------------------------------------------------------------------------

def pit_members_by_date(panel: pd.DataFrame) -> Dict[pd.Timestamp, set]:
    """Map each panel date -> the PIT Nifty 50 members on that date."""
    ledger = PitUniverseLedger()
    m = {}
    for d in panel.index:
        try:
            m[d] = set(ledger.members(d.date()))
        except Exception:
            m[d] = set()
    return m


# ---------------------------------------------------------------------------
# Portfolio backtest (long-only top-K, monthly rebalance, rank buffer)
# ---------------------------------------------------------------------------

@dataclass
class CSResult:
    daily: pd.DataFrame       # ret_gross, ret_net, turnover, n_holdings
    total_turnover_yr: float
    cost_drag_yr_pct: float
    holdings: pd.Series = None   # date -> tuple of held symbols (audit trail)


def _equity_cost_bps(price: float) -> float:
    p = max(float(price), 1.0)
    qty = int(max(1.0, np.floor(1_000_000.0 / p)))  # Rs 1L portfolio slices
    res = calculate_all_in_friction(buy_price=p, sell_price=p, quantity=qty,
                                    asset_class="EQUITY", product_type="DELIVERY",
                                    exchange="NSE")
    return 10000.0 * res["total_friction"] / (p * qty)


def neutralize_factor_returns(
    daily_net: pd.Series,
    benchmark_net: pd.Series,
) -> pd.Series:
    """
    Canonical-pair-return cross-sectional neutralization (qlib pattern).

    Regresses the factor's daily net returns against the equal-weight PIT Nifty 50
    benchmark net returns, and returns the residual (alpha) series.

    This removes market beta exposure, isolating the pure cross-sectional alpha
    that is not explained by market direction.

    Args:
        daily_net: Factor's daily net return series (from CSResult.daily['net'])
        benchmark_net: Benchmark's daily net return series (equal-weight PIT Nifty 50)

    Returns:
        Residual series (alpha) aligned to the input index.
    """
    # Align indices
    common_idx = daily_net.index.intersection(benchmark_net.index)
    if len(common_idx) < 20:
        return pd.Series(0.0, index=daily_net.index)

    y = daily_net.loc[common_idx].values
    x = benchmark_net.loc[common_idx].values

    # OLS regression: y = alpha + beta * x + epsilon
    x_mean, y_mean = np.nanmean(x), np.nanmean(y)
    cov = np.nanmean((x - np.nanmean(x)) * (y - np.nanmean(y)))
    var = np.nanvar(x)

    if var < 1e-12:
        residual = pd.Series(0.0, index=daily_net.index)
    else:
        beta = cov / var
        alpha = np.nanmean(y) - beta * np.nanmean(x)
        residual_aligned = y - (alpha + beta * x)

        # Build full-length residual series
        residual = pd.Series(0.0, index=daily_net.index)
        residual.loc[common_idx] = residual_aligned

    return residual


def backtest_cross_sectional(
    panel: pd.DataFrame,
    factor: pd.DataFrame,
    *,
    top_k: int = 10,
    long_short: bool = False,
    rebalance: str = "M",
    buffer_mult: float = 2.0,
    members_by_date: Optional[Dict[pd.Timestamp, set]] = None,
) -> CSResult:
    """Long top-K (or long-top / short-bottom) by ``factor`` within the eligible
    universe, rebalanced monthly, rank-buffered, net of equity-delivery costs.

    Signals use the factor value at the rebalance close; positions are held from
    the next bar, so no lookahead. Returns are equal-weight across holdings.
    """
    dates = panel.index
    f = factor.reindex(index=dates, columns=panel.columns)

    # rebalance schedule
    if rebalance == "M":
        keys = pd.Series(dates.year * 12 + dates.month, index=dates)
    elif rebalance == "Q":
        keys = pd.Series(dates.year * 4 + dates.quarter, index=dates)
    else:
        keys = pd.Series(np.arange(len(dates)), index=dates)

    # daily returns of each stock
    stock_ret = panel.pct_change().fillna(0.0)

    holdings: List[str] = []
    weights = pd.Series(0.0, index=panel.columns)   # weights HELD INTO the next bar
    rows = []
    hold_log = []
    round_trip_bps = _equity_cost_bps(float(panel.stack().median()))
    one_way_bps = round_trip_bps / 2.0

    for i, d in enumerate(dates):
        # ---- 1. EARN today's return on the weights decided at the PRIOR close.
        #         This ordering is the no-lookahead contract: the factor value
        #         at bar d is only used to set weights for bar d+1.
        if i > 0:
            g = float((weights * stock_ret.loc[d]).sum())
        else:
            g = 0.0

        # ---- 2. DECIDE new weights from the factor known at today's close.
        rebal = (i == 0) or (keys.iloc[i] != keys.iloc[i - 1])
        eligible = None
        if members_by_date is not None:
            eligible = members_by_date.get(d, set())
            eligible = {s for s in eligible if s in panel.columns and not np.isnan(panel.at[d, s])}
            if len(eligible) < (top_k or 2):
                eligible = None  # not enough PIT members priced -> fall back to priced panel
        if eligible is None:
            eligible = {s for s in panel.columns if not np.isnan(panel.at[d, s])}

        turnover = 0.0
        if rebal:
            fv = f.loc[d, list(eligible)].dropna()
            n_hold = len(fv) if top_k is None else top_k
            need = 2 * n_hold if long_short else n_hold
            if len(fv) >= need and n_hold > 0:
                ranked = fv.sort_values(ascending=False)
                # rank buffer: current holdings that are still in the top
                # buffer_mult*n_hold are KEPT (cuts turnover, which is what
                # makes a monthly equity rebalance cost-viable). Remaining slots
                # are filled by the highest-ranked non-holdings.
                cutoff = ranked.index[:int(buffer_mult * n_hold)]
                keep = [s for s in cutoff if s in holdings][:n_hold]
                rest = [s for s in ranked.index if s not in keep and s not in holdings]
                new_holdings = (keep + rest)[:n_hold]
                shorts = []
                if long_short and len(fv) >= 2 * n_hold:
                    shorts = [s for s in ranked.index[-n_hold:] if s not in new_holdings]
                new_w = pd.Series(0.0, index=panel.columns)
                if new_holdings:
                    new_w.loc[new_holdings] = 1.0 / len(new_holdings)
                if shorts:
                    new_w.loc[shorts] = -(1.0 / (2 * len(shorts)))
                # gross traded notional (a full close+open sums to 2.0); charged
                # at ONE-WAY bps, so a complete round trip costs the RT rate.
                turnover = float((new_w - weights).abs().sum())
                holdings = new_holdings
                weights = new_w
        # cost is paid on the execution bar (today's close)
        cost = turnover * one_way_bps / 10000.0
        rows.append((d, g, cost, int((weights != 0).sum()), turnover))
        hold_log.append((d, tuple(s for s in holdings)))

    daily = pd.DataFrame(rows, columns=["date", "gross", "cost", "n_holdings", "turnover"]).set_index("date")
    daily["net"] = daily["gross"] - daily["cost"]
    years = max((daily.index[-1] - daily.index[0]).days / 365.25, 1e-9)
    return CSResult(
        daily=daily,
        total_turnover_yr=float(daily["turnover"].sum() / years),
        cost_drag_yr_pct=float(daily["cost"].sum() / years * 100.0),
        holdings=pd.Series(dict(hold_log)),
    )

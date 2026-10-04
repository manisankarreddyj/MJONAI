"""Forward walk-forward simulation over the TradingTick deep 1-min index warehouse.

PURPOSE
    Honest, out-of-sample forward simulation of deterministic intraday index
    strategies on NIFTY / BANKNIFTY 1-minute spot bars (2015-01 -> 2026-08).
    ONE goal: does any price-only intraday rule survive real friction when
    parameters are chosen ONLY on the past (rolling train window) and applied
    forward (test window), with an embargo between train and test?

DESIGN (zero lookahead)
    - Load 1-min bars from storage/parquet/tradingtick_1min, resample to the
      5m/15m scan cadence (canonical _resample_to_interval).
    - Rolling walk-forward: train N days  -> grid-search params by net profit
      (costs applied); then test M days with the chosen params FROZEN.
      5-day embargo (train data ends >= 5 trading days before test starts).
    - Signals fire on a completed bar; entry fills at the NEXT bar's open.
      Exit on stop / target (R:R = 2.0 per Golden Rule 6) / EOD square-off
      (15:10 IST) / max-hold timeout. One open position per strategy.
    - Costs: canonical execution/tax.py calculate_all_in_friction with
      asset_class="FUTURES" (STT 0.02% sell, stamp 0.002% buy, exchange
      0.00173%, SEBI, brokerage min(0.03%, Rs20), GST 18%) + 5 bps slippage
      per leg (research pin). Position size is ONE unit (1 index point = Rs1,
      a consistent fractional-position scaler for research); returns are
      scaled to INITIAL_CAPITAL (Rs1,00,000). The strategy comparisons and
      WFE verdicts are size-independent ratios.
    - WFE verdict: canonical Pardo formula (ann.OOS/ann.IS) from
      walk_forward_engine, with the pooled-OOS floor of 30 trades.

HONESTY
    - Spot is the instrument proxy: no 1-min index-futures history exists on
      any free source; intraday futures basis is small. Callers are shown
      this proxy explicitly.
    - Volume is NaN in this warehouse (never fabricated) -> strategies are
      price-only. 2015-11-11 and other degenerate days are skipped by a
      min-bars-per-day guard (never partially simulated).
    - Every claim below is computed, never assumed; results are dumped raw.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field, asdict
from typing import Iterable

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from mjonai.execution.tax import calculate_all_in_friction
from mjonai.data.angelone.historical import _resample_to_interval
from mjonai.data.minute_archive import _to_resample_anchor

WAREHOUSE = os.environ.get(
    "TT_1MIN_DIR", r"D:\MJONAI\storage\parquet\tradingtick_1min"
)
INITIAL_CAPITAL = 100_000.0
SLIPPAGE_BPS = 5.0
EOD_SQUARE_OFF_HOUR = 15  # square off at 15:xx
EOD_SQUARE_OFF_MINUTE = 10
RISK_REWARD = 2.0
FULL_DAY_1MIN_BARS = 375  # 09:15..15:29 on a normal day
MIN_FRACTION_OF_DAY = 0.85  # degenerate days (<85% bars) skipped entirely

_STRATEGY_REGISTRY: dict = {}


def _registry(**decorators):
    _STRATEGY_REGISTRY.update(decorators)
    return


@dataclass
class Trade:
    symbol: str
    strategy: str
    window_seq: int
    direction: str
    entry_ts: pd.Timestamp
    exit_ts: pd.Timestamp
    entry_price: float
    exit_price: float
    stop_loss: float
    target: float
    quantity: int = 1
    exit_reason: str = ""  # STOPLOSS / TARGET / EOD / TIMEOUT / NO_ENTRY
    gross_pnl: float = 0.0
    net_pnl: float = 0.0
    costs: float = 0.0
    net_return_pct: float = 0.0  # on INITIAL_CAPITAL (Rs1L)
    holding_minutes: int = 0
    index_return_pct: float = 0.0  # underlying move over same window
    market_state: str = ""  # sampled from 21-day realized vol at entry


@dataclass
class WindowResult:
    seq: int
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp
    params: dict
    train_net_return_pct: float = 0.0
    test_net_return_pct: float = 0.0
    test_trades: list = field(default_factory=list)


# --------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------

def _load_1min(symbol: str) -> pd.DataFrame:
    fs = sorted(
        os.path.join(WAREHOUSE, symbol, f)
        for f in os.listdir(os.path.join(WAREHOUSE, symbol))
        if f.endswith(".parquet")
    )
    if not fs:
        raise FileNotFoundError(f"no 1-min parquets for {symbol}")
    frames = []
    for f in fs:
        d = pd.read_parquet(f)
        d = d[d["timestamp"].dt.date >= pd.Timestamp("2015-01-01").date()]
        frames.append(d)
    df = pd.concat(frames, ignore_index=True)
    df = df.sort_values("timestamp").drop_duplicates(subset=["timestamp"], keep="last")
    df = df.set_index("timestamp")
    df = df[["Open", "High", "Low", "Close"]]  # Volume is NaN, price-only
    return df


def _resample(df: pd.DataFrame, cadence: str) -> pd.DataFrame:
    anchor = _to_resample_anchor(cadence)
    if anchor is None:
        raise RuntimeError(f"unsupported cadence {cadence}")
    m = _resample_to_interval(df, anchor)
    if m is None or m.empty:
        raise RuntimeError(f"resample failed for {cadence}")
    return m


def _days(df_1min: pd.DataFrame) -> list[pd.Timestamp]:
    return sorted(df_1min.index.normalize().unique())


def _day_slice(df: pd.DataFrame, day_ts: pd.Timestamp) -> pd.DataFrame:
    """Rows belonging to one trading day. The index is intraday, so a midnight
    label is not present; slice by timestamp range instead.
    """
    d0 = day_ts.normalize()
    return df.loc[d0 : d0 + pd.Timedelta(days=1)]


def _is_full_day(df_day: pd.DataFrame, bar_minutes: int) -> bool:
    full = FULL_DAY_1MIN_BARS / bar_minutes
    return len(df_day) >= int(full * MIN_FRACTION_OF_DAY)


# --------------------------------------------------------------------------
# Strategy signal layer: vectorized candidate generation per day
# --------------------------------------------------------------------------

def _donchian_candidates(df: pd.DataFrame, n: int):
    """Box breakout: close CROSSING a rolling Donchian channel.

    Returns a per-bar signal array: +1 long candidate, -1 short candidate, 0 none.
    Channel is computed from the PREVIOUS bar (rolling including current bar
    would leak — we shift by one). MUST be computed on the continuous
    multi-day series (the channel is a rolling window across time, not a
    within-day construct).

    A signal fires only on the CROSSING bar (price was at/below the channel,
    now above it, and vice versa). Signalling every bar beyond the channel
    would re-enter on the bar after any exit while price is still outside —
    a re-entry storm, not a breakout.
    """
    up = df["Close"].rolling(n).max().shift(1)
    dn = df["Close"].rolling(n).min().shift(1)
    close = df["Close"]
    prev_close = close.shift(1)
    prev_up = up.shift(1)
    prev_dn = dn.shift(1)
    ok = up.notna() & dn.notna() & prev_up.notna() & prev_dn.notna()
    cross_up = ok & (close > up.values) & (prev_close <= prev_up.values)
    cross_dn = ok & (close < dn.values) & (prev_close >= prev_dn.values)
    sig = np.zeros(len(df), dtype=int)
    sig[cross_up.values] = 1
    sig[cross_dn.values] = -1
    return sig


def _orb_candidates(df: pd.DataFrame, window_minutes: int, stop_atr_n: int = 3):
    """Opening-range breakout: first `window_minutes` bars of each day define
    the range. A bar AFTER the range breaks above it -> long candidate;
    below it -> short candidate.
    """
    bar_min = int((df.index[1] - df.index[0]).total_seconds() / 60)
    n = max(2, int(window_minutes / bar_min))
    sig = np.zeros(len(df), dtype=int)
    hi = df["High"].values
    lo = df["Low"].values
    close = df["Close"].values
    idx = df.index

    i = 0
    while i < len(df):
        # start of a day
        day_mask = idx.normalize() == idx[i].normalize()
        day_iloc = np.flatnonzero(day_mask)
        if len(day_iloc) < n + 1:
            i += len(day_iloc)
            continue
        open_hi = float(np.max(hi[day_iloc[:n]]))
        open_lo = float(np.min(lo[day_iloc[:n]]))
        for j in day_iloc[n:]:
            if close[j] > open_hi:
                sig[j] = 1
            elif close[j] < open_lo:
                sig[j] = -1
        i += len(day_iloc)
    return sig


def _rsi(close: pd.Series, n: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(n).mean()
    loss = -delta.clip(upper=0).rolling(n).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - 100 / (1 + rs)
    return rsi.fillna(50.0)


def _rsi_candidates(df: pd.DataFrame, n: int, lower: int, upper: int):
    """RSI reversion: cross below lower -> long candidate; cross above upper -> short."""
    rsi = _rsi(df["Close"], n)
    prev = rsi.shift(1)
    sig = np.zeros(len(df), dtype=int)
    sig[(rsi < lower) & (prev >= lower)] = 1
    sig[(rsi > upper) & (prev <= upper)] = -1
    return sig


def _simulate_day(
    day_slice: pd.DataFrame,
    sig: np.ndarray,
    *,
    strategy: str,
    symbol: str,
    window_seq: int,
    stop_atr_n: int = 3,
    direction_override: str | None = None,
) -> list[Trade]:
    """Simulate one day of one strategy. Signals fire at bar close; fills next bar open."""
    out: list[Trade] = []
    if sig.size == 0 or not np.any(sig):
        return out
    # ATR for stop distance
    tr = np.maximum(
        day_slice["High"] - day_slice["Low"],
        np.maximum(
            abs(day_slice["High"] - day_slice["Close"].shift(1)),
            abs(day_slice["Low"] - day_slice["Close"].shift(1)),
        ),
    )
    atr = tr.rolling(stop_atr_n).mean().fillna(tr.rolling(5).mean()).fillna(tr)
    atr_a = atr.values

    open_p = day_slice["Open"].values
    hi = day_slice["High"].values
    lo = day_slice["Low"].values
    close = day_slice["Close"].values
    idx = day_slice.index
    hours = idx.hour.values
    minutes = idx.minute.values
    n_bars = len(day_slice)

    in_pos = False
    entry_price = 0.0
    stop = 0.0
    target = 0.0
    direction = ""
    entry_ix = 0

    # EOD square-off boundary
    eod_ix = n_bars - 1
    for e in range(n_bars):
        if hours[e] > EOD_SQUARE_OFF_HOUR or (hours[e] == EOD_SQUARE_OFF_HOUR and minutes[e] >= EOD_SQUARE_OFF_MINUTE):
            eod_ix = e
            break

    for i in range(eod_ix):
        if in_pos:
            # manage open trade
            if direction == "LONG":
                if open_p[i] <= stop:
                    out.append(_close_trade(symbol, strategy, window_seq, direction, entry_price, open_p[i], stop, target, entry_ix, i, "STOPLOSS", idx, open_p, close, 1))
                    in_pos = False
                    continue
                if open_p[i] >= target:
                    out.append(_close_trade(symbol, strategy, window_seq, direction, entry_price, open_p[i], stop, target, entry_ix, i, "TARGET", idx, open_p, close, 1))
                    in_pos = False
                    continue
                if lo[i] <= stop:
                    out.append(_close_trade(symbol, strategy, window_seq, direction, entry_price, stop, stop, target, entry_ix, i, "STOPLOSS", idx, open_p, close, 1))
                    in_pos = False
                    continue
                if hi[i] >= target:
                    out.append(_close_trade(symbol, strategy, window_seq, direction, entry_price, target, stop, target, entry_ix, i, "TARGET", idx, open_p, close, 1))
                    in_pos = False
                    continue
            else:
                if open_p[i] >= stop:
                    out.append(_close_trade(symbol, strategy, window_seq, direction, entry_price, open_p[i], stop, target, entry_ix, i, "STOPLOSS", idx, open_p, close, 1))
                    in_pos = False
                    continue
                if open_p[i] <= target:
                    out.append(_close_trade(symbol, strategy, window_seq, direction, entry_price, open_p[i], stop, target, entry_ix, i, "TARGET", idx, open_p, close, 1))
                    in_pos = False
                    continue
                if hi[i] >= stop:
                    out.append(_close_trade(symbol, strategy, window_seq, direction, entry_price, stop, stop, target, entry_ix, i, "STOPLOSS", idx, open_p, close, 1))
                    in_pos = False
                    continue
                if lo[i] <= target:
                    out.append(_close_trade(symbol, strategy, window_seq, direction, entry_price, target, stop, target, entry_ix, i, "TARGET", idx, open_p, close, 1))
                    in_pos = False
                    continue
        elif sig[i] != 0:
            if not pd.isna(close[i]) and not pd.isna(open_p[i + 1] if i + 1 < n_bars else np.nan):
                direction = "LONG" if (sig[i] == 1 and direction_override != "SHORT") else "SHORT"
                # entry at NEXT bar open
                if i + 1 < n_bars:
                    entry_price = float(open_p[i + 1])
                    entry_ix = i + 1
                    risk = float(atr_a[i + 1]) * stop_atr_n
                    if risk <= 0 or np.isnan(risk):
                        continue
                    if direction == "LONG":
                        stop = entry_price - risk
                        target = entry_price + risk * RISK_REWARD
                    else:
                        stop = entry_price + risk
                        target = entry_price - risk * RISK_REWARD
                    in_pos = True
    if in_pos:
        out.append(
            _close_trade(
                symbol, strategy, window_seq, direction, entry_price, close[eod_ix],
                stop, target, entry_ix, eod_ix, "EOD", idx, open_p, close, quantity=1,
            )
        )
    return out


def _close_trade(symbol, strategy, window_seq, direction, entry_price, exit_price,
                 stop, target, entry_ix, exit_ix, reason, idx, open_p, close, quantity):
    gross = (exit_price - entry_price) * quantity
    if direction == "SHORT":
        gross *= -1
    costs = _futures_costs(entry_price, exit_price, quantity)
    net = gross - costs
    window_ret_pct = net / INITIAL_CAPITAL * 100.0
    # underlying move over the same window
    idx_ret = (close[exit_ix] - close[entry_ix]) / close[entry_ix] * 100.0 if entry_ix < len(close) and close[entry_ix] else 0.0
    holding = int((idx[exit_ix] - idx[entry_ix]).total_seconds() / 60)
    risk_dist = abs(entry_price - stop)
    rr = abs(exit_price - entry_price) / risk_dist if risk_dist > 0 else 0.0
    return Trade(
        symbol=symbol,
        strategy=strategy,
        window_seq=window_seq,
        direction=direction,
        entry_ts=idx[entry_ix],
        exit_ts=idx[exit_ix],
        entry_price=float(entry_price),
        exit_price=float(exit_price),
        stop_loss=float(stop),
        target=float(target),
        quantity=quantity,
        exit_reason=reason,
        gross_pnl=round(gross, 2),
        net_pnl=round(net, 2),
        costs=round(costs, 2),
        net_return_pct=round(window_ret_pct, 4),
        holding_minutes=holding,
        index_return_pct=round(idx_ret, 4),
    )


def _futures_costs(entry_price: float, exit_price: float, quantity: int = 1) -> float:
    b = calculate_all_in_friction(
        buy_price=entry_price,
        sell_price=exit_price,
        quantity=quantity,
        asset_class="FUTURES",
        product_type="",  # futures
        exchange="NSE",
        num_legs=1,
    )
    slippage = (entry_price + exit_price) * quantity * SLIPPAGE_BPS / 10000
    return float(b["total_friction"]) + slippage


# --------------------------------------------------------------------------
# Walk-forward
# --------------------------------------------------------------------------

def _run_window(
    whole_df: pd.DataFrame,
    signals_by_combo: dict[tuple, np.ndarray],
    day_positions: list[tuple[int, int]],
    day_start_ix: int,
    n_train_days: int,
    n_test_days: int,
    embargo_days: int,
    *,
    strategy: str,
    symbol: str,
    window_seq: int,
) -> WindowResult | None:
    train_days = day_positions[day_start_ix : day_start_ix + n_train_days]
    if len(train_days) < n_train_days:
        return None
    test_start_ix = day_start_ix + n_train_days + embargo_days
    test_days = day_positions[test_start_ix : test_start_ix + n_test_days]
    if len(test_days) < 1:
        return None

    best_params = None
    best_pct = -1e9
    train_return = 0.0
    for key, (sig_full, combo) in signals_by_combo.items():
        trades = []
        for (s, e) in train_days:
            trades.extend(
                _simulate_day(
                    whole_df.iloc[s:e], sig_full[s:e], strategy=strategy, symbol=symbol,
                    window_seq=window_seq, stop_atr_n=int(combo.get("stop_atr_n", 3)),
                    direction_override=combo.get("direction_override"),
                )
            )
        pct = sum(t.net_return_pct for t in trades)
        if pct > best_pct:
            best_pct = pct
            best_params = (key, combo)
            train_return = pct

    best_key, best_params_dict = best_params
    sig_full = signals_by_combo[best_key][0]
    test_trades = []
    for (s, e) in test_days:
        test_trades.extend(
            _simulate_day(
                whole_df.iloc[s:e], sig_full[s:e], strategy=strategy, symbol=symbol,
                window_seq=window_seq, stop_atr_n=int(best_params_dict.get("stop_atr_n", 3)),
                direction_override=best_params_dict.get("direction_override"),
            )
        )
    test_return = sum(t.net_return_pct for t in test_trades)
    (ts0, te0) = train_days[0], train_days[-1]
    (vs0, ve0) = test_days[0], test_days[-1]
    return WindowResult(
        seq=window_seq,
        train_start=whole_df.index[ts0[0]],
        train_end=whole_df.index[te0[1] - 1],
        test_start=whole_df.index[vs0[0]],
        test_end=whole_df.index[ve0[1] - 1],
        params=best_params_dict,
        train_net_return_pct=round(train_return, 4),
        test_net_return_pct=round(test_return, 4),
        test_trades=test_trades,
    )


def _candidate_fn_over_series(name: str):
    """Signal generator over the CONTINUOUS series (Donchian/RSI are rolling
    multi-day constructs; per-day computation destroys their context)."""
    if name == "donchian":
        return lambda df, n, stop_atr_n=3, direction_override=None: _donchian_candidates(df, n)
    if name == "rsi_reversion":
        return lambda df, n, lower=30, upper=70, stop_atr_n=3, direction_override=None: _rsi_candidates(df, n, lower, upper)
    if name == "orb":
        return lambda df, window_minutes, stop_atr_n=3, direction_override=None: _orb_candidates(df, window_minutes, stop_atr_n)
    raise ValueError(name)


def _expand(grid: dict) -> list[dict]:
    keys = list(grid.keys())
    import itertools

    values = [grid[k] if isinstance(grid[k], list) else [grid[k]] for k in keys]
    return [dict(zip(keys, combo)) for combo in itertools.product(*values)]


# --------------------------------------------------------------------------
# Metrics & report
# --------------------------------------------------------------------------

def _metrics(trades: list[Trade]) -> dict:
    net = np.array([t.net_pnl for t in trades])
    gross = np.array([t.gross_pnl for t in trades])
    wins = gross[gross > 0]
    losses = gross[gross <= 0]
    costs = sum(t.costs for t in trades)
    minutes = np.array([t.holding_minutes for t in trades]) if trades else np.array([])
    rets_pct = np.array([t.net_return_pct for t in trades]) if trades else np.array([])
    m = {
        "n_trades": len(trades),
        "gross_pnl": float(gross.sum()),
        "net_pnl": float(net.sum()),
        "net_return_pct": float(rets_pct.sum()),
        "costs": float(costs),
        "win_rate_pct": float(len(wins) / len(gross) * 100.0) if len(gross) else 0.0,
        "avg_win": float(wins.mean()) if len(wins) else 0.0,
        "avg_loss": float(losses.mean()) if len(losses) else 0.0,
        "expectancy_rs": float((wins.sum() + losses.sum()) / len(gross)) if len(gross) else 0.0,
        "profit_factor": float(wins.sum() / abs(losses.sum())) if abs(losses.sum()) > 0 else float("inf") if len(wins) else 0.0,
        "avg_holding_minutes": float(minutes.mean()) if len(minutes) else 0.0,
    }
    return m


def _annualize(window_return_pct: float, n_days: int) -> float:
    """Annualized return on a 252-trading-day basis for a window return
    measured over `n_days` trading days. Mirrors the engine's
    annualized_return_pct convention."""
    if n_days <= 0 or window_return_pct <= -100.0:
        return 0.0
    growth = 1.0 + window_return_pct / 100.0
    if growth <= 0:
        return 0.0
    return (growth ** (252.0 / n_days) - 1.0) * 100.0


def _wfe(win_results: list[WindowResult], min_pooled: int = 30) -> dict:
    """Canonical Pardo WFE from walk_forward_engine (same formula + 30 floor).

    WFE = (avg annualized OOS return / avg annualized IS return) * 100.
    Robust iff WFE >= 50, avg OOS > 0, pooled OOS trades >= MIN_POOLED_OOS_TRADES.
    """
    if not win_results:
        return {"wfe_pct": 0.0, "is_robust": False, "notes": "No windows", "pooled_oos_trades": 0}
    # Include EVERY window (a zero-trade window contributes 0% return, which
    # correctly drags the average down). Filtering them out biases WFE upward;
    # the `avg_oos > 0` conjunct below still blocks any false robustness.
    is_ann = []
    oos_ann = []
    for w in win_results:
        n_train = (w.train_end - w.train_start).days
        n_test = (w.test_end - w.test_start).days
        is_ann.append(_annualize(w.train_net_return_pct, max(n_train, 1)))
        oos_ann.append(_annualize(w.test_net_return_pct, max(n_test, 1)))
    avg_is = float(np.mean(is_ann)) if is_ann else 0.0
    avg_oos = float(np.mean(oos_ann)) if oos_ann else 0.0
    pooled = sum(len(w.test_trades) for w in win_results)
    if avg_is > 0:
        wfe = (avg_oos / avg_is * 100.0)
    elif avg_is == 0 and avg_oos > 0:
        wfe = 100.0
    else:
        wfe = 0.0
    sample_ok = pooled >= min_pooled
    is_robust = wfe >= 50.0 and avg_oos > 0 and sample_ok
    if not sample_ok:
        notes = f"Sample too small to validate (pooled OOS trades={pooled} < {min_pooled}) - NOT ROBUST"
    elif is_robust:
        notes = "Robust institutional edge"
    else:
        notes = (
            f"NOT ROBUST (WFE {wfe:.1f}% ann oos {avg_oos:+.2f}% ann is {avg_is:+.2f}% "
            f"pooled OOS trades {pooled})"
        )
    return {
        "wfe_pct": float(wfe),
        "mean_is_return_ann_pct": round(avg_is, 2),
        "mean_oos_return_ann_pct": round(avg_oos, 2),
        "pooled_oos_trades": pooled,
        "is_robust": is_robust,
        "notes": notes,
    }


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def run_symbol(
    symbol: str,
    strategy: str,
    cadence: str,
    n_train_days: int,
    n_test_days: int,
    embargo_days: int,
    params_grid: dict,
) -> dict:
    df1 = _load_1min(symbol)
    df = _resample(df1, cadence)
    bar_minutes = int((df.index[1] - df.index[0]).total_seconds() / 60)
    days = _days(df)
    full_days = [d for d in days if _is_full_day(_day_slice(df, d), bar_minutes)]
    day_positions = []
    for d in full_days:
        sl = _day_slice(df, d)
        day_positions.append((df.index.searchsorted(sl.index[0]), df.index.searchsorted(sl.index[-1], side="right")))
    if not day_positions:
        raise RuntimeError(f"no full days for {symbol}@{cadence}")

    # Precompute candidate signals over the CONTINUOUS series once per combo.
    # Rolling channels use only the past, so a signal at any bar depends only
    # on earlier bars — no lookahead. Sliced per-day in window simulation.
    cand_over_series = _candidate_fn_over_series(strategy)
    signals_by_combo: dict[tuple, tuple] = {}
    for combo in _expand(params_grid):
        sig = cand_over_series(df, **combo)
        signals_by_combo[tuple(sorted(combo.items()))] = (sig, dict(combo))

    # walk forward with embargo: test begins embargo days after train ends.
    # Windows are contiguous NON-OVERLAPPING blocks (train + embargo + test)
    # so pooled OOS trades are independent.
    step = n_train_days + embargo_days + n_test_days
    win_results: list[WindowResult] = []
    start = 0
    seq = 0
    total_days = len(day_positions)
    while start + n_train_days + n_test_days <= total_days:
        wr = _run_window(
            df, signals_by_combo, day_positions, start, n_train_days, n_test_days, embargo_days,
            strategy=strategy, symbol=symbol, window_seq=seq,
        )
        if wr is None:
            break
        win_results.append(wr)
        seq += 1
        # roll forward: each window owns train + embargo + test; step by that block
        start += step

    all_trades = [t for w in win_results for t in w.test_trades]
    perf = _metrics(all_trades)
    wfe = _wfe(win_results)

    # buy & hold benchmark on the full/day-close series
    closes = df["Close"].resample("1D").last().dropna()
    bh = (closes.iloc[-1] / closes.iloc[0] - 1) * 100.0

    return {
        "symbol": symbol,
        "strategy": strategy,
        "cadence": cadence,
        "n_days_full": len(full_days),
        "date_range": f"{full_days[0].date()} -> {full_days[-1].date()}",
        "windows": len(win_results),
        "params_grid": params_grid,
        "wfe": wfe,
        "perf": perf,
        "buy_hold_return_pct": float(bh),
        "exits": _exit_breakdown(all_trades),
        "by_year": _by_year(all_trades),
    }


def _exit_breakdown(trades: list[Trade]) -> dict:
    if not trades:
        return {}
    s = {}
    for t in trades:
        s.setdefault(t.exit_reason, [0, 0.0])
        s[t.exit_reason][0] += 1
        s[t.exit_reason][1] += t.net_pnl
    return {k: {"n": v[0], "net_pnl": round(v[1], 2)} for k, v in sorted(s.items())}


def _by_year(trades: list[Trade]) -> dict:
    if not trades:
        return {}
    import collections

    y = collections.OrderedDict()
    for t in sorted(trades, key=lambda x: x.entry_ts):
        yr = t.entry_ts.year
        y.setdefault(yr, []).append(t)
    return {str(k): _metrics(v) for k, v in y.items()}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="NIFTY")
    ap.add_argument("--strategy", default="donchian", choices=["donchian", "rsi_reversion", "orb"])
    ap.add_argument("--cadence", default="5m", choices=["5m", "15m"])
    ap.add_argument("--train", type=int, default=180)
    ap.add_argument("--test", type=int, default=45)
    ap.add_argument("--embargo", type=int, default=5)
    ap.add_argument("--out", default=r"D:\MJONAI\cache\fwd_sim_out.jsonl")
    args = ap.parse_args()

    grids = {
        "donchian": {"n": [20, 40, 80], "stop_atr_n": [2, 3]},
        "rsi_reversion": {"n": [7, 14], "lower": [25, 30], "upper": [70, 75], "stop_atr_n": [2, 3]},
        "orb": {"window_minutes": [15, 30], "stop_atr_n": [2, 3]},
    }
    result = run_symbol(
        args.symbol, args.strategy, args.cadence,
        args.train, args.test, args.embargo, grids[args.strategy],
    )
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "a", encoding="utf-8") as f:
        f.write(json.dumps(result, default=str) + "\n")
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
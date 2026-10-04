"""Forward (out-of-sample-by-construction) simulation of directional ATM index
OPTIONS buying on NIFTY / BANKNIFTY, driven by price-only signals.

PURPOSE
    Second research pillar over the deep chain warehouse
    (storage/parquet/fno_chain/eod, 2016-06 -> 2026-09). The minute battery
    tests intraday futures-style scalping; THIS module tests the other side of
    the engine's option mandate: buying-directional, ATM, close-to-close,
    with canonical Indian option costs.

DESIGN (no lookahead)
    - Signal at day-t close on the index SPOT daily series (from
      storage/parquet/tradingtick_index/spot): close vs SMA20 -> bull/bear
      direction for the NEXT trading day.
    - Entry at the NEXT day's option CLOSE (we delay by a full day so the
      signal is genuinely actionable).
    - Instrument: the nearest-money strike of the nearest expiry with DTE in
      [2, 30] at entry (expires the following expiry).
    - Exit variants (each parameter-free, reported separately):
        * HOLD_EXPIRY : hold to the expiry close (theta is the story).
        * NEXT_DAY    : exit at next day's option close (momentum sculp).
        * HOLD_5D     : exit 5 trading days later at close.
      For 2024+ (NSE full-OHLC) a proportional stop variant is reported too.
    - Costs: canonical execution/tax.py calculate_all_in_friction with
      asset_class="OPTIONS" (STT 0.10% sell-only, exchange 0.03503%, stamp
      0.003% buy, SEBI, brokerage min(0.03%, Rs20), GST 18%) + 5 bps slippage
      on premium. 1 lot (actual lot size from the chain row).
    - Every missed trade is counted and logged as a gap (missing chain day,
      no usable expiry, NaN premium) — never skipped silently.

HONESTY
    - Premiums are EOD closes; intrabar simulation is impossible pre-2024
      (close-only era) and only approximated 2024+ (NSE OHLC). Intraday
      fills/stop-outs are NOT claimed.
    - The spot series' frontier has a known source defect (prev_close garbage
      on the rolling boundary) — this sim uses only 'close', which is clean.
    - Options buying is the engine's actual mandate: NIFTY+BANKNIFTY only.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from mjonai.execution.tax import calculate_all_in_friction
from mjonai.research.data.tradingtick_index import load_series as load_index
from mjonai.research.data.fno_eod import _month_path, _read_month_cached
from functools import lru_cache

CHAIN_DIR = os.environ.get("FNO_CHAIN_DIR", r"D:\MJONAI\storage\parquet\fno_chain")
TT_INDEX_DIR = os.environ.get("TT_INDEX_DIR", r"D:\MJONAI\storage\parquet\tradingtick_index")
INITIAL_CAPITAL = 100_000.0
SLIPPAGE_BPS = 5.0
SMA_N = 20
MIN_DTE = 2
MAX_DTE = 30


def _costs(buy: float, sell: float, lot_size: int) -> float:
    b = calculate_all_in_friction(
        buy_price=buy, sell_price=sell, quantity=lot_size,
        asset_class="OPTIONS", product_type="", exchange="NSE", num_legs=1,
    )
    slip = (buy + sell) * lot_size * SLIPPAGE_BPS / 10000
    return float(b["total_friction"]) + slip


def load_spot(underlying: str) -> pd.DataFrame:
    df = load_index(TT_INDEX_DIR, "spot", underlying,
                     pd.Timestamp("2014-01-01"), pd.Timestamp("2026-08-31"))
    df = df.set_index("trade_date")
    return df[["close"]].dropna()


_MONTH_CACHE: dict = {}
_NEED_COLS = ["trade_date", "underlying", "kind", "option_type", "strike",
              "expiry", "close", "lot_size"]


def _read_month_pruned(path: str) -> pd.DataFrame | None:
    """Read only the columns the options sim needs (parquet column pruning) —
    the NSE-overlay months carry every underlying and are otherwise large."""
    if not os.path.exists(path):
        return None
    try:
        return pd.read_parquet(path, columns=_NEED_COLS)
    except Exception as exc:
        print(f"[options_sim] unreadable {path}: {exc}", flush=True)
        return None


def _month_opt_index(ts: pd.Timestamp) -> dict:
    """OPT-only rows for one month, split by underlying, with a pre-normalized
    '_d' date column. Cached per month (a month file contains both NIFTY and
    BANKNIFTY, so one read serves both underlyings)."""
    ym = pd.Timestamp(ts).strftime("%Y-%m")
    if ym not in _MONTH_CACHE:
        month = _read_month_pruned(_month_path(CHAIN_DIR, pd.Timestamp(ts)))
        idx: dict = {}
        if month is not None and not month.empty:
            opt = month[month["kind"] == "OPT"].copy()
            if not opt.empty:
                opt["_d"] = pd.to_datetime(opt["trade_date"]).dt.normalize()
                for u, g in opt.groupby(opt["underlying"].astype(str).str.upper()):
                    idx[u] = g
        _MONTH_CACHE[ym] = idx
        if len(_MONTH_CACHE) > 8:  # sequential access; a few months is enough
            # FIFO by insertion order (dicts are ordered) — never evict the
            # month we just added (lexicographic eviction breaks when a later
            # config starts earlier in time than the cached months).
            del _MONTH_CACHE[next(iter(_MONTH_CACHE))]
    return _MONTH_CACHE.get(ym, {})


def _chain_for_day(ts: pd.Timestamp, underlying: str) -> pd.DataFrame | None:
    """OPT rows for one underlying on one trading day, from the monthly
    warehouse."""
    ts = pd.Timestamp(ts).normalize()
    sub = _month_opt_index(ts).get(underlying.upper())
    if sub is None or sub.empty:
        return None
    day = sub[sub["_d"] == ts]
    return day if not day.empty else None


def _atm_row(day: pd.DataFrame, spot: float, dte_window=(MIN_DTE, MAX_DTE), opt="CE"):
    """Nearest-money strike of the nearest expiry inside the DTE window for one
    option side. Returns a single row (Series) or None."""
    if "expiry" not in day.columns:
        return None
    cur = pd.Timestamp(day["trade_date"].iloc[0]).normalize()
    ex = pd.to_datetime(day["expiry"]).dt.normalize()
    dte = (ex - cur).dt.days
    valid = day[(ex > cur) & (dte >= dte_window[0]) & (dte <= dte_window[1])]
    if valid.empty:
        return None
    side = valid[valid["option_type"].astype(str).str.upper() == opt]
    if side.empty:
        return None
    # nearest expiry within the window
    ex_days = (pd.to_datetime(side["expiry"]).dt.normalize() - cur).dt.days
    nearest = side[ex_days == ex_days.min()]
    if nearest.empty:
        return None
    strikes = nearest["strike"].astype(float)
    best = (strikes - spot).abs().idxmin()
    return nearest.loc[best]


def _next_trading_day(dates: pd.DatetimeIndex, d: pd.Timestamp) -> pd.Timestamp | None:
    pos = dates.searchsorted(d)
    if pos + 1 >= len(dates):
        return None
    return dates[pos + 1]


def run_options_sim(underlying: str, exit_mode: str = "NEXT_DAY", max_entries: int = 0) -> dict:
    spot = load_spot(underlying)
    spot["sma"] = spot["close"].rolling(SMA_N).mean()
    spot["dir"] = np.where(spot["close"] > spot["sma"], 1, -1)
    dates = spot.index
    trades = []
    gaps = {"no_chain_day": 0, "no_expiry": 0, "no_premium": 0, "nan_entry": 0}
    entries = 0
    # One position at a time (₹1L capital, no overlapping lots). Position is
    # open from entry_day until exit_day; new signals are skipped while open.
    open_until: pd.Timestamp | None = None

    for i in range(len(spot) - 2):
        t = dates[i]
        sig_dir = spot["dir"].iloc[i]
        entry_day = dates[i + 1]
        if max_entries and entries >= max_entries:
            break
        if open_until is not None and entry_day <= open_until:
            gaps["in_position_skip"] = gaps.get("in_position_skip", 0) + 1
            continue
        chain_day = _chain_for_day(entry_day, underlying)
        if chain_day is None or chain_day.empty:
            gaps["no_chain_day"] += 1
            continue
        opt = "CE" if sig_dir == 1 else "PE"
        row = _atm_row(chain_day, float(spot["close"].iloc[i]), opt=opt)
        if row is None:
            gaps["no_expiry"] += 1
            continue
        buy_px = float(row["close"])
        if not np.isfinite(buy_px) or buy_px <= 0:
            gaps["no_premium"] += 1
            continue
        lot = row.get("lot_size", 0)
        lot = int(lot) if (pd.notna(lot) and lot) else (25 if underlying == "NIFTY" else 20)
        hk, sell_px, exit_day = _exit_price(spot, chain_day, entry_day, exit_mode, row, underlying)
        if sell_px is None:
            gaps[hk] = gaps.get(hk, 0) + 1
            continue
        if not np.isfinite(sell_px) or sell_px <= 0:
            gaps["no_premium"] += 1
            continue
        costs = _costs(buy_px, sell_px, lot)
        gross = (sell_px - buy_px) * lot
        net = gross - costs
        base = float(spot["close"].iloc[i])
        trades.append({
            "underlying": underlying,
            "entry_date": str(entry_day.date()),
            "exit_date": str(exit_day.date()) if exit_day is not None else "",
            "direction": opt,
            "buy_px": round(buy_px, 2),
            "sell_px": round(sell_px, 2),
            "lot": lot,
            "gross_pnl": round(gross, 2),
            "costs": round(costs, 2),
            "net_pnl": round(net, 2),
            "net_return_pct": round(net / INITIAL_CAPITAL * 100.0, 4),
            "idx_move_pct": round((float(spot["close"].iloc[i - 1]) / base - 1) * 100.0, 3) if i > 0 else 0.0,
            "exit_mode": exit_mode,
        })
        entries += 1
        open_until = pd.Timestamp(exit_day).normalize() if exit_day is not None \
            else pd.Timestamp(entry_day).normalize()

    # ---- deep metrics over the ACTUAL trade span (one position at a time, so
    # the cumulative P&L curve is a valid sequential equity curve) ----
    equity = INITIAL_CAPITAL
    peak = INITIAL_CAPITAL
    max_dd = 0.0
    curve = []
    for t in trades:
        equity += t["net_pnl"]
        peak = max(peak, equity)
        if peak > 0:
            max_dd = max(max_dd, (peak - equity) / peak * 100.0)
        curve.append(equity)
    per_year: dict = {}
    for t in trades:
        per_year[t["entry_date"][:4]] = round(
            per_year.get(t["entry_date"][:4], 0.0) + t["net_pnl"], 2)
    span_years = 0.0
    if trades:
        d0 = pd.Timestamp(trades[0]["entry_date"])
        d1 = max(pd.Timestamp(t["exit_date"] or t["entry_date"]) for t in trades)
        span_years = max((d1 - d0).days / 365.25, 1e-9)
    net_pnl = sum(t["net_pnl"] for t in trades)
    ann_pct = (net_pnl / INITIAL_CAPITAL * 100.0) / span_years if span_years else 0.0
    pos = sum(t["net_pnl"] for t in trades if t["net_pnl"] > 0)
    neg = sum(t["net_pnl"] for t in trades if t["net_pnl"] <= 0)

    perf = {
        "n_trades": len(trades),
        "net_pnl": round(net_pnl, 2),
        "gross_pnl": round(sum(t["gross_pnl"] for t in trades), 2),
        "costs": round(sum(t["costs"] for t in trades), 2),
        "net_return_pct": round(net_pnl / INITIAL_CAPITAL * 100.0, 4),
        "annualized_pct": round(ann_pct, 4),
        "trade_span_years": round(span_years, 2),
        "max_drawdown_pct": round(max_dd, 3),
        "final_equity": round(equity, 2),
        "ending_equity_multiple": round(equity / INITIAL_CAPITAL, 4),
        "win_rate_pct": round(len([t for t in trades if t["net_pnl"] > 0]) / len(trades) * 100, 2) if trades else 0.0,
        "avg_win": round(np.mean([t["net_pnl"] for t in trades if t["net_pnl"] > 0]), 2) if any(t["net_pnl"] > 0 for t in trades) else 0.0,
        "avg_loss": round(np.mean([t["net_pnl"] for t in trades if t["net_pnl"] <= 0]), 2) if any(t["net_pnl"] <= 0 for t in trades) else 0.0,
        "expectancy_per_trade": round(net_pnl / len(trades), 2) if trades else 0.0,
        "profit_factor_net": round(pos / abs(neg), 3) if neg < 0 else float("inf"),
    }
    bh = (float(spot["close"].iloc[-1]) / float(spot["close"].iloc[0]) - 1) * 100.0
    return {
        "underlying": underlying,
        "exit_mode": exit_mode,
        "date_range": f"{str(dates[0].date())} -> {str(dates[-1].date())}",
        "perf": perf,
        "per_year_net_pnl": per_year,
        "gaps": gaps,
        "buy_hold_index_pct": round(bh, 2),
        "first_entry": trades[0]["entry_date"] if trades else None,
        "last_entry": trades[-1]["entry_date"] if trades else None,
        "trades": trades,
    }


def _exit_price(spot: pd.DataFrame, chain_day: pd.DataFrame, entry_day: pd.Timestamp,
                exit_mode: str, row: pd.Series, underlying: str):
    """Return (gap_key, sell_px, exit_day)."""
    dates = spot.index
    if exit_mode == "NEXT_DAY":
        ed = _next_trading_day(dates, entry_day)
        if ed is None:
            return ("no_next_day", None, None)
        cday = _chain_for_day(ed, underlying)
        if cday is None or cday.empty:
            return ("no_chain_day", None, None)
        r2 = _match_row(cday, row)
        if r2 is None:
            return ("no_matching_strike", None, None)
        px = float(r2["close"])
        return ("", px, ed)
    if exit_mode == "EXPIRY":
        ex = pd.Timestamp(row["expiry"]).normalize() if "expiry" in row.index else None
        if ex is None:
            return ("no_expiry", None, None)
        cday = _chain_for_day(ex, underlying)
        if cday is None or cday.empty:
            return ("no_chain_day", None, None)
        r2 = _match_row(cday, row)
        if r2 is None:
            return ("no_matching_strike", None, None)
        return ("", float(r2["close"]), ex)
    if exit_mode == "HOLD_5D":
        ed = entry_day
        for _ in range(5):
            ed = _next_trading_day(dates, ed)
            if ed is None:
                return ("no_next_day", None, None)
        cday = _chain_for_day(ed, underlying)
        if cday is None or cday.empty:
            return ("no_chain_day", None, None)
        r2 = _match_row(cday, row)
        if r2 is None:
            return ("no_matching_strike", None, None)
        return ("", float(r2["close"]), ed)
    return ("unknown_mode", None, None)


def _match_row(cday: pd.DataFrame, row: pd.Series):
    m = cday[
        (cday["option_type"].astype(str).str.upper() == str(row["option_type"]).upper())
        & (cday["strike"].astype(float) == float(row["strike"]))
    ]
    if "expiry" in row.index and pd.notna(row["expiry"]):
        ex = pd.to_datetime(row["expiry"]).normalize()
        m = m[pd.to_datetime(m["expiry"]).dt.normalize() == ex]
    if m.empty:
        return None
    if len(m) > 1:
        m = m.iloc[[0]]
    return m.iloc[0]


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--underlying", default="NIFTY", choices=["NIFTY", "BANKNIFTY"])
    ap.add_argument("--exit", default="NEXT_DAY", choices=["NEXT_DAY", "EXPIRY", "HOLD_5D"])
    ap.add_argument("--out", default=r"D:\MJONAI\cache\fwd_sim_options.jsonl")
    args = ap.parse_args()
    res = run_options_sim(args.underlying, args.exit)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "a", encoding="utf-8") as f:
        f.write(json.dumps(res, default=str) + "\n")
    print(json.dumps(res, indent=2, default=str))
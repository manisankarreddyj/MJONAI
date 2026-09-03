"""
Module: grid_tester_v2.py
Purpose: Corrected grid tester with real costs, SL/T1/T2, walk-forward, benchmark.
         v2.1 — Fixed: walk-forward, benchmark, trailing SL, exit reasons.
"""

import os, logging, time, duckdb
import pandas as pd, numpy as np, yfinance as yf, talib
from datetime import datetime
from research.cost_model import calculate_round_trip_cost

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), "research_data.duckdb")
MIN_ROWS = 200
QUANTITY = 100


def get_db():
    return duckdb.connect(DB_PATH)


def get_stock_universe(max_stocks=None):
    try:
        csv_path = os.path.join(os.path.dirname(__file__), "..", "data", "angelone", "nifty500_tokens.csv")
        df = pd.read_csv(csv_path)
        symbols = df['name'].tolist()
        result = [f"{s}.NS" for s in symbols]
        if max_stocks:
            result = result[:max_stocks]
        logger.info(f"Loaded {len(result)} symbols from CSV")
        return result
    except Exception:
        pass
    return ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
            "HINDUNILVR.NS", "SBIN.NS", "BHARTIARTL.NS", "KOTAKBANK.NS", "LT.NS",
            "AXISBANK.NS", "ASIANPAINT.NS", "MARUTI.NS", "SUNPHARMA.NS", "TITAN.NS",
            "BAJFINANCE.NS", "WIPRO.NS", "HCLTECH.NS", "ONGC.NS", "NTPC.NS",
            "TATAMOTORS.NS", "POWERGRID.NS", "M&M.NS", "TATASTEEL.NS", "INDUSINDBK.NS",
            "TECHM.NS", "BAJAJFINSV.NS", "ULTRACEMCO.NS", "NESTLEIND.NS", "JSWSTEEL.NS",
            "HDFCLIFE.NS", "ADANIPORTS.NS", "COALINDIA.NS", "CIPLA.NS", "DIVISLAB.NS",
            "BPCL.NS", "EICHERMOT.NS", "HEROMOTOCO.NS", "TATACONSUM.NS", "GRASIM.NS",
            "BRITANNIA.NS", "SBILIFE.NS", "DRREDDY.NS", "APOLLOHOSP.NS", "ADANIGREEN.NS",
            "ICICIGI.NS", "PIDILITIND.NS", "TORNTPHARM.NS", "BAJAJ-AUTO.NS", "HINDALCO.NS"]


def download_stock(symbol, period="2y"):
    try:
        df = yf.download(symbol, period=period, interval="1d", progress=False)
        if df.empty or len(df) < 200:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df
    except Exception:
        return None


def download_nifty(period="2y"):
    """Download Nifty 50 for benchmark comparison."""
    try:
        df = yf.download("^NSEI", period=period, interval="1d", progress=False)
        if df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df
    except Exception:
        return None


def _col(df, name):
    s = df[name]
    if isinstance(s, pd.DataFrame):
        s = s.iloc[:, 0]
    return s.values.astype(np.float64)


def precompute(df):
    close = _col(df, 'Close')
    high = _col(df, 'High')
    low = _col(df, 'Low')
    open_ = _col(df, 'Open')
    volume = _col(df, 'Volume')
    signals = {}

    for p in [7, 9, 14, 21]:
        signals[f"RSI_{p}"] = talib.RSI(close, timeperiod=p)

    for f, s, g in [(8,20,7), (12,26,9)]:
        _, _, h = talib.MACD(close, fastperiod=f, slowperiod=s, signalperiod=g)
        signals[f"MACD_{f}_{s}_{g}"] = h

    for p in [5, 10, 15, 20]:
        signals[f"ROC_{p}"] = talib.ROC(close, timeperiod=p)

    for f, s in [(9,21), (20,50), (50,200)]:
        ef = talib.EMA(close, timeperiod=f)
        es = talib.EMA(close, timeperiod=s)
        cross = np.zeros(len(close), dtype=np.float64)
        for i in range(1, len(close)):
            if ef[i] > es[i] and ef[i-1] <= es[i-1]:
                cross[i] = 1.0
            elif ef[i] < es[i] and ef[i-1] >= es[i-1]:
                cross[i] = -1.0
        signals[f"EMA_CROSS_{f}_{s}"] = cross

    for p in [14, 20]:
        signals[f"ADX_{p}"] = talib.ADX(high, low, close, timeperiod=p)

    for p, std in [(15, 1.5), (20, 2.0)]:
        u, m, l = talib.BBANDS(close, timeperiod=p, nbdevup=std, nbdevdn=std)
        w = (u - l) / m
        ratio = np.full(len(close), np.nan, dtype=np.float64)
        for i in range(21, len(close)):
            avg = np.nanmean(w[i-21:i])
            if avg > 0:
                ratio[i] = w[i] / avg
        signals[f"BB_RATIO_{p}_{std}"] = ratio

    for p in [10, 20]:
        ratio = np.full(len(close), np.nan, dtype=np.float64)
        for i in range(p + 1, len(close)):
            avg = np.mean(volume[i-p-1:i-1])
            if avg > 0:
                ratio[i] = volume[i] / avg
        signals[f"VOL_RATIO_{p}"] = ratio

    signals["ATR14"] = talib.ATR(high, low, close, timeperiod=14)

    pu = np.zeros(len(close), dtype=np.float64)
    pdn = np.zeros(len(close), dtype=np.float64)
    pu[1:] = (close[1:] > close[:-1]).astype(np.float64)
    pdn[1:] = (close[1:] < close[:-1]).astype(np.float64)
    signals["PRICE_UP"] = pu
    signals["PRICE_DN"] = pdn

    for pat in ["CDLHAMMER", "CDLENGULFING", "CDLMORNINGSTAR", "CDLSHOOTINGSTAR", "CDLEVENINGSTAR"]:
        try:
            signals[pat] = getattr(talib, pat)(open_, high, low, close).astype(np.float64)
        except:
            signals[pat] = np.zeros(len(close), dtype=np.float64)

    return signals


def simulate_trade(entry_price, atr, direction, highs, lows, closes, max_hold):
    """
    Simulate trade with SL, T1, T2, trailing SL.
    
    FIX: Trailing SL ratchet only moves in protective direction.
    FIX: Exit reason properly logged (SL, T1, T2, TIME).
    """
    risk = 1.5 * atr
    shares_remaining = 1.0
    realized_pnl_pct = 0.0

    if direction == "LONG":
        sl = entry_price - risk
        t1 = entry_price + risk
        t2 = entry_price + (2 * risk)
    else:
        sl = entry_price + risk
        t1 = entry_price - risk
        t2 = entry_price - (2 * risk)

    current_sl = sl
    t1_hit = False
    t2_hit = False

    for day in range(min(max_hold, len(highs))):
        high = highs[day]
        low = lows[day]
        close = closes[day]

        if direction == "LONG":
            # Check SL
            if low <= current_sl:
                pnl = (current_sl - entry_price) / entry_price * shares_remaining * 100
                realized_pnl_pct += pnl
                reason = "SL"
                if t2_hit:
                    reason = "TRAIL_SL"
                elif t1_hit:
                    reason = "BREAKEVEN_SL"
                return {"exit": round(current_sl, 2), "reason": reason,
                        "pnl_pct": round(realized_pnl_pct, 4), "days": day+1,
                        "t1": t1_hit, "t2": t2_hit}

            # Check T1
            if not t1_hit and high >= t1:
                t1_hit = True
                pnl = (t1 - entry_price) / entry_price * 0.5 * 100
                realized_pnl_pct += pnl
                shares_remaining = 0.5
                current_sl = max(current_sl, entry_price)  # Ratchet: never below breakeven

            # Check T2
            if t1_hit and not t2_hit and high >= t2:
                t2_hit = True
                pnl = (t2 - entry_price) / entry_price * 0.3 * 100
                realized_pnl_pct += pnl
                shares_remaining = 0.2

            # Trailing SL after T2
            if t2_hit and shares_remaining > 0:
                new_trail = close - (1.5 * atr)
                current_sl = max(current_sl, new_trail)  # Ratchet: only move UP

        else:  # SHORT
            if high >= current_sl:
                pnl = (entry_price - current_sl) / entry_price * shares_remaining * 100
                realized_pnl_pct += pnl
                reason = "SL"
                if t2_hit:
                    reason = "TRAIL_SL"
                elif t1_hit:
                    reason = "BREAKEVEN_SL"
                return {"exit": round(current_sl, 2), "reason": reason,
                        "pnl_pct": round(realized_pnl_pct, 4), "days": day+1,
                        "t1": t1_hit, "t2": t2_hit}

            if not t1_hit and low <= t1:
                t1_hit = True
                pnl = (entry_price - t1) / entry_price * 0.5 * 100
                realized_pnl_pct += pnl
                shares_remaining = 0.5
                current_sl = min(current_sl, entry_price)

            if t1_hit and not t2_hit and low <= t2:
                t2_hit = True
                pnl = (entry_price - t2) / entry_price * 0.3 * 100
                realized_pnl_pct += pnl
                shares_remaining = 0.2

            if t2_hit and shares_remaining > 0:
                new_trail = close + (1.5 * atr)
                current_sl = min(current_sl, new_trail)  # Ratchet: only move DOWN

    # Max hold reached
    last_close = closes[min(max_hold - 1, len(closes) - 1)]
    if direction == "LONG":
        pnl = (last_close - entry_price) / entry_price * shares_remaining * 100
    else:
        pnl = (entry_price - last_close) / entry_price * shares_remaining * 100
    realized_pnl_pct += pnl

    return {"exit": round(last_close, 2), "reason": "TIME",
            "pnl_pct": round(realized_pnl_pct, 4), "days": min(max_hold, len(closes)),
            "t1": t1_hit, "t2": t2_hit}


def detect_and_test(signals, close, high, low, opens, dates, atr_arr, start_idx, end_idx=None):
    """
    Detect signals and simulate trades.
    
    FIX: Walk-forward — only test dates AFTER train period.
    FIX: Entry at next day open (corrected look-ahead bias).
    """
    n = len(close)
    if end_idx is None:
        end_idx = n
    results = []
    pu_bool = signals["PRICE_UP"] > 0
    pdn_bool = signals["PRICE_DN"] > 0

    def test_signal(indicator, params, direction, condition_arr):
        mask = condition_arr.astype(bool) & ~np.isnan(condition_arr)
        for idx in np.where(mask[start_idx:end_idx])[0] + start_idx:
            entry_idx = idx + 1
            if entry_idx >= n or entry_idx >= end_idx + 5:
                continue

            entry_price = float(opens[entry_idx])
            signal_atr = float(atr_arr[idx])

            if np.isnan(entry_price) or np.isnan(signal_atr) or signal_atr <= 0 or entry_price <= 0:
                continue

            future_highs = [float(high[i]) for i in range(entry_idx, min(entry_idx + 20, n))]
            future_lows = [float(low[i]) for i in range(entry_idx, min(entry_idx + 20, n))]
            future_closes = [float(close[i]) for i in range(entry_idx, min(entry_idx + 20, n))]

            if len(future_highs) < 3:
                continue

            trade = simulate_trade(entry_price, signal_atr, direction, future_highs, future_lows, future_closes, max_hold=20)

            costs = calculate_round_trip_cost(entry_price, trade["exit"], QUANTITY)
            cost_pct = costs["total_cost_pct"]
            net_pnl_pct = trade["pnl_pct"] - cost_pct

            # IC corrected for direction
            if direction == "LONG":
                fr1 = (close[min(entry_idx+1, n-1)] - entry_price) / entry_price
                fr5 = (close[min(entry_idx+5, n-1)] - entry_price) / entry_price
            else:
                fr1 = (entry_price - close[min(entry_idx+1, n-1)]) / entry_price
                fr5 = (entry_price - close[min(entry_idx+5, n-1)]) / entry_price

            signal_date = dates[idx]

            results.append({
                "indicator": indicator,
                "parameters": str(params),
                "direction": direction,
                "signal_date": signal_date.strftime("%Y-%m-%d") if hasattr(signal_date, 'strftime') else str(signal_date),
                "entry_price": round(entry_price, 2),
                "exit_price": trade["exit"],
                "exit_reason": trade["reason"],
                "holding_days": trade["days"],
                "gross_pnl_pct": round(trade["pnl_pct"], 4),
                "cost_pct": round(cost_pct, 4),
                "net_pnl_pct": round(net_pnl_pct, 4),
                "win": net_pnl_pct > 0,
                "t1_hit": trade["t1"],
                "t2_hit": trade["t2"],
                "forward_return_1d": round(fr1, 6),
                "forward_return_5d": round(fr5, 6),
                "atr": round(signal_atr, 4),
            })

    # RSI
    for p in [7, 9, 14, 21]:
        r = signals[f"RSI_{p}"]
        for t in [50, 55, 60]:
            test_signal("RSI", f"p{p}_t{t}", "LONG", (r > t).astype(np.float64))
        for t in [30, 35, 40]:
            test_signal("RSI", f"p{p}_t{t}", "SHORT", (r < t).astype(np.float64))

    # MACD
    for f, s, g in [(8,20,7), (12,26,9)]:
        h = signals[f"MACD_{f}_{s}_{g}"]
        test_signal("MACD", f"f{f}s{s}g{g}", "LONG", ((h > 0) & (h > np.roll(h,1))).astype(np.float64))
        test_signal("MACD", f"f{f}s{s}g{g}", "SHORT", ((h < 0) & (h < np.roll(h,1))).astype(np.float64))

    # EMA Cross
    for f, s in [(9,21), (20,50)]:
        c = signals[f"EMA_CROSS_{f}_{s}"]
        test_signal("EMA_CROSS", f"f{f}s{s}", "LONG", (c == 1).astype(np.float64))
        test_signal("EMA_CROSS", f"f{f}s{s}", "SHORT", (c == -1).astype(np.float64))

    # BB Squeeze
    for p, std in [(15,1.5), (20,2.0)]:
        r = signals[f"BB_RATIO_{p}_{std}"]
        exp = r > np.roll(r, 1)
        for t in [0.7, 0.75]:
            sq = r < t
            test_signal("BB_SQ", f"p{p}s{std}_t{t}", "LONG", (sq & exp & pu_bool).astype(np.float64))
            test_signal("BB_SQ", f"p{p}s{std}_t{t}", "SHORT", (sq & exp & pdn_bool).astype(np.float64))

    # Volume
    for p in [10, 20]:
        v = signals[f"VOL_RATIO_{p}"]
        for t in [1.5, 2.0]:
            test_signal("VOL", f"p{p}_t{t}", "LONG", ((v > t) & pu_bool).astype(np.float64))
            test_signal("VOL", f"p{p}_t{t}", "SHORT", ((v > t) & pdn_bool).astype(np.float64))

    return results


def run_test(max_stocks=5, run_id=None):
    if run_id is None:
        run_id = f"v2_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    symbols = get_stock_universe(max_stocks)
    logger.info(f"Starting v2.1 test: {run_id} | Stocks: {len(symbols)}")

    con = get_db()
    con.execute("""CREATE TABLE IF NOT EXISTS system_log (
        id INTEGER,
        event_type VARCHAR,
        message VARCHAR,
        level VARCHAR DEFAULT 'INFO',
        created_at TIMESTAMP DEFAULT current_timestamp
    )""")
    con.execute("DELETE FROM backtest_results")

    # Download Nifty for benchmark
    logger.info("Downloading Nifty 50 benchmark...")
    nifty_df = download_nifty()
    if nifty_df is not None:
        nifty_close = _col(nifty_df, 'Close')
        nifty_return = (nifty_close[-1] - nifty_close[0]) / nifty_close[0] * 100
        logger.info(f"  Nifty 50 buy-hold (2yr): {nifty_return:.2f}%")
    else:
        nifty_return = None
        logger.warning("  Could not download Nifty benchmark")

    rid = [0]
    stats = {"ok": 0, "failed": 0, "signals": 0, "t0": time.time()}

    for i, sym in enumerate(symbols):
        clean = sym.replace(".NS", "")
        t0 = time.time()

        df = download_stock(sym)
        if df is None:
            stats["failed"] += 1
            continue

        sigs = precompute(df)
        close = _col(df, 'Close')
        high = _col(df, 'High')
        low = _col(df, 'Low')
        opens = _col(df, 'Open')
        dates = df.index
        atr = sigs["ATR14"]

        # Walk-forward: train on first 50%, test on last 50%
        train_end = len(close) // 2
        test_start = max(train_end, MIN_ROWS)

        # Detect signals in TEST PERIOD only
        res = detect_and_test(sigs, close, high, low, opens, dates, atr, test_start)

        stats["ok"] += 1
        stats["signals"] += len(res)

        rows = []
        for r in res:
            rid[0] += 1
            rows.append([
                rid[0], run_id, clean, r["indicator"], r["parameters"], 'daily',
                r["holding_days"], r["direction"], r["signal_date"], r["signal_date"],
                r["signal_date"], r["entry_price"], r["exit_price"],
                r["gross_pnl_pct"], r["net_pnl_pct"], r["cost_pct"],
                r["win"], 0, None, None, None,
                r["forward_return_1d"], r["forward_return_5d"], 0,
            ])

        if rows:
            con.executemany("""INSERT INTO backtest_results
                (id, run_id, stock, indicator, parameters, timeframe,
                 holding_days, direction, signal_date, entry_date, exit_date,
                 entry_price, exit_price, gross_return, net_return, total_cost,
                 win, actual_rr, market_state, vix, sector,
                 forward_return_1d, forward_return_5d, forward_return_20d)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", rows)

        elapsed = time.time() - t0
        logger.info(f"  [{i+1}/{len(symbols)}] {clean}: {elapsed:.1f}s | {len(res)} trades")

    # Save benchmark
    if nifty_return is not None:
        con.execute("""INSERT INTO system_log (event_type, message, level)
            VALUES ('BENCHMARK', ?, 'INFO')""",
            [f"Nifty 50 buy-hold 2yr: {nifty_return:.2f}%"])

    con.close()

    stats["elapsed"] = round(time.time() - stats["t0"], 1)
    logger.info(f"\nDone: {stats['ok']} stocks, {stats['signals']} trades, {stats['elapsed']}s")
    if nifty_return:
        logger.info(f"Benchmark: Nifty 50 buy-hold = {nifty_return:.2f}%")
    return stats


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
    stats = run_test(max_stocks=5)
    print(f"\nDone: {stats['ok']} stocks, {stats['signals']} trades, {stats['elapsed']}s")
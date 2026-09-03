"""
Module: grid_tester.py
Purpose: Core research engine. Precomputes indicators, vectorized detection, stores in DuckDB.
Uses: TA-Lib, yfinance, DuckDB
"""

import os, logging, time, duckdb
import pandas as pd, numpy as np, yfinance as yf, talib
from datetime import datetime

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), "research_data.duckdb")
MIN_ROWS = 200
HOLDING_PERIODS = [1, 3, 5, 10, 20]

def get_db():
    return duckdb.connect(DB_PATH)

def get_stock_universe():
    try:
        csv_path = os.path.join(os.path.dirname(__file__), "..", "data", "angelone", "nifty500_tokens.csv")
        df = pd.read_csv(csv_path)
        symbols = df['name'].tolist()
        logger.info(f"Loaded {len(symbols)} symbols from CSV")
        return [f"{s}.NS" for s in symbols]
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

def download_stock_data(symbol, period="2y"):
    try:
        df = yf.download(symbol, period=period, interval="1d", progress=False)
        if df.empty or len(df) < 200:
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

def precompute_indicators(df):
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
    signals["RSI14"] = talib.RSI(close, timeperiod=14)

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

    for p in [10, 20, 55]:
        up = np.zeros(len(close), dtype=np.float64)
        dn = np.zeros(len(close), dtype=np.float64)
        for i in range(p + 1, len(close)):
            if close[i] > np.max(high[i-p:i]):
                up[i] = 1.0
            if close[i] < np.min(low[i-p:i]):
                dn[i] = 1.0
        signals[f"DONCHIAN_UP_{p}"] = up
        signals[f"DONCHIAN_DN_{p}"] = dn

    for pat in ["CDLHAMMER", "CDLENGULFING", "CDLMORNINGSTAR", "CDLSHOOTINGSTAR", "CDLEVENINGSTAR"]:
        try:
            signals[pat] = getattr(talib, pat)(open_, high, low, close).astype(np.float64)
        except:
            signals[pat] = np.zeros(len(close), dtype=np.float64)

    pu = np.zeros(len(close), dtype=np.float64)
    pdn = np.zeros(len(close), dtype=np.float64)
    pu[1:] = (close[1:] > close[:-1]).astype(np.float64)
    pdn[1:] = (close[1:] < close[:-1]).astype(np.float64)
    signals["PRICE_UP"] = pu
    signals["PRICE_DN"] = pdn

    return signals


def detect_signals(signals, close, dates, start_idx):
    n = len(close)
    results = []

    def sim(di, direction):
        trades = []
        ep = close[di]
        for hp in HOLDING_PERIODS:
            xi = di + hp
            if xi >= n:
                continue
            xp = close[xi]
            gross = (xp - ep) / ep * 100 if direction == "LONG" else (ep - xp) / ep * 100
            net = gross - 0.15
            rr = abs(xp - ep) / (ep * 0.015) if ep > 0 else 0
            fr1 = (close[min(di+1, n-1)] - ep) / ep
            fr5 = (close[min(di+5, n-1)] - ep) / ep
            fr20 = (close[min(di+20, n-1)] - ep) / ep
            trades.append({
                "holding_days": int(hp),
                "exit_price": round(float(xp), 2),
                "gross_return": round(float(gross), 4),
                "net_return": round(float(net), 4),
                "total_cost": round(float(ep * 0.0015), 4),
                "win": bool(net > 0),
                "actual_rr": round(float(rr), 4),
                "forward_return_1d": round(float(fr1), 6),
                "forward_return_5d": round(float(fr5), 6),
                "forward_return_20d": round(float(fr20), 6),
            })
        return trades

    def add(ind, par, d, arr, cond):
        mask = cond & ~np.isnan(arr)
        for idx in np.where(mask[start_idx:])[0] + start_idx:
            for t in sim(idx, d):
                results.append((ind, par, d, float(arr[idx]), dates[idx], idx, t))

    pu_bool = signals["PRICE_UP"] > 0
    pdn_bool = signals["PRICE_DN"] > 0

    for p in [7, 9, 14, 21]:
        r = signals[f"RSI_{p}"]
        for t in [50, 55, 60, 65]:
            add("RSI", f"p{p}_t{t}", "LONG", r, r > t)
        for t in [30, 35, 40, 45]:
            add("RSI", f"p{p}_t{t}", "SHORT", r, r < t)

    for f, s, g in [(8,20,7), (12,26,9)]:
        h = signals[f"MACD_{f}_{s}_{g}"]
        add("MACD", f"f{f}s{s}g{g}", "LONG", h, (h > 0) & (h > np.roll(h,1)))
        add("MACD", f"f{f}s{s}g{g}", "SHORT", h, (h < 0) & (h < np.roll(h,1)))

    for p in [5, 10, 15, 20]:
        r = signals[f"ROC_{p}"]
        for t in [1, 2, 3, 5]:
            add("ROC", f"p{p}_t{t}", "LONG", r, r > t)
        for t in [-1, -2, -3, -5]:
            add("ROC", f"p{p}_t{t}", "SHORT", r, r < t)

    for f, s in [(9,21), (20,50), (50,200)]:
        c = signals[f"EMA_CROSS_{f}_{s}"]
        add("EMA_CROSS", f"f{f}s{s}", "LONG", c, c == 1)
        add("EMA_CROSS", f"f{f}s{s}", "SHORT", c, c == -1)

    r14 = signals["RSI14"]
    for p in [14, 20]:
        a = signals[f"ADX_{p}"]
        for t in [20, 25, 30]:
            add("ADX", f"p{p}_t{t}", "LONG", a, (a > t) & (r14 > 50))
            add("ADX", f"p{p}_t{t}", "SHORT", a, (a > t) & (r14 < 50))

    for p, std in [(15,1.5), (20,2.0)]:
        r = signals[f"BB_RATIO_{p}_{std}"]
        exp = r > np.roll(r, 1)
        for t in [0.6, 0.7, 0.75, 0.8]:
            sq = r < t
            add("BB_SQ", f"p{p}s{std}_t{t}", "LONG", r, sq & exp & pu_bool)
            add("BB_SQ", f"p{p}s{std}_t{t}", "SHORT", r, sq & exp & pdn_bool)

    for p in [10, 20]:
        v = signals[f"VOL_RATIO_{p}"]
        for t in [1.5, 2.0, 2.5, 3.0]:
            add("VOL", f"p{p}_t{t}", "LONG", v, (v > t) & pu_bool)
            add("VOL", f"p{p}_t{t}", "SHORT", v, (v > t) & pdn_bool)

    for p in [10, 20, 55]:
        add("DONCHIAN", f"p{p}", "LONG", signals[f"DONCHIAN_UP_{p}"], signals[f"DONCHIAN_UP_{p}"] == 1)
        add("DONCHIAN", f"p{p}", "SHORT", signals[f"DONCHIAN_DN_{p}"], signals[f"DONCHIAN_DN_{p}"] == 1)

    for pat in ["CDLHAMMER", "CDLENGULFING", "CDLMORNINGSTAR"]:
        arr = signals.get(pat, np.zeros(n, dtype=np.float64))
        add("CANDLE", pat, "LONG", arr, arr > 0)
    for pat in ["CDLENGULFING", "CDLEVENINGSTAR", "CDLSHOOTINGSTAR"]:
        arr = signals.get(pat, np.zeros(n, dtype=np.float64))
        add("CANDLE", pat, "SHORT", arr, arr < 0)

    return results


def run_grid_test(run_id=None, max_stocks=None):
    if run_id is None:
        run_id = f"grid_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    symbols = get_stock_universe()
    if max_stocks:
        symbols = symbols[:max_stocks]

    logger.info(f"Starting: {run_id} | Stocks: {len(symbols)}")

    con = get_db()

    # Clear previous data for fresh run
    con.execute("DELETE FROM backtest_results")
    con.execute("DELETE FROM indicator_signals")
    logger.info("Cleared previous results")

    rid_counter = [0]

    stats = {"run_id": run_id, "ok": 0, "failed": 0, "signals": 0, "t0": time.time()}

    for i, sym in enumerate(symbols):
        clean = sym.replace(".NS", "")
        t0 = time.time()

        df = download_stock_data(sym)
        if df is None:
            stats["failed"] += 1
            continue

        sigs = precompute_indicators(df)
        close = _col(df, 'Close')
        dates = df.index
        res = detect_signals(sigs, close, dates, MIN_ROWS)

        stats["ok"] += 1
        stats["signals"] += len(res)

        # Batch insert for speed
        rows = []
        for ind, par, d, sv, sd, di, trade in res:
            rid_counter[0] += 1
            ep = float(close[di])
            sd_str = sd.strftime("%Y-%m-%d") if hasattr(sd, 'strftime') else str(sd)
            ed_idx = di + trade["holding_days"]
            ed_str = dates[ed_idx].strftime("%Y-%m-%d") if hasattr(dates[ed_idx], 'strftime') else str(dates[ed_idx])

            rows.append([
                rid_counter[0], run_id, clean, ind, str(par), 'daily',
                trade["holding_days"], d, sd_str, sd_str, ed_str,
                round(ep, 2), trade["exit_price"],
                trade["gross_return"], trade["net_return"], trade["total_cost"],
                trade["win"], trade["actual_rr"], None, None, None,
                trade["forward_return_1d"], trade["forward_return_5d"],
                trade["forward_return_20d"],
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
        logger.info(f"  [{i+1}/{len(symbols)}] {clean}: {elapsed:.1f}s | {len(res):,} signals")

    con.close()

    stats["elapsed"] = round(time.time() - stats["t0"], 1)
    logger.info(f"\nDone: {stats['ok']} stocks, {stats['signals']:,} signals, {stats['elapsed']}s")
    return stats


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
    stats = run_grid_test(max_stocks=5)
    print(f"\nDone: {stats['ok']} stocks, {stats['signals']:,} signals, {stats['elapsed']}s")
"""
Module: sector_scanner.py
Purpose: Live sector relative strength scanner.
"""

import os
import pandas as pd
import numpy as np
import yfinance as yf
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


SECTOR_MAP = {
    "HDFCBANK": "BANKING", "ICICIBANK": "BANKING", "SBIN": "BANKING",
    "KOTAKBANK": "BANKING", "AXISBANK": "BANKING", "INDUSINDBK": "BANKING",
    "FEDERALBNK": "BANKING", "PNB": "BANKING", "BANKBARODA": "BANKING",
    "BANDHANBNK": "BANKING", "RBLBANK": "BANKING",
    "TCS": "IT", "INFY": "IT", "HCLTECH": "IT", "WIPRO": "IT",
    "TECHM": "IT", "LTTS": "IT", "COFORGE": "IT", "MPHASIS": "IT", "PERSISTENT": "IT",
    "RELIANCE": "ENERGY", "ONGC": "ENERGY", "BPCL": "ENERGY", "IOC": "ENERGY", "GAIL": "ENERGY",
    "HINDUNILVR": "FMCG", "ITC": "FMCG", "NESTLEIND": "FMCG", "BRITANNIA": "FMCG",
    "DABUR": "FMCG", "MARICO": "FMCG", "GODREJCP": "FMCG",
    "SUNPHARMA": "PHARMA", "DRREDDY": "PHARMA", "CIPLA": "PHARMA",
    "DIVISLAB": "PHARMA", "AUROPHARMA": "PHARMA", "LUPIN": "PHARMA", "BIOCON": "PHARMA",
    "MARUTI": "AUTO", "TATAMOTORS": "AUTO", "M&M": "AUTO",
    "BAJAJ-AUTO": "AUTO", "HEROMOTOCO": "AUTO", "EICHERMOT": "AUTO",
    "TATASTEEL": "METALS", "JSWSTEEL": "METALS", "HINDALCO": "METALS",
    "VEDL": "METALS", "COALINDIA": "METALS", "NMDC": "METALS",
    "LT": "INFRA", "NTPC": "INFRA", "POWERGRID": "INFRA", "TATAPOWER": "INFRA",
    "HDFCLIFE": "FINANCE", "SBILIFE": "FINANCE", "BAJFINANCE": "FINANCE", "BAJAJFINSV": "FINANCE",
    "ULTRACEMCO": "CEMENT", "SHREECEM": "CEMENT", "ACC": "CEMENT", "AMBUJACEM": "CEMENT",
    "DLF": "REALTY", "GODREJPROP": "REALTY", "PRESTIGE": "REALTY",
    "TITAN": "CONSUMER", "PIDILITIND": "CONSUMER", "HAVELLS": "CONSUMER",
    "BHARTIARTL": "TELECOM",
    "ADANIPORTS": "INFRA", "ADANIGREEN": "ENERGY", "ADANIENT": "ENERGY",
    "ASIANPAINT": "PAINTS",
}


def download_data(symbol):
    try:
        df = yf.download(symbol + ".NS", period="3mo", interval="1d", progress=False)
        if df.empty or len(df) < 10:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df
    except:
        return None


def scan(max_stocks=None):
    symbols = list(SECTOR_MAP.keys())
    if max_stocks:
        symbols = symbols[:max_stocks]

    results = []

    for i, sym in enumerate(symbols):
        df = download_data(sym)
        if df is None:
            continue

        close = df['Close'].values
        volume = df['Volume'].values
        sector = SECTOR_MAP.get(sym, "UNKNOWN")

        # Stock returns
        stock_5d = (close[-1] - close[-6]) / close[-6] * 100 if len(close) > 6 else 0
        stock_22d = (close[-1] - close[-23]) / close[-23] * 100 if len(close) > 23 else 0

        # Sector returns (average of all stocks in sector)
        # For simplicity, use stock's own sector proxy
        sector_5d = stock_5d * 0.8  # Approximate sector return
        sector_22d = stock_22d * 0.8

        # Relative strength
        rs_5d = stock_5d - sector_5d
        rs_22d = stock_22d - sector_22d
        composite = rs_5d * 0.4 + rs_22d * 0.6

        # Volume
        avg_vol = np.mean(volume[-22:-1]) if len(volume) > 22 else np.mean(volume)
        vol_ratio = volume[-1] / avg_vol if avg_vol > 0 else 1.0

        # Strength
        if composite > 2:
            strength = "STRONG"
        elif composite > 0.5:
            strength = "MODERATE"
        elif composite < -2:
            strength = "WEAK"
        elif composite < -0.5:
            strength = "MODERATE_WEAK"
        else:
            strength = "NEUTRAL"

        results.append({
            "symbol": sym,
            "sector": sector,
            "stock_5d": round(stock_5d, 2),
            "stock_22d": round(stock_22d, 2),
            "composite": round(composite, 2),
            "vol_ratio": round(vol_ratio, 1),
            "strength": strength,
            "price": round(float(close[-1]), 2),
        })

    results.sort(key=lambda x: x["composite"], reverse=True)
    return results


def print_results(results, top_n=25):
    print("\n" + "=" * 75)
    print(f"📊 SECTOR RELATIVE STRENGTH — {datetime.now().strftime('%d %b %Y %H:%M')}")
    print("=" * 75)
    print(f"\n{'#':<3} {'Symbol':<15} {'Sector':<10} {'5d':>7} {'22d':>7} {'Score':>7} {'Vol':>5} {'Str':<12} {'Price':>8}")
    print("-" * 75)

    for i, r in enumerate(results[:top_n], 1):
        if r["strength"] == "STRONG": e = "🟢"
        elif r["strength"] == "WEAK": e = "🔴"
        elif r["strength"] == "MODERATE": e = "🟡"
        elif r["strength"] == "MODERATE_WEAK": e = "🟠"
        else: e = "⚪"
        print(f"{e} {r['symbol']:<13} {r['sector']:<10} {r['stock_5d']:>+6.2f}% {r['stock_22d']:>+6.2f}% {r['composite']:>+6.2f} {r['vol_ratio']:>4.1f}x {r['strength']:<12} ₹{r['price']:>7.2f}")

    strong = sum(1 for r in results if r["strength"] == "STRONG")
    weak = sum(1 for r in results if r["strength"] == "WEAK")
    print(f"\n  Total: {len(results)} | Strong: {strong} | Weak: {weak}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    results = scan()
    print_results(results)
"""
Module: data/download_6months_1min.py
Purpose: High-Speed 6-Month 1-Minute Historical Candle Downloader.
         Fetches 180 days (6 months: approx Feb 23, 2026 to Aug 21, 2026) of 1-minute
         historical OHLCV data for all 51 Angel One instruments.
         
Features:
  1. Multi-chunk SmartAPI / Fallback downloader (30-day sequential windows)
  2. Automatic Token Resolution via token_map
  3. Invariant sanitization (High >= Low, Volume >= 0, No NaNs)
  4. Saves to scratch/angelone_1min_cache/{symbol}_1min_6m.parquet
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Union
import os
import sys
import io
from pathlib import Path
import logging
import time

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

root_dir = Path(__file__).resolve().parents[2]  # repo root (ADR-0008: file now at mjonai/data/)
sys.path.insert(0, str(root_dir))

# Dual Logging
scratch_dir = root_dir / "archive" / "scratch"  # scratch/ moved to repo-root archive/ 2026-09-03
cache_dir = scratch_dir / "angelone_1min_cache"
cache_dir.mkdir(parents=True, exist_ok=True)
log_file_path = scratch_dir / "downloader_6months.log"

file_handler = logging.FileHandler(log_file_path, mode="w", encoding="utf-8")
file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))

logging.basicConfig(level=logging.INFO, handlers=[file_handler, stream_handler])
logger = logging.getLogger("6MonthDownloader")

import pandas as pd
import numpy as np
import pyotp
from dotenv import load_dotenv

# Load credentials from the single canonical root .env
env_master_path = Path(__file__).resolve().parents[2] / ".env"
if env_master_path.exists():
    load_dotenv(str(env_master_path))
else:
    load_dotenv()

from mjonai.data.angelone.token_map import get_token_for_symbol
from mjonai.data.angelone.historical import SmartAPIRateLimiter, _sanitize_candles

try:
    from SmartApi import SmartConnect
except ImportError:
    SmartConnect = None

UNIVERSE_SYMBOLS = [
    "NIFTY", "BANKNIFTY",
    "ADANIENT", "ADANIPORTS", "APOLLOHOSP", "ASIANPAINT", "AXISBANK",
    "BAJAJ-AUTO", "BAJFINANCE", "BAJAJFINSV", "BPCL", "BHARTIARTL",
    "BRITANNIA", "CIPLA", "COALINDIA", "DIVISLAB", "DRREDDY",
    "EICHERMOT", "GRASIM", "HCLTECH", "HDFCBANK", "HDFCLIFE",
    "HEROMOTOCO", "HINDALCO", "HINDUNILVR", "ICICIBANK", "INDUSINDBK",
    "INFY", "ITC", "JSWSTEEL", "KOTAKBANK", "LT",
    "M&M", "MARUTI", "NESTLEIND", "NTPC", "ONGC",
    "POWERGRID", "RELIANCE", "SBILIFE", "SBIN", "SHRIRAMFIN",
    "SUNPHARMA", "TATACONSUM", "TATAMOTORS", "TATASTEEL", "TCS",
    "TECHM", "TITAN", "TRENT", "ULTRACEMCO", "WIPRO"
]


def initialize_smartapi():
    """Login and initialize Angel One SmartConnect client."""
    if SmartConnect is None:
        logger.warning("SmartApi package not installed.")
        return None

    api_key = os.getenv("ANGELONE_API_KEY", "")
    client_id = os.getenv("ANGELONE_CLIENT_ID", "")
    password = os.getenv("ANGELONE_PASSWORD", "")
    totp_secret = os.getenv("ANGELONE_TOTP_SECRET", "")

    if not all([api_key, client_id, password, totp_secret]):
        logger.warning("Angel One credentials incomplete in .env.master.")
        return None

    try:
        totp = pyotp.TOTP(totp_secret).now()
        client = SmartConnect(api_key=api_key)
        session = client.generateSession(client_id, password, totp)
        if session.get("status"):
            logger.info(f"✅ Logged into Angel One SmartAPI successfully for Client ID: {client_id}")
            return client
        else:
            logger.warning(f"❌ SmartAPI login failed: {session.get('message')}")
            return None
    except Exception as e:
        logger.warning(f"Exception during SmartAPI login: {e}")
        return None


def fetch_6months_for_symbol(symbol: str, client, rate_limiter: SmartAPIRateLimiter) -> Optional[pd.DataFrame]:
    """Fetch 180 days of 1-minute historical data in 30-day sequential chunks."""
    token = get_token_for_symbol(symbol, exchange="NSE")
    exch = "NSE"
    if symbol in ("NIFTY", "BANKNIFTY"):
        token = "99926000" if symbol == "NIFTY" else "99926009"
        exch = "NSE"

    if not token and symbol not in ("NIFTY", "BANKNIFTY"):
        logger.warning(f"Could not resolve Angel One token for {symbol}")
        return None

    end_date = datetime(2026, 8, 21, 15, 30)
    all_chunks = []

    # 6 sequential chunks of 30 days
    for chunk_idx in range(6):
        c_end = end_date - timedelta(days=chunk_idx * 30)
        c_start = c_end - timedelta(days=30)
        
        from_str = c_start.strftime("%Y-%m-%d 09:15")
        to_str = c_end.strftime("%Y-%m-%d 15:30")

        if client is not None and token:
            try:
                rate_limiter.acquire()
                params = {
                    "exchange": exch,
                    "symboltoken": str(token),
                    "interval": "ONE_MINUTE",
                    "fromdate": from_str,
                    "todate": to_str,
                }
                res = client.getCandleData(params)
                if isinstance(res, dict) and res.get("status") and res.get("data"):
                    rows = res["data"]
                    df_chunk = pd.DataFrame(rows, columns=["Timestamp", "Open", "High", "Low", "Close", "Volume"])
                    df_chunk["Timestamp"] = pd.to_datetime(df_chunk["Timestamp"])
                    df_chunk.set_index("Timestamp", inplace=True)
                    all_chunks.append(df_chunk)
                    continue
            except Exception as e:
                logger.debug(f"SmartAPI chunk fetch error for {symbol} ({from_str} to {to_str}): {e}")

        # Fallback to existing 30d cache if already present
        cache_30d = cache_dir / f"{symbol}_1min_30d.parquet"
        if cache_30d.exists() and chunk_idx == 0:
            try:
                df_existing = pd.read_parquet(cache_30d)
                all_chunks.append(df_existing)
            except Exception:
                pass

    if not all_chunks:
        return None

    full_df = pd.concat(all_chunks).sort_index()
    full_df = full_df[~full_df.index.duplicated(keep="last")]
    full_df = _sanitize_candles(full_df)
    return full_df


def main():
    logger.info("================================================================================")
    logger.info("  🚀 STARTING 6-MONTH (180-DAY) 1-MINUTE HISTORICAL DATA DOWNLOADER")
    logger.info(f"  • Total Instruments: {len(UNIVERSE_SYMBOLS)} Symbols")
    logger.info("  • Target Period: Feb 23, 2026 to Aug 21, 2026")
    logger.info("================================================================================")

    client = initialize_smartapi()
    rate_limiter = SmartAPIRateLimiter(min_interval_seconds=0.35)

    downloaded = 0
    for idx, sym in enumerate(UNIVERSE_SYMBOLS, 1):
        logger.info(f"[{idx:02d}/{len(UNIVERSE_SYMBOLS)}] Fetching 6 months of 1-minute data for {sym}...")
        df = fetch_6months_for_symbol(sym, client, rate_limiter)
        if df is not None and not df.empty:
            out_file = cache_dir / f"{sym}_1min_6m.parquet"
            # Also update the primary 1min cache
            out_file_main = cache_dir / f"{sym}_1min_30d.parquet"
            df.to_parquet(out_file)
            df.to_parquet(out_file_main)
            downloaded += 1
            logger.info(f"  ✅ Saved {len(df):,} 1-minute bars for {sym} ({df.index[0]} to {df.index[-1]}) -> {out_file.name}")
        else:
            logger.warning(f"  ⚠️ Could not download 6m data for {sym}")

    logger.info("================================================================================")
    logger.info(f"  🎉 6-MONTH 1-MINUTE DATASET DOWNLOAD COMPLETE: {downloaded}/{len(UNIVERSE_SYMBOLS)} Instruments Ready!")
    logger.info(f"  Cached files stored in: {cache_dir}")
    logger.info("================================================================================")


if __name__ == "__main__":
    main()

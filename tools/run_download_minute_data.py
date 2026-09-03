"""
Script: run_download_minute_data.py
Purpose: Prefill the research parquet cache with INTRADAY candles
         (1m/5m/15m) from Angel One SmartAPI.

Downloads happen ONCE; every backtest/walk-forward then reads the
local coverage-aware cache. Requires Angel One credentials in the
environment (.env.master). Never prints credential values.

Examples:
  python run_download_minute_data.py --tier NIFTY_50 --count 5 --days 30
  python run_download_minute_data.py --symbols RELIANCE,TCS --days 60 --interval 15m
"""

from __future__ import annotations

# ADR-0008: repo-root bootstrap — allows `python <this file>` from the repo root.
import sys as _boot_sys
from pathlib import Path as _boot_Path
_BOOT_ROOT = _boot_Path(__file__).resolve().parents[1]
if str(_BOOT_ROOT) not in _boot_sys.path:
    _boot_sys.path.insert(0, str(_BOOT_ROOT))

import argparse
from datetime import datetime, timedelta
from time import perf_counter

from mjonai.core.enums import Provider

from mjonai.data.instruments.master import InstrumentMaster
from mjonai.data.angelone.scrip_master import (
    AngelInstrumentProvider,
)

from mjonai.research.data.market_data import MarketDataService
from mjonai.research.data.providers.angelone_intraday import (
    TIMEFRAME_TO_INTERVAL,
    AngelOneIntradayProvider,
)
from mjonai.research.data.requests import HistoricalDataRequest
from mjonai.research.data.timeframe import TimeFrame
from mjonai.research.universe_loader import (
    UniverseTier,
    load_universe_symbols,
)

from mjonai.storage.parquet_store import ParquetStore
from mjonai.storage.service import StorageService


def build_service() -> tuple:
    """Service wired with the Angel One intraday provider + parquet cache."""
    provider = AngelOneIntradayProvider()

    storage = StorageService()
    storage.register(ParquetStore(root="storage/parquet"))

    service = MarketDataService()
    service.register(provider)
    service.register_storage(storage)

    return service, provider


def resolve_instruments(symbols: list[str]):
    master = InstrumentMaster()
    try:
        master.load(AngelInstrumentProvider().download())
        from mjonai.research.universe import UniverseManager
        resolved = UniverseManager(master).symbols(symbols)
    except Exception as e:
        print(f"[warn] scrip-master unavailable ({e}) - using bare symbol instruments")
        from mjonai.data.instruments.models import Instrument

        resolved = [
            Instrument(
                instrument_id=f"1_{s}", symbol=s, name=s,
                provider="ANGEL", provider_type="SMARTAPI",
                provider_exchange="NSE", exchange="NSE",
                asset_type="EQUITY",
            )
            for s in symbols
        ]

    # Fallback for any symbol the master did not resolve
    have = {i.symbol for i in resolved}
    from mjonai.data.instruments.models import Instrument

    for s in symbols:
        if s not in have:
            resolved.append(
                Instrument(
                    instrument_id=f"1_{s}", symbol=s, name=s,
                    provider="ANGEL", provider_type="SMARTAPI",
                    provider_exchange="NSE", exchange="NSE",
                    asset_type="EQUITY",
                )
            )

    ordered = {i.symbol: i for i in resolved}
    return [ordered[s] for s in symbols if s in ordered]


def main():
    parser = argparse.ArgumentParser(description="Download intraday candles into the research parquet cache")
    parser.add_argument("--symbols", type=str, default="", help="Comma-separated symbols (overrides --tier/--count)")
    parser.add_argument("--tier", type=str, default="NIFTY_50", choices=["NIFTY_50", "NIFTY_500"])
    parser.add_argument("--count", type=int, default=5)
    parser.add_argument("--days", type=int, default=30, help="Calendar days of history (broker caps apply)")
    parser.add_argument("--interval", type=str, default="1m", choices=sorted(TIMEFRAME_TO_INTERVAL))
    args = parser.parse_args()

    symbols = (
        [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
        or load_universe_symbols(
            tier=getattr(UniverseTier, args.tier),
            max_count=args.count,
        )
    )

    timeframe = TimeFrame(args.interval)
    end = datetime.now()
    start = end - timedelta(days=args.days)

    started = perf_counter()

    print("=" * 90)
    print(f"MINUTE-DATA DOWNLOAD | interval={args.interval} days={args.days} symbols={len(symbols)}")
    print("=" * 90)

    service, _provider = build_service()

    instruments = resolve_instruments(symbols)

    ok = failed = 0

    for index, instrument in enumerate(instruments, start=1):
        request = HistoricalDataRequest(
            provider=Provider.ANGEL,
            instrument=instrument,
            timeframe=timeframe,
            start=start,
            end=end,
        )

        response = service.get_historical_data(request)

        if response.success and response.data is not None and response.data.candles:
            rows = len(response.data.candles)
            first = response.data.candles[0].timestamp.date()
            last = response.data.candles[-1].timestamp.date()
            print(f"[{index}/{len(symbols)}] {instrument.symbol:<12} OK   rows={rows:>7}  {first} -> {last}")
            ok += 1
        else:
            print(f"[{index}/{len(symbols)}] {instrument.symbol:<12} FAIL ({response.error})")
            failed += 1

    print("-" * 90)
    print(f"Done in {perf_counter() - started:.1f}s — ok={ok} failed={failed}")
    print("Data now lives in storage/parquet and serves backtests via the coverage-aware cache.")


if __name__ == "__main__":
    main()

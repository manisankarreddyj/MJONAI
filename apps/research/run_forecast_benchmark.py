"""
Script: run_forecast_benchmark.py
Purpose: F-wave entry point (ADR-0002). Rolling-origin benchmark of forecast
         models on one symbol/timeframe; classical baselines are ALWAYS the
         reference. TSFMs opt in via --models kronos_small etc. and fail
         honestly when weights are not in the local HF cache.

Example:
  python run_forecast_benchmark.py --symbol RELIANCE --tf 1d \
      --start 2023-01-01 --end 2025-12-31 --models seasonal_naive,rw_drift,exp_smoothing,kronos_small
"""

from __future__ import annotations

# ADR-0008: repo-root bootstrap — allows `python <this file>` from the repo root.
import sys as _boot_sys
from pathlib import Path as _boot_Path
_BOOT_ROOT = _boot_Path(__file__).resolve().parents[2]
if str(_BOOT_ROOT) not in _boot_sys.path:
    _boot_sys.path.insert(0, str(_BOOT_ROOT))

import argparse
from datetime import datetime

from mjonai.core.enums import Provider
from mjonai.data.angelone.scrip_master import AngelInstrumentProvider
from mjonai.research.config import ResearchConfig
from mjonai.research.data.market_data import MarketDataService
from mjonai.research.data.providers.angelone_intraday import AngelOneIntradayProvider
from mjonai.research.data.providers.yahoo import YahooProvider
from mjonai.research.data.requests import HistoricalDataRequest
from mjonai.research.data.timeframe import TimeFrame
from mjonai.research.forecasting.evaluate import compare_models, print_leaderboard
from mjonai.storage.parquet_store import ParquetStore
from mjonai.storage.service import StorageService


def build_market_service() -> MarketDataService:
    storage = StorageService()
    storage.register(ParquetStore())

    market = MarketDataService()
    market.register(YahooProvider())
    market.register(AngelOneIntradayProvider())  # lazy login on first fetch
    market.register_storage(storage)
    return market


def resolve_instrument(symbol: str):
    instruments = AngelInstrumentProvider().download()
    wanted = symbol.strip().upper()
    for instrument in instruments:
        if str(instrument.symbol).upper() == wanted:
            return instrument
    raise SystemExit(f"symbol {wanted} not found in instrument master")


def main():
    parser = argparse.ArgumentParser(description="MJONAI Forecast Benchmark (ADR-0002)")
    parser.add_argument("--symbol", type=str, default="RELIANCE")
    parser.add_argument("--tf", type=str, default="1d", choices=["1d", "15m", "5m", "1m"])
    parser.add_argument("--provider", type=str, default="YAHOO", choices=["YAHOO", "ANGEL"])
    parser.add_argument("--start", type=str, default="2022-01-01")
    parser.add_argument("--end", type=str, default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--horizon", type=int, default=5)
    parser.add_argument(
        "--models",
        type=str,
        default="seasonal_naive,rw_drift,exp_smoothing",
        help="comma separated: classical baselines always recommended; "
             "kronos_mini|kronos_small|kronos_base require local HF weights; "
             "timesfm (or timesfm_*) uses the TimesFM 3.0 forecaster (research opt-in)",
    )
    parser.add_argument("--min_history", type=int, default=250)
    parser.add_argument("--max_origins", type=int, default=300)
    args = parser.parse_args()

    from mjonai.research.forecasting import (
        DriftModel,
        ExpSmoothingModel,
        SeasonalNaiveModel,
    )

    model_map = {
        "seasonal_naive": lambda: SeasonalNaiveModel(),
        "rw_drift": lambda: DriftModel(),
        "exp_smoothing": lambda: ExpSmoothingModel(),
    }

    models = []
    requested = [m.strip() for m in args.models.split(",") if m.strip()]
    for name in requested:
        if name in model_map:
            models.append(model_map[name]())
        elif name.startswith("kronos_"):
            try:
                from mjonai.research.forecasting.kronos_adapter import KronosModel

                models.append(KronosModel(size=name.split("_", 1)[1]))
            except Exception as exc:
                print(f"[models] {name}: UNAVAILABLE -> {exc}")
        elif name == "timesfm" or name.startswith("timesfm_"):
            try:
                from mjonai.research.forecasting.timesfm_adapter import TimesFMModel

                # Prefer local weights (offline / restricted-network posture).
                local = _boot_Path("storage/models/timesfm-3.0-pytorch")
                if (local / "model.safetensors").is_file():
                    models.append(TimesFMModel(checkpoint=str(local.resolve()), local_files_only=True))
                else:
                    models.append(TimesFMModel())
            except Exception as exc:
                print(f"[models] {name}: UNAVAILABLE -> {exc}")
        else:
            print(f"[models] unknown '{name}' - skipped")

    if not models:
        raise SystemExit("no runnable models selected")

    instrument = resolve_instrument(args.symbol)
    config = ResearchConfig(
        provider=Provider(args.provider),
        timeframe=TimeFrame(args.tf),
        start=datetime.strptime(args.start, "%Y-%m-%d"),
        end=datetime.strptime(args.end, "%Y-%m-%d"),
        max_holding_bars=args.horizon,
    )

    market = build_market_service()
    response = market.get_historical_data(
        HistoricalDataRequest(
            provider=config.provider,
            instrument=instrument,
            timeframe=config.timeframe,
            start=config.start,
            end=config.end,
        )
    )
    if not response.success or response.data is None:
        raise SystemExit(f"data fetch failed: {response}")

    candles = response.data.candles
    print("=" * 72)
    print(f"MJONAI FORECAST BENCHMARK — {instrument.symbol} {args.tf} | "
          f"{len(candles)} bars | horizon={args.horizon} bars")
    print(f"origin range: last {min(args.max_origins, max(0, len(candles) - args.min_history))} eligible origins")
    print("=" * 72)

    import pandas as pd

    df = pd.DataFrame(
        [{
            "Open": c.open,
            "High": c.high,
            "Low": c.low,
            "Close": c.close,
            "Volume": c.volume,
        } for c in candles],
        index=[c.timestamp for c in candles],
    ).dropna()

    rows = compare_models(
        models,
        df,
        horizon=args.horizon,
        min_history=args.min_history,
        max_origins=args.max_origins,
    )
    print_leaderboard(rows)

    # ── ADR-0002 FINAL GATE: forecast-driven long/flat policy, friction from
    # the canonical tax engine. MAE winners can still lose here.
    from mjonai.research.forecasting.pipeline_gate import (
        REFERENCE_ROUND_TRIP_BPS,
        compare_trading_edge,
        print_edge_leaderboard,
    )

    print("=" * 92)
    print(f"TRADING-EDGE GATE — forecast long/flat policy, "
          f"friction {REFERENCE_ROUND_TRIP_BPS} bps round-trip (execution/tax.py reference)")
    edge_rows = compare_trading_edge(
        models,
        df,
        horizon=args.horizon,
        min_history=args.min_history,
        max_origins=args.max_origins,
    )
    print_edge_leaderboard(edge_rows)
    print("-" * 92)
    print("ADR-0002 rule: a TSFM must beat the classical baselines on BOTH tables "
          "before adoption; adoption itself additionally requires full-pipeline "
          "risk-adjusted improvement.")

    # ── VERSIONED EVIDENCE ARTIFACT ─────────────────────────────────────────
    # Persist both leaderboards so the "beat baselines on BOTH tables" bar can
    # be confronted to exact numbers and the producing commit later.
    from dataclasses import asdict

    from mjonai.research.evidence import record_evidence

    record_evidence(
        "forecast_benchmark",
        {
            "symbol": instrument.symbol,
            "timeframe": args.tf,
            "horizon": args.horizon,
            "min_history": args.min_history,
            "max_origins": args.max_origins,
            "bars": len(candles),
            "forecast_leaderboard": [asdict(r) for r in rows],
            "trading_edge_leaderboard": [asdict(r) for r in edge_rows],
            "reference_round_trip_bps": REFERENCE_ROUND_TRIP_BPS,
        },
    )


if __name__ == "__main__":
    main()

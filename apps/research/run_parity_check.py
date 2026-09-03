"""
Script: run_parity_check.py
Purpose: Side-by-side comparison of the ARCHIVED research copy of a
         strategy vs the LIVE registry version, on identical data.
         Documents how far the two implementations had drifted.
"""

from __future__ import annotations

# ADR-0008: repo-root bootstrap — allows `python <this file>` from the repo root.
import sys as _boot_sys
from pathlib import Path as _boot_Path
_BOOT_ROOT = _boot_Path(__file__).resolve().parents[2]
if str(_BOOT_ROOT) not in _boot_sys.path:
    _boot_sys.path.insert(0, str(_BOOT_ROOT))

from time import perf_counter

from mjonai.configs.research_config import (
    CONFIG,
    SYMBOLS,
)

from mjonai.research.bootstrap import ResearchBootstrap
from mjonai.research.context import ResearchContext

from mjonai.research.data_loader import ResearchDataLoader

from mjonai.research.registry_adapter import load_registry_strategy
from mjonai.research.runner import StrategyRunner

# The archived research copy moved out of the runtime tree on 2026-09-03
# (house rule: archives preserved at repo-root archive/). Bootstrap it.
# (ADR-0008: this file now lives at apps/research/ — repo root is parents[2].)
import sys
from pathlib import Path

_ARCHIVE_ROOT = Path(__file__).resolve().parents[2] / "archive"
if str(_ARCHIVE_ROOT) not in sys.path:
    sys.path.insert(0, str(_ARCHIVE_ROOT))

from research_archive.engine_strategies.s01_momentum_rsi import S01MomentumRSI


def stop_loss(df, signal_index, entry_price, direction):
    return entry_price * 0.97 if direction == "LONG" else entry_price * 1.03


def target(entry_price, stop_loss_price, direction):
    risk = abs(entry_price - stop_loss_price)
    return entry_price + risk * 2 if direction == "LONG" else entry_price - risk * 2


def collect(strategy, df, symbol):
    signals = StrategyRunner(strategy).run(symbol=symbol, data=df)
    dates = [df.index[s.index] for s in signals]
    return signals, set(dates)


def main():
    started = perf_counter()

    context = ResearchContext(config=CONFIG, symbols=SYMBOLS, strategy_ids=["S01_MomentumRSI"])

    _pipeline, instruments = ResearchBootstrap.build(context)

    loader = ResearchDataLoader(_pipeline._data_loader._market_data) if False else None

    print("=" * 100)
    print("PARITY CHECK: archived research COPY vs LIVE registry strategy (S01)")
    print("=" * 100)

    rows = []

    for instrument in instruments:

        response = _pipeline._data_loader.load(
            instruments=[instrument],
            provider=CONFIG.provider,
            timeframe=CONFIG.timeframe,
            start=CONFIG.start,
            end=CONFIG.end,
        )

        if not response:
            continue

        historical = response[0]

        df = historical_to_frame(historical)
        if df is None or len(df) < 250:
            continue

        symbol = instrument.symbol

        copy_signals, copy_dates = collect(S01MomentumRSI(), df, symbol)
        real = load_registry_strategy("S01_MomentumRSI", symbol=symbol)
        real_signals, real_dates = collect(real, df, symbol)

        common = len(copy_dates & real_dates)
        only_copy = len(copy_dates - real_dates)
        only_real = len(real_dates - copy_dates)

        rows.append((
            symbol, len(df),
            len(copy_signals), len(real_signals),
            common, only_copy, only_real,
        ))

        print(
            f"{symbol:<12} bars={len(df):5} | "
            f"COPY signals={len(copy_signals):4} | "
            f"REAL(v6.0) signals={len(real_signals):4} | "
            f"same-day agreement={common:4} | only-copy={only_copy:4} | only-real={only_real:4}"
        )

    total_copy = sum(r[2] for r in rows)
    total_real = sum(r[3] for r in rows)
    total_common = sum(r[4] for r in rows)

    print("-" * 100)
    print(
        f"TOTALS: copy={total_copy} signals, real={total_real}, "
        f"agreement={total_common} "
        f"({(total_common / max(1, max(total_copy, total_real)) * 100):.1f}% of the larger set)"
    )
    print()
    print("Reading: 'agreement' counts signals fired on the SAME DAY by BOTH versions.")
    print("Low agreement = the two 'S01' strategies are effectively different systems.")
    print(f"Completed in {perf_counter() - started:.1f}s")


def historical_to_frame(historical):
    import pandas as pd

    candles = historical.candles

    if not candles:
        return None

    df = pd.DataFrame(
        [
            {
                "Open": c.open,
                "High": c.high,
                "Low": c.low,
                "Close": c.close,
                "Volume": c.volume,
            }
            for c in candles
        ],
        index=[c.timestamp for c in candles],
    )

    return df.dropna()


if __name__ == "__main__":
    main()

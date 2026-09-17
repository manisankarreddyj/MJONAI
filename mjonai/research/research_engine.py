from __future__ import annotations

import pandas as pd

from mjonai.analytics.performance import PerformanceAnalyzer
from mjonai.research.backtest.engine import BacktestEngine
from mjonai.research.runner import StrategyRunner
from mjonai.research.data.models import HistoricalData
from mjonai.research.pit_universe import (
    mask_signals_by_membership,
)

from mjonai.research.models import ResearchResult


class ResearchEngine:

    def __init__(self):

        self._backtest = BacktestEngine()

        self._analytics = PerformanceAnalyzer()

    def run(
        self,
        *,
        strategy,
        historical_data_list: list[HistoricalData],
        stop_loss_func,
        target_func,
        max_holding_bars: int,
        membership_intervals_by_symbol: dict[str, list] | None = None,
    ) -> list[ResearchResult]:

        runner = StrategyRunner(strategy)

        results: list[ResearchResult] = []

        for historical_data in historical_data_list:

            df = pd.DataFrame(
                [
                    {
                        "Open": c.open,
                        "High": c.high,
                        "Low": c.low,
                        "Close": c.close,
                        "Volume": c.volume,
                    }
                    for c in historical_data.candles
                ],
                index=[
                    c.timestamp
                    for c in historical_data.candles
                ],
            )
            df = df.dropna()
            if len(df) < 50:
                continue

            signals = runner.run(
                symbol=historical_data.instrument.symbol,
                data=df,
            )

            # Decision 6 Phase 3 (PIT): drop any signal whose ENTRY bar falls
            # outside the symbol's curated membership legs. A non-member bar
            # never produces a trade — that is the survivorship-correction.
            if membership_intervals_by_symbol:
                legs = membership_intervals_by_symbol.get(
                    historical_data.instrument.symbol,
                )
                if legs is not None:
                    signals = mask_signals_by_membership(
                        df,
                        signals,
                        legs,
                    )

            trades = self._backtest.run(
                strategy=strategy,
                symbol=historical_data.instrument.symbol,
                df=df,
                signals=signals,
                stop_loss_func=stop_loss_func,
                target_func=target_func,
                max_holding_bars=max_holding_bars,
            )

            metrics = self._analytics.analyze(
                trades,
                # H7 fix: capital must match the ledger this trade list was
                # produced on, never a divergent default.
                initial_capital=self._backtest.initial_capital,
            )

            results.append(
                ResearchResult(
                    strategy_id=strategy.name,
                    instrument=historical_data.instrument,
                    signals=len(signals),
                    trades=len(trades),
                    report=metrics,
                    trades_list=list(trades),
                )
            )

        return results
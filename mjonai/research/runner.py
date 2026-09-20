"""
Strategy Runner

Runs a strategy against a single dataset.

This is the first executable component of the Research Engine.
"""

from __future__ import annotations

import pandas as pd

from mjonai.research.strategy import Strategy, StrategyResult


class StrategyRunner:
    """
    Executes a strategy on historical data.

    Initial version:
    - Processes one symbol
    - Processes one strategy
    - Evaluates every candle
    - Collects all generated signals

    Future versions:
    - Multi-asset
    - Multi-strategy
    - Parallel execution
    """

    def __init__(self, strategy: Strategy):
        self.strategy = strategy

    def run(
        self,
        symbol: str,
        data: pd.DataFrame,
    ) -> list[StrategyResult]:
        """
        Execute strategy over historical candles.

        Parameters
        ----------
        symbol : str
            Asset symbol.

        data : pd.DataFrame
            Historical OHLCV dataframe.

        Returns
        -------
        List[StrategyResult]
        """

        if data.empty:
            return []

        # Chain-aware strategies (e.g. S13 Gamma Flip) resolve REAL option-
        # chain inputs keyed on the symbol being simulated. The research
        # engine shares one strategy/adapter across symbols, so the per-run
        # symbol is pushed down here before the bar loop.
        if hasattr(self.strategy, "symbol"):
            try:
                self.strategy.symbol = symbol
            except (AttributeError, TypeError):
                pass

        signals: list[StrategyResult] = []

        # Minimum candles required before strategies become meaningful
        start_index = 200 if len(data) >= 200 else len(data)

        for i in range(start_index, len(data)):

            window = data.iloc[: i + 1]

            result = self.strategy.generate_signal(window)

            if result is not None:
                result.symbol = symbol
                signals.append(result)

        return signals
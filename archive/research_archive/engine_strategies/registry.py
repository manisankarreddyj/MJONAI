from __future__ import annotations

from engine.core.strategy import Strategy
from engine.strategies.dummy_strategy import DummyStrategy
from engine.strategies.s01_momentum_rsi import S01MomentumRSI
from engine.strategies.s02_mean_reversion import S02MeanReversion
from engine.strategies.s03_turtle_breakout import S03TurtleBreakout
from engine.strategies.s04_bollinger_squeeze import S04BollingerSqueeze
from engine.strategies.s05_price_action import S05PriceAction
from engine.strategies.s06_momentum_short import S06MomentumShort
from engine.strategies.s07_mean_reversion_short import S07MeanReversionShort
from engine.strategies.s08_intraday_all_day import S08IntradayAllDay


class StrategyRegistry:

    _strategies: dict[str, type[Strategy]] = {
        "S01_MomentumRSI": S01MomentumRSI,
        "S02_MeanReversion": S02MeanReversion,
        "S03_TurtleBreakout": S03TurtleBreakout,
        "S04_BollingerSqueeze": S04BollingerSqueeze,
        "S05_PriceAction": S05PriceAction,
        "S06_MomentumShort": S06MomentumShort,
        "S07_MeanReversionShort": S07MeanReversionShort,
        "S08_IntradayAllDay": S08IntradayAllDay,
        "Dummy": DummyStrategy,
    }

    @classmethod
    def load(
        cls,
        strategy_id: str,
    ) -> Strategy:

        strategy = cls._strategies.get(
            strategy_id,
        )

        if strategy is None:

            raise ValueError(
                f"Unknown strategy: {strategy_id}"
            )

        return strategy()

    @classmethod
    def load_all(
        cls,
    ) -> list[Strategy]:

        return [
            strategy()
            for strategy in cls._strategies.values()
        ]

    @classmethod
    def available(
        cls,
    ) -> list[str]:

        return sorted(
            cls._strategies.keys(),
        )
from __future__ import annotations

from mjonai.research.strategy import Strategy, StrategyResult
from mjonai.research.data.timeframe import TimeFrame


class DummyStrategy(Strategy):

    @property
    def name(self) -> str:
        return "Dummy"

    @property
    def version(self) -> str:
        return "1.0"

    @property
    def timeframe(self) -> str:
        return TimeFrame.DAY_1.value

    @property
    def description(self) -> str:
        return "Dummy strategy for engine testing."

    def generate_signal(
        self,
        data,
    ) -> StrategyResult | None:

        if len(data) % 25 != 0:
            return None

        return StrategyResult(
            symbol="",
            strategy_id=self.name,
            signal="LONG",
            score=100.0,
            index=len(data) - 1,
            metadata={
                "index": len(data) - 1,
            },
        )
from __future__ import annotations

from mjonai.research.data_loader import ResearchDataLoader
from mjonai.research.research_engine import ResearchEngine
from mjonai.research.config import ResearchConfig

class ResearchPipeline:

    def __init__(
        self,
        data_loader: ResearchDataLoader,
        research_engine: ResearchEngine,
    ):

        self._data_loader = data_loader
        self._research_engine = research_engine

    def run(
        self,
        *,
        instruments,
        config: ResearchConfig,
        strategy,
        stop_loss_func,
        target_func,
    ):

        historical_data = self._data_loader.load(
            instruments=instruments,
            provider=config.provider,
            timeframe=config.timeframe,
            start=config.start,
            end=config.end,
        )

        results = self._research_engine.run(
            strategy=strategy,
            historical_data_list=historical_data,
            stop_loss_func=stop_loss_func,
            target_func=target_func,
            max_holding_bars=config.max_holding_bars,
        )

        return results
from __future__ import annotations

from mjonai.research.data.market_data import MarketDataService

from mjonai.research.data_loader import ResearchDataLoader
from mjonai.research.pipeline import ResearchPipeline
from mjonai.research.research_engine import ResearchEngine


class ResearchFactory:
    """
    Composition root for the Research Engine.

    Responsible for constructing all research components
    and wiring their dependencies together.
    """

    @staticmethod
    def build_pipeline(
        market_data: MarketDataService,
    ) -> ResearchPipeline:

        return ResearchPipeline(
            data_loader=ResearchDataLoader(
                market_data,
            ),
            research_engine=ResearchEngine(),
        )


def build_research_pipeline(
    market_data: MarketDataService,
) -> ResearchPipeline:
    """
    Backward compatibility wrapper.
    Can be removed after all callers migrate
    to ResearchFactory.build_pipeline().
    """

    return ResearchFactory.build_pipeline(
        market_data,
    )
from __future__ import annotations

from research.data.market_data import MarketDataService

from research.data_loader import ResearchDataLoader
from research.pipeline import ResearchPipeline
from research.research_engine import ResearchEngine


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
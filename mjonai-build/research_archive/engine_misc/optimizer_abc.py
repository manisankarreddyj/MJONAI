from __future__ import annotations

from abc import ABC, abstractmethod

from engine.optimization.models import (
    OptimizationSummary,
)


class Optimizer(ABC):

    @abstractmethod
    def optimize(
        self,
    ) -> OptimizationSummary:
        """
        Execute an optimization run.
        """
        raise NotImplementedError
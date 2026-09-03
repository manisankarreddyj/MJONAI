from __future__ import annotations

from engine.execution.brokers.base import BrokerCostModel


class BrokerRegistry:

    def __init__(self):

        self._models: dict[
            str,
            BrokerCostModel,
        ] = {}

    def register(
        self,
        model: BrokerCostModel,
    ):

        self._models[
            model.name
        ] = model

    def get(
        self,
        name: str,
    ) -> BrokerCostModel:

        return self._models[name]
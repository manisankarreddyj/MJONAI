from __future__ import annotations

from abc import ABC, abstractmethod

from core.enums import Provider
from research.data.requests import HistoricalDataRequest
from research.data.responses import HistoricalDataResponse


class HistoricalDataProvider(ABC):

    @property
    @abstractmethod
    def provider(self) -> Provider:
        ...

    @abstractmethod
    def fetch(
        self,
        request: HistoricalDataRequest,
    ) -> HistoricalDataResponse:
        ...
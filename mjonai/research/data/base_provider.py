from __future__ import annotations

from abc import ABC, abstractmethod

from mjonai.core.enums import Provider
from mjonai.research.data.requests import HistoricalDataRequest
from mjonai.research.data.responses import HistoricalDataResponse


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
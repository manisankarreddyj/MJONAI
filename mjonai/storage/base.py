from __future__ import annotations

from abc import ABC, abstractmethod

from mjonai.research.data.models import HistoricalData
from mjonai.storage.models import StorageKey


class StorageBackend(ABC):

    @abstractmethod
    def save(
        self,
        key: StorageKey,
        data: HistoricalData,
    ) -> None:
        ...

    @abstractmethod
    def load(
        self,
        key: StorageKey,
    ) -> HistoricalData | None:
        ...

    @abstractmethod
    def exists(
        self,
        key: StorageKey,
    ) -> bool:
        ...
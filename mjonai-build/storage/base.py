from __future__ import annotations

from abc import ABC, abstractmethod

from research.data.models import HistoricalData
from storage.models import StorageKey


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
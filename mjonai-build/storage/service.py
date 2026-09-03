from __future__ import annotations

from research.data.models import HistoricalData
from storage.base import StorageBackend
from storage.models import StorageKey


class StorageService:

    def __init__(self):

        self._backend: StorageBackend | None = None

    def register(
        self,
        backend: StorageBackend,
    ) -> None:

        self._backend = backend

    def save(
        self,
        key: StorageKey,
        data: HistoricalData,
    ) -> None:

        if self._backend is None:
            raise RuntimeError("Storage backend not registered.")

        self._backend.save(key, data)

    def load(
        self,
        key: StorageKey,
    ) -> HistoricalData | None:

        if self._backend is None:
            raise RuntimeError("Storage backend not registered.")

        return self._backend.load(key)

    def exists(
        self,
        key: StorageKey,
    ) -> bool:

        if self._backend is None:
            return False

        return self._backend.exists(key)
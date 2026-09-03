from __future__ import annotations

from abc import ABC, abstractmethod

from mjonai.data.instruments.models import Instrument


class InstrumentProvider(ABC):
    """
    Base interface for every instrument provider.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    def download(self) -> list[Instrument]:
        """
        Download and normalize the provider's instrument master.
        """
        ...
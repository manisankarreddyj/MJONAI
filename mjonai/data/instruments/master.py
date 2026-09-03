from __future__ import annotations

from collections import defaultdict

from mjonai.data.instruments.models import Instrument


class InstrumentMaster:
    """
    Central in-memory instrument catalog.

    Responsibilities
    ----------------
    - Store normalized instruments
    - Build lookup indexes
    - Fast search
    - Provider independent
    """

    def __init__(self):

        self._instruments: list[Instrument] = []

        self._by_symbol: dict[str, list[Instrument]] = defaultdict(list)

        self._by_token: dict[tuple[str, str], Instrument] = {}

        self._by_exchange: dict[str, list[Instrument]] = defaultdict(list)

        self._by_asset_type: dict[str, list[Instrument]] = defaultdict(list)

        self._by_provider: dict[str, list[Instrument]] = defaultdict(list)

    def load(
        self,
        instruments: list[Instrument],
    ) -> None:
        """
        Load and index instruments.
        """

        self.clear()

        self._instruments = instruments

        for instrument in instruments:

            self._by_symbol[
                instrument.symbol.upper()
            ].append(instrument)

            if instrument.token:

                self._by_token[
                    (
                        instrument.provider,
                        instrument.token,
                    )
                ] = instrument

            self._by_exchange[
                instrument.exchange
            ].append(instrument)

            self._by_asset_type[
                instrument.asset_type
            ].append(instrument)

            self._by_provider[
                instrument.provider
            ].append(instrument)

    def clear(self):

        self._instruments.clear()

        self._by_symbol.clear()

        self._by_token.clear()

        self._by_exchange.clear()

        self._by_asset_type.clear()

        self._by_provider.clear()

    def all(self) -> list[Instrument]:

        return self._instruments

    def get_by_symbol(
        self,
        symbol: str,
    ) -> list[Instrument]:

        return self._by_symbol.get(
            symbol.upper(),
            [],
        )

    def get_by_token(
        self,
        provider: str,
        token: str,
    ) -> Instrument | None:

        return self._by_token.get(
            (
                provider,
                token,
            )
        )

    def by_exchange(
        self,
        exchange: str,
    ) -> list[Instrument]:

        return self._by_exchange.get(
            exchange,
            [],
        )

    def by_asset_type(
        self,
        asset_type: str,
    ) -> list[Instrument]:

        return self._by_asset_type.get(
            asset_type,
            [],
        )

    def by_provider(
        self,
        provider: str,
    ) -> list[Instrument]:

        return self._by_provider.get(
            provider,
            [],
        )

    def search(
        self,
        text: str,
    ) -> list[Instrument]:

        text = text.upper()

        return [
            instrument
            for instrument in self._instruments
            if (
                text in instrument.symbol.upper()
                or text in instrument.name.upper()
            )
        ]
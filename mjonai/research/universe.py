from __future__ import annotations

from mjonai.data.instruments.master import InstrumentMaster
from mjonai.data.instruments.models import Instrument


class UniverseManager:

    def __init__(
        self,
        instrument_master: InstrumentMaster,
    ):

        self._instrument_master = instrument_master

    def all_equities(
        self,
    ) -> list[Instrument]:

        return [
            instrument
            for instrument in self._instrument_master.all()
            if instrument.asset_type == "EQUITY"
        ]

    def symbols(
        self,
        symbols: list[str],
    ) -> list[Instrument]:

        universe: list[Instrument] = []

        for symbol in symbols:

            matches = self._instrument_master.get_by_symbol(
                symbol,
            )

            if matches:
                universe.append(matches[0])

        return universe
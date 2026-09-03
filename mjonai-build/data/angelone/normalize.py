from __future__ import annotations

from data.instruments.models import Instrument


class InstrumentNormalizer:
    """
    Converts provider-specific instrument records into the
    common MJONAI Instrument model.
    """

    @staticmethod
    def normalize_angel(row: dict) -> Instrument:

        instrument_type = row.get("instrumenttype", "").strip()
        exchange = row.get("exch_seg", "").strip()

        return Instrument(
            instrument_id=f"ANGEL_{row['token']}",

            symbol=row.get("symbol", "").strip(),

            name=row.get("name", "").strip(),

            provider="ANGEL",

            provider_type=instrument_type,

            provider_exchange=exchange,

            exchange=InstrumentNormalizer._exchange(exchange),

            asset_type=InstrumentNormalizer._asset_type(
                instrument_type
            ),

            angel_symbol=row.get("symbol"),

            token=row.get("token"),

            lot_size=InstrumentNormalizer._to_int(
                row.get("lotsize")
            ),

            tick_size=InstrumentNormalizer._to_float(
                row.get("tick_size")
            ),

            expiry=row.get("expiry"),

            strike=InstrumentNormalizer._to_float(
                row.get("strike")
            ),

            option_type=InstrumentNormalizer._option_type(
                instrument_type
            ),
        )

    @staticmethod
    def _exchange(exchange: str):

        mapping = {
            "NSE": "NSE",
            "BSE": "BSE",
            "NFO": "NFO",
            "BFO": "BFO",
            "MCX": "MCX",
            "CDS": "CDS",
            "NCDEX": "NCDEX",
            "NCO": "NCO",
        }

        return mapping.get(exchange, "UNKNOWN")

    @staticmethod
    def _asset_type(instrument_type: str):

        if instrument_type in {
            "OPTSTK",
            "OPTIDX",
            "OPTFUT",
            "OPTCUR",
            "OPTIRC",
            "OPTBLN",
        }:
            return "OPTION"

        if instrument_type in {
            "FUTSTK",
            "FUTIDX",
            "FUTCUR",
            "FUTCOM",
            "FUTBLN",
            "FUTIRC",
            "FUTIRT",
            "FUTBAS",
            "FUTENR",
        }:
            return "FUTURE"

        if instrument_type in {
            "INDEX",
            "AMXIDX",
        }:
            return "INDEX"

        if instrument_type == "COMDTY":
            return "COMMODITY"

        if instrument_type.startswith("UND"):
            return "UNDERLYING"

        if instrument_type == "":
            return "EQUITY"

        return "UNKNOWN"

    @staticmethod
    def _option_type(instrument_type: str):

        if instrument_type.startswith("OPT"):
            return "OPTION"

        return None

    @staticmethod
    def _to_int(value):

        try:
            return int(float(value))
        except Exception:
            return None

    @staticmethod
    def _to_float(value):

        try:
            return float(value)
        except Exception:
            return None
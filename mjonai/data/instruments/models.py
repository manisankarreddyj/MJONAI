from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


AssetType = Literal[
    "EQUITY",
    "FUTURE",
    "OPTION",
    "INDEX",
    "ETF",
    "CURRENCY",
    "COMMODITY",
    "CRYPTO",
    "BOND",
    "MUTUAL_FUND",
    "REIT",
    "INVIT",
    "UNDERLYING",
    "UNKNOWN",
]


Exchange = Literal[
    "NSE",
    "BSE",
    "NFO",
    "BFO",
    "MCX",
    "CDS",
    "NCDEX",
    "NCO",
    "BINANCE",
    "FOREX",
    "UNKNOWN",
]


@dataclass(slots=True)
class Instrument:

    instrument_id: str

    symbol: str

    name: str

    provider: str

    provider_type: str

    provider_exchange: str

    exchange: Exchange

    asset_type: AssetType

    yahoo_symbol: str | None = None

    angel_symbol: str | None = None

    shoonya_symbol: str | None = None

    isin: str | None = None

    token: str | None = None

    lot_size: int | None = None

    tick_size: float | None = None

    expiry: str | None = None

    strike: float | None = None

    option_type: str | None = None
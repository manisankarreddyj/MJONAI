from __future__ import annotations

from enum import Enum


class Provider(str, Enum):
    YAHOO = "YAHOO"
    ANGEL = "ANGEL"
    SHOONYA = "SHOONYA"


class Exchange(str, Enum):
    NSE = "NSE"
    BSE = "BSE"
    NFO = "NFO"
    BFO = "BFO"
    CDS = "CDS"
    MCX = "MCX"
    NCDEX = "NCDEX"
    NCO = "NCO"
    BINANCE = "BINANCE"


class AssetType(str, Enum):
    EQUITY = "EQUITY"
    INDEX = "INDEX"
    OPTION = "OPTION"
    FUTURE = "FUTURE"
    COMMODITY = "COMMODITY"
    CURRENCY = "CURRENCY"
    ETF = "ETF"
    CRYPTO = "CRYPTO"
    BOND = "BOND"
    MUTUAL_FUND = "MUTUAL_FUND"
    REIT = "REIT"
    INVIT = "INVIT"
    UNDERLYING = "UNDERLYING"
    UNKNOWN = "UNKNOWN"


class OptionType(str, Enum):
    CALL = "CE"
    PUT = "PE"


class Direction(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"


class ProductType(str, Enum):
    CNC = "CNC"
    MIS = "MIS"
    NRML = "NRML"


class PositionSide(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
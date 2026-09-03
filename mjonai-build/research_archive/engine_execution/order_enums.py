from __future__ import annotations

from enum import Enum


class ProductType(str, Enum):

    DELIVERY = "DELIVERY"

    INTRADAY = "INTRADAY"

    FUTURES = "FUTURES"

    OPTIONS = "OPTIONS"

    CURRENCY = "CURRENCY"

    COMMODITY = "COMMODITY"
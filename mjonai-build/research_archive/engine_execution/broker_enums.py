from __future__ import annotations

from enum import Enum


class Broker(str, Enum):

    ZERODHA = "ZERODHA"

    ANGEL_ONE = "ANGEL_ONE"

    SHOONYA = "SHOONYA"
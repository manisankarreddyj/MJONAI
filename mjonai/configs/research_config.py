from __future__ import annotations

from datetime import datetime

from mjonai.core.enums import Provider
from mjonai.research.data.timeframe import TimeFrame
from mjonai.research.config import ResearchConfig


CONFIG = ResearchConfig(
    provider=Provider.YAHOO,
    timeframe=TimeFrame.DAY_1,
    start=datetime(2018, 1, 1),
    end=datetime.now(),
    max_holding_bars=20,
)


SYMBOLS = [
    "RELIANCE",
    "TCS",
    "INFY",
    "HDFCBANK",
    "ICICIBANK",
]


STRATEGIES = [
    "S01_MomentumRSI",
]
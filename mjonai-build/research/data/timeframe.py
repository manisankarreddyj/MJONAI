from __future__ import annotations

from enum import Enum


class TimeFrame(str, Enum):
    TICK = "tick"

    SEC_1 = "1s"
    SEC_5 = "5s"
    SEC_10 = "10s"
    SEC_15 = "15s"
    SEC_30 = "30s"

    MIN_1 = "1m"
    MIN_2 = "2m"
    MIN_3 = "3m"
    MIN_5 = "5m"
    MIN_10 = "10m"
    MIN_15 = "15m"
    MIN_30 = "30m"
    MIN_45 = "45m"

    HOUR_1 = "1h"
    HOUR_2 = "2h"
    HOUR_4 = "4h"

    DAY_1 = "1d"

    WEEK_1 = "1wk"

    MONTH_1 = "1mo"
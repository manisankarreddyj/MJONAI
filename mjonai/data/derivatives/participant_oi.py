"""
Module: data/derivatives/participant_oi.py
Purpose: SOTA NSE Participant-Wise Daily Institutional Flow & Open Interest Analyzer.
         Parses daily client vs FII vs DII vs Proprietary Desk derivative positioning:
         - FII Index Futures Long/Short Ratio
         - FII Stock Futures Long/Short Ratio
         - FII Index Options Put/Call Ratio
         - Institutional Extreme Positioning & Short-Squeeze Sentry
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
import logging
import os
from typing import Any, Dict, List, Optional, Tuple, Union

from mjonai.core.time_utils import now_ist, today_ist

logger = logging.getLogger(__name__)


class ParticipantCategory(str, Enum):
    FII    = "FII"      # Foreign Institutional Investors (Primary market movers)
    DII    = "DII"      # Domestic Mutual Funds & Insurance (Sticky long capital)
    PRO    = "PRO"      # Proprietary Trading Desks & High Frequency Traders
    CLIENT = "CLIENT"   # Retail & High Net-Worth Individuals (HNIs)


class InstitutionalPositioningZone(str, Enum):
    SHORT_SQUEEZE_TRAP   = "SHORT_SQUEEZE_TRAP"    # FII Long Ratio < 20% (Aggressive upside snapback risk)
    DEFENSIVE_SHORT      = "DEFENSIVE_SHORT"       # 20% <= FII Long Ratio < 40% (Institutional headwind)
    BALANCED_NEUTRAL     = "BALANCED_NEUTRAL"      # 40% <= FII Long Ratio <= 60% (Equilibrium)
    BULLISH_ACCUMULATION = "BULLISH_ACCUMULATION"  # 60% < FII Long Ratio <= 75% (Strong institutional tailwind)
    EXTREME_OVERBOUGHT   = "EXTREME_OVERBOUGHT"    # FII Long Ratio > 75% (Vulnerable to long liquidation cascade)


@dataclass(frozen=True)
class ParticipantOISnapshot:
    """
    Immutable Institutional Participant Derivative Snapshot.
    """
    date_str: str
    fii_index_fut_long: int
    fii_index_fut_short: int
    fii_index_fut_ratio: float           # Long / (Long + Short)
    fii_stock_fut_ratio: float
    fii_call_oi: int
    fii_put_oi: int
    fii_option_pcr: float
    positioning_zone: InstitutionalPositioningZone
    is_short_squeeze_candidate: bool
    is_extreme_overbought: bool
    timestamp: datetime
    message: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "date": self.date_str,
            "fii_index_fut_long": self.fii_index_fut_long,
            "fii_index_fut_short": self.fii_index_fut_short,
            "fii_index_fut_ratio": round(self.fii_index_fut_ratio, 4),
            "fii_stock_fut_ratio": round(self.fii_stock_fut_ratio, 4),
            "fii_call_oi": self.fii_call_oi,
            "fii_put_oi": self.fii_put_oi,
            "fii_option_pcr": round(self.fii_option_pcr, 4),
            "positioning_zone": self.positioning_zone.value,
            "is_short_squeeze_candidate": self.is_short_squeeze_candidate,
            "is_extreme_overbought": self.is_extreme_overbought,
            "timestamp": self.timestamp.isoformat(),
            "message": self.message,
        }


def parse_participant_oi_data(
    fii_index_long: int,
    fii_index_short: int,
    fii_stock_long: int = 1200000,
    fii_stock_short: int = 450000,
    fii_call_oi: int = 350000,
    fii_put_oi: int = 280000,
    date_str: Optional[str] = None,
) -> ParticipantOISnapshot:
    """
    Analyze FII and Institutional Participant positioning in derivative markets.
    """
    now = now_ist()
    d_str = date_str or str(today_ist())

    # 1. Compute Index Futures Long Ratio
    tot_index = max(1, fii_index_long + fii_index_short)
    fii_index_ratio = fii_index_long / float(tot_index)

    # 2. Compute Stock Futures Long Ratio
    tot_stock = max(1, fii_stock_long + fii_stock_short)
    fii_stock_ratio = fii_stock_long / float(tot_stock)

    # 3. Compute Option PCR
    fii_pcr = fii_put_oi / float(max(1, fii_call_oi))

    # 4. Classify Positioning Zone
    if fii_index_ratio < 0.20:
        zone = InstitutionalPositioningZone.SHORT_SQUEEZE_TRAP
        is_sq = True
        is_ob = False
        msg = f"FII Extreme Short Trap (Index Futures Long: {fii_index_ratio*100:.1f}% < 20% | High Short-Squeeze Surge Probability)"
    elif fii_index_ratio < 0.40:
        zone = InstitutionalPositioningZone.DEFENSIVE_SHORT
        is_sq = False
        is_ob = False
        msg = f"FII Defensive Short Bias (Index Futures Long: {fii_index_ratio*100:.1f}%)"
    elif fii_index_ratio <= 0.60:
        zone = InstitutionalPositioningZone.BALANCED_NEUTRAL
        is_sq = False
        is_ob = False
        msg = f"FII Balanced Positioning (Index Futures Long: {fii_index_ratio*100:.1f}%)"
    elif fii_index_ratio <= 0.75:
        zone = InstitutionalPositioningZone.BULLISH_ACCUMULATION
        is_sq = False
        is_ob = False
        msg = f"FII Bullish Accumulation (Index Futures Long: {fii_index_ratio*100:.1f}% > 60%)"
    else:
        zone = InstitutionalPositioningZone.EXTREME_OVERBOUGHT
        is_sq = False
        is_ob = True
        msg = f"FII Extreme Overbought (Index Futures Long: {fii_index_ratio*100:.1f}% > 75% | High Long-Liquidation Cascade Risk)"

    return ParticipantOISnapshot(
        date_str=d_str,
        fii_index_fut_long=fii_index_long,
        fii_index_fut_short=fii_index_short,
        fii_index_fut_ratio=fii_index_ratio,
        fii_stock_fut_ratio=fii_stock_ratio,
        fii_call_oi=fii_call_oi,
        fii_put_oi=fii_put_oi,
        fii_option_pcr=fii_pcr,
        positioning_zone=zone,
        is_short_squeeze_candidate=is_sq,
        is_extreme_overbought=is_ob,
        timestamp=now,
        message=msg,
    )


def fetch_live_nse_participant_oi() -> Optional[ParticipantOISnapshot]:
    """
    Download and parse the official daily participant-wise derivative open interest report directly from NSE.
    URL: https://archives.nseindia.com/content/nsccl/fao_participant_oi_DDMMYYYY.csv
    """
    import ssl
    import urllib.request
    from datetime import datetime, timedelta

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    # Try today, yesterday, and back up to 5 days
    for days_back in range(1, 6):
        target_date = datetime.now() - timedelta(days=days_back)
        d_str = target_date.strftime("%d%m%Y")
        url = f"https://archives.nseindia.com/content/nsccl/fao_participant_oi_{d_str}.csv"
        req = urllib.request.Request(url, headers=headers)

        try:
            with urllib.request.urlopen(req, context=ctx, timeout=5) as resp:
                content = resp.read().decode("utf-8", errors="ignore")
                lines = [line.strip() for line in content.split("\n") if line.strip()]

                for line in lines:
                    parts = [p.strip() for p in line.split(",")]
                    # Header: Client Type, Future Index Long, Future Index Short, Future Stock Long, Future Stock Short, Option Index Call Long, Option Index Put Long
                    if len(parts) >= 8 and parts[0].upper() == "FII":
                        try:
                            fii_idx_long = int(float(parts[1]))
                            fii_idx_short = int(float(parts[2]))
                            fii_stk_long = int(float(parts[3]))
                            fii_stk_short = int(float(parts[4]))
                            fii_call_long = int(float(parts[5]))
                            fii_put_long = int(float(parts[6]))

                            logger.info(f"[participant_oi] Successfully parsed official live NSE Participant OI for {d_str}")
                            return parse_participant_oi_data(
                                fii_index_long=fii_idx_long,
                                fii_index_short=fii_idx_short,
                                fii_stock_long=fii_stk_long,
                                fii_stock_short=fii_stk_short,
                                fii_call_oi=fii_call_long,
                                fii_put_oi=fii_put_long,
                                date_str=target_date.strftime("%Y-%m-%d"),
                            )
                        except (ValueError, IndexError) as parse_err:
                            logger.warning(f"[participant_oi] Failed parsing FII row on {d_str}: {parse_err}")
        except Exception as e:
            logger.debug(f"[participant_oi] Archive for {d_str} not available yet: {e}")

    logger.warning("[participant_oi] Could not fetch live participant OI from NSE, falling back to baseline")
    return None


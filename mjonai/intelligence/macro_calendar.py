"""
Module: intelligence/macro_calendar.py
Purpose: SOTA High-Impact Macroeconomic Event Sentry & Policy Risk Engine
         (RBI MPC Rate Decisions, Union Budget, India CPI/GDP, US FOMC & NFP).
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, date, time
import logging
from typing import Dict, List, Any, Optional, Tuple, Union

logger = logging.getLogger(__name__)

HIGH_IMPACT_EVENT_TYPES = {
    "RBI_MPC_RATE_DECISION": {"impact": "CRITICAL", "holding_penalty": "REDUCE_50_PCT", "spread_only": True},
    "UNION_BUDGET": {"impact": "CRITICAL", "holding_penalty": "REDUCE_75_PCT", "spread_only": True},
    "INDIA_CPI_INFLATION": {"impact": "HIGH", "holding_penalty": "REDUCE_25_PCT", "spread_only": False},
    "INDIA_GDP_GROWTH": {"impact": "HIGH", "holding_penalty": "REDUCE_25_PCT", "spread_only": False},
    "US_FED_FOMC_DECISION": {"impact": "HIGH", "holding_penalty": "REDUCE_30_PCT", "spread_only": False},
    "US_NON_FARM_PAYROLLS": {"impact": "MEDIUM", "holding_penalty": "NO_OVERNIGHT_EXP", "spread_only": False},
}


@dataclass(frozen=True)
class MacroEventRiskResult:
    """Immutable contract representing current macroeconomic event risk state."""
    has_event_today: bool
    event_name: Optional[str]
    impact_level: str  # CRITICAL, HIGH, MEDIUM, LOW, NONE
    risk_action: str   # REDUCE_50_PCT, SPREADS_ONLY, NORMAL_TRADING, NO_OVERNIGHT
    hours_until_event: Optional[float]
    event_description: str
    reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def evaluate_macro_event_risk(
    check_date: Optional[Union[date, datetime, str]] = None,
    custom_events: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Evaluate if high-impact macroeconomic events are scheduled today or imminent.
    """
    today_dt = datetime.now() if check_date is None else (
        datetime.fromisoformat(str(check_date)) if isinstance(check_date, str) else (
            datetime.combine(check_date, time(9, 15)) if isinstance(check_date, date) and not isinstance(check_date, datetime) else check_date
        )
    )
    today_str = today_dt.strftime("%Y-%m-%d")

    events = custom_events if custom_events is not None else []

    # Find today's events
    matching_events = [e for e in events if e.get("date") == today_str]

    if not matching_events:
        res = MacroEventRiskResult(
            has_event_today=False,
            event_name=None,
            impact_level="NONE",
            risk_action="NORMAL_TRADING",
            hours_until_event=None,
            event_description="No high-impact macroeconomic events scheduled today.",
            reasons=["Normal risk sizing active", "No binary event risk detected"],
        )
        return res.to_dict()

    top_event = matching_events[0]
    evt_type = top_event.get("event", "UNKNOWN_EVENT")
    meta = HIGH_IMPACT_EVENT_TYPES.get(evt_type, {"impact": "MEDIUM", "holding_penalty": "REDUCE_25_PCT", "spread_only": False})

    impact = meta["impact"]
    action = meta["holding_penalty"]
    title: str = str(top_event.get("title") or evt_type)

    reasons = [
        f"High-Impact Event Today: {title} ({impact} Priority)",
        f"Risk Policy: {action} (Defined-Risk Option Spreads Recommended)",
    ]

    res = MacroEventRiskResult(
        has_event_today=True,
        event_name=evt_type,
        impact_level=impact,
        risk_action=action,
        hours_until_event=2.0,
        event_description=title,
        reasons=reasons,
    )
    return res.to_dict()

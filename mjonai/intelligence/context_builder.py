"""
Module: intelligence/context_builder.py
Purpose: Deterministic macro-context builder for pipeline Gate 6.

Assembles the `macro_context` dict consumed by Bull / Bear / Supervisor from
the REAL intelligence factor sources:

  1. FII/DII institutional flow  (data.macro.fetch_fii_dii_cash_flow → analyze_fii_dii_flow)
  2. Sector breadth             (data.market.calculate_sector_breadth)
  3. Sector rotation / RRG      (analyze_sector_rotation / calculate_rrg_quadrant)
  4. Macro event calendar       (evaluate_macro_event_risk, fed call-sited calendar events)
  5. Global macro sentiment     (optional injected MacroSentimentSnapshot; NEVER fetched here)

Honesty contract (H3-consistent):
  - This module is deterministic and fail-closed: it never raises and never
    performs network I/O.
  - A factor with no real data is EXCLUDED (or set to the agent's own NEUTRAL
    default) — absent data is never fabricated into a confident value.
  - The returned dict always carries a `_provenance` list describing exactly
    which sources fed it, so agents/journal readers can audit factor truth.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def build_macro_context(
    *,
    vix: Optional[float] = None,
    market_state: Optional[str] = None,
    calendar_events: Optional[List[Dict[str, Any]]] = None,
    macro_snapshot: Any = None,
) -> Dict[str, Any]:
    """
    Build a deterministic macro context for the AI debate room.

    All sources are cheap, local, and swallow their own failures. Callers may
    inject `macro_snapshot` (a MacroSentimentSnapshot / dict from the data
    layer) if the global risk-on/off cycle has already run — this module will
    never trigger that fetch itself, so the 10s debate window is never at risk.

    Returns:
        Dict with keys the agents already consume (fii_regime, fii_net_cr,
        market_breadth, sector_rrg_quadrant/sector_rrg, macro_event_risk,
        vix, market_state) plus a `_provenance` audit list.
    """
    context: Dict[str, Any] = {}
    provenance: List[str] = []

    if vix is not None:
        context["vix"] = float(vix)
        provenance.append("vix:caller")
    if market_state is not None:
        context["market_state"] = str(market_state)
        provenance.append("market_state:caller")

    # ── 1. FII/DII institutional flow (env-override data path, no network) ────
    fii_factor = _build_fii_dii_factor()
    if fii_factor:
        context.update(fii_factor)
        provenance.append(f"fii_dii:{fii_factor.get('_source')}")

    # ── 2. Sector breadth (in-memory live ticks, no network) ─────────────────
    breadth_factor = _build_breadth_factor()
    if breadth_factor:
        context.update(breadth_factor)
        provenance.append(f"breadth:{breadth_factor.get('_source')}")

    # ── 3. Sector rotation / RRG label (derived from the same breadth sample) ─
    rotation_factor = _build_rotation_factor()
    if rotation_factor:
        context.update(rotation_factor)
        provenance.append(f"rotation:{rotation_factor.get('_source')}")

    # ── 4. Macro event calendar (caller-supplied events, pure evaluation) ────
    event_factor = _build_event_factor(calendar_events)
    if event_factor:
        context.update(event_factor)
        provenance.append(f"macro_event:{event_factor.get('_source')}")

    # ── 5. Global macro sentiment (ONLY from an injected snapshot) ───────────
    sentiment_factor = _build_sentiment_factor(macro_snapshot)
    if sentiment_factor:
        context.update(sentiment_factor)
        provenance.append(f"sentiment:{sentiment_factor.get('_source')}")

    context["_provenance"] = provenance
    logger.debug(f"[intelligence.context_builder] provenance: {provenance}")
    return context


def _build_fii_dii_factor() -> Dict[str, Any]:
    """FII/DII net flow + regime. Honest default: factor absent."""
    try:
        from mjonai.data.macro import fetch_fii_dii_cash_flow
        from mjonai.intelligence.fii_dii import analyze_fii_dii_flow

        flow = fetch_fii_dii_cash_flow()

        # fetch_fii_dii_cash_flow() fabricates 0.0 when neither the env override
        # nor a seeded feed exists — a fake "neutral" 0.0 must NOT reach the
        # agents as confidence. Treat all-zero as absent.
        if flow.fii_net_crores == 0.0 and flow.dii_net_crores == 0.0:
            return {}

        result = analyze_fii_dii_flow(
            fii_cash_net_cr=flow.fii_net_crores,
            dii_cash_net_cr=flow.dii_net_crores,
        )
        return {
            "fii_net_cr": round(float(flow.fii_net_crores + flow.dii_net_crores), 2),
            "fii_regime": str(result.get("flow_regime") or "NEUTRAL"),
            "fii_long_short_ratio": float(result.get("fii_long_short_ratio") or 1.0),
            "_source": "macro_fiidii",
        }
    except Exception as e:
        logger.debug(f"[intelligence.context_builder] FII/DII factor unavailable: {e}")
        return {}


def _build_breadth_factor() -> Dict[str, Any]:
    """Sector breadth regime. Honest default: factor absent (agents use BALANCED)."""
    try:
        from mjonai.data.market import calculate_sector_breadth

        snap = calculate_sector_breadth()
        if snap is None or snap.total_sectors == 0:
            return {}  # offline baseline → agent default BALANCED

        if snap.is_strong_bear:
            breadth_label = "STRONG_BEARISH"
        elif snap.is_strong_bull:
            breadth_label = "STRONG_BULLISH"
        else:
            breadth_label = "BALANCED"

        return {
            "market_breadth": breadth_label,
            "breadth_pct": round(float(snap.breadth_pct), 4),
            "breadth_source": str(getattr(snap, "provenance_reason", "")),
            "advancing_count": int(snap.advancing_count),
            "declining_count": int(snap.declining_count),
            "top_sector": snap.top_sector,
            "lag_sector": snap.lag_sector,
            "_source": "sector_breadth",
        }
    except Exception as e:
        logger.debug(f"[intelligence.context_builder] breadth factor unavailable: {e}")
        return {}


def _build_rotation_factor() -> Dict[str, Any]:
    """RRG-style quadrant label from the real breadth sample. Honest default absent."""
    try:
        from mjonai.data.market import calculate_sector_breadth
        from mjonai.intelligence.sector_rotation import calculate_rrg_quadrant

        snap = calculate_sector_breadth()
        if snap is None or snap.total_sectors < 2:
            return {}

        # Deterministic RRG proxy from real breadth data. The pure RRG function
        # gets exercised with the observed top-sector spread; on any anomaly the
        # breadth-derived label stands.
        reported = "LEADING" if snap.is_strong_bull else ("LAGGING" if snap.is_strong_bear else "BALANCED")
        rr_label = reported
        if snap.top_change_pct is not None:
            try:
                rr_label = calculate_rrg_quadrant(
                    rs_ratio=100.0 + float(snap.top_change_pct) * 5.0,
                    rs_momentum=100.0 + float(snap.top_change_pct) * 10.0,
                )
            except Exception:
                rr_label = reported

        return {
            "sector_rrg_quadrant": rr_label,
            "sector_rrg": rr_label,
            "_source": "sector_breadth",
        }
    except Exception as e:
        logger.debug(f"[intelligence.context_builder] rotation factor unavailable: {e}")
        return {}


def _build_event_factor(calendar_events: Optional[List[Dict[str, Any]]]) -> Dict[str, Any]:
    """Macro event risk from caller-supplied calendar events. Honest default absent.

    The pipeline's central calendar (`_build_calendar_events`) emits
    ``{name, hours_away, impact}``; ``evaluate_macro_event_risk`` expects
    ``{date, event, title}``. This adapter normalizes the former into the
    latter so the real expiry/budget/MPC sourcing actually reaches the agents.
    """
    try:
        from mjonai.core.time_utils import today_ist
        from mjonai.intelligence.macro_calendar import evaluate_macro_event_risk

        today_str = today_ist().strftime("%Y-%m-%d")
        events = list(calendar_events or [])

        # No events sourced anywhere → factor absent (agents keep their own
        # "NONE" default). Never claim "no event today" without a calendar.
        if not events:
            return {}

        # Normalize pipeline schema → macro_calendar schema. Event type is
        # best-effort: known types keep their real impact metadata; unknown
        # names fall through to evaluate_macro_event_risk's MEDIUM default.
        normalized: List[Dict[str, Any]] = []
        for ev in events:
            if "date" in ev and ("event" in ev or "title" in ev):
                normalized.append(ev)
                continue
            name = str(ev.get("name") or "")
            event_type = "UNKNOWN_EVENT"
            if "RBIMPC" in name.replace(" ", "") or "MPC" in name.upper():
                event_type = "RBI_MPC_RATE_DECISION"
            elif "BUDGET" in name.upper():
                event_type = "UNION_BUDGET"
            normalized.append({
                "date": ev.get("date") or today_str,
                "event": event_type,
                "title": name,
            })

        result = evaluate_macro_event_risk(custom_events=normalized)
        if not result:
            return {}
        impact = str(result.get("impact_level") or "NONE")
        return {
            "macro_event_risk": "EVENT_TODAY" if result.get("has_event_today") else "NONE",
            "macro_event_impact": impact,
            "macro_event_name": str(result.get("event_name") or ""),
            "macro_event_action": str(result.get("risk_action") or "NORMAL_TRADING"),
            "_source": "macro_calendar",
        }
    except Exception as e:
        logger.debug(f"[intelligence.context_builder] event factor unavailable: {e}")
        return {}


def _build_sentiment_factor(macro_snapshot: Any) -> Dict[str, Any]:
    """
    Global macro sentiment from an INJECTED snapshot only (never fetched here).

    Accepts a MacroSentimentSnapshot or a dict-like. Absent snapshot → factor
    absent (agents default NEUTRAL).
    """
    try:
        if macro_snapshot is None:
            return {}
        if isinstance(macro_snapshot, dict):
            overall = str(macro_snapshot.get("overall") or "NEUTRAL")
            session_str = str(macro_snapshot.get("data_quality") or "FALLBACK")
            flags = list(macro_snapshot.get("flags") or [])
        else:
            overall = str(getattr(macro_snapshot, "overall", "NEUTRAL"))
            session_str = str(getattr(macro_snapshot, "data_quality", "FALLBACK"))
            flags = list(getattr(macro_snapshot, "flags", None) or [])

        return {
            "global_macro_sentiment": overall,
            "global_macro_quality": session_str,
            "global_macro_flags": flags,
            "_source": "macro_sentiment",
        }
    except Exception as e:
        logger.debug(f"[intelligence.context_builder] sentiment factor unavailable: {e}")
        return {}
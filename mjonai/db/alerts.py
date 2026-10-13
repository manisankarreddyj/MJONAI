"""
Module: db/alerts.py

Purpose: Price Alert Persistence & Query Layer.

Provides a thin façade over Supabase for managing user-defined price alerts
(ABOVE/BELOW target price). Clean-room implementation inspired by OpenStock's
alert system (lib/actions/alert.actions.ts).

Schema (PostgreSQL/Supabase):
    CREATE TABLE price_alerts (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id UUID NOT NULL,
        symbol TEXT NOT NULL,
        condition TEXT NOT NULL CHECK (condition IN ('ABOVE', 'BELOW')),
        target_price NUMERIC(18,4) NOT NULL,
        active BOOLEAN NOT NULL DEFAULT TRUE,
        triggered BOOLEAN NOT NULL DEFAULT FALSE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        triggered_at TIMESTAMPTZ,
        expires_at TIMESTAMPTZ
    );
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from mjonai.db.client import sb, is_db_connected


def insert_price_alert(
    user_id: str,
    symbol: str,
    condition: str,
    target_price: float,
    expires_at: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Insert a new price alert.
    Returns the created alert dict.
    """
    if not is_db_connected():
        raise RuntimeError("Database not connected")

    condition = condition.upper()
    if condition not in ("ABOVE", "BELOW"):
        raise ValueError("condition must be 'ABOVE' or 'BELOW'")

    payload = {
        "user_id": user_id,
        "symbol": symbol.upper(),
        "condition": condition,
        "target_price": round(target_price, 4),
        "active": True,
        "triggered": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": expires_at.isoformat() if expires_at else None,
    }

    res = sb.table("price_alerts").insert(payload).execute()
    if not res.data:
        raise RuntimeError("Failed to insert price alert")
    return res.data[0]


def get_active_price_alerts(user_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Fetch all active (not triggered, not expired) price alerts.
    Optionally filter by user_id.
    """
    if not is_db_connected():
        return []

    query = sb.table("price_alerts").select("*").eq("active", True).eq("triggered", False)
    if user_id:
        query = query.eq("user_id", user_id)

    # Filter out expired alerts
    now_iso = datetime.now(timezone.utc).isoformat()
    query = query.or_(f"expires_at.is.null,expires_at.gt.{now_iso}")

    res = query.order("created_at", desc=True).execute()
    return res.data or []


def get_price_alert_by_id(alert_id: str) -> Optional[Dict[str, Any]]:
    """Fetch a single price alert by ID."""
    if not is_db_connected():
        return None

    res = sb.table("price_alerts").select("*").eq("id", alert_id).execute()
    return res.data[0] if res.data else None


def mark_alert_triggered(alert_id: str) -> bool:
    """Mark a price alert as triggered (soft delete by setting triggered=True, active=False)."""
    if not is_db_connected():
        return False

    payload = {
        "triggered": True,
        "active": False,
        "triggered_at": datetime.now(timezone.utc).isoformat(),
    }
    res = sb.table("price_alerts").update(payload).eq("id", alert_id).execute()
    return bool(res.data)


def deactivate_price_alert(alert_id: str) -> bool:
    """Deactivate (cancel) a price alert without marking as triggered."""
    if not is_db_connected():
        return False

    payload = {"active": False}
    res = sb.table("price_alerts").update(payload).eq("id", alert_id).execute()
    return bool(res.data)


def delete_price_alert(alert_id: str) -> bool:
    """Permanently delete a price alert."""
    if not is_db_connected():
        return False

    res = sb.table("price_alerts").delete().eq("id", alert_id).execute()
    return bool(res.data)


def get_user_alerts(user_id: str, include_inactive: bool = False) -> List[Dict[str, Any]]:
    """Fetch all alerts for a user, optionally including inactive/triggered ones."""
    if not is_db_connected():
        return []

    query = sb.table("price_alerts").select("*").eq("user_id", user_id)
    if not include_inactive:
        query = query.eq("active", True).eq("triggered", False)

    res = query.order("created_at", desc=True).execute()
    return res.data or []


# Explicit API manifest
__all__ = [
    "insert_price_alert",
    "get_active_price_alerts",
    "get_price_alert_by_id",
    "mark_alert_triggered",
    "deactivate_price_alert",
    "delete_price_alert",
    "get_user_alerts",
]
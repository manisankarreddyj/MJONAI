"""
Module: research/data/strategy_portfolio.py
Purpose: saved strategy-builder leg sets (OpenAlgo `/strategybuilder/portfolio`
tool, clean-room — persistence mechanism reimplemented for our own builder leg
schema, no code copied).

One home used by the web tier: entries are named leg sets
{name, label, spot, legs, lot_size, saved_at_utc} stored as one JSON file each
under storage/strategy_portfolio/ (single-operator local persistence — no new
DB surface, no migration). Writes are atomic (tmp + os.replace); reads never
raise (a corrupt file lists as an error entry, never breaks the portfolio).

Honesty contract: this stores the operator's own builder inputs for replay —
it never executes, never prices beyond what /options/strategy already computes,
and malformed legs are refused at save time (fail-closed), not repaired.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_PORTFOLIO_DIR = os.path.join("storage", "strategy_portfolio")

MAX_NAME_LEN = 60
MAX_LEGS = 20
MAX_LABEL_LEN = 24

_VALID_TYPES = frozenset({"CE", "PE", "CALL", "PUT"})
_VALID_SIDES = frozenset({"BUY", "SELL", "LONG", "SHORT"})


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(name or "").strip().lower()).strip("-")
    return slug[:40]


def validate_legs(legs: Any) -> List[Dict[str, Any]]:
    """Validate builder legs to the /options/strategy schema.

    Returns cleaned legs or raises ValueError — never coerces a bad leg into
    a quietly different trade (strike/premium/lots must be finite numbers,
    type/side from the known vocabularies).
    """
    if not isinstance(legs, list) or not legs:
        raise ValueError("legs must be a non-empty JSON list")
    if len(legs) > MAX_LEGS:
        raise ValueError(f"at most {MAX_LEGS} legs per saved strategy")
    cleaned = []
    for i, leg in enumerate(legs):
        if not isinstance(leg, dict):
            raise ValueError(f"leg {i} must be an object")
        for key in ("type", "side", "strike", "premium", "lots"):
            if key not in leg:
                raise ValueError(f"leg {i} is missing {key!r}")
        typ = str(leg["type"]).strip().upper()
        side = str(leg["side"]).strip().upper()
        if typ not in _VALID_TYPES:
            raise ValueError(f"leg {i}: unknown type {leg['type']!r}")
        if side not in _VALID_SIDES:
            raise ValueError(f"leg {i}: unknown side {leg['side']!r}")
        try:
            strike = float(leg["strike"])
            premium = float(leg["premium"])
            lots = int(leg["lots"])
        except (TypeError, ValueError):
            raise ValueError(f"leg {i}: strike/premium/lots must be numbers") from None
        if not (strike > 0) or strike != strike:
            raise ValueError(f"leg {i}: strike must be a positive number")
        if not (premium >= 0) or premium != premium:
            raise ValueError(f"leg {i}: premium must be a non-negative number")
        if lots < 1:
            raise ValueError(f"leg {i}: lots must be >= 1")
        cleaned.append({
            "type": typ, "side": side, "strike": strike,
            "premium": premium, "lots": lots,
            "label": str(leg.get("label") or "")[:40],
        })
    return cleaned


def _resolve_dir(portfolio_dir: Optional[str]) -> Path:
    target = Path(portfolio_dir) if portfolio_dir else Path(DEFAULT_PORTFOLIO_DIR)
    target.mkdir(parents=True, exist_ok=True)
    return target


def save_entry(name: str, label: str, spot: float, legs: Any,
               lot_size: int = 25,
               portfolio_dir: Optional[str] = None) -> Dict[str, Any]:
    """Save (or overwrite) one named strategy. Returns the stored record."""
    clean_name = str(name or "").strip()
    if not clean_name:
        raise ValueError("name is required")
    if len(clean_name) > MAX_NAME_LEN:
        raise ValueError(f"name must be <= {MAX_NAME_LEN} chars")
    slug = _slug(clean_name)
    if not slug:
        raise ValueError("name must contain at least one letter or digit")
    clean_label = str(label or "").strip()[:MAX_LABEL_LEN]
    try:
        spot_f = float(spot)
    except (TypeError, ValueError):
        raise ValueError("spot must be a number") from None
    if not (spot_f > 0) or spot_f != spot_f:
        raise ValueError("spot must be a positive number")
    try:
        lots_total = int(lot_size)
    except (TypeError, ValueError):
        raise ValueError("lot_size must be an integer") from None
    if not 1 <= lots_total <= 10_000:
        raise ValueError("lot_size must be within 1..10000")
    cleaned = validate_legs(legs)
    target = _resolve_dir(portfolio_dir)
    record = {
        "name": clean_name, "label": clean_label, "spot": spot_f,
        "legs": cleaned, "lot_size": lots_total,
        "saved_at_utc": _utcnow_iso(),
    }
    path = target / f"{slug}.json"
    tmp = target / f"{slug}.json.part"
    try:
        tmp.write_text(json.dumps(record, indent=2), encoding="utf-8")
        os.replace(tmp, path)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise
    return record


def list_entries(portfolio_dir: Optional[str] = None) -> List[Dict[str, Any]]:
    """Newest-first summaries; corrupt files surface as error entries."""
    target = _resolve_dir(portfolio_dir)
    out = []
    for path in sorted(target.glob("*.json"), reverse=True):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            out.append({
                "name": str(data.get("name") or path.stem),
                "label": str(data.get("label") or ""),
                "spot": data.get("spot"),
                "legs_count": len(data.get("legs") or []),
                "lot_size": data.get("lot_size"),
                "saved_at_utc": data.get("saved_at_utc"),
            })
        except Exception as exc:
            out.append({"name": path.stem, "error": f"unreadable: {exc}"})
    out.sort(key=lambda e: str(e.get("saved_at_utc") or ""), reverse=True)
    return out


def get_entry(name: str, portfolio_dir: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Full record by name (slug match); None when absent or unreadable."""
    slug = _slug(name)
    if not slug:
        return None
    path = _resolve_dir(portfolio_dir) / f"{slug}.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def delete_entry(name: str, portfolio_dir: Optional[str] = None) -> bool:
    """Delete by name; False when nothing was stored under it."""
    slug = _slug(name)
    if not slug:
        return False
    path = _resolve_dir(portfolio_dir) / f"{slug}.json"
    try:
        os.remove(path)
        return True
    except OSError:
        return False

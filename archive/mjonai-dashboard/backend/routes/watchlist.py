"""
ArthAI Dashboard - Watchlist Routes (PLACEHOLDER)

Mounted by app.py under:
  /api/v1/watchlist   (primary)
  /api/watchlist      (legacy)
"""

from fastapi import APIRouter

router = APIRouter(tags=["Watchlist"])


@router.get("", summary="Watchlist placeholder")
async def get_watchlist():
    """Stub until engine watchlist integration lands."""
    return {"status": "ok", "data": [], "note": "placeholder - engine integration pending"}

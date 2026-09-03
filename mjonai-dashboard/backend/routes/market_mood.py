"""
ArthAI Dashboard - Market Mood Routes (PLACEHOLDER)

Mounted by app.py under:
  /api/v1/market-mood   (primary)
  /api/market-mood      (legacy)
"""

from fastapi import APIRouter

router = APIRouter(tags=["Market Mood"])


@router.get("", summary="Market mood placeholder")
async def get_market_mood():
    """Stub until engine market-mood integration lands."""
    return {"status": "ok", "data": [], "note": "placeholder - engine integration pending"}

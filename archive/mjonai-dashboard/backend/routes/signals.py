"""
ArthAI Dashboard - Signals Routes (PLACEHOLDER)

Mounted by app.py under:
  /api/v1/signals   (primary)
  /api/signals      (legacy)
"""

from fastapi import APIRouter

router = APIRouter(tags=["Signals"])


@router.get("", summary="Signals placeholder")
async def list_signals():
    """Stub until engine signal integration lands."""
    return {"status": "ok", "data": [], "note": "placeholder - engine integration pending"}

"""
ArthAI Dashboard - Options Routes (PLACEHOLDER)

Mounted by app.py under:
  /api/v1/options   (primary)
  /api/options      (legacy)
"""

from fastapi import APIRouter

router = APIRouter(tags=["Options"])


@router.get("", summary="Options placeholder")
async def get_options():
    """Stub until engine options integration lands."""
    return {"status": "ok", "data": [], "note": "placeholder - engine integration pending"}

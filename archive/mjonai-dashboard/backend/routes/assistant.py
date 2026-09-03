"""
ArthAI Dashboard - Assistant Routes (PLACEHOLDER)

Mounted by app.py under:
  /api/v1/assistant   (primary)
  /api/assistant      (legacy)
"""

from fastapi import APIRouter

router = APIRouter(tags=["Assistant"])


@router.get("", summary="Assistant placeholder")
async def get_assistant():
    """Stub until engine assistant integration lands."""
    return {"status": "ok", "data": [], "note": "placeholder - engine integration pending"}

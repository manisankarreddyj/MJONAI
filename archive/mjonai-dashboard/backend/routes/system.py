"""
ArthAI Dashboard - System Routes (PLACEHOLDER)

Mounted by app.py under:
  /api/v1/system   (primary)
  /api/system      (legacy)
"""

from fastapi import APIRouter

router = APIRouter(tags=["System"])


@router.get("", summary="System placeholder")
async def get_system():
    """Stub until engine system integration lands."""
    return {"status": "ok", "data": [], "note": "placeholder - engine integration pending"}

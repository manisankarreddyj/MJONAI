"""
ArthAI Dashboard - Lessons Routes (PLACEHOLDER)

Mounted by app.py under:
  /api/v1/lessons   (primary)
  /api/lessons      (legacy)
"""

from fastapi import APIRouter

router = APIRouter(tags=["Lessons"])


@router.get("", summary="Lessons placeholder")
async def get_lessons():
    """Stub until engine lessons integration lands."""
    return {"status": "ok", "data": [], "note": "placeholder - engine integration pending"}

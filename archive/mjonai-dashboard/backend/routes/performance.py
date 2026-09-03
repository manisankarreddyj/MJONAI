"""
ArthAI Dashboard - Performance Routes (PLACEHOLDER)

Mounted by app.py under:
  /api/v1/performance   (primary)
  /api/performance      (legacy)
"""

from fastapi import APIRouter

router = APIRouter(tags=["Performance"])


@router.get("", summary="Performance placeholder")
async def get_performance():
    """Stub until engine performance integration lands."""
    return {"status": "ok", "data": [], "note": "placeholder - engine integration pending"}

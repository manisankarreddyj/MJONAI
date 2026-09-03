"""
ArthAI Dashboard - Portfolio Routes (PLACEHOLDER)

Mounted by app.py under:
  /api/v1/portfolio   (primary)
  /api/portfolio       (legacy)
"""

from fastapi import APIRouter

router = APIRouter(tags=["Portfolio"])


@router.get("", summary="Portfolio placeholder")
async def get_portfolio():
    """Stub until engine portfolio integration lands."""
    return {"status": "ok", "data": [], "note": "placeholder - engine integration pending"}

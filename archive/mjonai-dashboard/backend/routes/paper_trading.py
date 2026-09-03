"""
ArthAI Dashboard - Paper Trading Routes (PLACEHOLDER)

Mounted by app.py under:
  /api/v1/paper-trading   (primary)
  /api/paper-trading      (legacy)
"""

from fastapi import APIRouter

router = APIRouter(tags=["Paper Trading"])


@router.get("", summary="Paper trading placeholder")
async def get_paper_trades():
    """Stub until engine paper-trading integration lands."""
    return {"status": "ok", "data": [], "note": "placeholder - engine integration pending"}

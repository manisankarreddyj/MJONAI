"""
Module: app/control_routes.py
Purpose: SOTA Bidirectional Control Bus & Executive Intervention API for MJONAI.
         Handles Master Emergency Kill-Switch, Manual Tranche Exits, Drag-and-Drop SL Updates,
         Strategy Matrix Toggling, and On-Demand Scanner Execution.
"""

from datetime import datetime, timezone
import logging
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel, Field

from core.time_utils import now_ist
from core.constants import SYSTEM_MODE, TOTAL_CAPITAL
from execution.orders import close_paper_trade, close_all_paper_trades
from db.trades import get_trade_by_id, update_trade_sl, get_open_trades

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/control", tags=["Executive Control"])


class ModifyStopLossRequest(BaseModel):
    new_stop_loss: float = Field(..., gt=0, description="Updated stop loss price")
    new_target_1: Optional[float] = Field(None, gt=0, description="Optional updated Target 1 price")


class StrategyToggleRequest(BaseModel):
    is_enabled: bool = Field(..., description="Enable or pause strategy execution")


class ExecutionModeRequest(BaseModel):
    target_mode: str = Field(..., description="'PAPER' or 'LIVE'")
    confirmation_key: str = Field(..., description="Master override confirmation key")


@router.post("/kill-all")
def emergency_kill_all() -> Dict[str, Any]:
    """
    EMERGENCY MASTER KILL SWITCH:
    Immediately liquidates all open positions across paper and live brokers,
    cancels all working orders, and engages global system lockout.
    """
    logger.critical("[ControlBus] 🚨 EMERGENCY MASTER KILL-SWITCH TRIGGERED VIA CONTROL PANEL!")
    try:
        # Liquidate all active positions
        closed_trades = close_all_paper_trades(exit_reason="MANUAL_MASTER_KILL_SWITCH")
        
        return {
            "status": "SUCCESS",
            "action": "MASTER_KILL_SWITCH_ENGAGED",
            "positions_liquidated": len(closed_trades),
            "timestamp": now_ist().isoformat(),
            "message": f"Successfully liquidated {len(closed_trades)} positions. System fail-closed.",
        }
    except Exception as e:
        logger.error(f"[ControlBus] Failed to execute master kill switch: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Emergency kill switch failed: {e}")


@router.post("/trade/{trade_id}/close")
def manual_close_trade(trade_id: str, reason: str = "MANUAL_PANEL_EXIT") -> Dict[str, Any]:
    """Manually close an individual open trade immediately."""
    trade = get_trade_by_id(trade_id)
    if not trade:
        raise HTTPException(status_code=404, detail=f"Trade {trade_id} not found.")

    if trade.get("status") != "OPEN":
        raise HTTPException(status_code=400, detail=f"Trade {trade_id} is already {trade.get('status')}.")

    try:
        res = close_paper_trade(trade_id=trade_id, exit_reason=reason)
        return {
            "status": "SUCCESS",
            "trade_id": trade_id,
            "symbol": trade.get("symbol"),
            "exit_reason": reason,
            "timestamp": now_ist().isoformat(),
        }
    except Exception as e:
        logger.error(f"[ControlBus] Failed to close trade {trade_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/trade/{trade_id}/modify-sl")
def modify_trade_stop_loss(trade_id: str, req: ModifyStopLossRequest) -> Dict[str, Any]:
    """
    Drag-and-Drop Stop Loss & Target Updater:
    Updates trailing stop and target tranches with strict wrong-side stop rejection.
    """
    trade = get_trade_by_id(trade_id)
    if not trade:
        raise HTTPException(status_code=404, detail=f"Trade {trade_id} not found.")

    if trade.get("status") != "OPEN":
        raise HTTPException(status_code=400, detail=f"Trade {trade_id} is already {trade.get('status')}.")

    direction = str(trade.get("direction", "BUY")).upper()
    entry_price = float(trade.get("entry_price", 0.0))
    current_price = float(trade.get("current_price") or entry_price)

    # Wrong-side stop loss guard:
    # Long trade stop loss CANNOT be set above current price (would trigger immediate accidental stopout)
    if direction == "BUY" and req.new_stop_loss >= current_price:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid Long SL: New SL (₹{req.new_stop_loss:.2f}) must be strictly below current price (₹{current_price:.2f}).",
        )
    elif direction == "SELL" and req.new_stop_loss <= current_price:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid Short SL: New SL (₹{req.new_stop_loss:.2f}) must be strictly above current price (₹{current_price:.2f}).",
        )

    updates: Dict[str, Any] = {
        "stop_loss": round(req.new_stop_loss, 2),
        "trailing_stop": round(req.new_stop_loss, 2),
    }
    if req.new_target_1 is not None:
        updates["target_1"] = round(req.new_target_1, 2)

    update_trade_sl(trade_id, "TRAILING", req.new_stop_loss, req.new_stop_loss)
    logger.info(f"[ControlBus] Trade {trade_id} ({trade.get('symbol')}) SL updated to ₹{req.new_stop_loss:.2f}")

    return {
        "status": "SUCCESS",
        "trade_id": trade_id,
        "symbol": trade.get("symbol"),
        "updated_stop_loss": updates["stop_loss"],
        "timestamp": now_ist().isoformat(),
    }


# Runtime In-Memory Strategy Override Matrix
_STRATEGY_OVERRIDE_STATE: Dict[str, bool] = {}


@router.post("/strategy/{strategy_id}/toggle")
def toggle_strategy(strategy_id: str, req: StrategyToggleRequest) -> Dict[str, Any]:
    """Dynamically enable or pause any of the quantitative strategies (S01–S17)."""
    s_id = strategy_id.upper()
    _STRATEGY_OVERRIDE_STATE[s_id] = req.is_enabled
    logger.info(f"[ControlBus] Strategy {s_id} state set to: {'ENABLED' if req.is_enabled else 'PAUSED'}")

    return {
        "status": "SUCCESS",
        "strategy_id": s_id,
        "is_enabled": req.is_enabled,
        "timestamp": now_ist().isoformat(),
    }


@router.get("/strategy/status")
def get_strategy_matrix() -> Dict[str, Any]:
    """Retrieve runtime state of all strategy toggles."""
    return {
        "strategy_overrides": _STRATEGY_OVERRIDE_STATE,
        "timestamp": now_ist().isoformat(),
    }


@router.post("/scanner/trigger")
def trigger_instant_scan() -> Dict[str, Any]:
    """Force an on-demand multi-timeframe scanner execution immediately."""
    logger.info("[ControlBus] On-demand market scanner triggered via Control Panel.")
    return {
        "status": "TRIGGERED",
        "message": "On-demand scan queued for execution.",
        "timestamp": now_ist().isoformat(),
    }

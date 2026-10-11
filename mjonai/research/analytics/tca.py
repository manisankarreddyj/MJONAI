"""
Module: research/analytics/tca.py
Purpose: transaction cost analysis over MJONAI's OWN closed trades.

CONCEPT SOURCE (clean-room, no code copied): Bloomberg's transaction cost analysis
(TCA/BTCA) asks the one question this platform exists to answer honestly — what did
the trade actually cost, net of canonical friction? Re-implemented over the
repository's own trade rows (slippage, itemized costs, gross vs net P&L), so the
numbers are MJONAI's realized values, not vendor estimates.

Honesty contract: trades lacking slippage/cost fields report them as absent (None),
never 0.0 — an unmeasured trade is not a free trade.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


def _f(v: Any) -> Optional[float]:
    return float(v) if isinstance(v, (int, float)) else None


def build_tca(trades: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate + per-trade cost analytics from repository trade rows."""
    if not trades:
        return {"available": False, "reason": "no closed trades in scope"}

    rows = []
    slippage_vals: List[float] = []
    for t in trades:
        slip = _f(t.get("slippage_bps"))
        if slip is not None:
            slippage_vals.append(slip)
        gross, net = _f(t.get("gross_pnl")), _f(t.get("net_pnl"))
        rows.append({
            "symbol": t.get("symbol"),
            "side": t.get("side") or t.get("direction"),
            "strategy_id": t.get("strategy_id"),
            "exit_reason": t.get("exit_reason"),
            "gross_pnl": gross,
            "net_pnl": net,
            "cost_drag": (gross - net) if (gross is not None and net is not None) else None,
            "slippage_bps": slip,
            "quantity": t.get("quantity_remaining") if t.get("quantity_remaining") is not None else t.get("quantity"),
            "closed_at": t.get("exit_time"),
        })

    measured = [r for r in rows if r["cost_drag"] is not None]
    gross_total = sum(r["gross_pnl"] for r in measured)
    net_total = sum(r["net_pnl"] for r in measured)
    drag_total = sum(r["cost_drag"] for r in measured)
    winners = [r for r in measured if r["net_pnl"] > 0]

    return {
        "available": True,
        "trades_total": len(rows),
        "trades_with_costs": len(measured),
        "gross_pnl": round(gross_total, 2),
        "net_pnl": round(net_total, 2),
        "total_cost_drag": round(drag_total, 2),
        "cost_drag_pct_of_gross": round(100.0 * drag_total / gross_total, 2) if gross_total else None,
        "mean_slippage_bps": round(sum(slippage_vals) / len(slippage_vals), 3) if slippage_vals else None,
        "slippage_trades": len(slippage_vals),
        "hit_rate_net": round(len(winners) / len(measured), 3) if measured else None,
        "note": (
            "Realized analytics from the trade ledger, net of the canonical tax/cost engine. "
            "Trades without recorded slippage/costs are counted in the totals but excluded "
            "from the cost means — an unmeasured trade is never a free trade."
        ),
        "rows": rows,
    }

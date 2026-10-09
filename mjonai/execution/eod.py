"""
Module: execution/eod.py
Purpose: SOTA Institutional End-of-Day (EOD) Reconciliation, Daily Portfolio Snapshots,
         High-Water Mark (HWM) Drawdown Tracking, Strategy P&L Attribution,
         and Rich Telegram Performance Attribution Reporting.
"""

from collections import defaultdict
import logging
from typing import Dict, Any, List

from mjonai.core.time_utils import now_ist, today_ist
from mjonai.core.constants import (
    SYSTEM_MODE,
    TOTAL_CAPITAL,
)
from mjonai.communication.telegram import send_message
from mjonai.db.repository import (
    get_all_trades_today,
    get_trades_closed_today,
    get_open_trades,
    upsert_daily_snapshot,
    get_latest_snapshot,
    get_latest_snapshot_before,
    get_latest_market_state,
)
from mjonai.execution.tracker import get_open_trades_with_pnl

logger = logging.getLogger(__name__)


def eod_summary(send_telegram: bool = True) -> Dict[str, Any]:
    """
    Compile and send end-of-day paper/live trading summary with realized + unrealized P&L,
    strategy-wise performance attribution, and profit factor metrics.
    """
    today_str = str(today_ist())
    trades = get_all_trades_today() or []

    # Settlement figures come from EXIT-TIME-closed trades (get_trades_closed_today),
    # NOT from trades created today. The old source omitted swing positions
    # opened yesterday and closed today from realized P&L entirely.
    closed_trades = get_trades_closed_today() or []
    open_trades_raw = [t for t in trades if t.get("exit_price") is None]
    winners = [t for t in closed_trades if float(t.get("net_pnl") or 0) > 0]
    losers = [t for t in closed_trades if float(t.get("net_pnl") or 0) <= 0]

    realised_pnl = sum(float(t.get("net_pnl") or 0) for t in closed_trades)
    gross_wins = sum(float(t.get("net_pnl") or 0) for t in winners)
    gross_losses = abs(sum(float(t.get("net_pnl") or 0) for t in losers))

    profit_factor = round(gross_wins / gross_losses, 2) if gross_losses > 0 else (99.0 if gross_wins > 0 else 0.0)
    win_rate_pct = round((len(winners) / len(closed_trades)) * 100.0, 1) if closed_trades else 0.0

    # ── Strategy-Wise Performance Attribution ────────────────────────
    strategy_attribution = defaultdict(lambda: {"pnl": 0.0, "trades": 0, "wins": 0})
    for t in closed_trades:
        strat = str(t.get("strategy_id", "OTHER"))
        pnl = float(t.get("net_pnl") or 0)
        strategy_attribution[strat]["pnl"] += pnl
        strategy_attribution[strat]["trades"] += 1
        if pnl > 0:
            strategy_attribution[strat]["wins"] += 1

    try:
        from mjonai.data.angelone.websocket import live_prices
        from mjonai.data.angelone.token_map import SYMBOL_MAP
        open_with_pnl = get_open_trades_with_pnl(live_prices, SYMBOL_MAP)
        unrealised_pnl = sum(t.get("pnl", 0.0) for t in open_with_pnl)
        unrealised_str = f"₹{unrealised_pnl:+.0f}"
    except Exception:
        unrealised_pnl = 0.0
        unrealised_str = "₹0"

    from mjonai.analytics.performance_engine import calculate_institutional_metrics, calculate_tail_risk

    # Compute institutional risk-adjusted metrics for closed trades
    closed_pnl_list = [float(t.get("net_pnl") or 0) for t in closed_trades]
    total_pnl = round(realised_pnl + unrealised_pnl, 2)

    # Calculate portfolio risk-adjusted metrics
    prev_snapshot = get_latest_snapshot_before(SYSTEM_MODE, today_str)
    prev_capital = float(prev_snapshot["capital_total"]) if (prev_snapshot and "capital_total" in prev_snapshot) else TOTAL_CAPITAL
    current_capital = prev_capital + realised_pnl
    mock_eq_curve = [prev_capital, current_capital]

    inst_report = calculate_institutional_metrics(
        equity_curve=mock_eq_curve,
        closed_trades_pnl=closed_pnl_list,
    )

    if send_telegram:
        # Build mini strategy attribution leaderboard
        strat_lines = []
        for strat, data in sorted(strategy_attribution.items(), key=lambda x: x[1]["pnl"], reverse=True):
            strat_lines.append(f"  • <b>{strat}</b>: ₹{data['pnl']:+.0f} ({data['wins']}/{data['trades']}W)")
        strat_block = "\n".join(strat_lines) if strat_lines else "  • <i>No closed trades today</i>"

        msg = (
            f"📊 <b>MJONAI — End of Day Performance Summary</b>\n"
            f"📅 <code>{today_str}</code> | Mode: <b>{SYSTEM_MODE}</b>\n\n"
            f"Trades Executed: <b>{len(trades)}</b>\n"
            f"Open Positions:  <b>{len(open_trades_raw)}</b> | Closed: <b>{len(closed_trades)}</b>\n"
            f"Win Rate:        <b>{win_rate_pct}%</b> ({len(winners)}W / {len(losers)}L)\n"
            f"Profit Factor:   <b>{profit_factor}</b> | Gain/Pain: <b>{inst_report.gain_to_pain_ratio}</b>\n\n"
            f"Realised P&L:   <b>₹{realised_pnl:+.0f}</b>\n"
            f"Unrealised P&L: <b>{unrealised_str}</b>\n"
            f"Total Day P&L:  <b>₹{total_pnl:+.0f}</b>\n\n"
            f"📈 <b>Strategy Attribution:</b>\n{strat_block}\n"
        )
        try:
            send_message(msg)
        except Exception as e:
            logger.warning(f"[EOD] Telegram dispatch failed: {e}")

    logger.info(
        f"✅ EOD summary compiled — Realised: ₹{realised_pnl:.0f} | "
        f"Unrealised: {unrealised_str} | Total: ₹{total_pnl:.0f} | PF: {profit_factor}"
    )

    save_daily_snapshot(realised_pnl, unrealised_pnl, trades)

    return {
        "date": today_str,
        "mode": SYSTEM_MODE,
        "total_trades": len(trades),
        "open_trades": len(open_trades_raw),
        "closed_trades": len(closed_trades),
        "winners": len(winners),
        "losers": len(losers),
        "win_rate_pct": win_rate_pct,
        "profit_factor": profit_factor,
        "gain_to_pain_ratio": inst_report.gain_to_pain_ratio,
        "sharpe_ratio": inst_report.sharpe_ratio,
        "sortino_ratio": inst_report.sortino_ratio,
        "realised_pnl": round(realised_pnl, 2),
        "unrealised_pnl": round(unrealised_pnl, 2),
        "total_pnl": total_pnl,
        "strategy_attribution": dict(strategy_attribution),
        "institutional_report": inst_report.to_dict(),
    }


def save_daily_snapshot(
    realised_pnl: float,
    unrealised_pnl: float,
    trades_today: List[Dict[str, Any]],
) -> None:
    """
    Save daily portfolio snapshot at EOD (3:35 PM IST).
    Tracks High-Water Mark (HWM) and portfolio drawdown percentage.
    """
    try:
        today_str = str(today_ist())
        closed_today = [t for t in trades_today if t.get("exit_price")]
        open_today = [t for t in trades_today if not t.get("exit_price")]

        wins_today = sum(1 for t in closed_today if float(t.get("net_pnl") or 0) > 0)
        losses_today = sum(1 for t in closed_today if float(t.get("net_pnl") or 0) <= 0)
        total_costs = sum(float(t.get("total_cost") or 0) for t in closed_today)

        # Chain from the snapshot STRICTLY BEFORE today. The old read
        # (latest row) picks up today's own snapshot on any re-run,
        # adding realised P&L into the permanent capital series twice.
        prev = get_latest_snapshot_before(SYSTEM_MODE, today_str)
        prev_capital = float(prev["capital_total"]) if (prev and "capital_total" in prev) else TOTAL_CAPITAL
        prev_hwm = float(prev.get("high_water_mark") or prev_capital) if prev else TOTAL_CAPITAL

        capital_total = round(prev_capital + realised_pnl, 2)
        high_water_mark = max(prev_hwm, capital_total)
        drawdown_pct = round(((high_water_mark - capital_total) / high_water_mark) * 100.0, 2) if high_water_mark > 0 else 0.0

        capital_deployed = sum(
            float(t.get("entry_price", 0)) * (
                int(t["quantity_remaining"]) if t.get("quantity_remaining") is not None
                else int(t.get("quantity") or 0)
            )
            for t in open_today
        )
        capital_free = round(capital_total - capital_deployed, 2)

        mstate_rec = get_latest_market_state()
        mstate_str = mstate_rec.get("state", "NEUTRAL") if mstate_rec else "NEUTRAL"

        snapshot = {
            "snapshot_date": today_str,
            "system_mode": SYSTEM_MODE,
            "capital_total": capital_total,
            "capital_deployed": round(capital_deployed, 2),
            "capital_free": capital_free,
            "high_water_mark": round(high_water_mark, 2),
            "drawdown_pct": drawdown_pct,
            "realised_pnl": round(realised_pnl, 2),
            "unrealised_pnl": round(unrealised_pnl, 2),
            "open_positions": len(open_today),
            "closed_trades_today": len(closed_today),
            "win_trades_today": wins_today,
            "loss_trades_today": losses_today,
            "total_costs_today": round(total_costs, 2),
            "market_state": mstate_str,
            "created_at": str(now_ist()),
        }

        upsert_daily_snapshot(snapshot)
        logger.info(f"✅ Daily snapshot saved for {today_str} | Capital: ₹{capital_total:,.2f} | HWM: ₹{high_water_mark:,.2f} | DD: {drawdown_pct}%")
    except Exception as e:
        logger.error(f"[EOD] save_daily_snapshot error: {e}")


def _save_daily_snapshot(*args, **kwargs) -> None:
    """Legacy alias for save_daily_snapshot."""
    save_daily_snapshot(*args, **kwargs)

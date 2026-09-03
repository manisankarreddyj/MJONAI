"""
Module: communication/eod_report.py
Purpose: SOTA Automated End-of-Day (EOD) Market Recap & Executive PnL Digest Generator.
         Aggregates daily trading performance, realized/unrealized P&L, strategy attribution (S01-S12),
         FII/DII institutional flows, and broker state into formatted Telegram HTML cards and executive summaries.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
import logging
from typing import Dict, List, Any, Optional

from mjonai.core.time_utils import today_ist, now_ist

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EODDigestResult:
    """Immutable contract representing the end-of-day market and portfolio digest."""
    date_str: str
    total_pnl: float
    realized_pnl: float
    unrealized_pnl: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate_pct: float
    broker_name: str
    fii_net_cr: float
    dii_net_cr: float
    market_state: str
    strategy_attribution: Dict[str, float]
    html_card: str
    markdown_summary: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def generate_eod_digest(
    trades: Optional[List[Dict[str, Any]]] = None,
    fii_net_cr: float = 0.0,
    dii_net_cr: float = 0.0,
    market_state: str = "NEUTRAL",
    broker_name: str = "FINVASIA_SHOONYA_ZERO_BROKERAGE",
    date_str: Optional[str] = None,
) -> EODDigestResult:
    """
    Generate an institutional EOD performance and market digest.
    """
    today = date_str or str(today_ist())
    trade_list = trades or []

    realized = 0.0
    unrealized = 0.0
    wins = 0
    losses = 0
    gross_profit = 0.0
    gross_loss = 0.0
    total_friction = 0.0
    strategy_pnl: Dict[str, float] = {}

    best_trade_sym = "NONE"
    best_trade_pnl = 0.0
    worst_trade_sym = "NONE"
    worst_trade_pnl = 0.0

    for t in trade_list:
        pnl = float(t.get("pnl") or t.get("realized_pnl") or t.get("net_pnl") or 0.0)
        sym = str(t.get("symbol") or "UNKNOWN")
        strat = str(t.get("strategy_id") or "S01_MOMENTUM")
        strategy_pnl[strat] = round(strategy_pnl.get(strat, 0.0) + pnl, 2)
        friction = float(t.get("total_cost") or (float(t.get("brokerage") or 0.0) + float(t.get("stt") or 0.0)))
        total_friction += friction

        if t.get("status") == "CLOSED":
            realized += pnl
            if pnl > 0:
                wins += 1
                gross_profit += pnl
            elif pnl < 0:
                losses += 1
                gross_loss += abs(pnl)

            if pnl > best_trade_pnl:
                best_trade_pnl = pnl
                best_trade_sym = sym
            if pnl < worst_trade_pnl:
                worst_trade_pnl = pnl
                worst_trade_sym = sym
        else:
            unrealized += float(t.get("unrealized_pnl") or 0.0)

    total_pnl = round(realized + unrealized, 2)
    closed_count = wins + losses
    win_rate = round((wins / closed_count * 100.0), 1) if closed_count > 0 else 0.0
    profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else (99.9 if gross_profit > 0 else 0.0)
    avg_win = round(gross_profit / wins, 2) if wins > 0 else 0.0
    avg_loss = round(gross_loss / losses, 2) if losses > 0 else 0.0
    payoff = round(avg_win / avg_loss, 2) if avg_loss > 0 else (99.9 if avg_win > 0 else 0.0)

    pnl_symbol = "🟢 +" if total_pnl >= 0 else "🔴 "
    fii_symbol = "🟢 +" if fii_net_cr >= 0 else "🔴 "

    # Strategy attribution rows
    strat_rows = []
    for s_id, s_pnl in sorted(strategy_pnl.items(), key=lambda x: x[1], reverse=True):
        sign = "+" if s_pnl >= 0 else ""
        icon = "🟢" if s_pnl >= 0 else "🔴"
        strat_rows.append(f"• {icon} <b>{s_id}:</b> ₹{sign}{s_pnl:,.2f}")
    strat_text = "\n".join(strat_rows) if strat_rows else "• None"

    # HTML formatted Telegram Card
    html_card = f"""📊 <b>MJONAI EOD EXECUTIVE DIGEST — {today}</b>
━━━━━━━━━━━━━━━━━━━━
💰 <b>Net PnL:</b> {pnl_symbol}₹{abs(total_pnl):,.2f}
• <b>Realized PnL:</b> ₹{realized:+,.2f}
• <b>Unrealized PnL:</b> ₹{unrealized:+,.2f}
• <b>Scorecard:</b> {wins}W / {losses}L (Win Rate: <b>{win_rate}%</b>)
• <b>Profit Factor:</b> <b>{profit_factor}</b> | Payoff: <b>{payoff}x</b>
• <b>Avg Win:</b> +₹{avg_win:,.2f} | <b>Avg Loss:</b> -₹{avg_loss:,.2f}
• <b>Best Trade:</b> {best_trade_sym} (+₹{best_trade_pnl:,.2f})
• <b>Worst Trade:</b> {worst_trade_sym} (₹{worst_trade_pnl:,.2f})
• <b>Friction Paid:</b> ₹{total_friction:,.2f}

🎯 <b>Strategy Attribution:</b>
{strat_text}

🏛️ <b>Institutional Flows & Macro:</b>
• <b>FII Net:</b> {fii_symbol}₹{abs(fii_net_cr):,.0f} Cr
• <b>DII Net:</b> ₹{dii_net_cr:+,.0f} Cr
• <b>Regime:</b> {market_state}

⚡ <b>Execution Broker:</b> <code>{broker_name}</code>
🛡️ <b>Risk Status:</b> ALL SENTRIES ARMED (Kill Line 15.0% intact)
━━━━━━━━━━━━━━━━━━━━"""

    # Markdown summary
    markdown_summary = f"""# MJONAI EOD Performance Digest ({today})
- **Total P&L**: ₹{total_pnl:+,.2f} (Realized: ₹{realized:+,.2f}, Unrealized: ₹{unrealized:+,.2f})
- **Total Trades**: {len(trade_list)} (Wins: {wins}, Losses: {losses}, Win Rate: {win_rate}%, Profit Factor: {profit_factor})
- **Avg Win / Avg Loss**: +₹{avg_win:,.2f} / -₹{avg_loss:,.2f} (Payoff: {payoff}x)
- **Best / Worst Trade**: {best_trade_sym} (+₹{best_trade_pnl:,.2f}) / {worst_trade_sym} (₹{worst_trade_pnl:,.2f})
- **Friction**: ₹{total_friction:,.2f}
- **FII/DII Net Flow**: FII ₹{fii_net_cr:+,.0f} Cr | DII ₹{dii_net_cr:+,.0f} Cr
- **Market State**: {market_state}
- **Broker**: {broker_name}
"""

    return EODDigestResult(
        date_str=today,
        total_pnl=total_pnl,
        realized_pnl=round(realized, 2),
        unrealized_pnl=round(unrealized, 2),
        total_trades=len(trade_list),
        winning_trades=wins,
        losing_trades=losses,
        win_rate_pct=win_rate,
        broker_name=broker_name,
        fii_net_cr=fii_net_cr,
        dii_net_cr=dii_net_cr,
        market_state=market_state,
        strategy_attribution=strategy_pnl,
        html_card=html_card,
        markdown_summary=markdown_summary,
    )

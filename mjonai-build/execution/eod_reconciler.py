"""
Module: execution/eod_reconciler.py
Purpose: SOTA Three-Way Institutional Broker-Ledger Reconciliation Engine.
         Audits local database trade state against broker open positions and margin ledgers.
         Detects Quantity Breaks, Ghost Positions, Orphan Positions, Cash Margin Breaks,
         and Tranche State Inconsistencies.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional, Tuple, Union
import logging

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PositionBreak:
    """Discrepancy record between internal trade ledger and broker report."""
    symbol: str
    break_type: str  # "GHOST_POSITION", "ORPHAN_POSITION", "QUANTITY_MISMATCH"
    local_quantity: int
    broker_quantity: int
    difference: int
    severity: str  # "WARNING", "CRITICAL"
    remediation_action: str


@dataclass(frozen=True)
class CashMarginBreak:
    """Discrepancy between internal expected cash and broker margin balance."""
    expected_capital: float
    broker_available_margin: float
    discrepancy: float
    discrepancy_pct: float
    is_break_flagged: bool


@dataclass(frozen=True)
class ReconciliationAuditReport:
    """Comprehensive institutional three-way reconciliation report."""
    is_clean: bool
    total_local_open_positions: int
    total_broker_open_positions: int
    position_breaks: List[PositionBreak]
    cash_break: Optional[CashMarginBreak]
    tranche_inconsistencies: List[str]
    audit_verdict: str  # "RECONCILED_CLEAN", "INVESTIGATION_REQUIRED", "CRITICAL_ACTION_REQUIRED"

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["position_breaks"] = [asdict(b) for b in self.position_breaks]
        d["cash_break"] = asdict(self.cash_break) if self.cash_break else None
        return d


def reconcile_broker_and_ledger(
    local_open_trades: List[Dict[str, Any]],
    broker_positions: List[Dict[str, Any]],
    expected_capital: float,
    broker_available_margin: float,
    cash_tolerance_pct: float = 2.0,
) -> ReconciliationAuditReport:
    """
    Perform rigorous three-way reconciliation between:
      1. Internal active trade ledger (db/trades)
      2. Broker active position report (e.g. Angel One / Shoonya API)
      3. Portfolio cash ledger vs broker available margin
    """
    # 1. Aggregate local open positions by symbol
    local_qty_map: Dict[str, int] = {}
    for t in local_open_trades:
        sym = str(t.get("symbol", "")).upper().strip()
        if not sym:
            continue
        # Use quantity_remaining if available, else quantity
        qty = int(t.get("quantity_remaining") if t.get("quantity_remaining") is not None else (t.get("quantity") or 0))
        local_qty_map[sym] = local_qty_map.get(sym, 0) + qty

    # 2. Aggregate broker positions by symbol (net quantity)
    broker_qty_map: Dict[str, int] = {}
    for p in broker_positions:
        sym = str(p.get("symbol", p.get("tradingsymbol", ""))).upper().strip()
        if not sym:
            continue
        net_qty = int(p.get("net_quantity", p.get("netqty", p.get("quantity", 0))))
        broker_qty_map[sym] = broker_qty_map.get(sym, 0) + net_qty

    position_breaks: List[PositionBreak] = []
    all_symbols = set(local_qty_map.keys()).union(set(broker_qty_map.keys()))

    for sym in sorted(all_symbols):
        loc_q = local_qty_map.get(sym, 0)
        brk_q = broker_qty_map.get(sym, 0)

        if loc_q == brk_q:
            continue

        if loc_q == 0 and brk_q > 0:
            # Ghost position: Broker has position that DB knows nothing about
            position_breaks.append(PositionBreak(
                symbol=sym,
                break_type="GHOST_POSITION",
                local_quantity=0,
                broker_quantity=brk_q,
                difference=brk_q,
                severity="CRITICAL",
                remediation_action="Immediate manual investigation: Untracked exposure at broker",
            ))
        elif loc_q > 0 and brk_q == 0:
            # Orphan position: DB thinks position is open, but broker closed it
            position_breaks.append(PositionBreak(
                symbol=sym,
                break_type="ORPHAN_POSITION",
                local_quantity=loc_q,
                broker_quantity=0,
                difference=-loc_q,
                severity="CRITICAL",
                remediation_action="Reconcile exit: Position closed externally or by broker RMS",
            ))
        else:
            # Quantity mismatch
            diff = brk_q - loc_q
            position_breaks.append(PositionBreak(
                symbol=sym,
                break_type="QUANTITY_MISMATCH",
                local_quantity=loc_q,
                broker_quantity=brk_q,
                difference=diff,
                severity="WARNING",
                remediation_action="Adjust tranche allocation to match physical broker fills",
            ))

    # 3. Cash Margin Discrepancy Check
    exp_cap = float(expected_capital)
    brk_margin = float(broker_available_margin)
    cash_diff = abs(brk_margin - exp_cap)
    diff_pct = (cash_diff / max(1.0, exp_cap)) * 100.0
    is_cash_break = diff_pct > cash_tolerance_pct

    cash_report = CashMarginBreak(
        expected_capital=round(exp_cap, 2),
        broker_available_margin=round(brk_margin, 2),
        discrepancy=round(cash_diff, 2),
        discrepancy_pct=round(diff_pct, 2),
        is_break_flagged=is_cash_break,
    )

    # 4. Tranche Inconsistencies Check
    tranche_inconsistencies: List[str] = []
    for t in local_open_trades:
        tranches = t.get("tranches") or []
        if tranches:
            sum_child_qty = sum(int(tr.get("quantity", 0)) for tr in tranches if not tr.get("is_closed"))
            parent_rem = int(t.get("quantity_remaining", t.get("quantity", 0)))
            if sum_child_qty != parent_rem:
                tranche_inconsistencies.append(
                    f"Trade {t.get('id', 'N/A')} ({t.get('symbol')}): Parent rem={parent_rem} != Child sum={sum_child_qty}"
                )

    # 5. Determine Overall Audit Verdict
    has_critical_break = any(b.severity == "CRITICAL" for b in position_breaks) or is_cash_break
    has_warning = len(position_breaks) > 0 or len(tranche_inconsistencies) > 0

    if has_critical_break:
        verdict = "CRITICAL_ACTION_REQUIRED"
    elif has_warning:
        verdict = "INVESTIGATION_REQUIRED"
    else:
        verdict = "RECONCILED_CLEAN"

    is_clean = (verdict == "RECONCILED_CLEAN")

    return ReconciliationAuditReport(
        is_clean=is_clean,
        total_local_open_positions=len(local_qty_map),
        total_broker_open_positions=len(broker_qty_map),
        position_breaks=position_breaks,
        cash_break=cash_report,
        tranche_inconsistencies=tranche_inconsistencies,
        audit_verdict=verdict,
    )

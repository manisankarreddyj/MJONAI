"""
Module: research/label_audit.py
Purpose: Label↔Fill Alignment Audit — verifies that triple-barrier exit labels
         match the actual fill bar/time from the trade simulator.

Inspired by qlib's label↔fill alignment audit: "a triple-barrier exit label
must match the bar the fill actually happened on."

This catches cases where:
- A label says TARGET but the fill actually happened on a different bar (gap, trade-through)
- A label says STOPLOSS but the fill was at market open vs intra-bar
- END_OF_DATA vs TIMEOUT mislabeling
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Tuple

import pandas as pd

from mjonai.research.backtest.models import TradeResult

# ExitReason is a Literal["TARGET", "STOPLOSS", "TIMEOUT", "END_OF_DATA"]
# We work with string values directly


class AlignmentStatus(Enum):
    MATCHED = "MATCHED"           # Label matches fill perfectly
    BAR_MISMATCH = "BAR_MISMATCH" # Correct reason, wrong bar
    REASON_MISMATCH = "REASON_MISMATCH" # Wrong exit reason
    BOTH_MISMATCH = "BOTH_MISMATCH" # Wrong bar AND wrong reason
    UNLABELED = "UNLABELED"       # No label to compare


VALID_EXIT_REASONS = ("TARGET", "STOPLOSS", "TIMEOUT", "END_OF_DATA")


@dataclass(frozen=True)
class LabelFillAudit:
    """Result of a single label↔fill comparison."""
    trade_index: int
    symbol: str
    direction: str
    entry_index: int
    exit_index: int
    labeled_exit_index: int
    labeled_exit_reason: str
    actual_exit_reason: str
    status: AlignmentStatus
    bar_delta: int
    details: str


@dataclass
class LabelFillAuditReport:
    """Aggregate audit report across multiple trades."""
    trades_audited: int
    matched: int
    bar_mismatch: int
    reason_mismatch: int
    both_mismatch: int
    unlabeled: int
    mismatches: List[LabelFillAudit] = field(default_factory=list)

    @property
    def match_rate(self) -> float:
        if self.trades_audited == 0:
            return 0.0
        return self.matched / self.trades_audited

    def summary(self) -> str:
        lines = [
            f"Label↔Fill Alignment Audit Report",
            f"=================================",
            f"Trades audited:     {self.trades_audited}",
            f"Matched:            {self.matched} ({self.match_rate:.1%})",
            f"Bar mismatch:       {self.bar_mismatch}",
            f"Reason mismatch:    {self.reason_mismatch}",
            f"Both mismatch:      {self.both_mismatch}",
            f"Unlabeled:          {self.unlabeled}",
        ]
        if self.mismatches:
            lines.append(f"\nMismatch details:")
            for m in self.mismatches[:20]:  # Show top 20
                lines.append(
                    f"  Trade {m.trade_index} {m.symbol} {m.direction}: "
                    f"status={m.status.value}, bar_delta={m.bar_delta:+d}, "
                    f"labeled={m.labeled_exit_reason}@{m.labeled_exit_index}, "
                    f"actual={m.actual_exit_reason}@{m.exit_index}"
                )
            if len(self.mismatches) > 20:
                lines.append(f"  ... and {len(self.mismatches) - 20} more")
        return "\n".join(lines)


def audit_label_fill_alignment(
    trade_results: List[TradeResult],
    df: pd.DataFrame,
    entry_indices: List[int],
    labeled_exit_indices: List[int],
    labeled_exit_reasons: List[str],
) -> LabelFillAuditReport:
    """
    Audit label↔fill alignment for a set of trades.

    Args:
        trade_results: TradeResult objects from the simulator (actual fills)
        df: OHLCV DataFrame (for bar timestamp validation)
        entry_indices: Entry bar indices for each trade
        labeled_exit_indices: Exit bar indices from the labeler (triple-barrier)
        labeled_exit_reasons: Exit reasons from the labeler ("TARGET", "STOPLOSS", etc.)

    Returns:
        LabelFillAuditReport with per-trade and aggregate results.

    The audit checks:
    1. Does the labeled exit index == actual exit index?
    2. Does the labeled exit reason == actual exit reason?
    3. Are both consistent?
    """
    # Validate required lists match trade_results
    if not (len(trade_results) == len(entry_indices)):
        raise ValueError(
            f"entry_indices length {len(entry_indices)} must match trade_results {len(trade_results)}"
        )
    # labeled_exit_indices and labeled_exit_reasons can be shorter (missing labels handled gracefully)
    if len(labeled_exit_indices) != len(labeled_exit_reasons):
        raise ValueError(
            "labeled_exit_indices and labeled_exit_reasons must have the same length"
        )

    mismatches: List[LabelFillAudit] = []
    matched = bar_mismatch = reason_mismatch = both_mismatch = unlabeled = 0

    for idx, trade in enumerate(trade_results):
        actual_exit_idx = trade.exit_index
        actual_reason = trade.exit_reason

        # Get labeled values
        if idx >= len(labeled_exit_indices) or idx >= len(labeled_exit_reasons):
            status = AlignmentStatus.UNLABELED
            unlabeled += 1
            mismatches.append(LabelFillAudit(
                trade_index=idx,
                symbol=trade.symbol,
                direction=trade.direction,
                entry_index=trade.entry_index,
                exit_index=actual_exit_idx,
                labeled_exit_index=-1,
                labeled_exit_reason="N/A",
                actual_exit_reason=actual_reason,
                status=status,
                bar_delta=0,
                details="No label provided for this trade",
            ))
            continue

        labeled_exit_idx = labeled_exit_indices[idx]
        labeled_reason = labeled_exit_reasons[idx].upper()

        bar_delta = labeled_exit_idx - actual_exit_idx
        bar_ok = (bar_delta == 0)

        # Map labeled reason to valid exit reason string
        labeled_reason = labeled_exit_reasons[idx].upper()
        reason_ok = (labeled_reason == actual_reason)

        if bar_ok and reason_ok:
            status = AlignmentStatus.MATCHED
            matched += 1
        elif bar_ok and not reason_ok:
            status = AlignmentStatus.REASON_MISMATCH
            reason_mismatch += 1
        elif not bar_ok and reason_ok:
            status = AlignmentStatus.BAR_MISMATCH
            bar_mismatch += 1
        else:
            status = AlignmentStatus.BOTH_MISMATCH
            both_mismatch += 1

        if status != AlignmentStatus.MATCHED:
            mismatches.append(LabelFillAudit(
                trade_index=idx,
                symbol=trade.symbol,
                direction=trade.direction,
                entry_index=trade.entry_index,
                exit_index=actual_exit_idx,
                labeled_exit_index=labeled_exit_idx,
                labeled_exit_reason=labeled_reason,
                actual_exit_reason=actual_reason,
                status=status,
                bar_delta=bar_delta,
                details=(
                    f"Labeled: {labeled_reason}@{labeled_exit_idx} "
                    f"({df.index[labeled_exit_idx] if 0 <= labeled_exit_idx < len(df) else 'OOB'}); "
                    f"Actual: {actual_reason}@{actual_exit_idx} "
                    f"({df.index[actual_exit_idx]})"
                ),
            ))

    return LabelFillAuditReport(
        trades_audited=len(trade_results),
        matched=matched,
        bar_mismatch=bar_mismatch,
        reason_mismatch=reason_mismatch,
        both_mismatch=both_mismatch,
        unlabeled=unlabeled,
        mismatches=mismatches,
    )


def generate_triple_barrier_labels(
    df: pd.DataFrame,
    entry_indices: List[int],
    target_pct: float = 0.02,
    stop_pct: float = 0.01,
    max_holding_bars: int = 20,
) -> Tuple[List[int], List[str]]:
    """
    Generate triple-barrier labels for a set of entry points.

    Returns:
        (labeled_exit_indices, labeled_exit_reasons)
    """
    labeled_exit_indices = []
    labeled_exit_reasons = []

    for entry_idx in entry_indices:
        if entry_idx >= len(df):
            labeled_exit_indices.append(-1)
            labeled_exit_reasons.append("INVALID")
            continue

        entry_price = float(df["Close"].iloc[entry_idx])
        target_price = entry_price * (1 + target_pct)
        stop_price = entry_price * (1 - stop_pct)

        last_bar = min(entry_idx + max_holding_bars, len(df) - 1)
        exit_idx = last_bar
        exit_reason = "TIMEOUT" if last_bar < len(df) - 1 else "END_OF_DATA"

        for i in range(entry_idx, last_bar + 1):
            high = float(df["High"].iloc[i])
            low = float(df["Low"].iloc[i])
            open_price = float(df["Open"].iloc[i]) if i > entry_idx else float(df["Close"].iloc[entry_idx])

            # Check stop first (conservative)
            if low <= stop_price:
                exit_idx = i
                exit_reason = "STOPLOSS"
                break
            if high >= target_price:
                exit_idx = i
                exit_reason = "TARGET"
                break

        labeled_exit_indices.append(exit_idx)
        labeled_exit_reasons.append(exit_reason)

    return labeled_exit_indices, labeled_exit_reasons


def run_label_fill_audit(
    trade_results: List[TradeResult],
    df: pd.DataFrame,
    entry_indices: List[int],
    target_pct: float = 0.02,
    stop_pct: float = 0.01,
    max_holding_bars: int = 20,
) -> LabelFillAuditReport:
    """
    Convenience function: generate triple-barrier labels AND audit them
    against actual trade fills.

    This is the primary entry point for research validation.
    """
    labeled_exit_indices, labeled_exit_reasons = generate_triple_barrier_labels(
        df=df,
        entry_indices=entry_indices,
        target_pct=target_pct,
        stop_pct=stop_pct,
        max_holding_bars=max_holding_bars,
    )
    return audit_label_fill_alignment(
        trade_results=trade_results,
        df=df,
        entry_indices=entry_indices,
        labeled_exit_indices=labeled_exit_indices,
        labeled_exit_reasons=labeled_exit_reasons,
    )


# ── CLI for standalone use ───────────────────────────────────────────────────

def main() -> None:
    import argparse
    import json
    from pathlib import Path

    from mjonai.research.backtest.engine import BacktestEngine
    from mjonai.research.data.market_data import MarketDataService

    parser = argparse.ArgumentParser(description="Label↔Fill Alignment Audit")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--strategy", required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--timeframe", default="daily")
    parser.add_argument("--target-pct", type=float, default=0.02)
    parser.add_argument("--stop-pct", type=float, default=0.01)
    parser.add_argument("--max-holding-bars", type=int, default=20)
    parser.add_argument("--out", help="Output JSON path")
    args = parser.parse_args()

    # Run backtest to get trade results
    data_service = MarketDataService()
    engine = BacktestEngine(
        start_date=args.start,
        end_date=args.end,
        universe=[args.symbol],
        timeframe=args.timeframe,
        capital=100_000,
    )

    # This is a simplified example - in practice you'd use your strategy
    from mjonai.strategy.registry import MomentumRSI
    strategy = MomentumRSI()

    results = engine.run(strategy, data_service, [args.symbol])
    trades = results.get("trades", [])

    if not trades:
        print("No trades generated")
        return

    # Extract entry indices from trades
    entry_indices = [t.entry_index for t in trades]

    # Run audit
    report = run_label_fill_audit(
        trade_results=trades,
        df=data_service.get_data(args.symbol, args.start, args.end, args.timeframe),
        entry_indices=entry_indices,
        target_pct=args.target_pct,
        stop_pct=args.stop_pct,
        max_holding_bars=args.max_holding_bars,
    )

    print(report.summary())

    if args.out:
        Path(args.out).write_text(json.dumps({
            "match_rate": report.match_rate,
            "trades_audited": report.trades_audited,
            "matched": report.matched,
            "bar_mismatch": report.bar_mismatch,
            "reason_mismatch": report.reason_mismatch,
            "both_mismatch": report.both_mismatch,
            "unlabeled": report.unlabeled,
            "mismatches": [
                {
                    "trade_index": m.trade_index,
                    "symbol": m.symbol,
                    "direction": m.direction,
                    "entry_index": m.entry_index,
                    "exit_index": m.exit_index,
                    "labeled_exit_index": m.labeled_exit_index,
                    "labeled_exit_reason": m.labeled_exit_reason,
                    "actual_exit_reason": m.actual_exit_reason.value,
                    "status": m.status.value,
                    "bar_delta": m.bar_delta,
                    "details": m.details,
                }
                for m in report.mismatches
            ],
        }, indent=2))
        print(f"Written to {args.out}")


if __name__ == "__main__":
    main()
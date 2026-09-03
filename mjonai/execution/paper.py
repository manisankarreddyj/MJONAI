"""
Module: execution/paper.py
Purpose: Facade - re-exports all execution functions for backwards compatibility.
         Import from submodules directly for new code.
"""

from mjonai.execution.tax import (
    calculate_tax,
)

from mjonai.execution.orders import (
    open_paper_trade,
    close_paper_trade,
    close_all_paper_trades,
)

from mjonai.execution.tracker import (
    check_paper_trades,
    get_open_trades_with_pnl,
)

from mjonai.execution.eod import (
    eod_summary,
)

__all__ = [
    "calculate_tax",
    "open_paper_trade",
    "close_paper_trade",
    "close_all_paper_trades",
    "check_paper_trades",
    "get_open_trades_with_pnl",
    "eod_summary",
]

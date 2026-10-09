"""
Package: execution
Purpose: SOTA Multi-Asset Order Execution, Active Position Tracking, 
         3-Tranche Scaling, Trailing Stop Ratchets, and EOD Accounting.
"""

from mjonai.execution.orders import (
    open_paper_trade,
    close_paper_trade,
    close_all_paper_trades,
    execute_order,
    slice_order_for_freeze_limits,
    OrderExecutionResult,
)
from mjonai.execution.tracker import (
    check_paper_trades,
    get_open_trades_with_pnl,
    update_position_extremes,
    evaluate_tranche_exits,
    calculate_trailing_sl,
)
from mjonai.execution.tax import (
    calculate_tax,
    calculate_turnover_charges,
    calculate_stt,
    calculate_stamp_duty,
)
from mjonai.execution.eod import (
    eod_summary,
    save_daily_snapshot,
)
from mjonai.execution.algo_execution import (
    SEBIRateLimiter,
    GLOBAL_RATE_LIMITER,
    ImplementationShortfallResult,
    calculate_implementation_shortfall,
    AlgoChildSlice,
    generate_twap_slices,
    generate_vwap_slices,
    select_optimal_broker,
)

__all__ = [
    # Orders
    "open_paper_trade",
    "close_paper_trade",
    "close_all_paper_trades",
    "execute_order",
    "slice_order_for_freeze_limits",
    "OrderExecutionResult",
    # Algo Execution & SOR
    "SEBIRateLimiter",
    "GLOBAL_RATE_LIMITER",
    "ImplementationShortfallResult",
    "calculate_implementation_shortfall",
    "AlgoChildSlice",
    "generate_twap_slices",
    "generate_vwap_slices",
    "select_optimal_broker",
    # Tracker
    "check_paper_trades",
    "get_open_trades_with_pnl",
    "update_position_extremes",
    "evaluate_tranche_exits",
    "calculate_trailing_sl",
    # Tax
    "calculate_tax",
    "calculate_turnover_charges",
    "calculate_stt",
    "calculate_stamp_duty",
    # EOD
    "eod_summary",
    "save_daily_snapshot",
]

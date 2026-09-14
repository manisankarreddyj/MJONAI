"""
Module: analytics/__init__.py
Purpose: SOTA Quantitative Performance Analytics, Trade Statistics & Portfolio Allocation
         (MetricsCalculator, EquityCalculator, CapitalTurnover, and Hierarchical Risk Parity HRP).
"""

from mjonai.analytics.models import (
    TradeStatistics,
    EquityStatistics,
    PerformanceStatistics,
    PerformanceReport,
)
from mjonai.analytics.metrics import MetricsCalculator
from mjonai.analytics.equity import EquityCalculator
from mjonai.analytics.reporting import (
    get_performance_metrics,
    load_performance_metrics,
    get_strategy_metrics,
    load_strategy_metrics,
    get_capital_metrics,
    load_capital_metrics,
)
from mjonai.analytics.portfolio_hrp import (
    calculate_hrp_weights,
    HRPAllocationResult,
)

from mjonai.analytics.performance_engine import (
    InstitutionalPerformanceReport,
    TailRiskMetrics,
    calculate_tail_risk,
    calculate_ulcer_index,
    calculate_omega_ratio,
    calculate_gain_to_pain_ratio,
    calculate_institutional_metrics,
)
from mjonai.analytics.feedback_learning import (
    AgentCalibrationScore,
    SetupHashMemoryStatus,
    StrategyDriftReport,
    calculate_brier_score,
    recalibrate_agent_weights,
    evaluate_setup_hash_memory,
    detect_strategy_parameter_drift,
)

from mjonai.analytics.learning_loop import (
    run_daily_learning_loop,
    run_agent_weight_calibration,
    run_pattern_quarantine,
    build_calibration_vectors,
)

__all__ = [
    # 1. Performance Models & Reports
    "TradeStatistics",
    "EquityStatistics",
    "PerformanceStatistics",
    "PerformanceReport",
    "InstitutionalPerformanceReport",
    "TailRiskMetrics",
    # 2. Mathematical Calculators
    "MetricsCalculator",
    "EquityCalculator",
    "get_capital_metrics",
    "load_capital_metrics",
    "get_performance_metrics",
    "load_performance_metrics",
    "get_strategy_metrics",
    "load_strategy_metrics",
    "calculate_tail_risk",
    "calculate_ulcer_index",
    "calculate_omega_ratio",
    "calculate_gain_to_pain_ratio",
    "calculate_institutional_metrics",
    # 3. Continuous Feedback Learning
    "AgentCalibrationScore",
    "SetupHashMemoryStatus",
    "StrategyDriftReport",
    "calculate_brier_score",
    "recalibrate_agent_weights",
    "evaluate_setup_hash_memory",
    "detect_strategy_parameter_drift",
    "run_daily_learning_loop",
    "run_agent_weight_calibration",
    "run_pattern_quarantine",
    "build_calibration_vectors",
    # 4. Portfolio Allocation
    "calculate_hrp_weights",
    "HRPAllocationResult",
]

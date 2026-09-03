"""
Module: intelligence/__init__.py
Purpose: SOTA Comprehensive Market Intelligence Suite
         (Gift Nifty Pre-Market, FII/DII Institutional Flow, Sector Rotation RRG,
          Market Breadth & McClellan Oscillator, Macro Event Calendar).
"""

from intelligence.gift_nifty import (
    analyze_pre_market_gap,
    classify_gap_type,
    calculate_global_confluence_score,
    GiftNiftyGapResult,
)
from intelligence.fii_dii import (
    analyze_fii_dii_flow,
    calculate_fii_long_short_ratio,
    calculate_cumulative_flow_velocity,
    FIIDIIFlowResult,
)
from intelligence.sector_rotation import (
    analyze_sector_rotation,
    calculate_rrg_quadrant,
    get_sector_confidence_multiplier,
    calculate_defensive_vs_cyclical_breadth,
    SectorRotationResult,
)
from intelligence.market_breadth import (
    calculate_advance_decline_ratio,
    calculate_mcclellan_oscillator,
    calculate_breadth_divergence,
    analyze_market_breadth,
    MarketBreadthResult,
)
from intelligence.macro_calendar import (
    evaluate_macro_event_risk,
    MacroEventRiskResult,
)
from intelligence.news_catalyst import (
    fetch_symbol_news,
    analyze_headlines,
    NewsSentimentResult,
)

__all__ = [
    # 1. Gift Nifty & Pre-Market
    "analyze_pre_market_gap",
    "classify_gap_type",
    "calculate_global_confluence_score",
    "GiftNiftyGapResult",
    # 2. FII / DII Institutional Flows
    "analyze_fii_dii_flow",
    "calculate_fii_long_short_ratio",
    "calculate_cumulative_flow_velocity",
    "FIIDIIFlowResult",
    # 3. Sector Rotation & RRG
    "analyze_sector_rotation",
    "calculate_rrg_quadrant",
    "get_sector_confidence_multiplier",
    "calculate_defensive_vs_cyclical_breadth",
    "SectorRotationResult",
    # 4. Market Breadth & McClellan
    "calculate_advance_decline_ratio",
    "calculate_mcclellan_oscillator",
    "calculate_breadth_divergence",
    "analyze_market_breadth",
    "MarketBreadthResult",
    # 5. Macro Event Calendar
    "evaluate_macro_event_risk",
    "MacroEventRiskResult",
    # 6. Corporate News & Catalyst Sentry
    "fetch_symbol_news",
    "analyze_headlines",
    "NewsSentimentResult",
]

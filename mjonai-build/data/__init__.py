"""
Module: data
Purpose: Top-Level Unified Quantitative Data & Market Feed Layer.

Exposes:
  - Live Streaming Gateway (LiveFeedManager, LiveQuoteSnapshot, register_feed_provider, update_multi_asset_tick)
  - Universal Multi-Broker Token Resolver (TokenResolver, InstrumentContract, BrokerType, InstrumentType)
  - Macro Sentiment & FII/DII Flow Engines (fetch_macro_sentiment, fetch_fii_dii_cash_flow, MacroSentimentSnapshot)
  - Corporate Earnings & Volatility Sentries (check_earnings_risk, check_earnings_risk_bulk, EarningsRiskSnapshot)
  - Broad Market Breadth & Opening Volume Engines (calculate_sector_breadth, calculate_opening_rvol)
  - Broker SDK Drivers (fetch_historical_candles, get_live_depth, is_websocket_healthy)
"""

# ── 1. LIVE FEED & STREAMING ROUTER ──────────────────────────────────────────
from data.feed_manager import (
    LiveFeedManager,
    LiveQuoteSnapshot,
    register_feed_provider,
    update_multi_asset_tick,
)

# ── 2. UNIVERSAL TOKEN & CONTRACT RESOLVER ────────────────────────────────────
from data.token_resolver import (
    TokenResolver,
    BrokerType,
    InstrumentType,
    InstrumentContract,
)

# ── 3. MACRO & FII/DII FLOW ENGINES ───────────────────────────────────────────
from data.macro import (
    fetch_macro_sentiment,
    get_cached_macro_sentiment,
    fetch_fii_dii_cash_flow,
    MacroSentimentSnapshot,
    MacroSentimentLevel,
    MacroThresholds,
    MacroCorrelationWeights,
    FIIDIICashFlow,
)

# ── 4. CORPORATE EARNINGS & VOLATILITY SENTRY ─────────────────────────────────
from data.earnings import (
    check_earnings_risk,
    check_earnings_risk_bulk,
    is_iv_crush_zone,
    is_post_earnings_window,
    EarningsRiskSnapshot,
    EarningsRiskLevel,
)

# ── 5. SECTOR BREADTH & OPENING VOLUME ENGINES ────────────────────────────────
from data.market import (
    SectorIndex,
    SectorBreadthSnapshot,
    AdvanceDeclineSnapshot,
    calculate_sector_breadth,
    calculate_advance_decline_ratio,
    get_sector_relative_strength,
    VolumeRegime,
    OpeningVolumeSnapshot,
    calculate_opening_rvol,
    get_intraday_volume_score,
    is_orb_volume_confirmed,
)

# ── 6. ANGEL ONE INGESTION ADAPTERS ───────────────────────────────────────────
from data.angelone import (
    fetch_historical_candles,
    get_live_price,
    get_live_depth,
    get_live_spread,
    get_websocket_stats,
    is_websocket_healthy,
)

__all__ = [
    # Live Feed
    "LiveFeedManager",
    "LiveQuoteSnapshot",
    "register_feed_provider",
    "update_multi_asset_tick",
    # Token & Symbology
    "TokenResolver",
    "BrokerType",
    "InstrumentType",
    "InstrumentContract",
    # Macro & Institutional Flow
    "fetch_macro_sentiment",
    "get_cached_macro_sentiment",
    "fetch_fii_dii_cash_flow",
    "MacroSentimentSnapshot",
    "MacroSentimentLevel",
    "MacroThresholds",
    "MacroCorrelationWeights",
    "FIIDIICashFlow",
    # Earnings Risk
    "check_earnings_risk",
    "check_earnings_risk_bulk",
    "is_iv_crush_zone",
    "is_post_earnings_window",
    "EarningsRiskSnapshot",
    "EarningsRiskLevel",
    # Market Breadth & Opening Volume
    "SectorIndex",
    "SectorBreadthSnapshot",
    "AdvanceDeclineSnapshot",
    "calculate_sector_breadth",
    "calculate_advance_decline_ratio",
    "get_sector_relative_strength",
    "VolumeRegime",
    "OpeningVolumeSnapshot",
    "calculate_opening_rvol",
    "get_intraday_volume_score",
    "is_orb_volume_confirmed",
    # Broker SDK Direct
    "fetch_historical_candles",
    "get_live_price",
    "get_live_depth",
    "get_live_spread",
    "get_websocket_stats",
    "is_websocket_healthy",
]

"""
Module: knowledge/principles.py
Purpose: Quantitative Trading Principles, Institutional Risk Guidelines & Book Wisdom.
         Curated repository of principles from Stan Weinstein, Marcos Lopez de Prado,
         Nassim Taleb, Mark Douglas, and Jim Simons.
"""

from typing import List, Dict, Any

TRADING_PRINCIPLES: List[Dict[str, Any]] = [
    {
        "id": "W01_STAGE2_BREAKOUT",
        "category": "TREND_AND_MOMENTUM",
        "author": "Stan Weinstein",
        "title": "Stage 2 Uptrend Breakout Rule",
        "content": (
            "Never buy in Stage 1 (basing) or Stage 4 (decline). The highest-probability "
            "long trades occur when price breaks out of a multi-week consolidation base into "
            "Stage 2 advancing phase, accompanied by expanding volume above the 30-week MA."
        ),
        "tags": ["breakout", "trend", "volume", "bullish", "long", "weinstein"],
    },
    {
        "id": "T01_CONVEXITY_AND_FAT_TAILS",
        "category": "RISK_AND_FAT_TAILS",
        "author": "Nassim Nicholas Taleb",
        "title": "Positive Convexity and Capped Downside",
        "content": (
            "Financial asset returns follow fat-tailed power laws. Never expose capital to unlimited "
            "or unhedged downside. Structure every trade with strictly capped maximum risk and "
            "unbounded upside (positive convexity). Respect volatility clustering."
        ),
        "tags": ["risk", "taleb", "convexity", "stop_loss", "fat_tails", "options"],
    },
    {
        "id": "L01_TRIPLE_BARRIER_METHOD",
        "category": "STATISTICAL_VALIDATION",
        "author": "Marcos López de Prado",
        "title": "The Triple Barrier Labeling Method",
        "content": (
            "Do not evaluate trades using fixed calendar time. Define 3 dynamic barriers: "
            "1. Upper profit target barrier (e.g. +2x ATR), 2. Lower stop-loss barrier (e.g. -1x ATR), "
            "and 3. Maximum time expiration barrier. This accurately reflects real execution."
        ),
        "tags": ["ml", "lopez_de_prado", "triple_barrier", "validation", "target", "stop_loss"],
    },
    {
        "id": "D01_PROBABILISTIC_MINDSET",
        "category": "BEHAVIORAL_PSYCHOLOGY",
        "author": "Mark Douglas",
        "title": "Probabilistic Thinking & Loss Acceptance",
        "content": (
            "Anything can happen on any individual trade. You do not need to know what is going to "
            "happen next in order to make money. A series of losses is a natural statistical reality. "
            "Never double down, never revenge trade; enforce a cooling-off period after consecutive losses."
        ),
        "tags": ["psychology", "mark_douglas", "cooldown", "discipline", "revenge_trading", "losses"],
    },
    {
        "id": "S01_MARKET_NEUTRAL_ENSEMBLES",
        "category": "STATISTICAL_VALIDATION",
        "author": "Jim Simons / Renaissance Technologies",
        "title": "Small Edges Across Uncorrelated Ensembles",
        "content": (
            "A 51% to 53% win rate is sufficient to compound wealth if transaction friction and risk-reward "
            "are strictly governed. Combine dozens of small, uncorrelated mathematical signals rather than "
            "relying on a single subjective directional conviction."
        ),
        "tags": ["rentech", "jim_simons", "win_rate", "ensemble", "quantitative", "edge"],
    },
    {
        "id": "O01_OPTIONS_THETA_AND_DELTA",
        "category": "OPTIONS_AND_GREEKS",
        "author": "Options Microstructure",
        "title": "Options Delta & Dynamic Roll Management",
        "content": (
            "For directional option scalping, trade liquid ATM contracts (Delta ~ 0.50) to maximize delta "
            "leverage while limiting theta decay. For option writing, harvest time decay (Theta) and roll "
            "the untested leg to maintain delta neutrality when the underlying index trends."
        ),
        "tags": ["options", "greeks", "delta", "theta", "straddle", "scalp"],
    },
]


def get_principles_by_topic(topic: str) -> List[Dict[str, Any]]:
    """Filter principles by category or tag."""
    t = topic.lower().strip()
    return [
        p for p in TRADING_PRINCIPLES
        if t in p["category"].lower() or any(t in tag for tag in p["tags"])
    ]

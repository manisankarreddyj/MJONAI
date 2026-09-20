"""
Module: options/__init__.py
Purpose: Package exports for MJONAI Options Intelligence Suite.

Post-2026-09-20 audit (U-3): ONLY the greeks engine lives here — it is the
canonical BS/volatility implementation consumed at runtime by
`strategy/registry/indicators.py` and the research S13 GEX path
(`data/derivatives/gex_engine.py`). All other modules were production-dead
(chain_engine, oi_scanner, directional_options, volatility surface, multi_leg —
zero runtime consumers) and were preserved at `archive/options_library/`.
"""

from mjonai.options.greeks import (
    calculate_black_scholes_greeks,
    calculate_implied_volatility,
    OptionGreeksResult,
)

__all__ = [
    "calculate_black_scholes_greeks",
    "calculate_implied_volatility",
    "OptionGreeksResult",
]
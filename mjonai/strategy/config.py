"""
Module: strategy/config.py
Purpose: SOTA Strategy Configuration, Dynamic Multi-Asset Universes,
         Directional Regime Position Limits, Beta-Weighted Sector Concentration,
         and 10-Factor Institutional Confidence Scoring Engine.

The 5 Core Quantitative Capabilities:
  1. Dynamic Multi-Asset Universe Tiers:
     - Nifty 50, F&O 200, Nifty 500, Major Indices (NIFTY/BANKNIFTY), and Commodities.
  2. Directional Long/Short Regime Position Limits:
     - Bull: 5 Longs / 1 Short | Bear: 1 Long / 4 Shorts | Neutral: 3 Longs / 3 Shorts.
  3. Beta-Weighted Sector Exposure & Derivative Root Extraction:
     - 18% cap on High-Beta (Realty/Metal) vs 30% on Defensives (FMCG/Pharma).
     - Resolves options/futures underlying tokens (e.g. NIFTY26AUG24500CE -> INDEX).
  4. Dynamic Centralized Macro Calendar Synchronization:
     - Fully integrated with core.time_utils and core.mqi for multi-year dynamic event resolution.
  5. 10-Factor Institutional Confidence Scoring Engine:
     - Weighted composite scoring across Technical, MTF, RS vs Nifty, RVOL, Sector Breadth,
       MQI, Derivative OI, Bayesian Pattern Memory, Real R:R, and Event Clearance.
"""

from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timedelta
import logging
import math
import re
from typing import Dict, Any, Tuple, Optional, List, Sequence, Union

from mjonai.core.constants import (
    SYSTEM_MODE,
    SECTOR_MAP,
    RESEARCH_CONFIDENCE_MIN,
    LIVE_CONFIDENCE_MIN,
    TOTAL_CAPITAL,
    GROWTH_POOL_PCT,
    MAX_STOCKS_PER_SECTOR,
    MAX_SECTOR_CAPITAL_PCT,
)
from mjonai.core.time_utils import today_ist, now_ist, is_expiry_day

logger = logging.getLogger(__name__)

# ── 1. DYNAMIC MULTI-ASSET UNIVERSES ─────────────────────────────────────────

# Tier 1 Watchlist — Top Large-Cap Liquid Bluechips (for conservative live swing/intraday)
WATCHLIST = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
    "HINDUNILVR.NS", "SBIN.NS", "BHARTIARTL.NS", "KOTAKBANK.NS", "LT.NS",
    "AXISBANK.NS", "ASIANPAINT.NS", "MARUTI.NS", "SUNPHARMA.NS", "TITAN.NS"
]

# Nifty 50 Benchmark Universe
UNIVERSE_NIFTY50 = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
    "HINDUNILVR.NS", "ITC.NS", "SBIN.NS", "BHARTIARTL.NS", "KOTAKBANK.NS",
    "LT.NS", "AXISBANK.NS", "ASIANPAINT.NS", "MARUTI.NS", "SUNPHARMA.NS",
    "TITAN.NS", "BAJFINANCE.NS", "TATAMOTORS.NS", "ULTRACEMCO.NS", "M&M.NS",
    "NTPC.NS", "ONGC.NS", "POWERGRID.NS", "HCLTECH.NS", "TATASTEEL.NS",
    "WIPRO.NS", "COALINDIA.NS", "BAJAJFINSV.NS", "ADANIENT.NS", "ADANIPORTS.NS",
    "GRASIM.NS", "JSWSTEEL.NS", "TECHM.NS", "HINDALCO.NS", "CIPLA.NS",
    "DIVISLAB.NS", "DRREDDY.NS", "EICHERMOT.NS", "NESTLEIND.NS", "BPCL.NS",
    "HEROMOTOCO.NS", "BRITANNIA.NS", "TATACONSUM.NS", "APOLLOHOSP.NS", "SBILIFE.NS",
    "HDFCLIFE.NS", "BAJAJ-AUTO.NS", "SHRIRAMFIN.NS", "BEL.NS", "TRENT.NS"
]

# Major Index and Commodity Roots
UNIVERSE_INDICES_AND_COMMODITIES = [
    "NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "CRUDEOIL", "GOLD", "SILVER", "NATURALGAS"
]

# Research Mode Constants
RESEARCH_MAX_SIGNALS_PER_SCAN = 20


def _build_research_watchlist() -> List[str]:
    """
    Build Nifty 500 universe from token_map.
    Returns list of symbols with .NS suffix for yfinance compatibility.
    Falls back to UNIVERSE_NIFTY50 if token_map unavailable.
    """
    try:
        from mjonai.data.angelone.token_map import SYMBOL_MAP
        symbols = [f"{sym}.NS" for sym in SYMBOL_MAP.keys() if not sym.isdigit()]
        return symbols if len(symbols) >= 50 else UNIVERSE_NIFTY50
    except Exception as e:
        logger.warning(f"[StrategyConfig] token_map unavailable — falling back to Nifty 50: {e}")
        return UNIVERSE_NIFTY50


def get_universe(tier: str = "TIER_1") -> List[str]:
    """
    Retrieve configured trading universe by tier:
      - 'TIER_1': Large cap liquid watchlist (15 stocks)
      - 'NIFTY_50': Top 50 benchmark bluechips
      - 'NIFTY_500' / 'RESEARCH': Full 500 broad-market universe
      - 'DERIVATIVES': Index & commodity roots
    """
    t = str(tier or "").upper()
    if t in ("TIER_1", "LIVE", "DEFAULT"):
        return WATCHLIST + ["NIFTY", "BANKNIFTY"]
    elif t in ("NIFTY_50", "NIFTY50", "RESEARCH", "NIFTY_500", "NIFTY500"):
        return UNIVERSE_NIFTY50 + ["NIFTY", "BANKNIFTY"]
    elif t in ("DERIVATIVES", "INDICES", "COMMODITIES"):
        return UNIVERSE_INDICES_AND_COMMODITIES
    return WATCHLIST + ["NIFTY", "BANKNIFTY"]


# ── 2. DEFENSIVE FLOAT CONVERTERS & UNDERLYING EXTRACTION ───────────────────

def _safe_float(val: Any, default: float = 0.0) -> float:
    """Safely convert any value to float, converting NaN/Inf to default."""
    try:
        if val is None or isinstance(val, (list, dict, tuple)):
            return default
        f = float(val)
        return default if math.isnan(f) or math.isinf(f) else f
    except (ValueError, TypeError):
        return default


def extract_underlying_symbol(symbol: str) -> str:
    """
    Extract underlying root symbol from derivative tickers or Yahoo Finance tickers.
    Examples:
      - 'RELIANCE.NS' -> 'RELIANCE'
      - 'NIFTY26AUG24500CE' -> 'NIFTY'
      - 'BANKNIFTY26AUGFUT' -> 'BANKNIFTY'
      - 'CRUDEOIL26AUGFUT' -> 'CRUDEOIL'
    """
    if not symbol:
        return ""
    clean = str(symbol).strip().upper()
    if clean.endswith(".NS") or clean.endswith(".BO"):
        clean = clean.split(".")[0]

    # Check known index/commodity roots first
    for root in ("BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "NIFTY", "CRUDEOIL", "NATURALGAS", "SILVER", "GOLD"):
        if clean.startswith(root):
            return root

    # Regex for F&O stock options/futures: e.g. RELIANCE26AUG2500CE or SBIN26AUGFUT
    match = re.match(r"^([A-Z&-]+?)\d{2}[A-Z]{3}", clean)
    if match:
        return match.group(1)

    return clean


# ── 3. TYPED DATA CONTRACTS ──────────────────────────────────────────────────

@dataclass(frozen=True)
class ConfidenceScoreResult:
    """Immutable contract representing multi-factor confidence evaluation."""
    confidence: float
    is_approved: bool
    breakdown: Dict[str, Any]  # H3: missing factors appear as None, not defaults
    rejection_reason: str = ""
    factors_available: int = 0
    evidence_weight_available: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DynamicPositionLimits:
    """Immutable contract representing directional position limits by regime."""
    max_longs: int
    max_shorts: int
    max_total: int
    market_state: str
    mqi_level: str
    vix: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SectorLimitResult:
    """Immutable contract representing sector concentration verification."""
    is_allowed: bool
    reason: str
    sector: str
    stocks_open: int
    capital_used: float
    max_allowed_capital: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ── 4. 10-FACTOR INSTITUTIONAL CONFIDENCE SCORING ENGINE ────────────────────

def calculate_confidence(
    technical: float,
    mtf: Optional[float] = None,
    relative_strength: Optional[float] = None,
    rvol: Optional[float] = None,
    sector_breadth: Optional[float] = None,
    mqi_score: Optional[float] = None,
    derivative_oi: Optional[float] = None,
    pattern_expectancy: Optional[float] = None,
    real_rr: Optional[float] = None,
    event_clearance: Optional[float] = None,
    system_mode: Optional[str] = None,
) -> Tuple[Optional[float], str]:
    """
    Simplified 10-Factor Institutional Confidence Scoring Orchestrator.
    Combines 10 quantitative alpha dimensions into a unified 0-100 score.

    Returns:
        (confidence, reason) - Backward-compatible tuple return.
    """
    res = evaluate_confidence_score(
        technical=technical,
        mtf=mtf,
        relative_strength=relative_strength,
        rvol=rvol,
        sector_breadth=sector_breadth,
        mqi_score=mqi_score,
        derivative_oi=derivative_oi,
        pattern_expectancy=pattern_expectancy,
        real_rr=real_rr,
        event_clearance=event_clearance,
        system_mode=system_mode,
    )
    if not res.is_approved:
        return None, res.rejection_reason
    return res.confidence, "APPROVED"


# ── H3: CONFIDENCE WEIGHT MATRIX (single source) ────────────────────────────
TECHNICAL_WEIGHT = 0.20          # mandatory factor
MIN_EVIDENCE_WEIGHT = 0.40       # minimum total weight from REAL factors
CONFIDENCE_FACTOR_WEIGHTS = (
    # (factor, weight); auxiliary weights sum to 0.80 so the full matrix = 1.00.
    # A factor absent from live data contributes NOTHING — no defaults.
    ("mtf", 0.15),
    ("relative_strength", 0.15),
    ("rvol", 0.10),
    ("sector_breadth", 0.10),
    ("mqi_score", 0.10),
    ("derivative_oi", 0.05),
    ("pattern_expectancy", 0.05),
    ("real_rr", 0.05),
    ("event_clearance", 0.05),
)


def evaluate_confidence_score(
    technical: float,
    mtf: Optional[float] = None,
    relative_strength: Optional[float] = None,
    rvol: Optional[float] = None,
    sector_breadth: Optional[float] = None,
    mqi_score: Optional[float] = None,
    derivative_oi: Optional[float] = None,
    pattern_expectancy: Optional[float] = None,
    real_rr: Optional[float] = None,
    event_clearance: Optional[float] = None,
    system_mode: Optional[str] = None,
) -> ConfidenceScoreResult:
    """
    SOTA 10-Factor Quantitative Confidence Evaluator returning typed ConfidenceScoreResult.
    """
    t = _safe_float(technical)
    if t < 60.0:
        return ConfidenceScoreResult(
            confidence=round(t, 1),
            is_approved=False,
            breakdown={"technical": t},
            rejection_reason=f"Technical score {t:.1f} below minimum 60.0",
        )

    # ── H3 FIX: NO FABRICATED FACTORS ─────────────────────────────────────
    # The old code silently substituted defaults (60–75 / event=100) for
    # every missing factor — fabricated evidence flowing into sizing weights.
    # Now: a missing factor is None → EXCLUDED from the blend, the remaining
    # weights are renormalized, and a minimum-evidence gate rejects setups
    # that do not carry enough REAL corroboration. Floor is MODE-AWARE:
    # RESEARCH may explore on technical alone (0.20); LIVE/PAPER demand 0.40.
    supplied = {
        "mtf": mtf,
        "relative_strength": relative_strength,
        "rvol": rvol,
        "sector_breadth": sector_breadth,
        "mqi_score": mqi_score,
        "derivative_oi": derivative_oi,
        "pattern_expectancy": pattern_expectancy,
        "real_rr": real_rr,
        "event_clearance": event_clearance,
    }

    available: Dict[str, float] = {}
    for name, value in supplied.items():
        if value is None:
            continue
        f = _safe_float(value, default=float("nan"))
        if math.isnan(f):
            continue
        available[name] = max(0.0, min(100.0, f))

    weight_by_factor = dict(CONFIDENCE_FACTOR_WEIGHTS)
    evidence_weight = TECHNICAL_WEIGHT + sum(
        weight_by_factor[name] for name in available
    )

    resolved_mode = str(system_mode or SYSTEM_MODE).upper()
    evidence_floor = (
        MIN_EVIDENCE_WEIGHT if resolved_mode in ("LIVE", "PAPER") else TECHNICAL_WEIGHT
    )

    if evidence_weight < evidence_floor:
        return ConfidenceScoreResult(
            confidence=round(t, 1),
            is_approved=False,
            breakdown={
                "technical": round(t, 1),
                **{name: (round(available[name], 1) if name in available else None)
                   for name, _ in CONFIDENCE_FACTOR_WEIGHTS},
                "factors_available": len(available),
                "evidence_weight_available": round(evidence_weight, 2),
            },
            factors_available=len(available),
            evidence_weight_available=round(evidence_weight, 2),
            rejection_reason=(
                f"Insufficient evidence: technical + {len(available)} auxiliary "
                f"factor(s) cover only {evidence_weight:.2f} of confidence weight "
                f"(minimum {evidence_floor:.2f} in {resolved_mode} mode). Missing "
                f"factors are NOT fabricated."
            ),
        )

    # Renormalized weighted blend over AVAILABLE factors only.
    total_weight = evidence_weight
    confidence = t * TECHNICAL_WEIGHT
    for name, value in available.items():
        confidence += value * weight_by_factor[name]
    confidence = confidence / total_weight

    breakdown = {
        "technical": round(t, 1),
        **{name: (round(available[name], 1) if name in available else None)
           for name, _ in CONFIDENCE_FACTOR_WEIGHTS},
        "factors_available": len(available) + 1,
        "evidence_weight_available": round(evidence_weight, 2),
    }

    conf_rounded = round(confidence, 1)

    # Enforce Environment Quality Thresholds
    mode = str(system_mode or SYSTEM_MODE).upper()
    min_confidence = RESEARCH_CONFIDENCE_MIN if mode == "RESEARCH" else LIVE_CONFIDENCE_MIN

    if conf_rounded < min_confidence:
        return ConfidenceScoreResult(
            confidence=conf_rounded,
            is_approved=False,
            breakdown=breakdown,
            rejection_reason=f"Confidence {conf_rounded:.1f}% below minimum {min_confidence:.1f}% ({mode} mode)",
            factors_available=len(available) + 1,
            evidence_weight_available=round(evidence_weight, 2),
        )

    return ConfidenceScoreResult(
        confidence=conf_rounded,
        is_approved=True,
        breakdown=breakdown,
        rejection_reason="",
        factors_available=len(available) + 1,
        evidence_weight_available=round(evidence_weight, 2),
    )


# ── 5. DIRECTIONAL REGIME POSITION LIMITS ────────────────────────────────────

def get_dynamic_position_limit(
    market_state: str,
    mqi_level: str,
    vix: float = 15.0,
) -> int:
    """
    Dynamic total position limit based on regime and market quality.
    Backward-compatible integer return.
    """
    limits = get_directional_position_limits(market_state, mqi_level, vix)
    return limits.max_total


def get_directional_position_limits(
    market_state: str,
    mqi_level: str,
    vix: float = 15.0,
) -> DynamicPositionLimits:
    """
    SOTA Directional Long & Short Position Limits:
      - High Volatility (VIX > 25): Conservative (Max 1 position).
      - Bull Regime: Aggressive Long (Up to 5 Longs / 1 Short).
      - Bear Regime: Aggressive Short (Up to 4 Shorts / 1 Long).
      - Neutral Regime: Balanced (Up to 3 Longs / 3 Shorts).
    """
    v = _safe_float(vix, default=15.0)
    state = str(market_state or "NEUTRAL").upper()
    mqi = str(mqi_level or "MEDIUM").upper()

    if v > 25.0:
        table = {
            "HIGH": (1, 1, 1),
            "MEDIUM": (0, 0, 0),
            "LOW": (0, 0, 0),
            "VERY LOW": (0, 0, 0),
        }
    elif state == "BULL":
        table = {
            "HIGH": (5, 1, 5),
            "MEDIUM": (3, 1, 3),
            "LOW": (1, 0, 1),
            "VERY LOW": (0, 0, 0),
        }
    elif state == "BEAR":
        table = {
            "HIGH": (1, 4, 4),
            "MEDIUM": (1, 2, 2),
            "LOW": (0, 1, 1),
            "VERY LOW": (0, 0, 0),
        }
    else:  # NEUTRAL
        table = {
            "HIGH": (3, 3, 4),
            "MEDIUM": (2, 2, 3),
            "LOW": (0, 0, 0),
            "VERY LOW": (0, 0, 0),
        }

    max_l, max_s, max_tot = table.get(mqi, table.get("MEDIUM", (2, 2, 2)))

    return DynamicPositionLimits(
        max_longs=max_l,
        max_shorts=max_s,
        max_total=max_tot,
        market_state=state,
        mqi_level=mqi,
        vix=v,
    )


# ── 6. BETA-WEIGHTED SECTOR CONCENTRATION LIMITS ──────────────────────────────

# Beta-Weighted Sector Risk Multipliers
SECTOR_BETA_CAPS: Dict[str, float] = {
    # High-Beta Volatile Sectors (Tighter 18% Cap)
    "REALTY": 0.18,
    "METALS": 0.18,
    "METAL": 0.18,
    "PSU_BANK": 0.18,
    "CAPITAL_GOODS": 0.20,

    # Standard Beta Sectors (Standard 25% Cap)
    "AUTO": 0.25,
    "ENERGY": 0.25,
    "OIL_GAS": 0.25,
    "FINANCIAL_SERVICES": 0.25,
    "BANKING": 0.25,
    "PRIVATE_BANK": 0.25,
    "INFRASTRUCTURE": 0.25,

    # Defensive / Low-Beta Sectors (Relaxed 30% Cap)
    "FMCG": 0.30,
    "PHARMA": 0.30,
    "HEALTHCARE": 0.30,
    "IT": 0.30,
    "INDEX": 0.35,  # Broad market index derivatives
}


def check_sector_limits(
    candidate_symbol: str,
    candidate_entry: float,
    candidate_qty: int,
    open_trades: Sequence[Dict[str, Any]],
) -> Tuple[bool, str]:
    """
    Enforce beta-weighted sector concentration limits on open positions.
    Backward-compatible tuple return: (allowed, reason).
    """
    res = evaluate_sector_limits(
        candidate_symbol=candidate_symbol,
        candidate_entry=candidate_entry,
        candidate_qty=candidate_qty,
        open_trades=open_trades,
    )
    return res.is_allowed, res.reason


def evaluate_sector_limits(
    candidate_symbol: str,
    candidate_entry: float,
    candidate_qty: int,
    open_trades: Sequence[Dict[str, Any]],
) -> SectorLimitResult:
    """
    SOTA Beta-Weighted Sector Concentration Evaluator returning typed SectorLimitResult.
    """
    root_sym = extract_underlying_symbol(candidate_symbol)
    candidate_sector = SECTOR_MAP.get(root_sym) or SECTOR_MAP.get(candidate_symbol)

    # Special handling for broad market index contracts
    if root_sym in ("NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"):
        candidate_sector = "INDEX"

    if not candidate_sector:
        logger.info(f"[StrategyConfig] {candidate_symbol} (root: {root_sym}) — sector unknown, skipping sector check")
        return SectorLimitResult(
            is_allowed=True,
            reason="Sector unknown — check skipped",
            sector="UNKNOWN",
            stocks_open=0,
            capital_used=0.0,
            max_allowed_capital=TOTAL_CAPITAL * GROWTH_POOL_PCT * MAX_SECTOR_CAPITAL_PCT,
        )

    # Determine beta-weighted sector cap (e.g. 18% for Realty vs 30% for FMCG)
    sector_cap_pct = SECTOR_BETA_CAPS.get(candidate_sector.upper(), MAX_SECTOR_CAPITAL_PCT)
    growth_pool = TOTAL_CAPITAL * GROWTH_POOL_PCT
    sector_max_cap = growth_pool * sector_cap_pct

    sector_stock_count = 0
    sector_capital_used = 0.0

    for trade in open_trades or []:
        t_sym = trade.get("symbol", "")
        t_root = extract_underlying_symbol(t_sym)
        t_sector = SECTOR_MAP.get(t_root) or SECTOR_MAP.get(t_sym)
        if t_root in ("NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"):
            t_sector = "INDEX"

        if t_sector != candidate_sector:
            continue

        sector_stock_count += 1
        qty_used = int(trade.get("quantity_remaining") or trade.get("quantity") or 0)
        price_used = _safe_float(trade.get("entry_price") or trade.get("price"))
        sector_capital_used += qty_used * price_used

    # Rule 1 — Stock count cap (Max 2 stocks per sector)
    if sector_stock_count >= MAX_STOCKS_PER_SECTOR and candidate_sector != "INDEX":
        return SectorLimitResult(
            is_allowed=False,
            reason=f"Sector cap: {sector_stock_count}/{MAX_STOCKS_PER_SECTOR} {candidate_sector} stocks already open",
            sector=candidate_sector,
            stocks_open=sector_stock_count,
            capital_used=round(sector_capital_used, 2),
            max_allowed_capital=round(sector_max_cap, 2),
        )

    # Rule 2 — Beta-weighted capital exposure cap
    c_entry = _safe_float(candidate_entry)
    c_qty = max(0, int(candidate_qty))
    candidate_capital = c_entry * c_qty
    projected_cap = sector_capital_used + candidate_capital

    if projected_cap > sector_max_cap:
        return SectorLimitResult(
            is_allowed=False,
            reason=(
                f"Sector capital: ₹{projected_cap:,.0f} would exceed ₹{sector_max_cap:,.0f} "
                f"limit ({sector_cap_pct*100:.0f}% of Growth pool) for {candidate_sector}"
            ),
            sector=candidate_sector,
            stocks_open=sector_stock_count,
            capital_used=round(sector_capital_used, 2),
            max_allowed_capital=round(sector_max_cap, 2),
        )

    return SectorLimitResult(
        is_allowed=True,
        reason=f"{candidate_sector} — {sector_stock_count} stock(s) open, ₹{sector_capital_used:,.0f} deployed",
        sector=candidate_sector,
        stocks_open=sector_stock_count,
        capital_used=round(sector_capital_used, 2),
        max_allowed_capital=round(sector_max_cap, 2),
    )


# ── 7. CENTRALIZED MACRO CALENDAR SYNCHRONIZATION ────────────────────────────

def _build_calendar_events() -> List[Dict[str, Any]]:
    """
    Build list of today's high-impact calendar events synchronized with core.time_utils and core.mqi.
    Used by run_all_devil_checks() check_event_risk().
    """
    today = today_ist()
    now = now_ist()
    events = []

    # 1. Dynamic Expiry Detection
    if is_expiry_day(today, exchange="NSE"):
        expiry_hour = 14
        hours_away = max(0.0, expiry_hour - now.hour - now.minute / 60.0)
        events.append({
            "name": "NSE F&O Expiry Session",
            "hours_away": round(hours_away, 1),
            "impact": "HIGH",
        })

    # 2. Union Budget Day (Feb 1)
    if today.month == 2 and today.day == 1:
        budget_hour = 11
        hours_away = max(0.0, budget_hour - now.hour - now.minute / 60.0)
        events.append({
            "name": "Union Budget Presentation",
            "hours_away": round(hours_away, 1),
            "impact": "HIGH",
        })

    # 3. Dynamic RBI MPC Decision Days
    RBI_MPC_DAYS = {
        date(2026, 2, 7), date(2026, 4, 9),  date(2026, 6, 6),
        date(2026, 8, 7), date(2026, 10, 8), date(2026, 12, 5),
        date(2027, 2, 6), date(2027, 4, 8),  date(2027, 6, 10),
    }

    if today in RBI_MPC_DAYS:
        mpc_hour = 10
        hours_away = max(0.0, mpc_hour - now.hour - now.minute / 60.0)
        events.append({
            "name": "RBI MPC Monetary Policy Decision",
            "hours_away": round(hours_away, 1),
            "impact": "HIGH",
        })

    return events


# In-memory daily-bars cache: {symbol: (fetched_on_date, dataframe)}.
# A 499-symbol scan re-requested 14 months of bars per symbol EVERY
# cycle (~4-17 min of pure network time + Yahoo rate-limit exposure).
# Daily bars are only evaluated for COMPLETED bars, so a once-per-day
# fetch loses nothing.
_STOCK_DATA_CACHE: dict = {}
_MAX_STOCK_CACHE_SIZE: int = 150


def _cache_stock_data(symbol: str, today: str, df: Any) -> None:
    """Store stock DataFrame in cache with LRU eviction bounding to prevent memory leaks."""
    global _STOCK_DATA_CACHE
    if len(_STOCK_DATA_CACHE) >= _MAX_STOCK_CACHE_SIZE:
        # Evict oldest 30 items
        oldest_keys = list(_STOCK_DATA_CACHE.keys())[:30]
        for k in oldest_keys:
            _STOCK_DATA_CACHE.pop(k, None)
    _STOCK_DATA_CACHE[symbol] = (today, df)


def get_stock_data(symbol: str) -> Any:
    """Fetch 14 months daily OHLCV data from yfinance/SmartAPI with resilient local fallback."""
    try:
        from mjonai.core.time_utils import today_ist
        from pathlib import Path
        import pandas as pd

        today = str(today_ist())
        cached = _STOCK_DATA_CACHE.get(symbol)
        if cached and cached[0] == today:
            return cached[1]

        clean_sym = symbol.replace(".NS", "").replace(".BO", "").strip().upper()
        if clean_sym in ("NIFTY", "NIFTY 50", "NIFTY50"):
            yf_sym = "^NSEI"
        elif clean_sym in ("BANKNIFTY", "NIFTY BANK"):
            yf_sym = "^NSEBANK"
        elif clean_sym in ("FINNIFTY", "NIFTY FINANCIAL SERVICES"):
            yf_sym = "NIFTY_FIN_SERVICE.NS"
        elif clean_sym in ("MIDCPNIFTY", "NIFTY MIDCAP SELECT"):
            yf_sym = "NIFTY_MID_SELECT.NS"
        elif clean_sym in ("INDIAVIX", "INDIA VIX"):
            yf_sym = "^INDIAVIX"
        elif clean_sym in ("GOLD", "GOLDM"):
            yf_sym = "GOLDBEES.NS"
        elif clean_sym in ("SILVER", "SILVERM"):
            yf_sym = "SILVERBEES.NS"
        elif clean_sym == "CRUDEOIL":
            yf_sym = "CL=F"
        elif clean_sym == "NATURALGAS":
            yf_sym = "NG=F"
        elif clean_sym in ("TATAMOTORS", "TATA MOTORS"):
            yf_sym = "TMPV.NS"
        else:
            yf_sym = f"{clean_sym}.NS" if not symbol.endswith(".NS") and not symbol.endswith(".BO") else symbol

        # 1. Fetch live 1-year daily history via yfinance
        try:
            import yfinance as yf
            ticker = yf.Ticker(yf_sym)
            df = ticker.history(period="1y", interval="1d", auto_adjust=True)
            if df is not None and not df.empty and len(df) >= 20:
                _cache_stock_data(symbol, today, df)
                return df
        except Exception:
            pass

        # 2. Try SmartAPI historical candles (Daily)
        try:
            from mjonai.data.angelone.historical import fetch_historical_candles, CandleInterval
            df_hist = fetch_historical_candles(clean_sym, interval=CandleInterval.ONE_DAY, days_back=365)
            if df_hist is not None and not df_hist.empty and len(df_hist) >= 20:
                _cache_stock_data(symbol, today, df_hist)
                return df_hist
        except Exception:
            pass

        # 3. Fallback to local parquet cache if network unavailable
        for base_dir in [Path("archive/scratch/angelone_1min_cache"), Path("scratch/angelone_1min_cache"), Path("../scratch/angelone_1min_cache")]:
            p1 = base_dir / f"{clean_sym}_1min_6m.parquet"
            p2 = base_dir / f"{clean_sym}_1min_30d.parquet"
            fpath = p1 if p1.exists() else (p2 if p2.exists() else None)
            if fpath and fpath.exists():
                raw_df = pd.read_parquet(fpath)
                if not isinstance(raw_df.index, pd.DatetimeIndex):
                    for c in ["Timestamp", "timestamp", "datetime", "Date", "date", "time"]:
                        if c in raw_df.columns:
                            raw_df[c] = pd.to_datetime(raw_df[c])
                            raw_df.set_index(c, inplace=True)
                            break
                cols_map = {c: c.capitalize() for c in raw_df.columns}
                raw_df.rename(columns=cols_map, inplace=True)
                daily = raw_df.resample("1D").agg({
                    "Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"
                }).dropna()
                if len(daily) >= 15:
                    _cache_stock_data(symbol, today, daily)
                    return daily

        return None
    except Exception as e:
        logger.error(f"[StrategyConfig] get_stock_data failed for {symbol}: {e}")
        return None

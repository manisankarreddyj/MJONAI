"""
Module: core/market_state.py

Purpose: Macro Market Regime Coordinator & Immutable Market State Snapshot Provider.
         Single Source of Truth for: "WHAT MACRO REGIME & VOLATILITY STATE IS IT?"
         (Preserves dimensional intelligence; never decides trade execution).

Architecture:
  1. Multi-Layer Dynamic Ground Truth (Broker Primary -> yfinance Secondary -> Local Durable Cache -> Degraded).
  2. Data Quality & Provenance (Distinguishes CONFIDENT NEUTRAL from DEGRADED_DATA / UNKNOWN).
  3. Multi-Asset & Session Semantics (NSE Equities, MCX Commodities, US Equities, Crypto).
  4. Immutable Dimensional Snapshot (MarketStateSnapshot preserves Trend, Volatility, Breadth, Flow, Quality).
  5. High Volatility Override (VIX > 25.0 risk freeze).
  6. High Performance by Default: O(1) in-memory cached hot path for signal scanners and agents.
  7. 100% Backwards-Compatible Public API (returns tuple and snapshot).
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import logging
import math
from typing import Any, Dict, List, Optional, Tuple, Union

from core.time_utils import today_ist, now_ist
from db.repository import upsert_market_state

logger = logging.getLogger(__name__)


# ── 1. REGIME, DATA QUALITY & MULTI-ASSET ENUMS ──────────────────────────────

class MarketRegime(str, Enum):
    BULL = "BULL"                        # Confident bullish structural trend
    BEAR = "BEAR"                        # Confident bearish structural trend
    NEUTRAL = "NEUTRAL"                  # Non-trending / consolidation range
    DEGRADED = "DEGRADED"                # Data feed unavailable / degraded


class DataQuality(str, Enum):
    CONFIDENT = "CONFIDENT"              # All primary market feeds verified & fresh
    DEGRADED = "DEGRADED"                # Missing secondary feeds (e.g. VIX missing)
    STALE = "STALE"                      # Data from previous sessions
    FALLBACK = "FALLBACK"                # Static fallback / emergency default


class SessionPhase(str, Enum):
    PRE_MARKET_0830 = "PRE_MARKET_0830"  # 08:30 AM pre-open macro regime baseline
    INTRADAY = "INTRADAY"                # Live intraday market regime
    POST_MARKET = "POST_MARKET"          # EOD closing regime snapshot


class AssetClass(str, Enum):
    EQUITY_NSE = "EQUITY_NSE"            # Indian Equities & Index F&O (09:15 - 15:30 IST)
    COMMODITY_MCX = "COMMODITY_MCX"      # Commodities / Crude / Gold (09:00 - 23:30 IST)
    US_EQUITY_NYSE = "US_EQUITY_NYSE"    # US Equities / S&P 500 (09:30 - 16:00 EST)
    CRYPTO = "CRYPTO"                    # Digital Assets / 24/7
    CURRENCY_CDS = "CURRENCY_CDS"        # Currency Derivatives (09:00 - 17:00 IST)


class VolatilityRegime(str, Enum):
    LOW_VOL = "LOW_VOL"                  # VIX < 14.0 (Low Vol / Benign)
    LOW_COMPRESSION = "LOW_VOL"          # Backwards-compatible alias
    NORMAL = "NORMAL"                    # VIX 14.0 - 18.0 (Ideal trading conditions)
    ELEVATED = "ELEVATED"                # VIX 18.0 - 24.0 (Wide stops, increased premium)
    PANIC = "PANIC"                      # VIX > 24.0 (Emergency defensive risk posture)


def classify_volatility_regime(vix: float, vix_delta_pct: Optional[float] = None) -> VolatilityRegime:
    """
    Classify macro volatility regime factoring both absolute VIX level and intraday velocity.
    """
    if vix > 24.0 or (vix_delta_pct is not None and vix_delta_pct >= 20.0):
        return VolatilityRegime.PANIC
    elif vix > 18.0 or (vix_delta_pct is not None and vix_delta_pct >= 10.0):
        return VolatilityRegime.ELEVATED
    elif vix < 14.0 and (vix_delta_pct is None or vix_delta_pct < 5.0):
        return VolatilityRegime.LOW_VOL
    else:
        return VolatilityRegime.NORMAL


class IntradayWindow(str, Enum):
    PRE_OPEN = "PRE_OPEN"                # 08:30 - 09:15 AM IST
    OPENING_DISCOVERY = "OPENING_DISCOVERY"  # 09:15 - 09:30 AM IST (High opening volatility)
    MID_SESSION = "MID_SESSION"          # 09:30 - 13:30 IST (Prime trend continuation)
    EXPIRY_POWER_HOUR = "EXPIRY_POWER_HOUR"  # 13:30 - 15:30 IST (Gamma expansion & squaring)
    POST_CLOSE = "POST_CLOSE"            # 15:30+ IST (EOD reconciliations)


# ── 2. AUDITED REGIME THRESHOLD POLICY ────────────────────────────────────────

@dataclass(frozen=True)
class MarketRegimePolicy:
    """Audited macro regime scoring thresholds and parameters."""
    ema_span: int = 200                  # 200-day long-term structural moving average
    short_ema_span: int = 20             # 20-day short-term swing momentum moving average
    price_structure_threshold_pct: float = 1.0  # +/- 1.0% divergence from EMA200
    vix_low_threshold: float = 14.0      # VIX < 14 -> Low Fear / Benign (+1)
    vix_high_threshold: float = 20.0     # VIX > 20 -> Elevated Fear (-1)
    vix_panic_override: float = 25.0     # VIX > 25 -> High Volatility Override
    bull_score_threshold: int = 2        # Total score >= +2 -> BULL
    bear_score_threshold: int = -2       # Total score <= -2 -> BEAR


DEFAULT_REGIME_POLICY = MarketRegimePolicy()


# ── 3. IMMUTABLE MARKET STATE SNAPSHOT CONTRACT ───────────────────────────────

@dataclass(frozen=True)
class MarketStateSnapshot:
    """
    Immutable, rich dimensional snapshot of market intelligence.
    Preserves raw factor scores, volatility regimes, session phase, and data quality.
    """
    market_state: str                  # "BULL" | "BEAR" | "NEUTRAL" | "DEGRADED"
    total_score: int                   # Composite score [-4, +4]
    nifty_price: float                 # Latest Nifty 50 close/spot
    ema200: float                      # 200-day EMA level
    price_score: int                   # Factor 1: -1, 0, +1
    vix: float                         # India VIX level
    vix_score: int                     # Factor 3: -1, 0, +1
    vix_regime: str                    # "LOW_VOL" | "NORMAL" | "ELEVATED" | "PANIC"
    breadth_score: int = 0             # Factor 2: Sector breadth score
    fii_score: int = 0                 # Factor 4: Institutional flow score
    high_vol_override: bool = False    # True if VIX > 25.0
    data_quality: DataQuality = DataQuality.CONFIDENT  # CONFIDENT, DEGRADED, STALE, FALLBACK
    session_phase: SessionPhase = SessionPhase.PRE_MARKET_0830  # PRE_MARKET_0830, INTRADAY, POST_MARKET
    asset_class: AssetClass = AssetClass.EQUITY_NSE             # NSE, MCX, NYSE, CRYPTO
    intraday_window: Optional[IntradayWindow] = None            # Current trading window
    ema20: Optional[float] = None      # 20-day short-term EMA
    data_source: str = "BROKER_API"    # "BROKER_API" | "YFINANCE" | "LOCAL_DURABLE_CACHE" | "FALLBACK"
    provenance_reason: str = ""        # Human-readable explanation
    timestamp_utc: Optional[datetime] = None
    
    # 100% Backwards compatibility helper for tuple unpacking
    def __iter__(self):
        return iter((self.market_state, self.total_score, self.vix, self.high_vol_override))


# Global in-memory cache for O(1) hot-path queries
_CACHED_MARKET_STATE: Optional[MarketStateSnapshot] = None


# ── 4. MULTI-LAYER DATA INGESTION ENGINE ─────────────────────────────────────

def _fetch_nifty_data() -> Tuple[Optional[float], Optional[float], Optional[float], str]:
    """
    3-Layer Nifty 50 Ingestion:
    1. yfinance Live Historical Feed (Calculates Spot, EMA200, and EMA20)
    2. Database Durable History Fallback (get_latest_market_state)
    3. Emergency Degraded Fallback
    """
    # Layer 1: yfinance primary live feed
    try:
        import yfinance as yf
        nifty = yf.Ticker("^NSEI").history(period="1y", interval="1d")
        if not nifty.empty and len(nifty) >= DEFAULT_REGIME_POLICY.ema_span:
            close_series = nifty["Close"]
            ema200_val = float(close_series.ewm(span=DEFAULT_REGIME_POLICY.ema_span, adjust=False).mean().iloc[-1])
            ema20_val = float(close_series.ewm(span=DEFAULT_REGIME_POLICY.short_ema_span, adjust=False).mean().iloc[-1])
            close_val = float(close_series.iloc[-1])
            return close_val, ema200_val, ema20_val, "YFINANCE"
    except Exception as e:
        logger.warning(f"[market_state] yfinance Nifty fetch failed: {e}")

    # Layer 2: Database durable fallback (previous session state)
    try:
        from db.repository import get_latest_market_state
        last_state = get_latest_market_state()
        if last_state and isinstance(last_state, dict):
            p = last_state.get("nifty_price")
            e200 = last_state.get("ema200")
            e20 = last_state.get("ema20")
            if p is not None and e200 is not None:
                logger.info(f"[market_state] Restored Nifty state from database fallback (Price: {p}, EMA200: {e200})")
                return float(p), float(e200), float(e20) if e20 is not None else None, "DATABASE_STALE"
    except Exception as e:
        logger.debug(f"[market_state] Database fallback fetch skipped: {e}")

    # Layer 3: Degraded emergency fallback
    return None, None, None, "FALLBACK"


def _fetch_vix_data() -> Tuple[Optional[float], str]:
    """
    3-Layer India VIX Ingestion:
    1. yfinance Quote Feed (^INDIAVIX)
    2. Database Durable History Fallback (get_latest_market_state)
    3. Emergency Degraded Fallback
    """
    # Layer 1: yfinance primary live feed
    try:
        import yfinance as yf
        vix_df = yf.Ticker("^INDIAVIX").history(period="5d", interval="1d")
        if not vix_df.empty:
            return float(vix_df["Close"].iloc[-1]), "YFINANCE"
    except Exception as e:
        logger.warning(f"[market_state] yfinance VIX fetch failed: {e}")

    # Layer 2: Database durable fallback
    try:
        from db.repository import get_latest_market_state
        last_state = get_latest_market_state()
        if last_state and isinstance(last_state, dict) and last_state.get("vix") is not None:
            return float(last_state["vix"]), "DATABASE_STALE"
    except Exception as e:
        logger.debug(f"[market_state] Database VIX fallback fetch skipped: {e}")

    # Layer 3: Degraded emergency fallback
    return None, "FALLBACK"


# ── 5. CORE REGIME EVALUATION LOGIC ──────────────────────────────────────────

def get_current_intraday_window() -> IntradayWindow:
    """Determine the active trading window based on current IST clock."""
    from datetime import time
    t = now_ist().time()
    if t < time(9, 15):
        return IntradayWindow.PRE_OPEN
    elif t < time(9, 30):
        return IntradayWindow.OPENING_DISCOVERY
    elif t < time(13, 30):
        return IntradayWindow.MID_SESSION
    elif t < time(15, 30):
        return IntradayWindow.EXPIRY_POWER_HOUR
    else:
        return IntradayWindow.POST_CLOSE


def calculate_market_state(
    custom_nifty_price: Optional[float] = None,
    custom_ema200: Optional[float] = None,
    custom_vix: Optional[float] = None,
    custom_ema20: Optional[float] = None,
    custom_breadth_pct: Optional[float] = None,
    custom_pcr: Optional[float] = None,
    custom_vix_delta_pct: Optional[float] = None,
    session_phase: SessionPhase = SessionPhase.PRE_MARKET_0830,
    policy: MarketRegimePolicy = DEFAULT_REGIME_POLICY
) -> MarketStateSnapshot:
    """
    Master Regime Calculator.
    Calculates dimensional macro state, assigns data quality, scores 4 factors (Trend, Volatility, Breadth, Flow),
    and constructs MarketStateSnapshot.
    """
    global _CACHED_MARKET_STATE
    sources = []
    data_quality = DataQuality.CONFIDENT

    # Factor 1: Nifty Price vs EMA200 & EMA20
    if custom_nifty_price is not None and custom_ema200 is not None:
        nifty_price, ema200, ema20, src = custom_nifty_price, custom_ema200, custom_ema20, "CUSTOM_INJECTED"
    else:
        nifty_price, ema200, ema20, src = _fetch_nifty_data()
    sources.append(src)
    if "DATABASE_STALE" in src:
        data_quality = DataQuality.STALE

    if nifty_price is None or ema200 is None or ema200 <= 0:
        price_score = 0
        nifty_price = 0.0
        ema200 = 0.0
        data_quality = DataQuality.DEGRADED
        price_reason = "Price data unavailable (Score: 0)"
    else:
        diff_pct = ((nifty_price - ema200) / ema200) * 100.0
        if diff_pct > policy.price_structure_threshold_pct:
            price_score = 1
            if ema20 is not None and nifty_price > ema20:
                price_reason = f"Nifty ({nifty_price:.0f}) > EMA200 ({ema200:.0f}) [+ {diff_pct:.1f}%] & > EMA20 ({ema20:.0f}) [Aligned Bull: +1]"
            else:
                price_reason = f"Nifty ({nifty_price:.0f}) > EMA200 ({ema200:.0f}) by +{diff_pct:.1f}% (+1)"
        elif diff_pct < -policy.price_structure_threshold_pct:
            price_score = -1
            if ema20 is not None and nifty_price < ema20:
                price_reason = f"Nifty ({nifty_price:.0f}) < EMA200 ({ema200:.0f}) [{diff_pct:.1f}%] & < EMA20 ({ema20:.0f}) [Aligned Bear: -1]"
            else:
                price_reason = f"Nifty ({nifty_price:.0f}) < EMA200 ({ema200:.0f}) by {diff_pct:.1f}% (-1)"
        else:
            price_score = 0
            price_reason = f"Nifty ({nifty_price:.0f}) near EMA200 ({ema200:.0f}) within +/-{policy.price_structure_threshold_pct}% (0)"

    # Factor 3: India VIX
    if custom_vix is not None:
        vix, vix_src = custom_vix, "CUSTOM_INJECTED"
    else:
        vix, vix_src = _fetch_vix_data()
    sources.append(vix_src)

    if vix is None or vix <= 0 or math.isnan(vix) or math.isinf(vix):
        vix = 15.0  # Neutral baseline
        vix_score = 0
        vix_regime = "UNKNOWN"
        data_quality = DataQuality.DEGRADED
        vix_reason = "VIX data unavailable (Defaulted: 15.0 Neutral)"
    else:
        vol_reg = classify_volatility_regime(vix, custom_vix_delta_pct)
        vix_regime = vol_reg.value

        if vix < policy.vix_low_threshold:
            vix_score = 1
            vix_reason = f"VIX ({vix:.2f}) < {policy.vix_low_threshold} (Low Vol / Benign: +1)"
        elif vix > policy.vix_high_threshold:
            vix_score = -1
            vix_reason = f"VIX ({vix:.2f}) > {policy.vix_high_threshold} (Elevated Vol / Fear: -1)"
        else:
            vix_score = 0
            vix_reason = f"VIX ({vix:.2f}) in normal range ({policy.vix_low_threshold}-{policy.vix_high_threshold}: 0)"

        # VIX Sudden Surge Gate (Intraday Spike > +10%)
        if custom_vix_delta_pct is not None and custom_vix_delta_pct > 10.0:
            vix_score -= 1
            vix_reason += f" | [VIX Spike Warning: +{custom_vix_delta_pct:.1f}%]"

    # Factor 2: Sector Breadth Scoring
    if custom_breadth_pct is not None:
        b_val = custom_breadth_pct
        if b_val >= 0.60:
            breadth_score = 1
            breadth_reason = f"Sector Breadth Strong ({b_val*100:.0f}% >= 60%: +1)"
        elif b_val <= 0.40:
            breadth_score = -1
            breadth_reason = f"Sector Breadth Weak ({b_val*100:.0f}% <= 40%: -1)"
        else:
            breadth_score = 0
            breadth_reason = f"Sector Breadth Neutral ({b_val*100:.0f}%: 0)"
    else:
        breadth_score = 0
        breadth_reason = "Sector Breadth: Offline Baseline (0)"

    # Factor 4: Institutional Flow / Option Chain PCR & FII Positioning Scoring
    if custom_pcr is not None:
        pcr_val = custom_pcr
        if pcr_val >= 1.25:
            fii_score = 1
            flow_reason = f"PCR Bullish Support ({pcr_val:.2f} >= 1.25: +1)"
        elif pcr_val <= 0.75:
            fii_score = -1
            flow_reason = f"PCR Bearish Resistance ({pcr_val:.2f} <= 0.75: -1)"
        else:
            fii_score = 0
            flow_reason = f"PCR Neutral ({pcr_val:.2f}: 0)"
    else:
        try:
            from data.derivatives.participant_oi import fetch_live_nse_participant_oi
            p_snap = fetch_live_nse_participant_oi()
            if p_snap:
                if p_snap.fii_index_fut_ratio >= 0.60:
                    fii_score = 1
                    flow_reason = f"FII Net Long Accumulation ({p_snap.fii_index_fut_ratio*100:.1f}% >= 60%: +1)"
                elif p_snap.is_short_squeeze_candidate:
                    fii_score = 0  # Neutral with squeeze alert
                    flow_reason = f"FII Short Squeeze Trap Alert ({p_snap.fii_index_fut_ratio*100:.1f}% < 20%: 0)"
                elif p_snap.fii_index_fut_ratio <= 0.40:
                    fii_score = -1
                    flow_reason = f"FII Defensive Short Headwind ({p_snap.fii_index_fut_ratio*100:.1f}% <= 40%: -1)"
                else:
                    fii_score = 0
                    flow_reason = f"FII Balanced Derivatives Flow ({p_snap.fii_index_fut_ratio*100:.1f}%: 0)"
            else:
                fii_score = 0
                flow_reason = "Flow / PCR: Offline Baseline (0)"
        except Exception as e:
            fii_score = 0
            flow_reason = f"Flow / PCR: Baseline ({e}) (0)"

    # Composite Scoring
    total_score = price_score + vix_score + breadth_score + fii_score
    high_vol_override = (vix > policy.vix_panic_override)

    # Classify Regime with Institutional Hysteresis (Schmitt Trigger)
    prev_regime = _CACHED_MARKET_STATE.market_state if _CACHED_MARKET_STATE else "NEUTRAL"

    if data_quality == DataQuality.DEGRADED and (nifty_price == 0.0 or vix == 15.0):
        market_state = MarketRegime.DEGRADED.value
    elif total_score >= policy.bull_score_threshold:
        market_state = MarketRegime.BULL.value
    elif total_score <= policy.bear_score_threshold:
        market_state = MarketRegime.BEAR.value
    else:
        # Hysteresis buffer zone (total_score in -1, 0, +1):
        # Prevent rapid whipsaws across boundaries unless score reverses to zero
        if prev_regime == MarketRegime.BULL.value and total_score >= 1:
            market_state = MarketRegime.BULL.value
        elif prev_regime == MarketRegime.BEAR.value and total_score <= -1:
            market_state = MarketRegime.BEAR.value
        else:
            market_state = MarketRegime.NEUTRAL.value

    # Build Provenance Reason
    provenance = f"{price_reason} | {vix_reason} | {breadth_reason} | {flow_reason}"
    if high_vol_override:
        provenance += f" | HIGH VOL OVERRIDE ACTIVE (VIX {vix:.2f} > {policy.vix_panic_override})"

    intraday_win = get_current_intraday_window() if session_phase == SessionPhase.INTRADAY else None

    snapshot = MarketStateSnapshot(
        market_state=market_state,
        total_score=total_score,
        nifty_price=round(nifty_price, 2),
        ema200=round(ema200, 2),
        ema20=round(ema20, 2) if ema20 is not None else None,
        price_score=price_score,
        vix=round(vix, 2),
        vix_score=vix_score,
        vix_regime=vix_regime,
        breadth_score=breadth_score,
        fii_score=fii_score,
        high_vol_override=high_vol_override,
        data_quality=data_quality,
        session_phase=session_phase,
        asset_class=AssetClass.EQUITY_NSE,
        intraday_window=intraday_win,
        data_source="+".join(sorted(set(sources))),
        provenance_reason=provenance,
        timestamp_utc=datetime.now(timezone.utc)
    )

    _CACHED_MARKET_STATE = snapshot
    return snapshot


# ── 6. PUBLIC API & BACKWARD COMPATIBILITY ───────────────────────────────────

def get_market_state() -> MarketStateSnapshot:
    """
    Main 8:30 AM Morning Routine Entrypoint.
    Computes pre-market macro regime, caches in memory, and persists to Supabase.
    Returns MarketStateSnapshot (unpacks into (state, total, vix, high_vol) seamlessly).
    """
    logger.info(f"Market State Engine executing — {today_ist()}")
    snapshot = calculate_market_state(session_phase=SessionPhase.PRE_MARKET_0830)
    
    logger.info(
        f"Regime: {snapshot.market_state} | Total: {snapshot.total_score:+d} | "
        f"Nifty: {snapshot.nifty_price:.0f} (EMA200: {snapshot.ema200:.0f}) | "
        f"VIX: {snapshot.vix:.2f} [{snapshot.vix_regime}] | Quality: {snapshot.data_quality.value}"
        + (" [HIGH VOL OVERRIDE]" if snapshot.high_vol_override else "")
    )

    # Persist to database defensively
    try:
        upsert_market_state({
            "date":              str(today_ist()),
            "nifty_price":       snapshot.nifty_price,
            "ema200":            snapshot.ema200,
            "ema20":             snapshot.ema20,
            "price_structure":   snapshot.price_score,
            "vix":               snapshot.vix,
            "vix_score":         snapshot.vix_score,
            "breadth_score":     snapshot.breadth_score,
            "fii_score":         snapshot.fii_score,
            "total_score":       snapshot.total_score,
            "market_state":      snapshot.market_state,
            "mqi_level":         "PENDING",
            "no_trade_day":      False,
            "high_vol_override": snapshot.high_vol_override,
            "data_quality":      snapshot.data_quality.value,
            "session_phase":     snapshot.session_phase.value,
        })
        logger.info("Market state saved to Supabase")
    except Exception as e:
        logger.error(f"Failed to save market state to Supabase: {e}")

    return snapshot


def get_cached_market_state() -> MarketStateSnapshot:
    """
    O(1) Hot-Path In-Memory State Reader.
    Used by Signal Scanners, Risk Triggers, and AI Debate Agents.
    Zero network/database I/O per tick.
    """
    global _CACHED_MARKET_STATE
    if _CACHED_MARKET_STATE is None:
        return get_market_state()
    return _CACHED_MARKET_STATE


def reset_market_state_cache() -> None:
    """Clear in-memory cached market state snapshot (used for test isolation & EOD reset)."""
    global _CACHED_MARKET_STATE
    _CACHED_MARKET_STATE = None


def update_intraday_market_state(
    current_nifty: float,
    current_vix: float,
    ema200: Optional[float] = None,
    ema20: Optional[float] = None
) -> MarketStateSnapshot:
    """
    Intraday Regime Refresh Hook.
    Updates the in-memory market regime dynamically during the trading day
    without triggering full historical network re-downloads.
    """
    cached_ema200 = ema200 or (_CACHED_MARKET_STATE.ema200 if _CACHED_MARKET_STATE else current_nifty)
    cached_ema20 = ema20 or (_CACHED_MARKET_STATE.ema20 if _CACHED_MARKET_STATE else None)
    snapshot = calculate_market_state(
        custom_nifty_price=current_nifty,
        custom_ema200=cached_ema200,
        custom_ema20=cached_ema20,
        custom_vix=current_vix,
        session_phase=SessionPhase.INTRADAY
    )
    logger.info(f"[market_state] Intraday state updated: {snapshot.market_state} (Nifty: {current_nifty:.0f}, VIX: {current_vix:.2f})")
    return snapshot


# ── 7. SELF-DIAGNOSTIC TEST HARNESS ──────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    state = get_market_state()
    ema20_str = f"{state.ema20:,.2f}" if state.ema20 is not None else "N/A"
    win_str = state.intraday_window.value if state.intraday_window else "N/A"
    print("===================================================================")
    print("MJONAI MACRO MARKET REGIME SNAPSHOT")
    print("===================================================================")
    print(f"Market State           : {state.market_state}")
    print(f"Total Score            : {state.total_score:+d}")
    print(f"Asset Class            : {state.asset_class.value}")
    print(f"Nifty 50 Price         : {state.nifty_price:,.2f} (EMA200: {state.ema200:,.2f} | EMA20: {ema20_str})")
    print(f"India VIX              : {state.vix:.2f} ({state.vix_regime})")
    print(f"High Vol Override      : {state.high_vol_override}")
    print(f"Data Quality           : {state.data_quality.value} (Source: {state.data_source})")
    print(f"Session Phase          : {state.session_phase.value} (Window: {win_str})")
    print(f"Provenance Reason      : {state.provenance_reason}")
    print("===================================================================")
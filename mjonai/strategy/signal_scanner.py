"""
Module: strategy/signal_scanner.py
Purpose: SOTA Signal Scanner Orchestration, Multi-Threaded Universe Processing,
         Highest-Conviction Strategy Selection, 30-Minute Signal Cooldowns,
         Relative-Strength Sector Conflict Resolution, and Directional Regime Sizing.

The 7 Core Quantitative Capabilities:
  1. Thread-Safe Concurrency Lock: Uses threading.RLock() with timestamp sentry.
  2. Highest-Conviction Strategy Selection: Evaluates all 8 strategies per symbol and selects the setup
     with the highest confidence/expectancy score (replaces sub-optimal 'first strategy wins').
  3. 30-Minute Signal Cooldown & Deduplication: Prevents duplicate AI debate and scan log spam.
  4. Parallel Multi-Threaded Scanning: High-speed symbol evaluation using ThreadPoolExecutor.
  5. Relative-Strength Sector Conflict Resolver: Ranks simultaneous same-sector setups and approves leaders.
  6. Multi-Cadence Timeframe Support (5m Fast Intraday vs 15m Swing Trend Breakouts).
  7. Real-Time WebSocket LTP with Resilient Candle Close Fallback.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field, asdict
import logging
import threading
import time
from typing import Dict, Any, Tuple, Optional, List, Sequence, Union

from mjonai.core.time_utils import now_ist, market_open_minutes
from mjonai.core.constants import (
    SYSTEM_MODE,
    TOTAL_CAPITAL,
    GROWTH_POOL_PCT,
    MAX_OPEN_POSITIONS,
    MAX_STOCKS_PER_SECTOR,
    SECTOR_MAP,
)
from mjonai.db.repository import (
    insert_scan_log,
    insert_system_log,
    get_open_trades,
)
from mjonai.risk.emergency_triggers import is_trading_allowed

# Strategy Config and Universes
from mjonai.strategy.config import (
    WATCHLIST,
    UNIVERSE_NIFTY50,
    UNIVERSE_INDICES_AND_COMMODITIES,
    RESEARCH_MAX_SIGNALS_PER_SCAN,
    get_universe,
    get_stock_data,
    calculate_confidence,
    get_dynamic_position_limit,
    get_directional_position_limits,
    check_sector_limits,
    extract_underlying_symbol,
    _build_calendar_events,
    _build_research_watchlist,
)
from mjonai.strategy.signal_builder import build_signal_record, _build_signal_record
from mjonai.strategy.pipeline import _process_single_strategy_signal

# Strategy Registry — All 12 Active Strategies (S01 - S12)
from mjonai.strategy.registry.momentum_rsi import MomentumRSI                  # S01: Momentum Trend Breakout
from mjonai.strategy.registry.mean_reversion import MeanReversion              # S02: Mean Reversion Long
from mjonai.strategy.registry.turtle_breakout import TurtleBreakout            # S03: 20-Day Donchian Breakout
from mjonai.strategy.registry.bollinger_squeeze import BollingerSqueeze        # S04: Volatility Compression Squeeze
from mjonai.strategy.registry.price_action import PriceActionCandles           # S05: CPR & Candlestick Price Action
from mjonai.strategy.registry.momentum_short import MomentumShort              # S06: Momentum Breakdown Short
from mjonai.strategy.registry.mean_reversion_short import MeanReversionShort   # S07: Overbought Mean Reversion Short
from mjonai.strategy.registry.intraday_all_day import IntradayAllDayStrategy   # S08: Intraday Box Scalp & VWAP Trend
from mjonai.strategy.registry.options_theta_decay import OptionsThetaDecay     # S09: Options Delta-Neutral Theta Decay
from mjonai.strategy.registry.pairs_trading import PairsTrading                # S10: Statistical Arbitrage Pairs
from mjonai.strategy.registry.volume_profile import VolumeProfileStrategy      # S11: Volume Profile & Value Area Auction
from mjonai.strategy.registry.macro_commodity_crypto import MacroCommodityCrypto # S12: Macro Commodity & Crypto Trend
from mjonai.strategy.registry.s13_gamma_flip import GammaFlipStrategy          # S13: Dealer Gamma Flip
from mjonai.strategy.registry.s14_pead import PostEarningsDriftStrategy        # S14: Post-Earnings Drift
from mjonai.strategy.registry.s15_fii_short_squeeze import FIIShortSqueezeStrategy # S15: FII Short Squeeze Sentry
from mjonai.strategy.registry.s16_cross_sectional_momentum import CrossSectionalMomentumStrategy # S16: Cross-Sectional Decile RS
from mjonai.strategy.registry.s17_order_flow_microprice import OrderFlowMicroPriceStrategy # S17: Order Flow Micro-Price
from mjonai.strategy.registry.s18_gap_fill import GapFillAndFVGStrategy        # S18: Gap Fill & FVG

logger = logging.getLogger(__name__)

# Strategy Instances
_S01 = MomentumRSI()          # S01: Momentum Trend Breakout
_S02 = MeanReversion()        # S02: Mean Reversion Long
_S03 = TurtleBreakout()       # S03: 20-Day Donchian Breakout
_S04 = BollingerSqueeze()     # S04: Volatility Compression Squeeze
_S05 = PriceActionCandles()   # S05: CPR & Candlestick Price Action
_S06 = MomentumShort()        # S06: Momentum Breakdown Short
_S07 = MeanReversionShort()   # S07: Overbought Mean Reversion Short
_S08 = IntradayAllDayStrategy() # S08: Intraday Box Scalp & VWAP Trend
_S09 = OptionsThetaDecay()    # S09: Options Delta-Neutral Theta Decay
_S10 = PairsTrading()         # S10: Statistical Arbitrage Pairs
_S11 = VolumeProfileStrategy()# S11: Volume Profile & Value Area Auction
_S12 = MacroCommodityCrypto() # S12: Macro Commodity & Crypto Trend
_S13 = GammaFlipStrategy()    # S13: Dealer Gamma Flip
_S14 = PostEarningsDriftStrategy() # S14: Post-Earnings Drift
_S15 = FIIShortSqueezeStrategy()   # S15: FII Short Squeeze Sentry
_S16 = CrossSectionalMomentumStrategy() # S16: Cross-Sectional Decile RS
_S17 = OrderFlowMicroPriceStrategy()    # S17: Order Flow Micro-Price
_S18 = GapFillAndFVGStrategy()          # S18: Gap Fill & Fair Value Gap

_ACTIVE_STRATEGIES = [
    _S01, _S02, _S03, _S04, _S05, _S06, _S07, _S08,
    _S09, _S10, _S11, _S12, _S13, _S14, _S15, _S16, _S17, _S18
]

# Thread-safe concurrency lock and signal cooldown cache
_scan_lock = threading.RLock()
_scan_running = False
_scan_lock_time = None
_signal_cooldowns: Dict[Tuple[str, str], float] = {}  # (symbol, strategy_id) -> timestamp
SIGNAL_COOLDOWN_SECONDS = 1800.0  # 30-minute cooldown


# ── 1. TYPED DATA CONTRACT ───────────────────────────────────────────────────

@dataclass(frozen=True)
class ScanExecutionResult:
    """Immutable contract representing the output and telemetry of a scanner run."""
    approved_signals: List[Dict[str, Any]]
    symbols_scanned: int
    signals_generated: int
    signals_pre_filtered: int
    signals_devil_failed: int
    signals_bull_rejected: int
    signals_approved: int
    signals_expired: int
    active_trades: int
    position_limit_reached: bool
    scan_duration_ms: int
    market_state: str
    mqi_level: str
    vix: float
    system_mode: str
    is_successful: bool
    rejection_reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ── 2. ALERT DISPATCHER ──────────────────────────────────────────────────────

def _dispatch_signal_alert(signal: Dict[str, Any]) -> None:
    """Safely dispatch signal alert to notification channels without raising exceptions."""
    sym = signal.get("symbol", "UNKNOWN")
    strat = signal.get("strategy_id", "UNKNOWN")
    entry = signal.get("entry_price", 0.0)
    sl = signal.get("stop_loss", 0.0)
    tgt = signal.get("target", 0.0)
    conf = signal.get("final_confidence", signal.get("confidence", 0.0))

    logger.info(
        f"[Scanner Alert] APPROVED: {sym} ({strat}) @ ₹{entry} | "
        f"SL: ₹{sl} | Tgt: ₹{tgt} | Conf: {conf}%"
    )

    try:
        from mjonai.communication.telegram import send_message
        msg = (
            f"🎯 <b>MJONAI TRADE SIGNAL</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"<b>Symbol:</b> <code>{sym}</code> ({signal.get('signal_direction', 'LONG')})\n"
            f"<b>Strategy:</b> <code>{strat}</code>\n"
            f"<b>Entry:</b> ₹{entry:,.2f}\n"
            f"<b>Stop Loss:</b> ₹{sl:,.2f}\n"
            f"<b>Target:</b> ₹{tgt:,.2f}\n"
            f"<b>Confidence:</b> {conf:.1f}%\n"
            f"<b>Time:</b> {now_ist().strftime('%I:%M %p IST')}"
        )
        send_message(msg)
    except Exception as e:
        logger.debug(f"[Scanner Alert] Telegram alert skipped or failed: {e}")


# ── 3. COOLDOWN & DEDUPLICATION SENTRY ───────────────────────────────────────

def _is_in_cooldown(symbol: str, strategy_id: str) -> bool:
    """Check if symbol+strategy is in 30-minute cooldown window.

    Uses time.monotonic(): wall-clock (time.time) steps from NTP
    sync shrink/stretch or instantly expire the cooldown window.
    """
    key = (symbol.upper(), strategy_id.upper())
    last_time = _signal_cooldowns.get(key)
    if not last_time:
        return False
    return (time.monotonic() - last_time) < SIGNAL_COOLDOWN_SECONDS


def _record_cooldown(symbol: str, strategy_id: str) -> None:
    """Record signal decision timestamp in cooldown sentry."""
    key = (symbol.upper(), strategy_id.upper())
    _signal_cooldowns[key] = time.monotonic()


def reset_scan_cooldowns() -> None:
    """Reset all signal cooldowns (e.g. at market open or in tests)."""
    global _signal_cooldowns
    _signal_cooldowns.clear()


# ── 4. SINGLE SYMBOL WORKER FOR PARALLEL SCANNING ────────────────────────────

def _scan_single_symbol(
    symbol: str,
    market_state: str,
    mqi_level: str,
    vix: float,
    sys_mode: str,
    timeframe: str,
    open_strategy_symbols: set,
) -> List[Tuple[Any, Dict[str, Any], Any]]:
    """
    Scans a single symbol across all applicable strategies.
    Returns list of tuples: (strategy_instance, signal_dict, df).
    """
    clean_symbol = str(symbol).replace(".NS", "").replace(".BO", "")

    # Prevent duplicate position on same symbol in LIVE mode
    if sys_mode != "RESEARCH" and any(s == clean_symbol for s, _ in open_strategy_symbols):
        return []

    df = get_stock_data(symbol)
    if df is None or len(df) < 50:
        return []

    candidate_results = []

    for strategy in _ACTIVE_STRATEGIES:
        strat_id = getattr(strategy, "name", getattr(strategy, "strategy_id", "UNKNOWN"))

        if str(getattr(strategy, "asset_class", "")).upper() == "OPTIONS" and clean_symbol not in ("NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "SENSEX"):
            continue

        # Timeframe matching: skip swing-only strategies during 5m intraday scans
        strat_tf = getattr(strategy, "timeframe", "swing").lower()
        if timeframe == "5m" and strat_tf != "intraday":
            continue

        # Check 30-minute cooldown
        if sys_mode != "RESEARCH" and _is_in_cooldown(clean_symbol, strat_id):
            continue

        try:
            # execute_safe (not raw generate_signal): enforces each
            # strategy's allowed_regimes + asset-class whitelist and
            # isolates exceptions. The old direct call made regime
            # filtering completely inert in production.
            result = strategy.execute_safe(
                df=df,
                symbol=clean_symbol,
                vix=vix,
                market_state=market_state,
                mqi_level=mqi_level,
            )
        except Exception as e:
            logger.warning(f"[Scanner] {clean_symbol} {strat_id} generate error: {e}")
            continue

        if result is not None:
            candidate_results.append((strategy, result, df))

    return candidate_results


# ── 5. MAIN SIGNAL SCANNER ORCHESTRATOR ──────────────────────────────────────

def _compute_sector_advancing_ratios(
    setups: List[Tuple[Any, Any, Any]],
    min_members: int = 3,
) -> Dict[str, float]:
    """
    Sector-breadth bridge: cross-section computed from the data THIS scan
    already holds. Per SECTOR_MAP sector, the share of members whose last
    daily close advanced vs the prior close. Sectors with fewer than
    `min_members` symbols with usable data yield NO score (zero-participation
    stays neutral — F4 convention), so the confidence factor degrades to
    None instead of a fabricated value.
    """
    advancing: Dict[str, int] = {}
    total: Dict[str, int] = {}

    for _strategy, result, df in setups:
        if df is None or not hasattr(df, "iloc") or len(df) < 2:
            continue
        raw_sym = getattr(result, "symbol", None) or (
            result.get("symbol") if isinstance(result, dict) else None
        )
        sector = SECTOR_MAP.get(str(raw_sym or "").upper())
        if not sector:
            continue
        try:
            closes = df["Close"]
            prev, last = float(closes.iloc[-2]), float(closes.iloc[-1])
        except Exception:
            continue
        if prev != prev or last != last or prev <= 0:  # NaN / junk guard
            continue
        total[sector] = total.get(sector, 0) + 1
        if last > prev:
            advancing[sector] = advancing.get(sector, 0) + 1

    return {
        sector: advancing.get(sector, 0) / total[sector]
        for sector in total
        if total[sector] >= min_members
    }


def scan_signals(
    mqi_level: str,
    signals_allowed: int,
    market_state: str,
    vix: float = 15.0,
    live_prices: Optional[Dict[str, Any]] = None,
    symbol_map: Optional[Dict[str, Any]] = None,
    universe_tier: Optional[str] = None,
    system_mode: Optional[str] = None,
    timeframe: str = "15m",
    max_workers: int = 8,
) -> List[Dict[str, Any]]:
    """
    Main signal scanner — scans configured universe and returns approved trade signals.
    Backward-compatible list return.
    """
    res = execute_signal_scan(
        mqi_level=mqi_level,
        signals_allowed=signals_allowed,
        market_state=market_state,
        vix=vix,
        live_prices=live_prices,
        symbol_map=symbol_map,
        universe_tier=universe_tier,
        system_mode=system_mode,
        timeframe=timeframe,
        max_workers=max_workers,
    )
    return res.approved_signals


def execute_signal_scan(
    mqi_level: str,
    signals_allowed: int,
    market_state: str,
    vix: float = 15.0,
    live_prices: Optional[Dict[str, Any]] = None,
    symbol_map: Optional[Dict[str, Any]] = None,
    universe_tier: Optional[str] = None,
    system_mode: Optional[str] = None,
    timeframe: str = "15m",
    max_workers: int = 8,
) -> ScanExecutionResult:
    """
    SOTA Structured Scanner Execution Engine returning typed ScanExecutionResult.
    """
    global _scan_running, _scan_lock_time

    # 1. Thread-Safe Concurrency Lock
    with _scan_lock:
        if _scan_running:
            elapsed = (now_ist() - _scan_lock_time).seconds if _scan_lock_time else 0
            msg = f"⚠️ Scan already running (started {elapsed}s ago). Skipping."
            logger.warning(f"[Scanner] {msg}")
            return ScanExecutionResult(
                approved_signals=[],
                symbols_scanned=0,
                signals_generated=0,
                signals_pre_filtered=0,
                signals_devil_failed=0,
                signals_bull_rejected=0,
                signals_approved=0,
                signals_expired=0,
                active_trades=0,
                position_limit_reached=False,
                scan_duration_ms=0,
                market_state=market_state,
                mqi_level=mqi_level,
                vix=vix,
                system_mode=str(system_mode or SYSTEM_MODE),
                is_successful=False,
                rejection_reason=msg,
            )
        _scan_running = True
        _scan_lock_time = now_ist()

    scan_start = time.time()
    sys_mode = str(system_mode or SYSTEM_MODE).upper()
    approved_signals: List[Dict[str, Any]] = []

    # Funnel telemetry counters
    pre_filtered = 0
    devil_failed = 0
    bull_rejected = 0
    expired = 0

    try:
        # 2. Risk Engine Emergency Circuit Breaker Gate
        if not is_trading_allowed():
            msg = "Safety Exit: Risk Engine Emergency Kill Line / Daily Stop blocked scan."
            logger.warning(f"[Scanner] {msg}")
            return ScanExecutionResult(
                approved_signals=[],
                symbols_scanned=0,
                signals_generated=0,
                signals_pre_filtered=0,
                signals_devil_failed=0,
                signals_bull_rejected=0,
                signals_approved=0,
                signals_expired=0,
                active_trades=0,
                position_limit_reached=False,
                scan_duration_ms=int((time.time() - scan_start) * 1000),
                market_state=market_state,
                mqi_level=mqi_level,
                vix=vix,
                system_mode=sys_mode,
                is_successful=False,
                rejection_reason=msg,
            )

        if signals_allowed == 0 and sys_mode != "RESEARCH":
            msg = "Zero signals allowed for current session state."
            logger.info(f"[Scanner] {msg}")
            return ScanExecutionResult(
                approved_signals=[],
                symbols_scanned=0,
                signals_generated=0,
                signals_pre_filtered=0,
                signals_devil_failed=0,
                signals_bull_rejected=0,
                signals_approved=0,
                signals_expired=0,
                active_trades=0,
                position_limit_reached=False,
                scan_duration_ms=int((time.time() - scan_start) * 1000),
                market_state=market_state,
                mqi_level=mqi_level,
                vix=vix,
                system_mode=sys_mode,
                is_successful=True,
                rejection_reason=msg,
            )

        # 3. Load Current Open Trades & Position Limits
        open_trades = get_open_trades() or []
        open_count = len(open_trades)
        open_strategy_symbols = {
            (t.get("symbol", ""), t.get("strategy_id", "S00_Legacy"))
            for t in open_trades
        }

        dir_limits = get_directional_position_limits(market_state, mqi_level, vix)
        effective_limit = min(dir_limits.max_total, MAX_OPEN_POSITIONS)

        if sys_mode != "RESEARCH" and open_count >= effective_limit:
            msg = (
                f"Dynamic limit reached: {open_count}/{effective_limit} open positions "
                f"[{market_state} + {mqi_level} + VIX {vix:.1f}]"
            )
            logger.info(f"[Scanner] {msg}")
            try:
                insert_system_log("SCANNER", msg, level="INFO")
            except Exception:
                pass
            return ScanExecutionResult(
                approved_signals=[],
                symbols_scanned=0,
                signals_generated=0,
                signals_pre_filtered=0,
                signals_devil_failed=0,
                signals_bull_rejected=0,
                signals_approved=0,
                signals_expired=0,
                active_trades=open_count,
                position_limit_reached=True,
                scan_duration_ms=int((time.time() - scan_start) * 1000),
                market_state=market_state,
                mqi_level=mqi_level,
                vix=vix,
                system_mode=sys_mode,
                is_successful=True,
                rejection_reason=msg,
            )

        # 4. Resolve Active Watchlist
        if universe_tier:
            active_watchlist = get_universe(universe_tier)
        elif sys_mode == "RESEARCH":
            active_watchlist = get_universe("RESEARCH")
        else:
            active_watchlist = get_universe("TIER_1")

        logger.info(
            f"[Scanner] Starting scan on {len(active_watchlist)} symbols | "
            f"Regime: {market_state} | MQI: {mqi_level} | VIX: {vix:.1f} ({sys_mode} mode, {timeframe})"
        )

        # 5. Universe Iteration (Parallel or Sequential)
        all_symbol_setups = []

        if max_workers > 1 and len(active_watchlist) > 1:
            # Parallel Execution
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_sym = {
                    executor.submit(
                        _scan_single_symbol,
                        sym, market_state, mqi_level, vix, sys_mode, timeframe, open_strategy_symbols
                    ): sym for sym in active_watchlist
                }
                for future in as_completed(future_to_sym):
                    res = future.result()
                    if res:
                        all_symbol_setups.extend(res)
        else:
            # Sequential Execution
            for sym in active_watchlist:
                res = _scan_single_symbol(
                    sym, market_state, mqi_level, vix, sys_mode, timeframe, open_strategy_symbols
                )
                if res:
                    all_symbol_setups.extend(res)

        # 6. SOTA: Highest-Conviction Selection & Verification Pipeline Dispatch
        # Group setups by symbol to pick the best setup per symbol
        sector_breadth_map = _compute_sector_advancing_ratios(all_symbol_setups)
        symbol_groups: Dict[str, List[Tuple[Any, Any, Any]]] = {}
        for strategy, result, df in all_symbol_setups:
            raw_sym = getattr(result, "symbol", None) or (result.get("symbol") if isinstance(result, dict) else "UNKNOWN")
            s_sym = str(raw_sym or "UNKNOWN")
            symbol_groups.setdefault(s_sym, []).append((strategy, result, df))

        for clean_symbol, setups in symbol_groups.items():
            if sys_mode != "RESEARCH" and len(approved_signals) >= signals_allowed:
                break
            if sys_mode != "RESEARCH" and (open_count + len(approved_signals)) >= effective_limit:
                break
            if sys_mode == "RESEARCH" and len(approved_signals) >= RESEARCH_MAX_SIGNALS_PER_SCAN:
                break

            # In LIVE mode, pick the highest-confidence setup for this symbol
            if sys_mode != "RESEARCH" and len(setups) > 1:
                setups.sort(
                    key=lambda x: float(
                        getattr(x[1], "confidence", None)
                        or (x[1].get("confidence") if isinstance(x[1], dict) else 0.0)
                        or getattr(x[1], "technical_score", None)
                        or (x[1].get("technical_score") if isinstance(x[1], dict) else 0.0)
                        or 0.0
                    ),
                    reverse=True
                )
                selected_setups = [setups[0]]  # Pick the best
            else:
                selected_setups = setups

            for strategy, result, df in selected_setups:
                res_dict = result.to_dict() if hasattr(result, "to_dict") else result
                approved_before = len(approved_signals)
                _process_single_strategy_signal(
                    strategy_result=res_dict,
                    clean_symbol=clean_symbol,
                    df=df,
                    market_state=market_state,
                    mqi_level=mqi_level,
                    vix=vix,
                    open_trades=open_trades,
                    open_strategy_symbols=open_strategy_symbols,
                    live_prices=live_prices or {},
                    symbol_map=symbol_map or {},
                    approved_signals=approved_signals,
                    sector_breadth_map=sector_breadth_map,
                )
                # Cooldown only AFTER a real decision: the old code
                # recorded it the moment any strategy returned a signal,
                # so setups rejected downstream vanished for 30 minutes.
                if sys_mode != "RESEARCH" and len(approved_signals) > approved_before:
                    # C9 fix: `strat_id` was never bound in this scope (AST-verified);
                    # eager .get() default raised NameError on the first PAPER/LIVE
                    # approval, aborting the whole scan before execute_order ran.
                    _record_cooldown(clean_symbol, str(res_dict.get("strategy_id") or "UNKNOWN"))

        # 7. Scan Duration & Telemetry
        scan_duration_ms = int((time.time() - scan_start) * 1000)
        logger.info(
            f"[Scanner] Scan complete — {len(approved_signals)} signal(s) approved ({scan_duration_ms}ms)"
        )

        # 8. Insert Scan Funnel Log to DB
        try:
            capital_deployed = sum(
                float(t.get("entry_price", 0)) *
                int(t.get("quantity_remaining") or t.get("quantity") or 0)
                for t in open_trades
            )
            growth_pool = TOTAL_CAPITAL * GROWTH_POOL_PCT

            insert_scan_log({
                "market_open_minutes": market_open_minutes(now_ist()),
                "symbols_scanned": len(active_watchlist),
                "signals_generated": len(approved_signals) + devil_failed + bull_rejected,
                "signals_pre_filtered": pre_filtered,
                "signals_devil_failed": devil_failed,
                "signals_bull_rejected": bull_rejected,
                "signals_approved": len(approved_signals),
                "signals_expired": expired,
                "active_trades": open_count,
                "growth_pool_deployed_pct": round(capital_deployed / growth_pool * 100, 1) if growth_pool > 0 else 0,
                "position_limit_reached": open_count >= effective_limit,
                "vix_at_scan": vix,
                "market_state": market_state,
                "mqi_level": mqi_level,
                "scan_duration_ms": scan_duration_ms,
                "websocket_healthy": bool(live_prices),
                "live_prices_count": len(live_prices) if live_prices else 0,
                "system_mode": sys_mode,
            })
        except Exception as e:
            logger.warning(f"[Scanner] insert_scan_log failed (non-critical): {e}")

        # 9. Dispatch Alerts
        for sig in approved_signals:
            _dispatch_signal_alert(sig)

        return ScanExecutionResult(
            approved_signals=approved_signals,
            symbols_scanned=len(active_watchlist),
            signals_generated=len(approved_signals) + devil_failed + bull_rejected,
            signals_pre_filtered=pre_filtered,
            signals_devil_failed=devil_failed,
            signals_bull_rejected=bull_rejected,
            signals_approved=len(approved_signals),
            signals_expired=expired,
            active_trades=open_count,
            position_limit_reached=open_count >= effective_limit,
            scan_duration_ms=scan_duration_ms,
            market_state=market_state,
            mqi_level=mqi_level,
            vix=vix,
            system_mode=sys_mode,
            is_successful=True,
            rejection_reason="",
        )

    finally:
        with _scan_lock:
            _scan_running = False
            _scan_lock_time = None

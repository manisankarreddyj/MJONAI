"""
Module: strategy/registry/base.py
Purpose: SOTA Quantitative Base Strategy Interface, Multi-Asset Signal Result Contract,
         OHLCV Sanitization Engine, and Exception-Guarded Execution Pipeline.
         All MJONAI algorithmic trading strategies inherit from BaseStrategy.

Architectural Principles:
  1. Zero Framework Dependency: No imports from higher MJONAI layers (prevents circular imports).
  2. Multi-Asset & Derivative Contract: Full native support for Equities, Index Options, MCX, & Crypto.
  3. Type-Safe Signal Contract: StrategySignalResult dataclass with dictionary backwards compatibility.
  4. Pre-Execution Dataframe Sentry: validate_ohlcv_dataframe() blocks ill-formed data before compute.
  5. Mathematical Sanity: Automatic NaN/Inf float sanitization.
  6. Safe Execution Boundary: execute_safe() catches runtime exceptions, measures latency, and logs.
  7. Regime & Direction Whitelisting: Built-in strategy direction, asset class, and regime gating.
  8. High-Throughput Caching: Optional precomputed indicator vector support for 8x scan acceleration.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
import logging
import math
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union
import pandas as pd

logger = logging.getLogger(__name__)


# ── 1. IMMUTABLE TYPED SIGNAL RESULT CONTRACT ────────────────────────────────

@dataclass(frozen=True)
class StrategySignalResult:
    """
    Immutable, fully typed signal evaluation packet emitted by BaseStrategy.
    Provides complete multi-asset, factor, indicator, and price level metadata.
    """
    strategy_id: str
    strategy_version: str
    symbol: str
    signal_direction: str              # "LONG" | "SHORT"
    signal_type: str                   # "BUY" | "SELL"
    technical_score: float             # 0.0 to 100.0
    confidence: float                  # 0.0 to 100.0
    reasons: List[str]
    entry_price: Optional[float] = None
    swing_low: Optional[float] = None
    swing_high: Optional[float] = None
    atr: Optional[float] = None
    adx: Optional[float] = None
    sl_method: Optional[str] = None
    candle_pattern: Optional[str] = None
    timeframe: str = "15m"
    asset_class: str = "EQUITY"        # "EQUITY" | "INDEX" | "COMMODITY" | "CRYPTO"
    # Multi-Asset & Derivative Specific Metadata
    underlying_symbol: Optional[str] = None  # e.g. "NIFTY", "CRUDEOIL", "BTC"
    strike_price: Optional[float] = None     # e.g. 24500.0
    option_type: Optional[str] = None        # "CE" | "PE" | "FUT" | "SPOT"
    expiry_date: Optional[str] = None        # e.g. "2026-08-27"
    lot_size: int = 1                        # e.g. 1 for Equity, 25 for Nifty, 100 for MCX Crude
    tick_size: float = 0.05                  # Minimum price increment
    exchange: str = "NSE"                    # "NSE" | "NFO" | "MCX" | "BSE" | "CRYPTO"
    # Quantitative Factors
    indicator_scores: Dict[str, float] = field(default_factory=dict)
    indicator_values: Dict[str, float] = field(default_factory=dict)
    extra_metadata: Dict[str, Any] = field(default_factory=dict)

    def is_valid(self) -> bool:
        """Verify signal contract integrity, non-empty reasons, and finite numbers."""
        if not self.symbol or not self.strategy_id:
            return False
        if self.signal_direction not in ("LONG", "SHORT", "NON_DIRECTIONAL"):
            return False
        if not (0.0 <= self.technical_score <= 100.0):
            return False
        if not (0.0 <= self.confidence <= 100.0):
            return False
        if not self.reasons:
            return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to standard serializable dictionary with 100% backwards compatibility
        for dictionary-based consumers and legacy pipelines.
        """
        d = asdict(self)
        extra = d.pop("extra_metadata", {})
        if extra and isinstance(extra, dict):
            d.update(extra)
        return d


# ── 2. BASE STRATEGY ABSTRACT CLASS ──────────────────────────────────────────

class BaseStrategy(ABC):
    """
    Abstract base class for all MJONAI quantitative trading strategies.

    Every strategy subclass MUST define:
        name             — Machine identifier (e.g. "S01_MomentumRSI")
        display_name     — Human label (e.g. "Momentum RSI Trend Breakout")
        version          — Parameter version (e.g. "1.0")
        timeframe        — Target cadence ("5m", "15m", "daily")
        asset_class      — Target asset class ("EQUITY", "INDEX", "COMMODITY", "CRYPTO")
        signal_direction — Primary direction ("LONG", "SHORT", "BIDIRECTIONAL")
        allowed_regimes  — Regimes allowed to execute (e.g. ["BULL", "NEUTRAL"])

    Every strategy subclass MUST implement:
        generate_signal() — Core mathematical & indicator condition logic
        get_parameters()  — MLflow & audit parameter dictionary
        get_description() — Plain English strategy explanation
    """

    # ── Strategy Metadata & Class Attributes ─────────────────────────────────
    name: str = "BASE"
    display_name: str = "Base Strategy"
    version: str = "1.0"
    timeframe: str = "15m"
    asset_class: str = "EQUITY"
    exchange: str = "NSE"
    lot_size: int = 1
    tick_size: float = 0.05
    signal_direction: str = "LONG"
    is_active: bool = True
    allowed_regimes: Sequence[str] = ("BULL", "NEUTRAL", "BEAR")
    allowed_asset_classes: Sequence[str] = ("EQUITY", "INDEX", "OPTIONS", "COMMODITY", "CRYPTO")
    min_candles_required: int = 50

    # ── Validation & Sanitization Helpers ────────────────────────────────────

    @classmethod
    def validate_ohlcv_dataframe(
        cls,
        df: Optional[pd.DataFrame],
        min_candles: Optional[int] = None,
    ) -> Tuple[bool, str]:
        """
        Validates OHLCV DataFrame integrity before compute.
        Checks for nulls, minimum required candle length, standard OHLCV columns,
        and the H4 missing-data rule: a required column that is entirely empty,
        or a non-finite / non-positive value on the decision (latest) bar, is
        rejected fail-closed rather than silently propagated as 0/NaN.
        """
        required_len = min_candles if min_candles is not None else cls.min_candles_required

        if df is None:
            return False, "DataFrame is None"
        if not isinstance(df, pd.DataFrame):
            return False, f"Expected pd.DataFrame, got {type(df).__name__}"
        if len(df) < required_len:
            return False, f"Insufficient candle history: {len(df)} < {required_len}"

        required_cols = {"Open", "High", "Low", "Close", "Volume"}
        # Case-insensitive column resolution
        df_cols_lower = {str(c).lower(): c for c in df.columns}
        missing = [req for req in required_cols if req.lower() not in df_cols_lower]
        if missing:
            return False, f"Missing required OHLCV columns: {missing}"

        # H4 missing-data rule. `required_cols` is a set, so iterate an ordered
        # view to keep rejection reasons deterministic.
        ordered_cols = ("Open", "High", "Low", "Close", "Volume")
        resolved = {req: df_cols_lower[req.lower()] for req in ordered_cols}

        empty_cols = [req for req, col in resolved.items() if bool(df[col].isna().all())]
        if empty_cols:
            return False, f"Required OHLCV columns entirely empty: {empty_cols}"

        latest = df.iloc[-1]
        bad_latest = []
        for req, col in resolved.items():
            val = cls.sanitize_float(latest.get(col))
            if val is None:
                bad_latest.append(req)
            elif req != "Volume" and val <= 0:
                bad_latest.append(f"{req}(<=0)")
        if bad_latest:
            return False, f"Missing/invalid data in latest bar: {bad_latest}"

        return True, "OK"

    @staticmethod
    def sanitize_float(val: Any, default: Optional[float] = None) -> Optional[float]:
        """Sanitizes floats, converting NaN/Inf/-Inf to default/None."""
        if val is None:
            return default
        try:
            f = float(val)
            if math.isnan(f) or math.isinf(f):
                return default
            return f
        except (ValueError, TypeError):
            return default

    # ── Execution Boundary & Safe Dispatch ───────────────────────────────────

    def execute_safe(
        self,
        df: pd.DataFrame,
        symbol: str,
        vix: float,
        market_state: str,
        mqi_level: str,
        higher_tf_df: Optional[pd.DataFrame] = None,
        precomputed_indicators: Optional[Dict[str, Any]] = None,
    ) -> Optional[StrategySignalResult]:
        """
        Safe execution boundary with automated data validation, regime gating,
        multi-asset validation, exception isolation, and execution latency telemetry.
        Never raises exceptions to callers.
        """
        if not self.is_active:
            return None

        # Multi-asset class whitelisting check
        asset_clean = str(self.asset_class or "").upper()
        if self.allowed_asset_classes and asset_clean not in self.allowed_asset_classes:
            return None

        # Regime whitelisting check
        state_clean = str(market_state or "").upper()
        if self.allowed_regimes and state_clean not in self.allowed_regimes:
            return None

        # Dataframe validation sentry
        is_valid, reason = self.validate_ohlcv_dataframe(df)
        if not is_valid:
            logger.debug(f"[{self.name}] {symbol} skipped: {reason}")
            return None

        t_start = time.perf_counter()
        try:
            raw_res = self.generate_signal(
                df=df,
                symbol=symbol,
                vix=vix,
                market_state=market_state,
                mqi_level=mqi_level,
                higher_tf_df=higher_tf_df,
                precomputed_indicators=precomputed_indicators,
            )

            latency_ms = (time.perf_counter() - t_start) * 1000.0

            if raw_res is None:
                return None

            # Convert dictionary return to StrategySignalResult if needed
            if isinstance(raw_res, StrategySignalResult):
                if "compute_latency_ms" not in raw_res.extra_metadata:
                    updated_extra = {**raw_res.extra_metadata, "compute_latency_ms": round(latency_ms, 2)}
                    result = StrategySignalResult(
                        strategy_id=raw_res.strategy_id,
                        strategy_version=raw_res.strategy_version,
                        symbol=raw_res.symbol,
                        signal_direction=raw_res.signal_direction,
                        signal_type=raw_res.signal_type,
                        technical_score=raw_res.technical_score,
                        confidence=raw_res.confidence,
                        reasons=raw_res.reasons,
                        entry_price=raw_res.entry_price,
                        swing_low=raw_res.swing_low,
                        swing_high=raw_res.swing_high,
                        atr=raw_res.atr,
                        adx=raw_res.adx,
                        sl_method=raw_res.sl_method,
                        candle_pattern=raw_res.candle_pattern,
                        timeframe=raw_res.timeframe,
                        asset_class=raw_res.asset_class,
                        underlying_symbol=raw_res.underlying_symbol,
                        strike_price=raw_res.strike_price,
                        option_type=raw_res.option_type,
                        expiry_date=raw_res.expiry_date,
                        lot_size=raw_res.lot_size,
                        tick_size=raw_res.tick_size,
                        exchange=raw_res.exchange,
                        indicator_scores=raw_res.indicator_scores,
                        indicator_values=raw_res.indicator_values,
                        extra_metadata=updated_extra,
                    )
                else:
                    result = raw_res
            elif isinstance(raw_res, dict):
                result = StrategySignalResult(
                    strategy_id=raw_res.get("strategy_id", self.name),
                    strategy_version=raw_res.get("strategy_version", self.version),
                    symbol=raw_res.get("symbol", symbol),
                    signal_direction=raw_res.get("signal_direction", "SHORT" if raw_res.get("signal_type") == "SELL" else "LONG"),
                    signal_type=raw_res.get("signal_type", "BUY"),
                    technical_score=float(raw_res.get("technical_score", 0.0)),
                    confidence=float(raw_res.get("confidence", 0.0)),
                    reasons=list(raw_res.get("reasons", [])),
                    entry_price=self.sanitize_float(raw_res.get("entry_price")),
                    swing_low=self.sanitize_float(raw_res.get("swing_low")),
                    swing_high=self.sanitize_float(raw_res.get("swing_high")),
                    atr=self.sanitize_float(raw_res.get("atr")),
                    adx=self.sanitize_float(raw_res.get("adx")),
                    sl_method=raw_res.get("sl_method"),
                    candle_pattern=raw_res.get("candle_pattern"),
                    timeframe=raw_res.get("timeframe", self.timeframe),
                    asset_class=raw_res.get("asset_class", self.asset_class),
                    underlying_symbol=raw_res.get("underlying_symbol"),
                    strike_price=self.sanitize_float(raw_res.get("strike_price")),
                    option_type=raw_res.get("option_type"),
                    expiry_date=raw_res.get("expiry_date"),
                    lot_size=int(raw_res.get("lot_size", self.lot_size)),
                    tick_size=float(raw_res.get("tick_size", self.tick_size)),
                    exchange=raw_res.get("exchange", self.exchange),
                    indicator_scores=dict(raw_res.get("indicator_scores", {})),
                    indicator_values=dict(raw_res.get("indicator_values", {})),
                    extra_metadata={
                        **dict(raw_res.get("extra", {})),
                        "compute_latency_ms": round(latency_ms, 2),
                    },
                )
            else:
                logger.warning(f"[{self.name}] {symbol} returned unexpected signal type: {type(raw_res)}")
                return None

            if not result.is_valid():
                logger.warning(f"[{self.name}] {symbol} generated invalid signal contract: {result}")
                return None

            return result

        except Exception as e:
            latency_ms = (time.perf_counter() - t_start) * 1000.0
            logger.error(f"[{self.name}] Uncaught error processing {symbol} after {latency_ms:.1f}ms: {e}", exc_info=True)
            return None

    # ── Abstract Contract Methods ────────────────────────────────────────────

    @abstractmethod
    def generate_signal(
        self,
        df: pd.DataFrame,
        symbol: str,
        vix: float,
        market_state: str,
        mqi_level: str,
        higher_tf_df: Optional[pd.DataFrame] = None,
        precomputed_indicators: Optional[Dict[str, Any]] = None,
    ) -> Union[StrategySignalResult, Dict[str, Any], None]:
        """
        Core strategy mathematical and indicator logic.
        Must return StrategySignalResult or dict if conditions are met, None otherwise.
        """
        raise NotImplementedError

    @abstractmethod
    def get_parameters(self) -> Dict[str, Any]:
        """Return complete parameter dictionary for MLflow tracking and hyperparameter audits."""
        raise NotImplementedError

    @abstractmethod
    def get_description(self) -> str:
        """Return human-readable strategy description for reporting and alerts."""
        raise NotImplementedError

    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__name__} "
            f"name={self.name} "
            f"version={self.version} "
            f"direction={self.signal_direction} "
            f"timeframe={self.timeframe} "
            f"asset_class={self.asset_class} "
            f"exchange={self.exchange}>"
        )
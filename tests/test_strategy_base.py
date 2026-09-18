import math
from typing import Any, Dict, Optional, Union
import numpy as np
import pandas as pd
import pytest

from mjonai.strategy.registry.base import BaseStrategy, StrategySignalResult


# ── Mock Implementation for Testing Base Class ───────────────────────────────

class DummyBullishStrategy(BaseStrategy):
    name = "S99_DummyBullish"
    display_name = "Dummy Bullish Test Strategy"
    version = "1.0"
    timeframe = "15m"
    asset_class = "EQUITY"
    signal_direction = "LONG"
    allowed_regimes = ("BULL", "NEUTRAL")
    min_candles_required = 10

    def generate_signal(
        self,
        df: pd.DataFrame,
        symbol: str,
        vix: float,
        market_state: str,
        mqi_level: str,
        higher_tf_df: Optional[pd.DataFrame] = None,
        precomputed_indicators: Optional[Dict[str, Any]] = None,
    ) -> Optional[StrategySignalResult]:
        if vix > 30.0:
            return None
        return StrategySignalResult(
            strategy_id=self.name,
            strategy_version=self.version,
            symbol=symbol,
            signal_direction="LONG",
            signal_type="BUY",
            technical_score=85.0,
            confidence=78.0,
            reasons=["Dummy Momentum Breakout ✓"],
            entry_price=100.0,
            swing_low=95.0,
            atr=2.5,
            adx=28.0,
            sl_method="STRUCTURE",
        )

    def get_parameters(self) -> Dict[str, Any]:
        return {"min_vix": 10.0, "max_vix": 30.0}

    def get_description(self) -> str:
        return "Dummy strategy for unit testing BaseStrategy contract."


class CrashingStrategy(BaseStrategy):
    name = "S98_Crashing"
    display_name = "Crashing Strategy"
    version = "1.0"

    def generate_signal(
        self,
        df: pd.DataFrame,
        symbol: str,
        vix: float,
        market_state: str,
        mqi_level: str,
        higher_tf_df: Optional[pd.DataFrame] = None,
        precomputed_indicators: Optional[Dict[str, Any]] = None,
    ) -> Optional[StrategySignalResult]:
        # Deliberately raise zero division error
        raise ZeroDivisionError("Deliberate test crash")

    def get_parameters(self) -> Dict[str, Any]:
        return {}

    def get_description(self) -> str:
        return "Always crashes to test error boundary."


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def valid_ohlcv_df():
    dates = pd.date_range("2026-01-01", periods=60, freq="15min")
    return pd.DataFrame({
        "Open": np.linspace(100, 110, 60),
        "High": np.linspace(101, 112, 60),
        "Low": np.linspace(99, 109, 60),
        "Close": np.linspace(100.5, 111.5, 60),
        "Volume": [10000] * 60,
    }, index=dates)


# ── 1. CONTRACT SERIALIZATION TESTS ──────────────────────────────────────────

def test_strategy_signal_result_contract():
    """Verify StrategySignalResult dataclass validity and dictionary serialization."""
    res = StrategySignalResult(
        strategy_id="S01_MomentumRSI",
        strategy_version="1.0",
        symbol="NIFTY26AUG24500CE",
        signal_direction="LONG",
        signal_type="BUY",
        technical_score=80.0,
        confidence=75.0,
        reasons=["RSI Bullish ✓", "EMA 20 > 50 ✓"],
        entry_price=150.0,
        swing_low=120.0,
        atr=15.0,
        asset_class="INDEX",
        underlying_symbol="NIFTY",
        strike_price=24500.0,
        option_type="CE",
        expiry_date="2026-08-27",
        lot_size=25,
        tick_size=0.05,
        exchange="NFO",
        extra_metadata={"custom_flag": True},
    )

    assert res.is_valid() is True
    d = res.to_dict()
    assert d["strategy_id"] == "S01_MomentumRSI"
    assert d["symbol"] == "NIFTY26AUG24500CE"
    assert d["underlying_symbol"] == "NIFTY"
    assert d["lot_size"] == 25
    assert d["exchange"] == "NFO"
    assert d["custom_flag"] is True  # Flattened extra metadata


def test_strategy_signal_result_validation_fails_on_empty_reasons():
    """Verify invalid contract returns False from is_valid()."""
    res = StrategySignalResult(
        strategy_id="S01_MomentumRSI",
        strategy_version="1.0",
        symbol="RELIANCE",
        signal_direction="LONG",
        signal_type="BUY",
        technical_score=80.0,
        confidence=75.0,
        reasons=[],  # Empty reasons must fail
    )
    assert res.is_valid() is False


# ── 2. DATAFRAME VALIDATION SENTRY TESTS ─────────────────────────────────────

def test_validate_ohlcv_dataframe_success(valid_ohlcv_df):
    """Verify valid dataframe passes inspection."""
    is_ok, reason = BaseStrategy.validate_ohlcv_dataframe(valid_ohlcv_df, min_candles=50)
    assert is_ok is True
    assert reason == "OK"


def test_validate_ohlcv_dataframe_catches_short_history(valid_ohlcv_df):
    """Verify short candle history is rejected."""
    short_df = valid_ohlcv_df.iloc[:20]
    is_ok, reason = BaseStrategy.validate_ohlcv_dataframe(short_df, min_candles=50)
    assert is_ok is False
    assert "Insufficient candle history" in reason


def test_validate_ohlcv_dataframe_catches_missing_columns():
    """Verify missing OHLCV columns are rejected."""
    bad_df = pd.DataFrame({"Close": [100, 101, 102], "Volume": [10, 20, 30]})
    is_ok, reason = BaseStrategy.validate_ohlcv_dataframe(bad_df, min_candles=3)
    assert is_ok is False
    assert "Missing required OHLCV columns" in reason


def test_validate_ohlcv_dataframe_catches_nan_in_latest_bar(valid_ohlcv_df):
    """H4: a NaN in the decision (latest) bar's OHLCV must fail closed."""
    bad = valid_ohlcv_df.copy()
    bad.iloc[-1, bad.columns.get_loc("Close")] = np.nan
    is_ok, reason = BaseStrategy.validate_ohlcv_dataframe(bad, min_candles=50)
    assert is_ok is False
    assert "latest bar" in reason
    assert "Close" in reason


def test_validate_ohlcv_dataframe_catches_entirely_empty_column(valid_ohlcv_df):
    """H4: a required column that is entirely empty must fail closed."""
    bad = valid_ohlcv_df.copy()
    bad["Volume"] = np.nan
    is_ok, reason = BaseStrategy.validate_ohlcv_dataframe(bad, min_candles=3)
    assert is_ok is False
    assert "entirely empty" in reason


def test_validate_ohlcv_dataframe_catches_nonpositive_price(valid_ohlcv_df):
    """H4: a non-positive price on the decision bar is invalid market data."""
    bad = valid_ohlcv_df.copy()
    bad.iloc[-1, bad.columns.get_loc("Close")] = 0.0
    is_ok, reason = BaseStrategy.validate_ohlcv_dataframe(bad, min_candles=50)
    assert is_ok is False
    assert "latest bar" in reason


def test_execute_safe_fails_closed_on_nan_latest_bar(valid_ohlcv_df):
    """H4: execute_safe returns None (no signal) on an incomplete decision bar."""
    bad = valid_ohlcv_df.copy()
    bad.iloc[-1, bad.columns.get_loc("High")] = np.nan
    strat = DummyBullishStrategy()
    res = strat.execute_safe(
        df=bad,
        symbol="TCS",
        vix=15.0,
        market_state="BULL",
        mqi_level="HIGH",
    )
    assert res is None


# ── 3. SANITIZATION & SAFE EXECUTION TESTS ────────────────────────────────────

def test_sanitize_float():
    """Verify float sanitizer replaces NaN and Inf with None or default."""
    assert BaseStrategy.sanitize_float(10.5) == 10.5
    assert BaseStrategy.sanitize_float(float("nan")) is None
    assert BaseStrategy.sanitize_float(float("inf"), default=0.0) == 0.0
    assert BaseStrategy.sanitize_float("not_a_number") is None


def test_execute_safe_successful(valid_ohlcv_df):
    """Verify execute_safe runs successfully and tracks latency."""
    strat = DummyBullishStrategy()
    res = strat.execute_safe(
        df=valid_ohlcv_df,
        symbol="TCS",
        vix=15.0,
        market_state="BULL",
        mqi_level="HIGH",
    )
    assert res is not None
    assert res.symbol == "TCS"
    assert res.technical_score == 85.0
    assert "compute_latency_ms" in res.extra_metadata


def test_execute_safe_blocks_unallowed_regime(valid_ohlcv_df):
    """Verify strategy in BEAR regime is blocked when only BULL/NEUTRAL allowed."""
    strat = DummyBullishStrategy()
    res = strat.execute_safe(
        df=valid_ohlcv_df,
        symbol="INFY",
        vix=15.0,
        market_state="BEAR",  # Unallowed regime
        mqi_level="LOW",
    )
    assert res is None


def test_execute_safe_catches_crashes_gracefully(valid_ohlcv_df):
    """Verify strategy crash is caught inside error boundary without raising."""
    crashing_strat = CrashingStrategy()
    res = crashing_strat.execute_safe(
        df=valid_ohlcv_df,
        symbol="HDFCBANK",
        vix=15.0,
        market_state="BULL",
        mqi_level="HIGH",
    )
    assert res is None  # Graceful None return, no uncaught exception!


def test_execute_safe_skips_inactive_strategy(valid_ohlcv_df):
    """Verify deactivated strategy immediately returns None."""
    strat = DummyBullishStrategy()
    strat.is_active = False
    res = strat.execute_safe(
        df=valid_ohlcv_df,
        symbol="TCS",
        vix=15.0,
        market_state="BULL",
        mqi_level="HIGH",
    )
    assert res is None


def test_execute_safe_blocks_unallowed_asset_class(valid_ohlcv_df):
    """Verify strategy with unallowed asset class is blocked."""
    strat = DummyBullishStrategy()
    strat.allowed_asset_classes = ("INDEX", "COMMODITY")  # EQUITY not allowed
    strat.asset_class = "EQUITY"
    res = strat.execute_safe(
        df=valid_ohlcv_df,
        symbol="TCS",
        vix=15.0,
        market_state="BULL",
        mqi_level="HIGH",
    )
    assert res is None


class DictReturningStrategy(BaseStrategy):
    name = "S97_DictStrategy"
    display_name = "Dict Returning Strategy"

    def generate_signal(
        self,
        df: pd.DataFrame,
        symbol: str,
        vix: float,
        market_state: str,
        mqi_level: str,
        higher_tf_df: Optional[pd.DataFrame] = None,
        precomputed_indicators: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return {
            "strategy_id": self.name,
            "strategy_version": "1.0",
            "symbol": symbol,
            "signal_type": "BUY",
            "technical_score": 77.0,
            "confidence": 72.0,
            "reasons": ["Dict Breakout ✓"],
            "entry_price": 500.0,
            "swing_low": 480.0,
            "lot_size": 10,
        }

    def get_parameters(self) -> Dict[str, Any]:
        return {}

    def get_description(self) -> str:
        return "Returns raw dict to test auto-conversion."


def test_execute_safe_auto_converts_dict(valid_ohlcv_df):
    """Verify raw dict returned by legacy strategy is auto-converted to StrategySignalResult."""
    strat = DictReturningStrategy()
    res = strat.execute_safe(
        df=valid_ohlcv_df,
        symbol="SBIN",
        vix=15.0,
        market_state="BULL",
        mqi_level="HIGH",
    )
    assert res is not None
    assert isinstance(res, StrategySignalResult)
    assert res.symbol == "SBIN"
    assert res.signal_direction == "LONG"
    assert res.technical_score == 77.0
    assert res.lot_size == 10


def test_base_strategy_repr():
    """Verify __repr__ formats strategy metadata correctly."""
    strat = DummyBullishStrategy()
    r = repr(strat)
    assert "DummyBullishStrategy" in r
    assert "S99_DummyBullish" in r
    assert "EQUITY" in r

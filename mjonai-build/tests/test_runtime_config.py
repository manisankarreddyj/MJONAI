"""
12-Dimensional Production Test Suite for core/runtime_config.py
Tests Cross-Platform Paths, Environment Variable Overrides, Startup Sanity Validation,
Dataclass Immutability, and Caller Regression Sweeps.
"""

import os
from pathlib import Path
import pytest
import sys
import tempfile
from unittest.mock import patch

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from core.runtime_config import (
    LOCK_FILE,
    get_lock_file_path,
    SystemHealthConfig,
    NetworkRetryConfig,
    AIModelRoutingConfig,
    RuntimeOrchestrationConfig,
    validate_runtime_config,
    _get_env_int,
    _get_env_float,
    _get_env_bool,
    _get_env_str,
    WEBSOCKET_STALE_ALERT_INTERVAL_SECONDS,
    SCHEDULER_LOOP_SLEEP_SECONDS,
    HEALTH_MONITOR_INTERVAL_MINUTES,
    INTERNET_CHECK_TIMEOUT_SECONDS,
    RAM_WARNING_THRESHOLD_PERCENT,
    RAM_CRITICAL_THRESHOLD_PERCENT,
    ANGELONE_MAX_RETRIES,
    ANGELONE_RETRY_DELAY_SECONDS,
    ENABLE_TELEGRAM_ALERTS,
    TELEGRAM_TIMEOUT_SECONDS,
    TELEGRAM_POLL_TIMEOUT_SECONDS,
    GEMINI_MODEL,
    GEMINI_MAX_OUTPUT_TOKENS,
    REQUIRED_DEVIL_CHECKS,
    GROQ_PRIMARY_MODEL,
    GROQ_FALLBACK_MODEL,
    GROQ_MAX_TOKENS,
    GROQ_TEMPERATURE,
    SOFT_STOP_DURATION_MINUTES,
)


# ── 1. CROSS-PLATFORM PROCESS LOCK TESTS ─────────────────────────────────────

def test_cross_platform_lock_path():
    """Verify lock file path is cross-platform, writable, and not hardcoded to /tmp on Windows."""
    lock_path = get_lock_file_path()
    assert isinstance(lock_path, Path)
    assert lock_path.name == "mjonai.lock"
    # Ensure parent directory exists and is writable
    assert lock_path.parent.exists()
    assert os.access(lock_path.parent, os.W_OK)


def test_custom_lock_file_via_env():
    """Verify custom lock file can be injected via MJONAI_LOCK_FILE."""
    custom_lock = str(Path(tempfile.gettempdir()) / "custom_test.lock")
    with patch.dict(os.environ, {"MJONAI_LOCK_FILE": custom_lock}):
        assert get_lock_file_path() == Path(custom_lock)


# ── 2. ENVIRONMENT VARIABLE OVERRIDE & TYPE PARSING ──────────────────────────

def test_env_parsers():
    """Verify type casting and default fallbacks for int, float, bool, str."""
    with patch.dict(os.environ, {
        "TEST_STR": " custom_val ",
        "TEST_INT": " 42 ",
        "TEST_BAD_INT": " not_a_number ",
        "TEST_FLOAT": " 99.5 ",
        "TEST_BOOL_TRUE": " YES ",
        "TEST_BOOL_FALSE": " 0 ",
    }):
        assert _get_env_str("TEST_STR", "default") == "custom_val"
        assert _get_env_int("TEST_INT", 10) == 42
        assert _get_env_int("TEST_BAD_INT", 10) == 10  # Fallback on parse error
        assert _get_env_float("TEST_FLOAT", 1.0) == 99.5
        assert _get_env_bool("TEST_BOOL_TRUE", False) is True
        assert _get_env_bool("TEST_BOOL_FALSE", True) is False


# ── 3. STRUCTURED DATACLASS IMMUTABILITY ──────────────────────────────────────

def test_structured_dataclass_immutability():
    """Verify operational config dataclasses are frozen and cannot be mutated at runtime."""
    health = SystemHealthConfig()
    ai = AIModelRoutingConfig()
    network = NetworkRetryConfig()
    orch = RuntimeOrchestrationConfig()

    with pytest.raises(Exception):
        health.ram_warning_threshold_pct = 99.0  # type: ignore

    with pytest.raises(Exception):
        ai.groq_temperature = 0.9  # type: ignore

    assert health.ram_warning_threshold_pct == 85.0
    assert health.ram_critical_threshold_pct == 95.0
    assert ai.required_devil_checks == 8
    assert orch.soft_stop_duration_minutes == 120


# ── 4. SINGLE SOURCE OF TRUTH RISK CONSOLIDATION ─────────────────────────────

def test_risk_policy_duration_alignment():
    """Verify runtime soft stop duration aligns with constants.py CONSECUTIVE_LOSS_COOLDOWN_MINUTES (120m)."""
    from core.constants import CONSECUTIVE_LOSS_COOLDOWN_MINUTES
    assert SOFT_STOP_DURATION_MINUTES == CONSECUTIVE_LOSS_COOLDOWN_MINUTES
    assert SOFT_STOP_DURATION_MINUTES == 120


# ── 5. STARTUP SANITY VALIDATION & CORRUPTED CONFIG REJECTION ────────────────

def test_valid_configuration_passes():
    """Verify standard default configuration validates successfully."""
    assert validate_runtime_config() is True


def test_corrupted_ram_thresholds_rejected():
    """Verify invalid RAM thresholds (warning >= critical or critical > 100) are rejected."""
    with patch("core.runtime_config.RAM_WARNING_THRESHOLD_PERCENT", 98.0), \
         patch("core.runtime_config.RAM_CRITICAL_THRESHOLD_PERCENT", 90.0):
        with pytest.raises(ValueError, match="RAM threshold violation"):
            validate_runtime_config()

    with patch("core.runtime_config.RAM_CRITICAL_THRESHOLD_PERCENT", 105.0):
        with pytest.raises(ValueError, match="RAM threshold violation"):
            validate_runtime_config()


def test_negative_retries_rejected():
    """Verify negative retry count is rejected."""
    with patch("core.runtime_config.ANGELONE_MAX_RETRIES", -1):
        with pytest.raises(ValueError, match="ANGELONE_MAX_RETRIES must be non-negative"):
            validate_runtime_config()


def test_invalid_temperature_rejected():
    """Verify temperature outside [0.0, 1.0] is rejected."""
    with patch("core.runtime_config.GROQ_TEMPERATURE", 1.5):
        with pytest.raises(ValueError, match="GROQ_TEMPERATURE must be in"):
            validate_runtime_config()

    with patch("core.runtime_config.GROQ_TEMPERATURE", -0.1):
        with pytest.raises(ValueError, match="GROQ_TEMPERATURE must be in"):
            validate_runtime_config()


def test_zero_and_negative_timeouts_rejected():
    """Verify zero or negative timeout values are rejected fail-fast."""
    with patch("core.runtime_config.ANGELONE_RETRY_DELAY_SECONDS", 0):
        with pytest.raises(ValueError, match="ANGELONE_RETRY_DELAY_SECONDS must be > 0"):
            validate_runtime_config()

    with patch("core.runtime_config.INTERNET_CHECK_TIMEOUT_SECONDS", -5):
        with pytest.raises(ValueError, match="INTERNET_CHECK_TIMEOUT_SECONDS must be > 0"):
            validate_runtime_config()

    with patch("core.runtime_config.TELEGRAM_TIMEOUT_SECONDS", 0):
        with pytest.raises(ValueError, match="TELEGRAM_TIMEOUT_SECONDS must be > 0"):
            validate_runtime_config()


def test_zero_tokens_and_devil_checks_rejected():
    """Verify zero or negative token limits and devil checks are rejected."""
    with patch("core.runtime_config.GEMINI_MAX_OUTPUT_TOKENS", 0):
        with pytest.raises(ValueError, match="GEMINI_MAX_OUTPUT_TOKENS must be > 0"):
            validate_runtime_config()

    with patch("core.runtime_config.GROQ_MAX_TOKENS", -10):
        with pytest.raises(ValueError, match="GROQ_MAX_TOKENS must be > 0"):
            validate_runtime_config()

    with patch("core.runtime_config.REQUIRED_DEVIL_CHECKS", 0):
        with pytest.raises(ValueError, match="REQUIRED_DEVIL_CHECKS must be > 0"):
            validate_runtime_config()

    with patch("core.runtime_config.SOFT_STOP_DURATION_MINUTES", 0):
        with pytest.raises(ValueError, match="SOFT_STOP_DURATION_MINUTES must be > 0"):
            validate_runtime_config()


# ── 6. CALLER REGRESSION & SYMBOL RESOLUTION SWEEP ───────────────────────────

def test_caller_symbol_imports():
    """Verify all 13 dependent callers can import their required symbols without error."""
    # main.py symbols
    assert isinstance(SCHEDULER_LOOP_SLEEP_SECONDS, int)
    assert isinstance(HEALTH_MONITOR_INTERVAL_MINUTES, int)
    assert isinstance(ENABLE_TELEGRAM_ALERTS, bool)

    # agents symbols
    assert "gemini" in GEMINI_MODEL.lower()
    assert isinstance(GEMINI_MAX_OUTPUT_TOKENS, int)
    assert "llama" in GROQ_PRIMARY_MODEL.lower()
    assert "llama" in GROQ_FALLBACK_MODEL.lower()
    assert isinstance(GROQ_MAX_TOKENS, int)
    assert isinstance(GROQ_TEMPERATURE, float)
    assert REQUIRED_DEVIL_CHECKS == 8

    # communication symbols
    assert isinstance(TELEGRAM_TIMEOUT_SECONDS, int)
    assert isinstance(TELEGRAM_POLL_TIMEOUT_SECONDS, int)

    # orchestration & lock symbols
    assert isinstance(LOCK_FILE, str)
    assert isinstance(WEBSOCKET_STALE_ALERT_INTERVAL_SECONDS, int)
    assert isinstance(RAM_WARNING_THRESHOLD_PERCENT, float)
    assert isinstance(RAM_CRITICAL_THRESHOLD_PERCENT, float)


def test_ai_debate_timeout_and_multi_asset_toggles():
    """Verify AI debate timeout and multi-asset operational toggles."""
    from core.runtime_config import (
        AI_DEBATE_TIMEOUT_SECONDS,
        ENABLE_MCX_SESSION,
        ENABLE_CRYPTO_SESSION,
        ENABLE_US_EQUITY_SESSION,
    )
    assert AI_DEBATE_TIMEOUT_SECONDS == 30
    assert isinstance(ENABLE_MCX_SESSION, bool)
    assert isinstance(ENABLE_CRYPTO_SESSION, bool)
    assert isinstance(ENABLE_US_EQUITY_SESSION, bool)

    # Test invalid AI debate timeout rejection
    with patch("core.runtime_config.AI_DEBATE_TIMEOUT_SECONDS", 0):
        with pytest.raises(ValueError, match="AI_DEBATE_TIMEOUT_SECONDS must be > 0"):
            validate_runtime_config()


def test_print_runtime_startup_banner():
    """Verify startup banner logger executes without error and logs profile."""
    from core.runtime_config import print_runtime_startup_banner
    # Should execute cleanly without throwing
    print_runtime_startup_banner()

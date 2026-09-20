"""
Module: core/runtime_config.py

Purpose: Centralized Runtime Operational Configuration, Health Thresholds,
         AI Model Routing, and Cross-Platform Process Guardrails.

Architectural Principles:
  1. Single Source of Truth for Operational & Orchestration Parameters.
  2. Cross-Platform Compatibility (Windows & Linux POSIX locking).
  3. Environment-Variable Backed with Audited Production Defaults (No Secrets Stored Here).
  4. Structured Immutable Dataclasses (AIModelRoutingConfig, SystemHealthConfig, NetworkRetryConfig).
  5. Startup Sanity Validation Engine (validate_runtime_config).
  6. 100% Backwards-Compatible Public API for all 13 dependent callers.
"""

from dataclasses import dataclass
import logging
import os
from pathlib import Path
import tempfile
from typing import Optional

logger = logging.getLogger(__name__)

_ENV_LOADED = False


def load_mjonai_env() -> None:
    """Load the single root `.env` once. Repo root is two levels above this file (mjonai/core/).

    Layout (2026-09-20 consolidation): `credentials/.env.master` was retired and its
    contents merged into the repo-root `.env` (77 keys, single canonical environment file)."""
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    envelope = Path(__file__).resolve().parents[2] / ".env"
    if envelope.is_file():
        load_dotenv(envelope, override=False)
    _ENV_LOADED = True


load_mjonai_env()


# ── 1. ENVIRONMENT CONFIGURATION HELPERS ─────────────────────────────────────

def _get_env_str(key: str, default: str) -> str:
    return os.getenv(key, default).strip()

def _get_env_int(key: str, default: int) -> int:
    val = os.getenv(key)
    if val is None:
        return default
    try:
        return int(val.strip())
    except ValueError:
        logger.warning(f"[runtime_config] Invalid integer for {key}='{val}', using default {default}")
        return default

def _get_env_float(key: str, default: float) -> float:
    val = os.getenv(key)
    if val is None:
        return default
    try:
        return float(val.strip())
    except ValueError:
        logger.warning(f"[runtime_config] Invalid float for {key}='{val}', using default {default}")
        return default

def _get_env_bool(key: str, default: bool) -> bool:
    val = os.getenv(key)
    if val is None:
        return default
    return val.strip().lower() in ("true", "1", "yes", "on")


# ── 2. CROSS-PLATFORM PROCESS LOCK ───────────────────────────────────────────

def get_lock_file_path() -> Path:
    """
    Returns platform-aware, writable lock file path.
    Windows: %TEMP%/mjonai.lock
    Linux: /tmp/mjonai.lock
    """
    custom_path = os.getenv("MJONAI_LOCK_FILE")
    if custom_path:
        return Path(custom_path)
    return Path(tempfile.gettempdir()) / "mjonai.lock"


LOCK_FILE: str = str(get_lock_file_path())


# ── 3. STRUCTURED OPERATIONAL CONFIGURATIONS ─────────────────────────────────

@dataclass(frozen=True)
class SystemHealthConfig:
    """System health monitoring intervals and resource thresholds."""
    monitor_interval_minutes: int = 1
    internet_check_timeout_seconds: int = 3
    ram_warning_threshold_pct: float = 85.0
    ram_critical_threshold_pct: float = 95.0


@dataclass(frozen=True)
class NetworkRetryConfig:
    """Broker API and WebSocket network retry specifications."""
    angelone_max_retries: int = 3
    angelone_retry_delay_seconds: int = 10
    websocket_stale_alert_interval_seconds: int = 300
    telegram_timeout_seconds: int = 10
    telegram_poll_timeout_seconds: int = 15


@dataclass(frozen=True)
class AIModelRoutingConfig:
    """AI debate agent model names, token ceilings, and temperatures."""
    gemini_model: str = "models/gemini-2.5-flash"
    gemini_max_output_tokens: int = 600
    groq_primary_model: str = "llama-3.3-70b-versatile"
    groq_fallback_model: str = "llama-3.1-8b-instant"
    groq_max_tokens: int = 800
    groq_temperature: float = 0.2
    required_devil_checks: int = 8
    ai_debate_timeout_seconds: int = 30


@dataclass(frozen=True)
class RuntimeOrchestrationConfig:
    """Main scheduler and risk coordination settings."""
    scheduler_loop_sleep_seconds: int = 30
    enable_telegram_alerts: bool = True
    soft_stop_duration_minutes: int = 120  # Aligned with constants.py RiskPolicySpec
    enable_mcx_session: bool = False       # MCX Commodities session toggle
    enable_crypto_session: bool = False    # Crypto 24/7 continuous session toggle
    enable_us_equity_session: bool = False # US Equities (NYSE) session toggle


# ── 4. MODULE-LEVEL OPERATIONAL CONSTANTS (100% BACKWARD COMPATIBLE) ─────────

# WebSocket supervision
WEBSOCKET_STALE_ALERT_INTERVAL_SECONDS: int = _get_env_int(
    "MJONAI_WS_STALE_ALERT_SECONDS", 300
)

# Scheduler timings
SCHEDULER_LOOP_SLEEP_SECONDS: int = _get_env_int(
    "MJONAI_SCHEDULER_SLEEP_SECONDS", 30
)

# Health monitoring
HEALTH_MONITOR_INTERVAL_MINUTES: int = _get_env_int(
    "MJONAI_HEALTH_INTERVAL_MINUTES", 1
)
INTERNET_CHECK_TIMEOUT_SECONDS: int = _get_env_int(
    "MJONAI_INTERNET_CHECK_TIMEOUT_SECONDS", 3
)

RAM_WARNING_THRESHOLD_PERCENT: float = _get_env_float(
    "MJONAI_RAM_WARNING_PERCENT", 85.0
)
RAM_CRITICAL_THRESHOLD_PERCENT: float = _get_env_float(
    "MJONAI_RAM_CRITICAL_PERCENT", 95.0
)

# AngelOne retry config
ANGELONE_MAX_RETRIES: int = _get_env_int(
    "ANGELONE_MAX_RETRIES", 3
)
ANGELONE_RETRY_DELAY_SECONDS: int = _get_env_int(
    "ANGELONE_RETRY_DELAY_SECONDS", 10
)

# Runtime behavior & Telegram
ENABLE_TELEGRAM_ALERTS: bool = _get_env_bool(
    "ENABLE_TELEGRAM_ALERTS", True
)
TELEGRAM_TIMEOUT_SECONDS: int = _get_env_int(
    "TELEGRAM_TIMEOUT_SECONDS", 10
)
TELEGRAM_POLL_TIMEOUT_SECONDS: int = _get_env_int(
    "TELEGRAM_POLL_TIMEOUT_SECONDS", 15
)

# Gemini AI Configuration
GEMINI_MODEL: str = _get_env_str(
    "GEMINI_MODEL", "models/gemini-2.5-flash"
)
GEMINI_MAX_OUTPUT_TOKENS: int = _get_env_int(
    "GEMINI_MAX_OUTPUT_TOKENS", 600
)
GEMINI_TEMPERATURE: float = _get_env_float(
    "GEMINI_TEMPERATURE", 0.2
)

# Devil checks & Groq AI Configuration
REQUIRED_DEVIL_CHECKS: int = _get_env_int(
    "REQUIRED_DEVIL_CHECKS", 8
)
GROQ_PRIMARY_MODEL: str = _get_env_str(
    "GROQ_PRIMARY_MODEL", "llama-3.3-70b-versatile"
)
GROQ_FALLBACK_MODEL: str = _get_env_str(
    "GROQ_FALLBACK_MODEL", "llama-3.1-8b-instant"
)
GROQ_MAX_TOKENS: int = _get_env_int(
    "GROQ_MAX_TOKENS", 800
)
GROQ_TEMPERATURE: float = _get_env_float(
    "GROQ_TEMPERATURE", 0.2
)
AI_DEBATE_TIMEOUT_SECONDS: int = _get_env_int(
    "AI_DEBATE_TIMEOUT_SECONDS", 30
)

# Risk controls (Single Source of Truth: aligned with constants.py 120m)
SOFT_STOP_DURATION_MINUTES: int = _get_env_int(
    "SOFT_STOP_DURATION_MINUTES", 120
)

# Multi-Asset Session Controls
ENABLE_MCX_SESSION: bool = _get_env_bool(
    "ENABLE_MCX_SESSION", False
)
ENABLE_CRYPTO_SESSION: bool = _get_env_bool(
    "ENABLE_CRYPTO_SESSION", False
)
ENABLE_US_EQUITY_SESSION: bool = _get_env_bool(
    "ENABLE_US_EQUITY_SESSION", False
)


# ── 5. STARTUP SANITY VALIDATION ENGINE ──────────────────────────────────────

def validate_runtime_config() -> bool:
    """
    Fail-fast startup validation for runtime configuration.
    Raises ValueError on invalid bounds or conflicting configurations.
    """
    errors = []

    # 1. RAM thresholds
    if not (0.0 < RAM_WARNING_THRESHOLD_PERCENT < RAM_CRITICAL_THRESHOLD_PERCENT <= 100.0):
        errors.append(
            f"RAM threshold violation: 0 < warning ({RAM_WARNING_THRESHOLD_PERCENT}%) "
            f"< critical ({RAM_CRITICAL_THRESHOLD_PERCENT}%) <= 100.0 required."
        )

    # 2. Retries and timeouts
    if ANGELONE_MAX_RETRIES < 0:
        errors.append(f"ANGELONE_MAX_RETRIES must be non-negative, got {ANGELONE_MAX_RETRIES}")
    if ANGELONE_RETRY_DELAY_SECONDS <= 0:
        errors.append(f"ANGELONE_RETRY_DELAY_SECONDS must be > 0, got {ANGELONE_RETRY_DELAY_SECONDS}")
    if INTERNET_CHECK_TIMEOUT_SECONDS <= 0:
        errors.append(f"INTERNET_CHECK_TIMEOUT_SECONDS must be > 0, got {INTERNET_CHECK_TIMEOUT_SECONDS}")
    if TELEGRAM_TIMEOUT_SECONDS <= 0:
        errors.append(f"TELEGRAM_TIMEOUT_SECONDS must be > 0, got {TELEGRAM_TIMEOUT_SECONDS}")

    # 3. AI Model limits
    if not (0.0 <= GROQ_TEMPERATURE <= 1.0):
        errors.append(f"GROQ_TEMPERATURE must be in [0.0, 1.0], got {GROQ_TEMPERATURE}")
    if GEMINI_MAX_OUTPUT_TOKENS <= 0:
        errors.append(f"GEMINI_MAX_OUTPUT_TOKENS must be > 0, got {GEMINI_MAX_OUTPUT_TOKENS}")
    if GROQ_MAX_TOKENS <= 0:
        errors.append(f"GROQ_MAX_TOKENS must be > 0, got {GROQ_MAX_TOKENS}")
    if REQUIRED_DEVIL_CHECKS <= 0:
        errors.append(f"REQUIRED_DEVIL_CHECKS must be > 0, got {REQUIRED_DEVIL_CHECKS}")
    if AI_DEBATE_TIMEOUT_SECONDS <= 0:
        errors.append(f"AI_DEBATE_TIMEOUT_SECONDS must be > 0, got {AI_DEBATE_TIMEOUT_SECONDS}")
    if SOFT_STOP_DURATION_MINUTES <= 0:
        errors.append(f"SOFT_STOP_DURATION_MINUTES must be > 0, got {SOFT_STOP_DURATION_MINUTES}")

    if errors:
        msg = "Runtime configuration validation failed:\n" + "\n".join(f" - {e}" for e in errors)
        logger.error(msg)
        raise ValueError(msg)

    logger.info("Runtime configuration successfully validated.")
    return True


def print_runtime_startup_banner() -> None:
    """Print clean operational configuration banner at system startup."""
    banner = f"""
===================================================================
MJONAI RUNTIME CONFIGURATION & SYSTEM HEALTH PROFILE
===================================================================
Primary LLM Model       : {GEMINI_MODEL} (max {GEMINI_MAX_OUTPUT_TOKENS} tokens)
Debate LLM Model        : {GROQ_PRIMARY_MODEL} (temp {GROQ_TEMPERATURE})
Fallback LLM Model      : {GROQ_FALLBACK_MODEL}
AI Debate Timeout       : {AI_DEBATE_TIMEOUT_SECONDS}s (Devil Checks: {REQUIRED_DEVIL_CHECKS})
-------------------------------------------------------------------
RAM Warning Threshold   : {RAM_WARNING_THRESHOLD_PERCENT}%
RAM Critical Threshold  : {RAM_CRITICAL_THRESHOLD_PERCENT}%
Broker Retries          : {ANGELONE_MAX_RETRIES} attempts ({ANGELONE_RETRY_DELAY_SECONDS}s delay)
WebSocket Stale Window  : {WEBSOCKET_STALE_ALERT_INTERVAL_SECONDS}s
Soft Stop Duration      : {SOFT_STOP_DURATION_MINUTES}m
Lock File Location      : {LOCK_FILE}
-------------------------------------------------------------------
Multi-Asset Sessions    : MCX={ENABLE_MCX_SESSION} | Crypto={ENABLE_CRYPTO_SESSION} | US={ENABLE_US_EQUITY_SESSION}
Telegram Alerts         : {ENABLE_TELEGRAM_ALERTS} (Timeout: {TELEGRAM_TIMEOUT_SECONDS}s)
===================================================================
"""
    logger.info(banner)


# Run startup validation on module import
try:
    validate_runtime_config()
except Exception as _e:
    logger.error(f"FATAL: Runtime configuration error on module load: {_e}")
    raise
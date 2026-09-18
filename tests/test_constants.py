"""
Unit & Boundary Integration Tests for core/constants.py
Tests Evidence-Backed Statutory Taxes, Dynamic Capital Tiers, Dual-Key Security,
Unknown-Symbol Observability, and Fail-Fast Startup Sanity Validation.
"""

from datetime import datetime, date, time
import pytest
import sys
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent  # repo root (ADR-0008)
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from mjonai.core.constants import (
    CONFIG_VERSION,
    STATUTORY_RATES,
    CONTRACT_SPECS,
    STRATEGY_RISK_POLICIES,
    CAPITAL_TIERS,
    SEBI_CIRCUIT_BREAKERS,
    TOTAL_CAPITAL,
    DAILY_LOSS_LIMIT_PCT,
    KILL_LINE_PCT,
    CONSECUTIVE_LOSS_LIMIT,
    MAX_OPEN_POSITIONS,
    STT_EQUITY_DELIVERY,
    STT_EQUITY_INTRADAY_SELL,
    STT_FUTURES_SELL,
    STT_OPTIONS_PREMIUM_SELL,
    EXCHANGE_TURNOVER_NSE_EQUITY,
    GST_RATE,
    DEFAULT_BROKERAGE_PER_ORDER,
    LOT_SIZES,
    TICK_SIZES,
    STRATEGY_REGISTRY,
    ACTIVE_STRATEGIES,
    get_lot_size,
    get_capital_tier,
    get_dynamic_max_open_positions,
    is_live_execution_permitted,
    get_sector,
    get_unmapped_instruments,
    build_setup_hash,
    get_time_bucket,
    validate_configuration,
    SYSTEM_MODE,
    LIVE_EXECUTION_AUTHORIZED,
)


def test_statutory_rates_and_evidence():
    """Verify statutory tax specs have complete circular citations and match 2024 SEBI rates."""
    stt_fut = STATUTORY_RATES["STT_FUTURES"]
    assert stt_fut.rate == 0.0002              # 0.02%
    assert stt_fut.levied_on == "SELL"
    assert "Finance (No. 2) Act 2024" in stt_fut.regulatory_source
    assert "SEBI/HO/MRD" in stt_fut.circular_reference

    stt_opt = STATUTORY_RATES["STT_OPTIONS_PREMIUM"]
    assert stt_opt.rate == 0.001               # 0.10%
    assert stt_opt.levied_on == "SELL"
    assert stt_opt.tax_base == "PREMIUM"

    # Verify backwards compatible floats match specs
    assert STT_FUTURES_SELL == 0.0002
    assert STT_OPTIONS_PREMIUM_SELL == 0.001
    assert GST_RATE == 0.18
    assert DEFAULT_BROKERAGE_PER_ORDER == 20.0


def test_contract_specs_and_lot_sizes():
    """Verify derivative contract specs have SEBI rebalancing circular provenance."""
    nifty = CONTRACT_SPECS["NIFTY"]
    assert nifty.lot_size == 50
    assert nifty.freeze_qty == 1800
    assert nifty.exchange == "NSE"
    assert "NSE/FAOP/64795" in nifty.circular_reference

    banknifty = CONTRACT_SPECS["BANKNIFTY"]
    assert banknifty.lot_size == 15
    assert banknifty.freeze_qty == 900

    # Test dynamic get_lot_size
    assert get_lot_size("NIFTY") == 50
    assert get_lot_size("NSE:BANKNIFTY") == 15
    assert get_lot_size("CRUDEOIL") == 100
    assert get_lot_size("RELIANCE") == 1  # Cash stock unit lot


def test_dynamic_capital_tiers():
    """Verify dynamic tier scaler adjusts positions and reserves based on capital."""
    # Tier 1 (₹2 Lakhs)
    t1 = get_capital_tier(200_000)
    assert t1.tier_name == "TIER_1_RETAIL"
    assert t1.max_open_positions == 3
    assert t1.max_position_size_pct == 0.20
    assert get_dynamic_max_open_positions(200_000) == 3

    # Tier 2 (₹10 Lakhs)
    t2 = get_capital_tier(1_000_000)
    assert t2.tier_name == "TIER_2_PRO"
    assert t2.max_open_positions == 5
    assert t2.max_position_size_pct == 0.15
    assert get_dynamic_max_open_positions(1_000_000) == 5

    # Tier 3 (₹50 Lakhs)
    t3 = get_capital_tier(5_000_000)
    assert t3.tier_name == "TIER_3_INSTITUTIONAL"
    assert t3.max_open_positions == 8


def test_dual_key_live_security_gate():
    """Verify live order routing is blocked unless BOTH mode is LIVE and authorized is True."""
    # In standard research mode, live execution MUST be False
    if SYSTEM_MODE != "LIVE" or not LIVE_EXECUTION_AUTHORIZED:
        assert is_live_execution_permitted() is False


def test_unknown_symbol_observability():
    """Verify get_sector records diagnostics for unmapped symbols instead of silent swallowing."""
    initial_unmapped_count = len(get_unmapped_instruments())
    
    # Mapped symbol -> No unmapped event recorded
    assert get_sector("RELIANCE") == "OIL_GAS"
    assert len(get_unmapped_instruments()) == initial_unmapped_count

    # Unmapped symbol -> Records event into telemetry registry
    res = get_sector("UNKNOWN_EXPERIMENTAL_CO_2026")
    assert res == "DIVERSIFIED"
    assert len(get_unmapped_instruments()) == initial_unmapped_count + 1
    latest_event = get_unmapped_instruments()[-1]
    assert latest_event["symbol"] == "UNKNOWN_EXPERIMENTAL_CO_2026"
    assert latest_event["action"] == "FALLBACK_DIVERSIFIED"


def test_strategy_registry_complete():
    """Verify the legacy S01-S08 default subset (R1, 2026-09-03).

    `strategy/registry/__init__.py` is the ONLY inventory of record (S01-S18);
    these rows are a labeled legacy default subset pinned for historical lookup
    sites. This test proves the subset is internally consistent and that every
    module path resolves to a physical file — it does NOT claim to cover the
    registry-of-record, which the scanner drives independently.

    S09/S10 were removed 2026-09-18: they mapped to the production-dead
    `mjonai.options.*` package under names that never matched the registry.
    """
    assert len(ACTIVE_STRATEGIES) == 8
    assert "S08_IntradayAllDay" in ACTIVE_STRATEGIES
    assert "S01_MomentumRSI" in ACTIVE_STRATEGIES
    assert not [s for s in ACTIVE_STRATEGIES if s.startswith(("S09", "S10"))]

    # Legacy list and legacy map must agree with each other.
    assert set(STRATEGY_REGISTRY.keys()) <= set(ACTIVE_STRATEGIES)

    for strat_id, mod_path in STRATEGY_REGISTRY.items():
        assert strat_id in ACTIVE_STRATEGIES
        # No legacy mapping may target the retired options package.
        assert ".options" not in mod_path, f"{strat_id} points at dead package: {mod_path}"
        # Platform-neutral module path -> file path (forward slashes work
        # with pathlib on both Windows and Linux).
        rel_path = Path(*mod_path.split("."))
        full_path = root_dir / rel_path.with_suffix(".py")
        assert full_path.exists(), f"File missing: {full_path}"


def test_build_setup_hash_and_versioning():
    """Verify deterministic versioned setup hash with VIX range buckets."""
    h_low = build_setup_hash("RELIANCE", "S01_MomentumRSI", "ATR", "BULL", vix=12.5, candle_pattern="HAMMER")
    assert "RELIANCE" in h_low
    assert "LOW" in h_low
    assert "HAMMER" in h_low
    assert "V1" in h_low


def test_startup_sanity_validation():
    """Verify validate_configuration passes on default valid configuration."""
    # Should run with zero exceptions on valid configuration
    validate_configuration()

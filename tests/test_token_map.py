"""
Production-Level Test Suite for data/angelone/token_map.py
Tests Token Resolution, Case-Insensitive Normalization, Fallback Hierarchy,
Options Contract Matching, and WebSocket Subscription Formats.
"""

from datetime import date
from pathlib import Path
import pytest
import sys
from unittest.mock import patch, MagicMock

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent  # repo root (ADR-0008)
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from mjonai.data.angelone.token_map import (
    TOKEN_MAP,
    SYMBOL_MAP,
    OPTION_TOKEN_MAP,
    INDEX_TOKEN_MAP,
    LOT_SIZE_MAP,
    TICK_SIZE_MAP,
    WATCHLIST_TOKENS,
    _TOKEN_MAP_LOADED,
    get_token_for_symbol,
    get_symbol_for_token,
    get_index_token,
    get_option_token,
    get_lot_size,
    get_tick_size,
    sync_instrument_master,
    is_token_map_loaded,
    _normalize_symbol,
)
from mjonai.data.token_resolver import TokenResolver, BrokerType


def test_token_map_initialization_and_counts():
    """Verify token map initializes on import with NIFTY 500 symbols."""
    assert is_token_map_loaded() is True
    assert len(TOKEN_MAP) >= 400
    assert len(SYMBOL_MAP) >= 400
    assert WATCHLIST_TOKENS["exchangeType"] == 1
    assert len(WATCHLIST_TOKENS["tokens"]) >= 400


def test_case_insensitive_symbol_normalization():
    """Verify symbol normalization strips suffixes and handles case differences."""
    assert _normalize_symbol("reliance") == "RELIANCE"
    assert _normalize_symbol("RELIANCE.NS") == "RELIANCE"
    assert _normalize_symbol("TCS-EQ") == "TCS"
    assert _normalize_symbol(" infy ") == "INFY"


def test_two_way_symbol_and_token_lookups():
    """Verify two-way O(1) lookup works seamlessly for prominent index constituents."""
    test_symbol = "RELIANCE" if "RELIANCE" in SYMBOL_MAP else list(SYMBOL_MAP.keys())[0]
    token = get_token_for_symbol(test_symbol)
    assert token is not None
    assert isinstance(token, str)

    # Reverse lookup
    resolved_symbol = get_symbol_for_token(token)
    assert resolved_symbol == test_symbol

    # Case insensitivity check
    assert get_token_for_symbol(test_symbol.lower()) == token
    assert get_token_for_symbol(f"{test_symbol}.NS") == token


def test_index_spot_token_resolution():
    """Verify official spot index tokens (Nifty 50, Bank Nifty, FinNifty, India VIX)."""
    assert get_index_token("NIFTY") == "99926000"
    assert get_index_token("BANKNIFTY") == "99926009"
    assert get_index_token("FINNIFTY") == "99926037"
    assert get_index_token("INDIAVIX") == "99926017"
    assert get_token_for_symbol("NIFTY") == "99926000"


def test_lot_size_and_tick_size_helpers():
    """Verify lot size and tick size lookup functions."""
    LOT_SIZE_MAP["NIFTY"] = 65
    TICK_SIZE_MAP["NIFTY"] = 0.05

    assert get_lot_size("NIFTY") == 65
    assert get_tick_size("NIFTY") == 0.05


def test_unknown_symbol_returns_none():
    """Verify non-existent symbols return None without raising exceptions."""
    assert get_token_for_symbol("NON_EXISTENT_TICKER_XYZ") is None
    assert get_symbol_for_token("999999999999") is None


def test_dynamic_option_token_resolution():
    """Verify options token resolver formats keys and queries store accurately."""
    test_key = "NIFTY_27AUG2026_24500.0_CE"
    OPTION_TOKEN_MAP[test_key] = "998877"

    resolved = get_option_token("nifty", "27aug2026", 24500.0, "ce")
    assert resolved == "998877"

    # Non-existent option
    assert get_option_token("NIFTY", "27AUG2026", 30000.0, "PE") is None


def test_universal_token_resolver_gateway():
    """Verify generic multi-broker TokenResolver gateway."""
    assert TokenResolver.get_index_token("NIFTY", BrokerType.ANGELONE) == "99926000"
    assert TokenResolver.get_index_token("NIFTY", BrokerType.PAPER) == "99926000"

    test_symbol = list(SYMBOL_MAP.keys())[0]
    expected_token = SYMBOL_MAP[test_symbol]
    assert TokenResolver.get_token(test_symbol, BrokerType.ANGELONE) == expected_token
    assert TokenResolver.get_symbol(expected_token, BrokerType.ANGELONE) == test_symbol


def test_network_failure_falls_back_to_local_json_cache():
    """Fault Injection Test: Network failure during sync gracefully falls back to local JSON cache."""
    with patch("urllib.request.urlopen", side_effect=Exception("Connection Timeout")):
        result = sync_instrument_master(force=True, timeout_seconds=1)
        assert result is True
        assert len(TOKEN_MAP) > 0
        assert is_token_map_loaded() is True


def test_atm_strike_calculation():
    """Verify ATM strike calculation accurately rounds to standard exchange steps."""
    from mjonai.data.angelone.token_map import get_atm_strike

    # NIFTY step is 50.0
    assert get_atm_strike("NIFTY", 24532.5) == 24550.0
    assert get_atm_strike("NIFTY", 24524.9) == 24500.0

    # BANKNIFTY step is 100.0
    assert get_atm_strike("BANKNIFTY", 51249.0) == 51200.0
    assert get_atm_strike("BANKNIFTY", 51251.0) == 51300.0

    # MIDCPNIFTY step is 25.0
    assert get_atm_strike("MIDCPNIFTY", 12115.0) == 12125.0


def test_option_chain_tokens_ladder():
    """Verify option chain token ladder generation for ATM + 5 ITM/OTM strikes."""
    from mjonai.data.angelone.token_map import get_option_chain_tokens
    import mjonai.data.angelone.token_map as tm_mod
    # Populate dummy tokens for testing
    tm_mod.OPTION_TOKEN_MAP["NIFTY_27AUG2026_24550.0_CE"] = "111000"
    tm_mod.OPTION_TOKEN_MAP["NIFTY_27AUG2026_24550.0_PE"] = "111001"
    tm_mod.OPTION_TOKEN_MAP["NIFTY_27AUG2026_24600.0_CE"] = "111002"
    tm_mod.OPTION_TOKEN_MAP["NIFTY_27AUG2026_24500.0_PE"] = "111003"

    chain = get_option_chain_tokens(
        underlying="NIFTY",
        expiry_str="27AUG2026",
        spot_price=24535.0,
        num_strikes=2,
    )

    assert chain["underlying"] == "NIFTY"
    assert chain["atm_strike"] == 24550.0
    assert chain["strike_interval"] == 50.0
    assert len(chain["strikes"]) == 5  # -2, -1, 0, +1, +2
    assert "111000" in chain["tokens_to_stream"]
    assert "111001" in chain["tokens_to_stream"]


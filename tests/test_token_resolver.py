"""
Unit & Boundary Integration Tests for data/token_resolver.py
Universal Multi-Broker Instrument Token Resolution Gateway.
"""

from pathlib import Path
import sys
from unittest.mock import MagicMock, patch
import pytest

# Ensure workspace root is in sys.path
_root_dir = Path(__file__).resolve().parent.parent  # repo root (ADR-0008)
if str(_root_dir) not in sys.path:
    sys.path.insert(0, str(_root_dir))

from mjonai.data.token_resolver import (
    BrokerType,
    InstrumentType,
    InstrumentContract,
    TokenResolver,
    register_broker_token_resolver,
    register_broker_symbol_resolver,
    register_broker_contract_resolver,
    reset_custom_resolvers,
)


@pytest.fixture(autouse=True)
def clean_registry():
    """Ensure clean custom broker adapter registry between tests."""
    reset_custom_resolvers()
    yield
    reset_custom_resolvers()


# ── 1. ENUMS & DATA CONTRACT TESTS ───────────────────────────────────────────

def test_broker_and_instrument_enums():
    assert BrokerType.ANGELONE.value == "ANGELONE"
    assert BrokerType.SHOONYA.value == "SHOONYA"
    assert BrokerType.ZERODHA.value == "ZERODHA"
    assert BrokerType.PAPER.value == "PAPER"

    assert InstrumentType.EQUITY.value == "EQUITY"
    assert InstrumentType.INDEX.value == "INDEX"
    assert InstrumentType.OPTION.value == "OPTION"
    assert InstrumentType.FUTURE.value == "FUTURE"


def test_instrument_contract_contract():
    contract = InstrumentContract(
        symbol="RELIANCE",
        token="2885",
        exchange="NSE",
        broker=BrokerType.ANGELONE,
        instrument_type=InstrumentType.EQUITY,
        lot_size=1,
        tick_size=0.05,
        is_tradable=True,
    )
    assert contract.symbol == "RELIANCE"
    assert contract.token == "2885"
    assert contract["token"] == "2885"
    assert contract.get("exchange") == "NSE"
    assert contract.get("non_existent", "DEFAULT") == "DEFAULT"

    d = contract.to_dict()
    assert isinstance(d, dict)
    assert d["symbol"] == "RELIANCE"
    assert d["broker"] == "ANGELONE"
    assert d["lot_size"] == 1


# ── 2. TOKEN RESOLVER CORE METHODS ───────────────────────────────────────────

def test_get_token_digits_passthrough():
    # Digits pass through without looking up maps
    assert TokenResolver.get_token("2885") == "2885"
    assert TokenResolver.get_token(" 99926004 ") == "99926004"
    assert TokenResolver.get_token("") is None


@patch("mjonai.data.token_resolver._angel_get_token")
def test_get_token_angel_and_paper(mock_angel_token):
    mock_angel_token.return_value = "2885"

    t1 = TokenResolver.get_token("RELIANCE", broker=BrokerType.ANGELONE, exchange="NSE")
    assert t1 == "2885"
    mock_angel_token.assert_called_with("RELIANCE", exchange="NSE")

    t2 = TokenResolver.get_token("RELIANCE", broker=BrokerType.PAPER, exchange="NSE")
    assert t2 == "2885"


@patch("mjonai.data.token_resolver._angel_get_token")
def test_get_tokens_bulk_vector_resolution(mock_angel_token):
    mock_angel_token.side_effect = lambda sym, exchange="NSE": "101" if sym == "INFY" else ("102" if sym == "TCS" else None)

    bulk = TokenResolver.get_tokens_bulk(["INFY", "TCS", "UNKNOWN"], broker=BrokerType.ANGELONE)
    assert len(bulk) == 3
    assert bulk["INFY"] == "101"
    assert bulk["TCS"] == "102"
    assert bulk["UNKNOWN"] is None


@patch("mjonai.data.token_resolver._angel_get_symbol")
def test_get_symbol_reverse_lookup(mock_angel_symbol):
    mock_angel_symbol.return_value = "RELIANCE"

    assert TokenResolver.get_symbol("2885", broker=BrokerType.ANGELONE) == "RELIANCE"
    assert TokenResolver.get_symbol("2885", broker=BrokerType.PAPER) == "RELIANCE"
    assert TokenResolver.get_symbol("") is None


@patch("mjonai.data.token_resolver._angel_get_index_token")
def test_get_index_token(mock_angel_index):
    mock_angel_index.return_value = "99926000"

    assert TokenResolver.get_index_token("NIFTY") == "99926000"
    assert TokenResolver.get_index_token("") is None


@patch("mjonai.data.token_resolver._angel_get_option_token")
def test_get_option_token(mock_angel_option):
    mock_angel_option.return_value = "45210"

    tok = TokenResolver.get_option_token("NIFTY", "28AUG26", 24500.0, "CE")
    assert tok == "45210"
    mock_angel_option.assert_called_with("NIFTY", "28AUG26", 24500.0, "CE")


@patch("mjonai.data.token_resolver._angel_get_atm_strike")
def test_get_atm_strike(mock_angel_atm):
    mock_angel_atm.return_value = 24850.0
    assert TokenResolver.get_atm_strike("NIFTY", 24862.30) == 24850.0
    mock_angel_atm.assert_called_with("NIFTY", 24862.30)


@patch("mjonai.data.token_resolver._angel_get_option_chain_tokens")
def test_get_option_chain_tokens(mock_angel_chain):
    mock_angel_chain.return_value = {
        "underlying": "NIFTY",
        "atm_strike": 24850.0,
        "strikes": [
            {"strike": 24800.0, "ce_token": "1001", "pe_token": "1002"},
            {"strike": 24850.0, "ce_token": "1003", "pe_token": "1004"},
        ],
        "tokens": ["1001", "1002", "1003", "1004"],
    }
    chain = TokenResolver.get_option_chain_tokens("NIFTY", "28AUG26", 24850.0, num_strikes=2)
    assert isinstance(chain, dict)
    assert chain["underlying"] == "NIFTY"
    assert len(chain["strikes"]) == 2
    assert chain["strikes"][0]["strike"] == 24800.0


# ── 3. MULTI-BROKER CUSTOM ADAPTER TESTS ─────────────────────────────────────

def test_custom_broker_adapter_registration():
    # 1. Custom Shoonya Token Resolver
    def shoonya_token_resolver(symbol: str, exchange: str = "NSE") -> str:
        if symbol == "RELIANCE":
            return "SHOONYA_2885"
        return ""

    register_broker_token_resolver(BrokerType.SHOONYA, shoonya_token_resolver)
    assert TokenResolver.get_token("RELIANCE", broker=BrokerType.SHOONYA) == "SHOONYA_2885"

    # Unregistered broker logs warning and returns None
    assert TokenResolver.get_token("RELIANCE", broker=BrokerType.ZERODHA) is None

    # 2. Custom Shoonya Reverse Symbol Resolver
    def shoonya_symbol_resolver(token: str, exchange: str = "NSE") -> str:
        if token == "SHOONYA_2885":
            return "RELIANCE"
        return ""

    register_broker_symbol_resolver(BrokerType.SHOONYA, shoonya_symbol_resolver)
    assert TokenResolver.get_symbol("SHOONYA_2885", broker=BrokerType.SHOONYA) == "RELIANCE"


def test_translate_symbol_cross_broker():
    # Same broker returns identical symbol
    assert TokenResolver.translate_symbol("RELIANCE", BrokerType.ANGELONE, BrokerType.ANGELONE) == "RELIANCE"

    # Strips prefixes/suffixes across brokers
    assert TokenResolver.translate_symbol("NSE:RELIANCE-EQ", BrokerType.ZERODHA, BrokerType.ANGELONE) == "RELIANCE"
    assert TokenResolver.translate_symbol("TCS.NS", BrokerType.INTERACTIVE_BROKERS, BrokerType.ANGELONE) == "TCS"


@patch("mjonai.data.token_resolver._angel_get_token")
@patch("mjonai.data.token_resolver._angel_get_lot_size")
@patch("mjonai.data.token_resolver._angel_get_tick_size")
def test_get_contract_resolution(mock_tick, mock_lot, mock_token):
    mock_token.return_value = "2885"
    mock_lot.return_value = 1
    mock_tick.return_value = 0.05

    contract = TokenResolver.get_contract("RELIANCE", broker=BrokerType.ANGELONE, exchange="NSE")
    assert contract is not None
    assert isinstance(contract, InstrumentContract)
    assert contract.symbol == "RELIANCE"
    assert contract.token == "2885"
    assert contract.exchange == "NSE"
    assert contract.instrument_type == InstrumentType.EQUITY
    assert contract.lot_size == 1
    assert contract.tick_size == 0.05


@patch("mjonai.data.token_resolver._angel_get_token")
@patch("mjonai.data.token_resolver._angel_get_lot_size")
@patch("mjonai.data.token_resolver._angel_get_tick_size")
def test_get_contract_derivative_beats_index_substring(mock_tick, mock_lot, mock_token):
    """P0-DATA-3: exchange/suffix must win over the underlying-name
    substring — NIFTY derivatives are not the index. (get_contract has no
    production callers yet; this pins the classifier for future use.)"""
    mock_token.return_value = "OPT123"
    mock_lot.return_value = 25
    mock_tick.return_value = 0.05

    opt = TokenResolver.get_contract("NIFTY24OCT24500CE", broker=BrokerType.ANGELONE, exchange="NFO")
    assert opt is not None and opt.instrument_type == InstrumentType.OPTION

    mock_token.return_value = "FUT123"
    fut = TokenResolver.get_contract("NIFTY24OCTFUT", broker=BrokerType.ANGELONE, exchange="NFO")
    assert fut is not None and fut.instrument_type == InstrumentType.FUTURE

    mock_token.return_value = "99926000"
    idx = TokenResolver.get_contract("NIFTY", broker=BrokerType.ANGELONE, exchange="NSE")
    assert idx is not None and idx.instrument_type == InstrumentType.INDEX

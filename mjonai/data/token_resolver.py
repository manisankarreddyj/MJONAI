"""
Module: data/token_resolver.py
Purpose: Universal Multi-Broker Instrument & Security Token Resolver Gateway.
         Decouples trading strategies, risk engines, and execution routers from
         broker-specific token formats and symbology conventions.
         Supports primary broker (AngelOne), failover brokers (Shoonya / Finvasia, Zerodha, Dhan, Fyers, IBKR),
         and simulated Paper trading environments (TD-013).

Architectural Principles:
  1. Universal Abstraction: Strategies call `TokenResolver.get_token("RELIANCE")` without broker lock-in.
  2. Multi-Broker Failover Ready (TD-013): Pluggable broker adapter registry for seamless runtime switching.
  3. High-Throughput Vector Resolution: `get_tokens_bulk()` for universe breadth and sector scanning.
  4. Rich Instrument Contract Metadata: Type-safe `InstrumentContract` representation across all asset classes.
  5. Multi-Exchange Option Chains: Native resolution for NSE, NFO, BSE, BFO (Sensex), MCX, and CDS.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging
from pathlib import Path
import sys
import threading
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

# Ensure workspace root is in sys.path
_root_dir = Path(__file__).resolve().parent.parent
if str(_root_dir) not in sys.path:
    sys.path.insert(0, str(_root_dir))

from mjonai.data.angelone.token_map import (
    get_token_for_symbol as _angel_get_token,
    get_symbol_for_token as _angel_get_symbol,
    get_option_token as _angel_get_option_token,
    get_index_token as _angel_get_index_token,
    get_atm_strike as _angel_get_atm_strike,
    get_option_chain_tokens as _angel_get_option_chain_tokens,
    get_lot_size as _angel_get_lot_size,
    get_tick_size as _angel_get_tick_size,
    INDEX_TOKEN_MAP,
)

logger = logging.getLogger(__name__)


# ── 1. ENUMS & DATA CONTRACTS ────────────────────────────────────────────────

class BrokerType(str, Enum):
    """Supported Broker Environments & Adapters."""
    ANGELONE            = "ANGELONE"
    SHOONYA             = "SHOONYA"              # Finvasia backup broker (TD-013)
    ZERODHA             = "ZERODHA"              # Kite Connect adapter
    DHAN                = "DHAN"                 # DhanHQ API adapter
    FYERS               = "FYERS"                # Fyers Data & Order API
    INTERACTIVE_BROKERS = "INTERACTIVE_BROKERS"  # Global Multi-Asset & US Equities
    PAPER               = "PAPER"                # Local In-Memory Paper Execution


class InstrumentType(str, Enum):
    """Institutional Instrument Asset Class Classification."""
    EQUITY    = "EQUITY"
    INDEX     = "INDEX"
    OPTION    = "OPTION"
    FUTURE    = "FUTURE"
    COMMODITY = "COMMODITY"
    CURRENCY  = "CURRENCY"


@dataclass(frozen=True)
class InstrumentContract:
    """
    Unified immutable instrument contract specification.
    Provides complete execution metadata across all brokers and exchanges.
    """
    symbol: str
    token: str
    exchange: str = "NSE"
    broker: BrokerType = BrokerType.ANGELONE
    instrument_type: InstrumentType = InstrumentType.EQUITY
    lot_size: int = 1
    tick_size: float = 0.05
    strike_price: Optional[float] = None
    expiry_date: Optional[str] = None
    option_type: Optional[str] = None  # "CE" or "PE"
    freeze_limit: Optional[int] = None
    is_tradable: bool = True

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)

    def get(self, item: str, default: Any = None) -> Any:
        return getattr(self, item, default)

    def to_dict(self) -> Dict[str, Any]:
        """Convert instrument contract to dictionary."""
        return {
            "symbol": self.symbol,
            "token": self.token,
            "exchange": self.exchange,
            "broker": self.broker.value,
            "instrument_type": self.instrument_type.value,
            "lot_size": self.lot_size,
            "tick_size": self.tick_size,
            "strike_price": self.strike_price,
            "expiry_date": self.expiry_date,
            "option_type": self.option_type,
            "freeze_limit": self.freeze_limit,
            "is_tradable": self.is_tradable,
        }


# ── 2. PLUGGABLE MULTI-BROKER ADAPTER REGISTRY ───────────────────────────────

_CUSTOM_TOKEN_RESOLVERS: Dict[BrokerType, Callable[[str, str], Optional[str]]] = {}
_CUSTOM_SYMBOL_RESOLVERS: Dict[BrokerType, Callable[[str, str], Optional[str]]] = {}
_CUSTOM_CONTRACT_RESOLVERS: Dict[BrokerType, Callable[[str, str], Optional[InstrumentContract]]] = {}
_registry_lock = threading.Lock()


def register_broker_token_resolver(
    broker: BrokerType,
    resolver_fn: Callable[[str, str], Optional[str]]
) -> None:
    """Register custom symbol-to-token resolver function for a secondary broker."""
    with _registry_lock:
        _CUSTOM_TOKEN_RESOLVERS[broker] = resolver_fn
    logger.info(f"[token_resolver] Registered custom token resolver for broker: {broker.value}")


def register_broker_symbol_resolver(
    broker: BrokerType,
    resolver_fn: Callable[[str, str], Optional[str]]
) -> None:
    """Register custom token-to-symbol reverse resolver function for a secondary broker."""
    with _registry_lock:
        _CUSTOM_SYMBOL_RESOLVERS[broker] = resolver_fn
    logger.info(f"[token_resolver] Registered custom symbol resolver for broker: {broker.value}")


def register_broker_contract_resolver(
    broker: BrokerType,
    resolver_fn: Callable[[str, str], Optional[InstrumentContract]]
) -> None:
    """Register custom full contract resolver function for a secondary broker."""
    with _registry_lock:
        _CUSTOM_CONTRACT_RESOLVERS[broker] = resolver_fn
    logger.info(f"[token_resolver] Registered custom contract resolver for broker: {broker.value}")


def reset_custom_resolvers() -> None:
    """Clear all dynamically registered custom broker resolvers (useful for test teardowns)."""
    with _registry_lock:
        _CUSTOM_TOKEN_RESOLVERS.clear()
        _CUSTOM_SYMBOL_RESOLVERS.clear()
        _CUSTOM_CONTRACT_RESOLVERS.clear()


# ── 3. UNIVERSAL TOKEN RESOLVER GATEWAY ──────────────────────────────────────

class TokenResolver:
    """
    Universal Instrument Token Resolver Gateway.
    Strategies and execution routers query this gateway to resolve security tokens and contract specs.
    """

    @staticmethod
    def get_token(
        symbol: str,
        broker: BrokerType = BrokerType.ANGELONE,
        exchange: str = "NSE"
    ) -> Optional[str]:
        """
        Resolve security token for a given symbol, broker, and exchange.
        Pass-through: If an integer token string is passed, returns it directly.
        """
        if not symbol:
            return None

        clean_sym = symbol.strip()
        if clean_sym.isdigit():
            return clean_sym

        # S8 (canonical verification wave 2026-09-03): an explicitly
        # registered custom resolver takes precedence over any built-in
        # map — registration must never be a silent no-op.
        with _registry_lock:
            resolver = _CUSTOM_TOKEN_RESOLVERS.get(broker)

        if resolver:
            try:
                return resolver(clean_sym, exchange)
            except Exception as e:
                logger.warning(f"[token_resolver] Custom resolver failed for {broker.value}:{clean_sym}: {e}")
                return None

        if broker in (BrokerType.ANGELONE, BrokerType.PAPER):
            return _angel_get_token(clean_sym, exchange=exchange)

        if broker == BrokerType.SHOONYA:
            from mjonai.data.shoonya.token_map import get_token_for_symbol as _shoonya_get_token
            return _shoonya_get_token(clean_sym, exchange=exchange)

        logger.warning(f"[token_resolver] No token resolver for broker: {broker.value} (no built-in map, none registered)")
        return None

    @staticmethod
    def get_tokens_bulk(
        symbols: List[str],
        broker: BrokerType = BrokerType.ANGELONE,
        exchange: str = "NSE"
    ) -> Dict[str, Optional[str]]:
        """
        High-throughput batch resolution of security tokens for a list of symbols.
        Essential for market breadth, index constituents, and sector momentum scanners.
        """
        results: Dict[str, Optional[str]] = {}
        for sym in symbols:
            results[sym] = TokenResolver.get_token(sym, broker=broker, exchange=exchange)
        return results

    @staticmethod
    def get_symbol(
        token: str,
        broker: BrokerType = BrokerType.ANGELONE,
        exchange: str = "NSE"
    ) -> Optional[str]:
        """
        Reverse lookup: resolve canonical symbol name from broker instrument token.
        """
        if not token:
            return None

        clean_token = token.strip()
        # S8 (canonical verification wave 2026-09-03): an explicitly
        # registered custom reverse resolver takes precedence over any
        # built-in map — registration must never be a silent no-op
        # (mirror of the get_token fix).
        with _registry_lock:
            resolver = _CUSTOM_SYMBOL_RESOLVERS.get(broker)

        if resolver:
            try:
                return resolver(clean_token, exchange)
            except Exception as e:
                logger.warning(f"[token_resolver] Custom reverse resolver failed for {broker.value}:{clean_token}: {e}")
                return None

        if broker in (BrokerType.ANGELONE, BrokerType.PAPER):
            return _angel_get_symbol(clean_token, exchange=exchange)

        if broker == BrokerType.SHOONYA:
            from mjonai.data.shoonya.token_map import get_symbol_for_token as _shoonya_get_symbol
            return _shoonya_get_symbol(clean_token, exchange=exchange)

        return None

    @staticmethod
    def get_index_token(
        index_name: str,
        broker: BrokerType = BrokerType.ANGELONE
    ) -> Optional[str]:
        """
        Resolve spot index token (e.g. 'NIFTY', 'BANKNIFTY', 'FINNIFTY', 'MIDCPNIFTY', 'SENSEX', 'INDIAVIX').
        """
        if not index_name:
            return None

        if broker in (BrokerType.ANGELONE, BrokerType.PAPER):
            return _angel_get_index_token(index_name)

        if broker == BrokerType.SHOONYA:
            from mjonai.data.shoonya.token_map import get_token_for_symbol as _shoonya_get_token
            return _shoonya_get_token(index_name, exchange="NSE")

        return TokenResolver.get_token(index_name, broker=broker, exchange="NSE")

    @staticmethod
    def get_option_token(
        underlying: str,
        expiry_str: str,
        strike_price: float,
        option_type: str,
        broker: BrokerType = BrokerType.ANGELONE,
        exchange: str = "NFO"
    ) -> Optional[str]:
        """
        Resolve live option contract strike token across NFO, BFO (Sensex), and MCX options.
        """
        if broker in (BrokerType.ANGELONE, BrokerType.PAPER):
            return _angel_get_option_token(underlying, expiry_str, strike_price, option_type)

        if broker == BrokerType.SHOONYA:
            from mjonai.data.shoonya.token_map import get_option_token as _shoonya_get_option_token
            return _shoonya_get_option_token(underlying, expiry_str, strike_price, option_type)

        return None

    @staticmethod
    def get_atm_strike(
        underlying: str,
        spot_price: float,
        broker: BrokerType = BrokerType.ANGELONE
    ) -> float:
        """
        Calculate mathematical At-The-Money (ATM) strike price rounded to instrument step size.
        """
        return _angel_get_atm_strike(underlying, spot_price)

    @staticmethod
    def get_option_chain_tokens(
        underlying: str,
        expiry_str: str,
        spot_price: float,
        num_strikes: int = 5,
        broker: BrokerType = BrokerType.ANGELONE
    ) -> Dict[str, Any]:
        """
        High-throughput multi-strike ladder generation (ITM, ATM, OTM strikes).
        Returns a dictionary containing underlying, atm_strike, strikes ladder, and tokens list.
        """
        if broker in (BrokerType.ANGELONE, BrokerType.PAPER):
            return _angel_get_option_chain_tokens(underlying, expiry_str, spot_price, num_strikes=num_strikes)
        return {}

    @staticmethod
    def translate_symbol(
        symbol: str,
        from_broker: BrokerType,
        to_broker: BrokerType,
        exchange: str = "NSE"
    ) -> str:
        """
        Translate symbol notation between broker conventions during failover execution.
        """
        if from_broker == to_broker:
            return symbol

        # Canonical normalization
        clean = symbol.strip().upper()
        clean = clean.replace("NSE:", "").replace("BSE:", "").replace("-EQ", "").replace(".NS", "").replace(".BO", "")
        return clean

    @staticmethod
    def get_lot_size(
        symbol: str,
        broker: BrokerType = BrokerType.ANGELONE
    ) -> int:
        """
        Resolve live market lot size for an instrument. Defaults to 1 for cash equity.
        """
        if broker in (BrokerType.ANGELONE, BrokerType.PAPER):
            lot = _angel_get_lot_size(symbol)
            return lot if lot is not None and lot > 0 else 1

        return 1

    @staticmethod
    def get_tick_size(
        symbol: str,
        broker: BrokerType = BrokerType.ANGELONE
    ) -> float:
        """
        Resolve minimum tick size for an instrument. Defaults to 0.05.
        """
        if broker in (BrokerType.ANGELONE, BrokerType.PAPER):
            tick = _angel_get_tick_size(symbol)
            return tick if tick is not None and tick > 0 else 0.05

        return 0.05

    @staticmethod
    def get_contract(
        symbol_or_token: str,
        broker: BrokerType = BrokerType.ANGELONE,
        exchange: str = "NSE"
    ) -> Optional[InstrumentContract]:
        """
        Resolve full type-safe InstrumentContract metadata representation.
        """
        if not symbol_or_token:
            return None

        clean_input = symbol_or_token.strip()

        # 1. Check custom broker contract resolver
        with _registry_lock:
            custom_resolver = _CUSTOM_CONTRACT_RESOLVERS.get(broker)
        if custom_resolver:
            contract = custom_resolver(clean_input, exchange)
            if contract:
                return contract

        # 2. Standard AngelOne / Paper resolution path
        if clean_input.isdigit():
            token = clean_input
            symbol = TokenResolver.get_symbol(token, broker=broker, exchange=exchange) or token
        else:
            symbol = clean_input
            token = TokenResolver.get_token(symbol, broker=broker, exchange=exchange)

        if not token:
            return None

        # Determine instrument type.
        # P0-DATA-3: the exchange leg MUST come before the underlying-name
        # substring — the old order classified every NIFTY/SENSEX derivative
        # (e.g. NIFTY24OCT24500CE, NIFTY24OCTFUT) as INDEX because "NIFTY"
        # appears in the symbol. Exchange is authoritative for F&O; the
        # digit-plus-suffix rule catches derivative symbols mistagged to
        # NSE (the digit guard matters: RELIANCE ends in "CE" but is equity).
        import re as _re

        upper_sym = symbol.upper()
        if exchange.upper() in ("NFO", "BFO"):
            inst_type = InstrumentType.OPTION if ("CE" in upper_sym or "PE" in upper_sym) else InstrumentType.FUTURE
        elif _re.search(r"\d(CE|PE)$", upper_sym):
            inst_type = InstrumentType.OPTION
        elif upper_sym in INDEX_TOKEN_MAP or "NIFTY" in upper_sym or "SENSEX" in upper_sym:
            inst_type = InstrumentType.INDEX
        elif exchange.upper() == "MCX":
            inst_type = InstrumentType.COMMODITY
        elif exchange.upper() == "CDS":
            inst_type = InstrumentType.CURRENCY
        else:
            inst_type = InstrumentType.EQUITY

        lot = TokenResolver.get_lot_size(symbol, broker=broker)
        tick = TokenResolver.get_tick_size(symbol, broker=broker)

        return InstrumentContract(
            symbol=symbol,
            token=token,
            exchange=exchange.upper(),
            broker=broker,
            instrument_type=inst_type,
            lot_size=lot,
            tick_size=tick,
            is_tradable=True,
        )


# ── 4. SELF-DIAGNOSTIC DEMONSTRATION HARNESS ─────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("===================================================================")
    print("MJONAI UNIVERSAL MULTI-BROKER TOKEN RESOLVER GATEWAY")
    print("===================================================================")

    # 1. Direct Resolution
    nifty_tok = TokenResolver.get_index_token("NIFTY")
    reliance_tok = TokenResolver.get_token("RELIANCE", exchange="NSE")
    print(f"Index Token (NIFTY)       : {nifty_tok}")
    print(f"Equity Token (RELIANCE)   : {reliance_tok}")

    # 2. Reverse Lookup
    if reliance_tok:
        rev_sym = TokenResolver.get_symbol(reliance_tok, exchange="NSE")
        print(f"Reverse Lookup ({reliance_tok}) : {rev_sym}")

    # 3. Vector Batch Resolution
    batch_symbols = ["NIFTY 50", "RELIANCE", "TCS", "INFY", "HDFCBANK"]
    bulk = TokenResolver.get_tokens_bulk(batch_symbols, exchange="NSE")
    print("-------------------------------------------------------------------")
    print("BULK VECTOR TOKEN RESOLUTION:")
    for sym, tok in bulk.items():
        print(f"  - {sym:<12} -> Token: {tok}")

    # 4. Rich Contract Resolution
    contract = TokenResolver.get_contract("RELIANCE", exchange="NSE")
    print("-------------------------------------------------------------------")
    print("INSTRUMENT CONTRACT SPECIFICATION:")
    if contract:
        print(f"  - Symbol       : {contract.symbol}")
        print(f"  - Token        : {contract.token}")
        print(f"  - Exchange     : {contract.exchange}")
        print(f"  - Asset Class  : {contract.instrument_type.value}")
        print(f"  - Lot Size     : {contract.lot_size}")
        print(f"  - Tick Size    : {contract.tick_size}")
        print(f"  - Tradable     : {contract.is_tradable}")
    print("===================================================================")

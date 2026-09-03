"""
Module: data/feed_manager.py
Purpose: Universal Multi-Asset Real-Time Live Feed Manager Gateway.
         Single Source of Truth for live streaming ticks across all asset classes:
         - Indian Cash Equities & F&O Options (NSE / NFO / BSE / BFO / MCX via AngelOne & Shoonya)
         - Commodities (MCX) & Currency (CDS)
         - US Equities (US_EQUITY via Interactive Brokers / Alpaca / Polygon)
         - Crypto 24/7 (CRYPTO via Binance / Coinbase)

Architectural Principles:
  1. Unified Gateway: Strategies query `LiveFeedManager.get_price("RELIANCE")` without broker lock-in.
  2. Multi-Asset Extensibility: Dynamic plug-and-play driver registration for foreign & 24/7 markets.
  3. Microsecond Hot Path: Direct sub-microsecond in-memory lookups with thread-safe atomic snapshots.
  4. Top-of-Book Microstructure: Real-time Bid-Ask spreads, order book depth, and Order Flow Imbalance.
  5. High-Throughput Vector Queries: `get_prices_bulk()` for high-speed universe breadth calculations.
"""

from dataclasses import dataclass, field
from datetime import datetime
import logging
from pathlib import Path
import sys
import threading
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

# Ensure workspace root is in sys.path when executed directly
_root_dir = Path(__file__).resolve().parent.parent
if str(_root_dir) not in sys.path:
    sys.path.insert(0, str(_root_dir))

from core.time_utils import Exchange, now_ist
from data.angelone.websocket import (
    get_live_price as _angel_get_price,
    get_live_volume as _angel_get_volume,
    get_live_oi as _angel_get_oi,
    get_live_quote as _angel_get_quote,
    get_live_depth as _angel_get_depth,
    get_live_spread as _angel_get_spread,
    get_token_staleness as _angel_get_staleness,
    is_websocket_healthy as _angel_is_healthy,
    get_websocket_stats as _angel_get_stats,
    clear_tick_caches as _angel_clear_caches,
)
from data.angelone.historical import (
    fetch_historical_candles as _angel_fetch_candles,
    CandleInterval,
)
from data.token_resolver import TokenResolver, BrokerType

logger = logging.getLogger(__name__)


# ── 1. UNIFIED LIVE QUOTE CONTRACT ───────────────────────────────────────────

@dataclass(frozen=True)
class LiveQuoteSnapshot:
    """
    Unified immutable live quote representation across all exchanges and asset classes.
    """
    symbol: str
    token: Optional[str] = None
    exchange: str = "NSE"
    ltp: float = 0.0
    volume: Optional[int] = None
    oi: Optional[int] = None
    vwap: Optional[float] = None
    best_bid: Optional[float] = None
    best_ask: Optional[float] = None
    spread_bps: Optional[float] = None
    order_imbalance_ratio: Optional[float] = None
    timestamp: Optional[datetime] = None
    staleness_seconds: Optional[float] = None

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)

    def get(self, item: str, default: Any = None) -> Any:
        return getattr(self, item, default)

    def to_dict(self) -> Dict[str, Any]:
        """Convert quote snapshot to dictionary."""
        return {
            "symbol": self.symbol,
            "token": self.token,
            "exchange": self.exchange,
            "ltp": self.ltp,
            "volume": self.volume,
            "oi": self.oi,
            "vwap": self.vwap,
            "best_bid": self.best_bid,
            "best_ask": self.best_ask,
            "spread_bps": self.spread_bps,
            "order_imbalance_ratio": self.order_imbalance_ratio,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "staleness_seconds": self.staleness_seconds,
        }


# ── 2. MULTI-ASSET REGISTRY & CUSTOM PROVIDERS ──────────────────────────────

# Multi-Asset Live Tick Storage for Non-Indian / Custom Feeds
_MULTI_ASSET_PRICES: Dict[str, float] = {}
_MULTI_ASSET_VOLUMES: Dict[str, int] = {}
_MULTI_ASSET_OI: Dict[str, int] = {}
_MULTI_ASSET_VWAP: Dict[str, float] = {}
_MULTI_ASSET_DEPTH: Dict[str, Dict[str, Any]] = {}
_MULTI_ASSET_TIMESTAMPS: Dict[str, datetime] = {}
_feed_lock = threading.RLock()

# Custom Feed Provider Registry (e.g. US Equity / Crypto WebSockets)
_CUSTOM_FEED_PROVIDERS: Dict[Exchange, Callable[[str], Optional[Dict[str, Any]]]] = {}


def register_feed_provider(exchange: Exchange, provider_fn: Callable[[str], Optional[Dict[str, Any]]]) -> None:
    """Register custom real-time streaming feed provider for global assets (e.g. US_EQUITY, CRYPTO)."""
    _CUSTOM_FEED_PROVIDERS[exchange] = provider_fn
    logger.info(f"[feed_manager] Registered real-time live feed provider for exchange: {exchange.value}")


def update_multi_asset_tick(
    symbol: str,
    ltp: float,
    volume: Optional[int] = None,
    oi: Optional[int] = None,
    vwap: Optional[float] = None,
    best_bid: Optional[float] = None,
    best_ask: Optional[float] = None,
    timestamp: Optional[datetime] = None
) -> None:
    """
    Ingest live tick from non-Indian or custom multi-asset streaming connections (e.g. Crypto/US Equities).
    """
    sym_key = symbol.strip().upper()
    if ltp <= 0.0:
        return
    ts = timestamp or now_ist()
    with _feed_lock:
        _MULTI_ASSET_PRICES[sym_key] = ltp
        if volume is not None:
            _MULTI_ASSET_VOLUMES[sym_key] = volume
        if oi is not None:
            _MULTI_ASSET_OI[sym_key] = oi
        if vwap is not None:
            _MULTI_ASSET_VWAP[sym_key] = vwap
        if best_bid is not None and best_ask is not None:
            _MULTI_ASSET_DEPTH[sym_key] = {
                "best_bid": best_bid,
                "best_ask": best_ask,
            }
        _MULTI_ASSET_TIMESTAMPS[sym_key] = ts


def clear_multi_asset_ticks() -> None:
    """Clear all in-memory custom and multi-asset streaming ticks (used for session rollover & testing)."""
    with _feed_lock:
        _MULTI_ASSET_PRICES.clear()
        _MULTI_ASSET_VOLUMES.clear()
        _MULTI_ASSET_OI.clear()
        _MULTI_ASSET_VWAP.clear()
        _MULTI_ASSET_DEPTH.clear()
        _MULTI_ASSET_TIMESTAMPS.clear()


def get_multi_asset_ticks_count() -> int:
    """Return number of custom/multi-asset symbols currently cached in memory."""
    with _feed_lock:
        return len(_MULTI_ASSET_PRICES)


# ── 3. UNIFIED LIVE FEED MANAGER GATEWAY ─────────────────────────────────────

class LiveFeedManager:
    """
    Unified Multi-Asset Live Feed Gateway.
    Decouples strategies and risk sentries from broker-specific WebSocket implementations.
    """

    @staticmethod
    def _resolve_token(
        symbol_or_token: str,
        exch_enum: Exchange,
        broker: BrokerType = BrokerType.ANGELONE
    ) -> Optional[str]:
        """Internal helper to resolve symbol to token with exchange awareness."""
        if symbol_or_token.isdigit():
            return symbol_or_token
        return TokenResolver.get_token(symbol_or_token, broker=broker, exchange=exch_enum.value)

    @staticmethod
    def get_price(
        symbol_or_token: str,
        exchange: Union[Exchange, str] = Exchange.NSE,
        broker: BrokerType = BrokerType.ANGELONE,
        max_staleness_seconds: Optional[float] = None,
        fallback_to_candle: bool = False
    ) -> Optional[float]:
        """
        Get real-time Last Traded Price (₹ / $ / USDT) for an instrument.
        - max_staleness_seconds: If specified, rejects prices older than this threshold.
        - fallback_to_candle: If WebSocket price is None, falls back to latest historical 1m candle.
        """
        exch_enum = Exchange(exchange) if isinstance(exchange, str) else exchange
        price: Optional[float] = None

        # 1. Indian Markets (NSE, NFO, BSE, BFO, MCX, CDS)
        if exch_enum in (Exchange.NSE, Exchange.NFO, Exchange.BSE, Exchange.BFO, Exchange.MCX, Exchange.CDS):
            token = LiveFeedManager._resolve_token(symbol_or_token, exch_enum, broker)
            if token:
                if broker == BrokerType.SHOONYA:
                    from data.shoonya.websocket import (
                        get_live_price as _shoonya_get_price,
                        get_token_staleness as _shoonya_get_staleness,
                    )
                    if max_staleness_seconds is not None:
                        staleness = _shoonya_get_staleness(token)
                        if staleness is not None and staleness > max_staleness_seconds:
                            return None
                    price = _shoonya_get_price(token)
                else:
                    if max_staleness_seconds is not None:
                        staleness = _angel_get_staleness(token)
                        if staleness is not None and staleness > max_staleness_seconds:
                            logger.warning(
                                f"[feed_manager] Stale price rejected for token {token} ({staleness:.1f}s > {max_staleness_seconds}s limit)"
                            )
                            return None

                    price = _angel_get_price(token)

                # Fallback to historical 1m candle if socket has no tick yet
                if price is None and fallback_to_candle:
                    try:
                        df = _angel_fetch_candles(symbol_or_token, interval=CandleInterval.ONE_MINUTE, days_back=1, exchange=exch_enum)
                        if df is not None and not df.empty:
                            close_col = "Close" if "Close" in df.columns else ("close" if "close" in df.columns else None)
                            if close_col:
                                price = float(df[close_col].iloc[-1])
                    except Exception as e:
                        logger.debug(f"[feed_manager] Candle fallback failed for {symbol_or_token}: {e}")

            return price

        # 2. Custom / Global Markets (US_EQUITY, CRYPTO)
        if exch_enum in _CUSTOM_FEED_PROVIDERS:
            quote = _CUSTOM_FEED_PROVIDERS[exch_enum](symbol_or_token)
            return quote.get("ltp") if quote else None

        # 3. Fallback Multi-Asset Registry
        with _feed_lock:
            if max_staleness_seconds is not None:
                ts = _MULTI_ASSET_TIMESTAMPS.get(symbol_or_token.upper())
                if ts and (now_ist() - ts).total_seconds() > max_staleness_seconds:
                    return None
            return _MULTI_ASSET_PRICES.get(symbol_or_token.upper())

    @staticmethod
    def get_vwap(
        symbol_or_token: str,
        exchange: Union[Exchange, str] = Exchange.NSE,
        broker: BrokerType = BrokerType.ANGELONE
    ) -> Optional[float]:
        """
        Get real-time Volume-Weighted Average Price (VWAP / ATP) for execution benchmarking.
        """
        quote = LiveFeedManager.get_quote(symbol_or_token, exchange=exchange, broker=broker)
        if quote and "vwap" in quote and quote["vwap"] is not None:
            return quote["vwap"]

        with _feed_lock:
            return _MULTI_ASSET_VWAP.get(symbol_or_token.upper())

    @staticmethod
    def get_prices_bulk(
        symbols_or_tokens: List[str],
        exchange: Union[Exchange, str] = Exchange.NSE,
        broker: BrokerType = BrokerType.ANGELONE
    ) -> Dict[str, Optional[float]]:
        """
        High-throughput batch retrieval of Last Traded Prices for a list of instruments.
        Essential for quantitative universe breadth and sector momentum calculations.
        """
        results: Dict[str, Optional[float]] = {}
        exch_enum = Exchange(exchange) if isinstance(exchange, str) else exchange

        # Indian Markets Vector Path
        if exch_enum in (Exchange.NSE, Exchange.NFO, Exchange.BSE, Exchange.BFO, Exchange.MCX, Exchange.CDS):
            for item in symbols_or_tokens:
                token = LiveFeedManager._resolve_token(item, exch_enum, broker)
                results[item] = _angel_get_price(token) if token else None
            return results

        # Custom Global Providers Vector Path
        if exch_enum in _CUSTOM_FEED_PROVIDERS:
            provider = _CUSTOM_FEED_PROVIDERS[exch_enum]
            for item in symbols_or_tokens:
                quote = provider(item)
                results[item] = quote.get("ltp") if quote else None
            return results

        # Fallback Multi-Asset Registry Vector Path
        with _feed_lock:
            for item in symbols_or_tokens:
                results[item] = _MULTI_ASSET_PRICES.get(item.upper())
        return results

    @staticmethod
    def get_volume(
        symbol_or_token: str,
        exchange: Union[Exchange, str] = Exchange.NSE,
        broker: BrokerType = BrokerType.ANGELONE
    ) -> Optional[int]:
        """Get real-time cumulative day volume."""
        exch_enum = Exchange(exchange) if isinstance(exchange, str) else exchange

        if exch_enum in (Exchange.NSE, Exchange.NFO, Exchange.BSE, Exchange.BFO, Exchange.MCX, Exchange.CDS):
            token = LiveFeedManager._resolve_token(symbol_or_token, exch_enum, broker)
            if token:
                return _angel_get_volume(token)
            return None

        with _feed_lock:
            return _MULTI_ASSET_VOLUMES.get(symbol_or_token.upper())

    @staticmethod
    def get_oi(
        symbol_or_token: str,
        exchange: Union[Exchange, str] = Exchange.NFO,
        broker: BrokerType = BrokerType.ANGELONE
    ) -> Optional[int]:
        """Get real-time Open Interest for derivatives."""
        exch_enum = Exchange(exchange) if isinstance(exchange, str) else exchange
        token = LiveFeedManager._resolve_token(symbol_or_token, exch_enum, broker)
        if token:
            return _angel_get_oi(token)

        with _feed_lock:
            return _MULTI_ASSET_OI.get(symbol_or_token.upper())

    @staticmethod
    def get_depth(
        symbol_or_token: str,
        exchange: Union[Exchange, str] = Exchange.NSE,
        broker: BrokerType = BrokerType.ANGELONE
    ) -> Optional[Dict[str, Any]]:
        """
        Get live top-of-book market depth:
        {'best_bid': ..., 'best_ask': ..., 'bid_qty': ..., 'ask_qty': ...}
        """
        exch_enum = Exchange(exchange) if isinstance(exchange, str) else exchange

        if exch_enum in (Exchange.NSE, Exchange.NFO, Exchange.BSE, Exchange.BFO, Exchange.MCX, Exchange.CDS):
            token = LiveFeedManager._resolve_token(symbol_or_token, exch_enum, broker)
            if token:
                return _angel_get_depth(token)
            return None

        with _feed_lock:
            return _MULTI_ASSET_DEPTH.get(symbol_or_token.upper())

    @staticmethod
    def get_spread(
        symbol_or_token: str,
        exchange: Union[Exchange, str] = Exchange.NSE,
        broker: BrokerType = BrokerType.ANGELONE
    ) -> Optional[float]:
        """
        Get live bid-ask spread percentage in basis points (bps).
        Returns None if market depth is unavailable or crossed.
        """
        exch_enum = Exchange(exchange) if isinstance(exchange, str) else exchange

        if exch_enum in (Exchange.NSE, Exchange.NFO, Exchange.BSE, Exchange.BFO, Exchange.MCX, Exchange.CDS):
            token = LiveFeedManager._resolve_token(symbol_or_token, exch_enum, broker)
            if token:
                return _angel_get_spread(token)
            return None

        with _feed_lock:
            d = _MULTI_ASSET_DEPTH.get(symbol_or_token.upper())
            if d and d.get("best_bid") and d.get("best_ask") and d["best_bid"] > 0:
                spread = d["best_ask"] - d["best_bid"]
                if spread >= 0:
                    return round((spread / d["best_bid"]) * 10000.0, 2)
        return None

    @staticmethod
    def get_order_imbalance(
        symbol_or_token: str,
        exchange: Union[Exchange, str] = Exchange.NSE,
        broker: BrokerType = BrokerType.ANGELONE
    ) -> Optional[float]:
        """
        Compute real-time Top-of-Book Order Flow Imbalance ratio:
        Imbalance = (Bid_Qty - Ask_Qty) / (Bid_Qty + Ask_Qty)
        Returns float between -1.0 (100% Ask dominance) and +1.0 (100% Bid dominance).
        """
        depth = LiveFeedManager.get_depth(symbol_or_token, exchange=exchange, broker=broker)
        if not depth:
            return None

        bid_qty = depth.get("bid_qty") or depth.get("buy_qty") or 0
        ask_qty = depth.get("ask_qty") or depth.get("sell_qty") or 0
        total_qty = bid_qty + ask_qty

        if total_qty <= 0:
            return 0.0

        return round((bid_qty - ask_qty) / total_qty, 3)

    @staticmethod
    def get_quote(
        symbol_or_token: str,
        exchange: Union[Exchange, str] = Exchange.NSE,
        broker: BrokerType = BrokerType.ANGELONE
    ) -> Optional[Dict[str, Any]]:
        """
        Get unified rich dimensional live quote dictionary.
        """
        exch_enum = Exchange(exchange) if isinstance(exchange, str) else exchange

        if exch_enum in (Exchange.NSE, Exchange.NFO, Exchange.BSE, Exchange.BFO, Exchange.MCX, Exchange.CDS):
            token = LiveFeedManager._resolve_token(symbol_or_token, exch_enum, broker)
            if token:
                quote = _angel_get_quote(token)
                if quote:
                    quote["symbol"] = symbol_or_token
                    quote["token"] = token
                    quote["exchange"] = exch_enum.value
                    quote["spread_bps"] = _angel_get_spread(token)
                    depth = _angel_get_depth(token)
                    if depth:
                        quote["best_bid"] = depth.get("best_bid")
                        quote["best_ask"] = depth.get("best_ask")
                    quote["order_imbalance_ratio"] = LiveFeedManager.get_order_imbalance(symbol_or_token, exchange=exch_enum, broker=broker)
                    return quote
            return None

        if exch_enum in _CUSTOM_FEED_PROVIDERS:
            return _CUSTOM_FEED_PROVIDERS[exch_enum](symbol_or_token)

        with _feed_lock:
            sym_key = symbol_or_token.upper()
            ltp = _MULTI_ASSET_PRICES.get(sym_key)
            if ltp is None:
                return None
            ts = _MULTI_ASSET_TIMESTAMPS.get(sym_key)
            staleness = (now_ist() - ts).total_seconds() if ts else None
            depth = _MULTI_ASSET_DEPTH.get(sym_key, {})
            bid = depth.get("best_bid")
            ask = depth.get("best_ask")
            bid_qty = depth.get("bid_qty") or 0
            ask_qty = depth.get("ask_qty") or 0
            total_qty = bid_qty + ask_qty
            imbalance = round((bid_qty - ask_qty) / total_qty, 3) if total_qty > 0 else 0.0
            spread_bps = round(((ask - bid) / bid) * 10000.0, 2) if (bid and ask and bid > 0 and ask >= bid) else None

            return {
                "symbol": symbol_or_token,
                "token": None,
                "exchange": exch_enum.value,
                "ltp": ltp,
                "volume": _MULTI_ASSET_VOLUMES.get(sym_key),
                "oi": _MULTI_ASSET_OI.get(sym_key),
                "vwap": _MULTI_ASSET_VWAP.get(sym_key),
                "best_bid": bid,
                "best_ask": ask,
                "spread_bps": spread_bps,
                "order_imbalance_ratio": imbalance,
                "timestamp": ts,
                "staleness_seconds": staleness,
            }

    @staticmethod
    def get_quote_snapshot(
        symbol_or_token: str,
        exchange: Union[Exchange, str] = Exchange.NSE,
        broker: BrokerType = BrokerType.ANGELONE
    ) -> Optional[LiveQuoteSnapshot]:
        """
        Get unified typed LiveQuoteSnapshot instance.
        """
        q = LiveFeedManager.get_quote(symbol_or_token, exchange=exchange, broker=broker)
        if not q:
            return None
        return LiveQuoteSnapshot(
            symbol=q.get("symbol", symbol_or_token),
            token=q.get("token"),
            exchange=q.get("exchange", "NSE"),
            ltp=q.get("ltp", 0.0),
            volume=q.get("volume"),
            oi=q.get("oi"),
            vwap=q.get("vwap"),
            best_bid=q.get("best_bid") or q.get("bid"),
            best_ask=q.get("best_ask") or q.get("ask"),
            spread_bps=q.get("spread_bps"),
            order_imbalance_ratio=q.get("order_imbalance_ratio"),
            timestamp=q.get("timestamp"),
            staleness_seconds=q.get("staleness_seconds"),
        )

    @staticmethod
    def is_healthy(exchange: Union[Exchange, str] = Exchange.NSE) -> bool:
        """Check overall real-time market stream health."""
        exch_enum = Exchange(exchange) if isinstance(exchange, str) else exchange
        if exch_enum in (Exchange.NSE, Exchange.NFO, Exchange.BSE, Exchange.BFO, Exchange.MCX, Exchange.CDS):
            return _angel_is_healthy()
        return True

    @staticmethod
    def get_diagnostics() -> Dict[str, Any]:
        """Observability telemetry for the streaming feed subsystem."""
        with _feed_lock:
            custom_count = len(_MULTI_ASSET_PRICES)
        angel_stats = _angel_get_stats()
        return {
            "is_angelone_healthy": _angel_is_healthy(),
            "angelone_stats": angel_stats,
            "custom_multi_asset_tracked": custom_count,
            "registered_custom_exchanges": [e.value for e in _CUSTOM_FEED_PROVIDERS.keys()],
        }

    @staticmethod
    def reset_feed_manager() -> None:
        """Clear all in-memory feed caches (useful for testing & daily market rollover)."""
        with _feed_lock:
            _MULTI_ASSET_PRICES.clear()
            _MULTI_ASSET_VOLUMES.clear()
            _MULTI_ASSET_OI.clear()
            _MULTI_ASSET_VWAP.clear()
            _MULTI_ASSET_DEPTH.clear()
            _MULTI_ASSET_TIMESTAMPS.clear()
            _CUSTOM_FEED_PROVIDERS.clear()
        _angel_clear_caches()


# ── 4. SELF-DIAGNOSTIC LIVE DEMONSTRATION HARNESS ─────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("===================================================================")
    print("MJONAI UNIVERSAL MULTI-ASSET STREAMING FEED MANAGER")
    print("===================================================================")

    # 1. Simulate Ingestion of Live Multi-Asset Ticks
    update_multi_asset_tick(
        symbol="BTCUSDT",
        ltp=64850.50,
        volume=1240,
        vwap=64720.00,
        best_bid=64849.00,
        best_ask=64851.00
    )
    update_multi_asset_tick(
        symbol="AAPL",
        ltp=188.75,
        volume=14500000,
        vwap=187.90,
        best_bid=188.70,
        best_ask=188.80
    )

    print(f"Feed Gateway Health Status : {'OPERATIONAL' if LiveFeedManager.is_healthy() else 'DEGRADED'}")
    print(f"Timestamp (IST)            : {now_ist().isoformat()}")
    print("-------------------------------------------------------------------")
    print("LIVE MULTI-ASSET STREAMING QUOTES:")

    sample_symbols = ["BTCUSDT", "AAPL"]
    for sym in sample_symbols:
        exch = Exchange.CRYPTO if "BTC" in sym else Exchange.US_EQUITY
        quote = LiveFeedManager.get_quote(sym, exchange=exch)
        spread = LiveFeedManager.get_spread(sym, exchange=exch)
        vwap = LiveFeedManager.get_vwap(sym, exchange=exch)
        ltp_val = quote.get('ltp', 0.0) if quote else 0.0
        vol_val = quote.get('volume', 0) if quote else 0
        vwap_str = f"{vwap:,.2f}" if vwap is not None else "N/A"
        spread_str = f"{spread} bps" if spread is not None else "N/A"
        print(f"  - {sym:<8} [{exch.value}] | LTP: {ltp_val:,.2f} | Vol: {vol_val:,d} | VWAP: {vwap_str} | Spread: {spread_str}")

    print("-------------------------------------------------------------------")
    print("BULK VECTOR PRICE RETRIEVAL:")
    bulk_prices = LiveFeedManager.get_prices_bulk(sample_symbols, exchange=Exchange.CRYPTO)
    for k, v in bulk_prices.items():
        print(f"  - Vector Lookup -> {k}: {v}")

    print("-------------------------------------------------------------------")
    diag = LiveFeedManager.get_diagnostics()
    print("STREAMING TELEMETRY DIAGNOSTICS:")
    print(f"  - Active Multi-Asset Tracked : {diag['custom_multi_asset_tracked']}")
    print(f"  - Broker WebSocket Connected : {diag['is_angelone_healthy']}")
    print(f"  - Registered Custom Feeds   : {diag['registered_custom_exchanges']}")
    print("===================================================================")

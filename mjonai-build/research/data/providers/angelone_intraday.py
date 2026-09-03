"""
Angel One INTRADAY candle provider for the research pipeline.

Serves minute-scale OHLCV (1m base) from the Angel One SmartAPI
historical endpoint through the existing battle-tested fetcher in
data/angelone/historical.py, into the same coverage-aware parquet
cache the daily pipeline uses.

Login is LAZY: the provider never touches credentials at import or
construction time — only on the first real fetch.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional

from core.enums import Provider
from research.data.base_provider import HistoricalDataProvider
from research.data.models import Candle, HistoricalData
from research.data.requests import HistoricalDataRequest
from research.data.responses import HistoricalDataResponse

from data.angelone.historical import (
    CandleInterval,
    fetch_historical_candles,
)

logger = logging.getLogger(__name__)


# research TimeFrame value -> SmartAPI candle interval
TIMEFRAME_TO_INTERVAL: dict = {
    "1m": CandleInterval.ONE_MINUTE,
    "3m": CandleInterval.THREE_MINUTE,
    "5m": CandleInterval.FIVE_MINUTE,
    "10m": CandleInterval.TEN_MINUTE,
    "15m": CandleInterval.FIFTEEN_MINUTE,
    "30m": CandleInterval.THIRTY_MINUTE,
    "1h": CandleInterval.ONE_HOUR,
}


def default_smartapi_client_factory() -> Optional[Any]:
    """
    Lazily log into Angel One SmartAPI using credentials from the
    environment (.env.master). Returns None when unavailable — the
    provider then falls back to the fetcher's yfinance path or fails
    honestly, without ever exposing credential values here.
    """
    try:
        from data.download_6months_1min import initialize_smartapi

        return initialize_smartapi()
    except Exception as e:
        logger.warning(f"[AngelOneIntraday] client factory failed: {e}")
        return None


class AngelOneIntradayProvider(HistoricalDataProvider):
    """
    Serves intraday candles for research requests.

    The SmartAPI client is created lazily via `client_factory`
    (default: environment-based login) and cached after first use.
    """

    # Broker caps on how much history one minute-candle request can span;
    # callers wanting more should chunk (the downloader does).
    MAX_DAYS_PER_REQUEST: int = 100

    def __init__(
        self,
        client_factory: Optional[Callable[[], Optional[Any]]] = None,
    ):
        self._client_factory = (
            client_factory
            or default_smartapi_client_factory
        )

        self._client: Optional[Any] = None

        self._login_attempted = False

    @property
    def provider(self) -> Provider:
        return Provider.ANGEL

    def _get_client(self) -> Optional[Any]:
        """Log in once, lazily, on first use."""
        if not self._login_attempted:
            self._login_attempted = True
            try:
                self._client = self._client_factory()
            except Exception as e:
                logger.warning(f"[AngelOneIntraday] login failed: {e}")
                self._client = None
        return self._client

    def fetch(
        self,
        request: HistoricalDataRequest,
    ) -> HistoricalDataResponse:
        interval = TIMEFRAME_TO_INTERVAL.get(
            str(request.timeframe.value)
        )

        if interval is None:
            return HistoricalDataResponse(
                success=False,
                error=(
                    f"Unsupported intraday timeframe: "
                    f"{request.timeframe.value} "
                    f"(supported: {sorted(TIMEFRAME_TO_INTERVAL)})"
                ),
            )

        days_back = min(
            self.MAX_DAYS_PER_REQUEST,
            max(1, (request.end - request.start).days + 1),
        )

        # use_cache=False: research requests span different windows, and
        # the underlying 60s TTL RAM cache would happily serve a frame
        # fetched for a DIFFERENT range.
        df = fetch_historical_candles(
            symbol=request.instrument.symbol,
            interval=interval,
            days_back=days_back,
            exchange="NSE",
            smart_api_client=self._get_client(),
            use_cache=False,
        )

        if df is None or df.empty:
            return HistoricalDataResponse(
                success=False,
                error=(
                    f"No intraday candles returned for "
                    f"{request.instrument.symbol} "
                    f"({request.timeframe.value}, {days_back}d)"
                ),
            )

        # Normalize timestamps to NAIVE IST: SmartAPI returns tz-aware
        # stamps (UTC+05:30) while the research stack compares against
        # naive IST datetimes. Mixed comparison raises TypeError.
        idx = df.index
        if getattr(idx, "tz", None) is not None:
            idx = idx.tz_convert("Asia/Kolkata").tz_localize(None)
        df.index = idx

        # Clip strictly to the requested window.
        df = df[
            (df.index >= request.start)
            & (df.index <= request.end)
        ]

        if df.empty:
            return HistoricalDataResponse(
                success=False,
                error=(
                    f"Intraday fetch for {request.instrument.symbol} "
                    f"returned nothing inside the requested range"
                ),
            )

        candles: list[Candle] = []

        for ts, row in df.iterrows():
            ts_py = (
                ts.to_pydatetime()
                if hasattr(ts, "to_pydatetime")
                else ts
            )

            candles.append(
                Candle(
                    timestamp=ts_py,
                    open=float(row["Open"]),
                    high=float(row["High"]),
                    low=float(row["Low"]),
                    close=float(row["Close"]),
                    volume=float(row.get("Volume", 0.0) or 0.0),
                )
            )

        return HistoricalDataResponse(
            success=True,
            data=HistoricalData(
                instrument=request.instrument,
                timeframe=request.timeframe,
                candles=candles,
            ),
        )
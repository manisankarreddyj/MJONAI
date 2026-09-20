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

from mjonai.core.enums import Provider
from mjonai.research.data.base_provider import HistoricalDataProvider
from mjonai.research.data.models import Candle, HistoricalData
from mjonai.research.data.requests import HistoricalDataRequest
from mjonai.research.data.responses import HistoricalDataResponse

from mjonai.data.angelone.historical import (
    CandleInterval,
    DataProvider,
    fetch_historical_candles,
)

logger = logging.getLogger(__name__)

# Minute pipeline Phase 3 (research-read of the archive): the LIVE archive.
# A shared default so the research provider prefers captured minutes over a
# fresh broker pull wherever the archive already covers the request — the
# archive is the same ANGEL/RAW identity research reads through the cache,
# so validating intraday strategies on captured bars is just a cache read.
from mjonai.data.minute_archive import MinuteBarArchive

_DEFAULT_ARCHIVE = MinuteBarArchive()


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
    environment (.env.master). Returns None when unavailable; the fetcher
    will then attempt its yfinance path, which this RAW-native provider
    detects and REFUSES (see `fetch`) rather than admit adjusted bars into
    the RAW research cache. No credential values are ever exposed here.
    """
    try:
        from mjonai.data.download_6months_1min import initialize_smartapi

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
        archive: Optional[MinuteBarArchive] = None,
    ):
        self._client_factory = (
            client_factory
            or default_smartapi_client_factory
        )

        self._client: Optional[Any] = None

        self._login_attempted = False

        # Minute pipeline Phase 3: the intraday provider prefers the persisted
        # live minute archive when it covers the request window; the broker is
        # the fallback. Injectable for offline tests.
        self._archive = archive if archive is not None else _DEFAULT_ARCHIVE

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

    def _resolve_archive_cadence(self, timeframe_value: str) -> Optional[str]:
        """Map a research TimeFrame value to the archive resample cadence.

        The archive owns native 1m bars and resamples to 5m/10m/15m/30m/1h/2h.
        Anything else (incl. 3m, which is not a supported resample target
        here) returns None so the caller falls through to the broker.
        """
        if timeframe_value in ("5m", "10m", "15m", "30m", "1h"):
            return timeframe_value
        return None

    def _serve_from_archive(
        self,
        request: HistoricalDataRequest,
    ) -> Optional[HistoricalDataResponse]:
        """Serve the request from the persisted live minute archive.

        Returns None when the archive cannot cover the request — no captured
        bars for the symbol, an unsupported cadence, or nothing inside the
        requested window. The broker path is then used unchanged.
        """
        symbol = request.instrument.symbol
        timeframe_value = str(request.timeframe.value)

        if timeframe_value == "1m":
            df = self._archive.to_dataframe(symbol)
        else:
            cadence = self._resolve_archive_cadence(timeframe_value)
            if cadence is None:
                return None
            df = self._archive.load_cadence(
                symbol,
                cadence=cadence,
                min_bars=None,
            )

        if df is None or df.empty:
            return None

        # Defensive homogeneous timestamps: the archive stores naive IST
        # stamps, but an injected/tz-aware seed must compare against the
        # request bounds (naive IST) without raising.
        idx = df.index
        if getattr(idx, "tz", None) is not None:
            idx = idx.tz_convert("Asia/Kolkata").tz_localize(None)
        df.index = idx

        # Clip to the requested window (the archive holds everything captured;
        # the provider must honor the request range like the broker path does).
        df = df[(df.index >= request.start) & (df.index <= request.end)]
        if df.empty:
            logger.info(
                "[AngelOneIntraday] archive for %s has bars, but none inside "
                "%s..%s; falling through to broker",
                symbol, request.start, request.end,
            )
            return None

        candles = []
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

        logger.info(
            "[AngelOneIntraday] served %s (%s) from the live minute archive "
            "(%d bars inside the requested window)",
            symbol, timeframe_value, len(candles),
        )
        return HistoricalDataResponse(
            success=True,
            data=HistoricalData(
                instrument=request.instrument,
                timeframe=request.timeframe,
                candles=candles,
            ),
        )

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

        # Minute pipeline Phase 3: prefer captured real minutes over a fresh
        # broker pull. The archive is the same ANGEL/RAW identity the cache
        # uses, so this never fabricates data — it serves what the live feed
        # actually recorded, resampled to the requested cadence.
        archived = self._serve_from_archive(request)
        if archived is not None:
            return archived

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

        # P0.2 (2026-09-18): fail closed on a silent cross-regime
        # substitution. `fetch_historical_candles` falls back to yfinance
        # (auto_adjust=True => the ADJUSTED regime) when SmartAPI is
        # unavailable. This provider is ANGEL, whose native regime is RAW;
        # admitting adjusted bars here would store them under the RAW cache
        # key and corrupt every absolute-price indicator read back from it.
        # The fetcher always stamps provenance — any explicit non-SMART_API
        # tag is refused. (Untagged frames only occur for injected/test
        # fetchers and are treated as native.)
        provenance = df.attrs.get("data_provider")
        if provenance is not None and provenance != DataProvider.SMART_API.value:
            return HistoricalDataResponse(
                success=False,
                error=(
                    f"Angel One SmartAPI unavailable for "
                    f"{request.instrument.symbol} "
                    f"({request.timeframe.value}); refuses the {provenance} "
                    f"fallback (ADJUSTED regime) instead of mixing "
                    f"adjustment regimes in the RAW research cache."
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
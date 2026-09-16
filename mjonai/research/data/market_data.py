from __future__ import annotations

from datetime import timedelta
from typing import Callable, Iterable

from mjonai.research.data.adjustment import adjust_historical_data
from mjonai.research.data.base_provider import HistoricalDataProvider
from mjonai.research.data.corporate_actions import (
    CorporateActionError,
    CorporateActionFactor,
)
from mjonai.research.data.models import HistoricalData
from mjonai.research.data.requests import HistoricalDataRequest
from mjonai.research.data.responses import HistoricalDataResponse

from mjonai.storage.models import StorageKey
from mjonai.storage.service import StorageService

from mjonai.core.enums import AdjustmentMode, Provider


# YahooProvider serves auto_adjust=True adjusted bars (corporate actions
# applied, no artificial gaps). AngelOne SmartAPI serves native raw bars.
# The regime is part of the cache identity — mixing the two would corrupt
# every absolute-price indicator read from the cache.
_ADJUSTMENT_MODE_BY_PROVIDER = {
    Provider.YAHOO: AdjustmentMode.ADJUSTED,
    Provider.ANGEL: AdjustmentMode.RAW,
    Provider.SHOONYA: AdjustmentMode.RAW,
}


def _corporate_action_symbol(instrument) -> str:
    """NSE symbol for the corporate-action lookup.

    Angel/Shoonya instruments carry the bare NSE ticker in `symbol`
    (e.g. "RELIANCE"); Yahoo instruments carry a ".NS"-suffixed
    `yahoo_symbol`. The india-corp-actions source is keyed on the plain
    NSE symbol, so strip the suffix defensively.
    """
    symbol = instrument.angel_symbol or instrument.symbol
    for suffix in (".NS", ".NSE", ".BSE"):
        if isinstance(symbol, str) and symbol.upper().endswith(suffix):
            symbol = symbol[: -len(suffix)]
    return symbol


class MarketDataService:

    # A cached series may end a few days short of the requested end
    # (today's bar not closed yet, market holidays) without being
    # considered stale.
    END_COVERAGE_GRACE_DAYS = 7

    # H6: endpoint checks alone let an INTERIOR hole (a missing chunk of
    # months inside an otherwise-spanning cache) pass as continuous history.
    # For daily-or-coarser series, any gap larger than this multiple of the
    # median bar spacing marks the cached slice as NOT covered, forcing an
    # honest refetch/merge. Intraday series legitimately contain overnight/
    # session gaps, so the interior rule applies only when median spacing is
    # >= INTRADAY_MEDIAN_SPACING_FLOOR.
    MAX_INTERIOR_GAP_MULTIPLIER = 8
    INTRADAY_MEDIAN_SPACING_FLOOR_HOURS = 6.0

    def __init__(
        self,
        adjustment_factor_provider: (
            Callable[[HistoricalDataRequest], Iterable[CorporateActionFactor]]
            | None
        ) = None,
    ):

        self._providers: dict[
            Provider,
            HistoricalDataProvider,
        ] = {}

        self._storage = StorageService()

        # Decision 6 Phase 2: the corporate-action factor source that turns
        # a native-RAW (Angel/Shoonya) series into the ADJUSTED regime when
        # the request asks for it. Optional for testability; the default is
        # built lazily from india-corp-actions (never on the import path).
        self._adjustment_factor_provider = (
            adjustment_factor_provider
            or self._default_adjustment_factors
        )

    def _default_adjustment_factors(
        self,
        request: HistoricalDataRequest,
    ) -> list[CorporateActionFactor]:
        from mjonai.research.data.corporate_actions import (
            CorporateActionsClient,
        )

        return CorporateActionsClient().fetch_factors(
            _corporate_action_symbol(request.instrument),
        )

    def register(
        self,
        provider: HistoricalDataProvider,
    ) -> None:

        self._providers[
            provider.provider
        ] = provider

    def register_storage(
        self,
        storage: StorageService,
    ) -> None:

        self._storage = storage

    def get_historical_data(
        self,
        request: HistoricalDataRequest,
    ) -> HistoricalDataResponse:

        native_mode = _ADJUSTMENT_MODE_BY_PROVIDER.get(
            request.provider,
            AdjustmentMode.RAW,
        )
        target_mode = request.adjustment_mode or native_mode

        key = StorageKey(
            provider=request.provider,
            instrument=request.instrument,
            timeframe=request.timeframe,
            adjustment_mode=target_mode,
        )

        cache_exists = self._storage.exists(key)

        print("=" * 80)
        print("MARKET DATA REQUEST")
        print("Symbol :", request.instrument.symbol)
        print("Start  :", request.start)
        print("End    :", request.end)
        print("Cache Exists :", cache_exists)
        print("Regime :", native_mode.value, "->", target_mode.value)

        # The cache holds one merged history per symbol/timeframe/regime;
        # it is only usable when it actually SPANS the requested
        # range, and only the requested slice is served. Serving a
        # short or shifted series silently corrupts every downstream
        # backtest window.
        if (
            not request.force_refresh
            and cache_exists
        ):

            data = self._covered_slice(
                self._storage.load(key),
                request,
            )

            if data is not None:

                print("Cache Coverage : HIT")

                return HistoricalDataResponse(
                    success=True,
                    data=data,
                    cached=True,
                    source="PARQUET",
                )

            print("Cache Coverage : MISS (range not covered)")

        provider = self._providers.get(
            request.provider
        )

        if provider is None:

            raise ValueError(
                f"Provider not registered: {request.provider}"
            )

        response = provider.fetch(request)

        if (
            response.success
            and response.data is not None
        ):

            if target_mode is not native_mode:
                if not (
                    native_mode is AdjustmentMode.RAW
                    and target_mode is AdjustmentMode.ADJUSTED
                ):
                    raise ValueError(
                        f"Cannot serve {target_mode.value} from provider "
                        f"{request.provider.value} (native {native_mode.value}): "
                        "the adjustment engine only converts RAW -> ADJUSTED, "
                        "never the reverse. Use a RAW-native provider."
                    )

            if target_mode is AdjustmentMode.ADJUSTED and (
                native_mode is not AdjustmentMode.ADJUSTED
            ):

                # Engine-produced ADJUSTED regime from a native-RAW
                # provider (Decision 6 Phase 2). Fail closed when the
                # factor source is unavailable: an unadjusted raw series
                # must never masquerade as adjusted.
                try:
                    adjusted = adjust_historical_data(
                        response.data,
                        self._adjustment_factor_provider(request),
                    )
                except CorporateActionError as exc:
                    response.success = False
                    response.data = None
                    response.error = (
                        f"ADJUSTED regime unavailable for "
                        f"{request.instrument.symbol}: {exc}"
                    )
                    return response

                # Warm BOTH regimes from this single provider fetch: the
                # native RAW cache (for future raw requests) and the
                # engine-produced ADJUSTED cache under the target key.
                if native_mode is not target_mode:
                    native_key = StorageKey(
                        provider=request.provider,
                        instrument=request.instrument,
                        timeframe=request.timeframe,
                        adjustment_mode=native_mode,
                    )
                    self._storage.save(
                        native_key,
                        response.data,
                    )

                self._storage.save(
                    key,
                    adjusted,
                )

                response.cached = False

                response.source = (
                    f"{provider.provider.value}.ADJUSTED"
                )

                response.data = adjusted

            else:

                self._storage.save(
                    key,
                    response.data,
                )

                response.cached = False

                response.source = provider.provider.value

        return response

    def _covered_slice(
        self,
        data: HistoricalData | None,
        request: HistoricalDataRequest,
    ) -> HistoricalData | None:

        if data is None or not data.candles:
            return None

        candles = data.candles

        first = candles[0].timestamp
        last = candles[-1].timestamp

        covered_start = first <= request.start

        covered_end = (
            last
            >= request.end - timedelta(days=self.END_COVERAGE_GRACE_DAYS)
        )

        if not (covered_start and covered_end):
            return None

        sliced = [
            candle
            for candle in candles
            if request.start <= candle.timestamp <= request.end
        ]

        if not sliced:
            return None

        if self._has_suspicious_interior_gap(sliced):
            print("Cache Coverage : MISS (interior gap detected - forcing refetch/merge)")
            return None

        return HistoricalData(
            instrument=request.instrument,
            timeframe=request.timeframe,
            candles=sliced,
        )

    def _has_suspicious_interior_gap(self, candles) -> bool:
        """
        True when a daily-or-coarser series contains an interior gap larger
        than MAX_INTERIOR_GAP_MULTIPLIER × its median bar spacing. Intraday
        series (median spacing below the floor) are exempt: session/overnight
        breaks are legitimate there, and range slicing already guards them.
        A detected hole forces a provider refetch whose merge heals truncated
        caches; if the provider genuinely lacks the data too, the hole is real.
        """
        from datetime import timedelta as _td

        timestamps = sorted(c.timestamp for c in candles)
        if len(timestamps) < 3:
            return False

        deltas = [
            (b - a).total_seconds()
            for a, b in zip(timestamps, timestamps[1:])
            if b > a
        ]
        if not deltas:
            return False

        ordered = sorted(deltas)
        median = ordered[len(ordered) // 2]
        if median <= 0:
            return False

        if median < self.INTRADAY_MEDIAN_SPACING_FLOOR_HOURS * 3600.0:
            return False  # intraday cadence — session gaps are normal

        threshold = median * self.MAX_INTERIOR_GAP_MULTIPLIER
        return any(d > threshold for d in deltas)

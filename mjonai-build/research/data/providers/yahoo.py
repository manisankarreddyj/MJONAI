from __future__ import annotations

from datetime import datetime

import pandas as pd
import yfinance as yf

from research.data.base_provider import HistoricalDataProvider
from research.data.models import Candle, HistoricalData
from research.data.requests import HistoricalDataRequest
from research.data.responses import HistoricalDataResponse
from core.enums import Provider


class YahooProvider(HistoricalDataProvider):

    @property
    def provider(self) -> Provider:
        return Provider.YAHOO

    def fetch(
        self,
        request: HistoricalDataRequest,
    ) -> HistoricalDataResponse:

        symbol = request.instrument.yahoo_symbol

        print("=" * 80)
        print("YAHOO FETCH")
        print("Symbol :", symbol)
        print("Start  :", request.start)
        print("End    :", request.end)

        if not symbol:

            return HistoricalDataResponse(
                success=False,
                error="Yahoo symbol not available.",
            )

        # Adjusted prices: splits/dividends applied so returns,
        # indicators and stop levels are not corrupted by
        # artificial gaps on corporate-action dates.
        df = yf.download(
            symbol,
            start=request.start,
            end=request.end,
            interval=request.timeframe.value,
            progress=False,
            auto_adjust=True,
        )

        if df.empty:
            return HistoricalDataResponse(
                success=False,
                error="No market data returned.",
            )

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df = df.dropna()
        if df.empty:
            return HistoricalDataResponse(
                success=False,
                error="All market data rows were NaN.",
            )

        candles: list[Candle] = []

        for ts, row in df.iterrows():

            candles.append(
                Candle(
                    timestamp=ts.to_pydatetime()
                    if hasattr(ts, "to_pydatetime")
                    else datetime.fromisoformat(str(ts)),
                    open=float(row["Open"]),
                    high=float(row["High"]),
                    low=float(row["Low"]),
                    close=float(row["Close"]),
                    volume=float(row["Volume"]),
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
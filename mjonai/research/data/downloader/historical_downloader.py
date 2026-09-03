from __future__ import annotations

from mjonai.research.data.downloader.jobs import (
    DownloadJob,
    DownloadResult,
)

from mjonai.research.data.requests import (
    HistoricalDataRequest,
)

from mjonai.research.data.market_data import (
    MarketDataService,
)


class HistoricalDownloader:

    def __init__(
        self,
        market_data: MarketDataService,
    ):

        self.market_data = market_data

    def download(
        self,
        job: DownloadJob,
    ) -> DownloadResult:

        result = DownloadResult()

        total = len(job.instruments)

        print()
        print("=" * 80)
        print("Historical Download")
        print()

        for index, instrument in enumerate(job.instruments, start=1):

            print(
                f"[{index}/{total}] "
                f"{instrument.symbol:<20}",
                end="",
            )

            request = HistoricalDataRequest(
                provider=job.provider,
                instrument=instrument,
                timeframe=job.timeframe,
                start=job.start,
                end=job.end,
                force_refresh=job.force_refresh,
            )

            response = self.market_data.get_historical_data(
                request
            )

            if response.success:

                if response.cached:

                    result.cached += 1

                    print(" Cached")

                else:

                    result.downloaded += 1

                    print(" Downloaded")

            else:

                result.failed += 1

                print(f" Failed ({response.error})")

        print()
        print("=" * 80)
        print("Summary")
        print()

        print(f"Downloaded : {result.downloaded}")
        print(f"Cached      : {result.cached}")
        print(f"Failed      : {result.failed}")

        return result
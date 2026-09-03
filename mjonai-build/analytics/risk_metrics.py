from __future__ import annotations

import math

import numpy as np
import pandas as pd

from analytics.models import (
    EquityStatistics,
    PerformanceStatistics,
    TradeStatistics,
)


TRADING_DAYS_PER_YEAR = 252

CALENDAR_DAYS_PER_YEAR = 365.25


class PerformanceMetricsCalculator:
    """
    Risk-adjusted performance statistics.

    Daily returns are derived from the equity curve (mark on each
    trade exit, forward-filled between exits), so they describe the
    strategy's active period rather than calendar time before the
    first trade.
    """

    def __init__(
        self,
        risk_free_annual: float = 0.0,
    ):

        self._risk_free_annual = (
            risk_free_annual
        )

    def calculate(
        self,
        trade: TradeStatistics,
        equity: EquityStatistics,
    ) -> PerformanceStatistics:

        recovery_factor = 0.0

        if equity.max_drawdown_pct > 0:
            recovery_factor = (
                equity.total_return_pct
                / equity.max_drawdown_pct
            )

        daily_returns = (
            self._daily_returns(equity)
        )

        sharpe_ratio = 0.0
        sortino_ratio = 0.0
        annualized_return_pct = 0.0

        if daily_returns is not None and len(daily_returns) >= 2:

            rf_daily = (
                self._risk_free_annual
                / TRADING_DAYS_PER_YEAR
            )

            mean_return = float(
                np.mean(daily_returns)
            )

            std_return = float(
                np.std(daily_returns, ddof=1)
            )

            downside = daily_returns[
                daily_returns < rf_daily
            ]

            downside_deviation = float(
                np.sqrt(
                    np.mean(
                        (downside - rf_daily) ** 2
                    )
                )
            ) if len(downside) else 0.0

            if std_return > 0:
                sharpe_ratio = (
                    (mean_return - rf_daily)
                    / std_return
                    * math.sqrt(TRADING_DAYS_PER_YEAR)
                )

            if downside_deviation > 0:
                sortino_ratio = (
                    (mean_return - rf_daily)
                    / downside_deviation
                    * math.sqrt(TRADING_DAYS_PER_YEAR)
                )

            annualized_return_pct = (
                mean_return
                * TRADING_DAYS_PER_YEAR
                * 100
            )

        cagr_pct = self._cagr_pct(equity)

        calmar_ratio = (
            cagr_pct
            / equity.max_drawdown_pct
            if equity.max_drawdown_pct > 0
            else 0.0
        )

        mar_ratio = (
            annualized_return_pct
            / equity.max_drawdown_pct
            if equity.max_drawdown_pct > 0
            else 0.0
        )

        return PerformanceStatistics(
            cagr_pct=round(
                cagr_pct,
                4,
            ),
            annualized_return_pct=round(
                annualized_return_pct,
                4,
            ),
            sharpe_ratio=round(
                sharpe_ratio,
                4,
            ),
            sortino_ratio=round(
                sortino_ratio,
                4,
            ),
            calmar_ratio=round(
                calmar_ratio,
                4,
            ),
            recovery_factor=round(
                recovery_factor,
                4,
            ),
            mar_ratio=round(
                mar_ratio,
                4,
            ),
        )

    @staticmethod
    def _daily_returns(
        equity: EquityStatistics,
    ) -> np.ndarray | None:

        points = equity.equity_curve.points

        if not points:
            return None

        series = pd.Series(
            [point.equity for point in points],
            index=pd.DatetimeIndex(
                [point.timestamp for point in points]
            ),
        )

        # Several trades may exit on the same day;
        # the last point holds that day's final equity.
        series = (
            series.groupby(level=0)
            .last()
            .sort_index()
        )

        calendar = pd.bdate_range(
            series.index[0],
            series.index[-1],
        )

        series = (
            series.reindex(calendar)
            .ffill()
        )

        returns = series.pct_change().dropna()

        if returns.empty:
            return None

        return returns.to_numpy(
            dtype=float,
        )

    @staticmethod
    def _cagr_pct(
        equity: EquityStatistics,
    ) -> float:

        points = equity.equity_curve.points

        if not points or equity.initial_capital <= 0:
            return 0.0

        if equity.final_capital <= 0:
            return -100.0

        start = min(
            point.timestamp for point in points
        )

        end = max(
            point.timestamp for point in points
        )

        days = (end - start).days

        if days <= 0:
            return 0.0

        growth = (
            equity.final_capital
            / equity.initial_capital
        ) ** (
            CALENDAR_DAYS_PER_YEAR / days
        )

        return (growth - 1) * 100
from __future__ import annotations

from engine.execution.brokers.base import BrokerCostModel
from engine.execution.models import TransactionCost


class ZerodhaCostModel(BrokerCostModel):

    @property
    def name(self) -> str:
        return "ZERODHA"

    def calculate(
        self,
        *,
        entry_price: float,
        exit_price: float,
        quantity: int,
        slippage_bps: float = 5.0,
    ) -> TransactionCost:

        buy_turnover = (
            entry_price * quantity
        )

        sell_turnover = (
            exit_price * quantity
        )

        turnover = (
            buy_turnover +
            sell_turnover
        )

        # Equity Delivery
        brokerage = 0.0

        stt = (
            sell_turnover *
            0.001
        )

        exchange_charge = (
            turnover *
            0.0000345
        )

        sebi_charge = (
            turnover *
            0.000001
        )

        stamp_duty = (
            buy_turnover *
            0.00015
        )

        gst = (
            (
                brokerage +
                exchange_charge
            )
            * 0.18
        )

        # Market impact / spread cost on both legs,
        # expressed in basis points of turnover.
        slippage = (
            turnover *
            slippage_bps /
            10000
        )

        taxes = (
            stt +
            exchange_charge +
            sebi_charge +
            gst +
            stamp_duty
        )

        total = (
            brokerage +
            slippage +
            taxes
        )

        return TransactionCost(
            brokerage=round(
                brokerage,
                2,
            ),
            slippage=round(
                slippage,
                2,
            ),
            taxes=round(
                taxes,
                2,
            ),
            total=round(
                total,
                2,
            ),
        )
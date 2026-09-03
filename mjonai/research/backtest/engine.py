from mjonai.research.backtest.processor import (
    TradeProcessor,
)
from mjonai.research.backtest.trade_simulator import (
    TradeSimulator,
)


INITIAL_CAPITAL = 100_000  # ₹1 Lakh


class BacktestEngine:
    """
    Turns signals into a trade ledger.

    Semantics fixed on 2026-08-22:
    - entries fill at the NEXT bar's open (no look-ahead)
    - one position at a time per symbol
    - real transaction costs incl. slippage
    - quantity clamped to affordable shares
    """

    def __init__(
        self,
        initial_capital: float = INITIAL_CAPITAL,
    ):

        self.simulator = (
            TradeSimulator()
        )

        self._initial_capital = (
            initial_capital
        )

    @property
    def initial_capital(self) -> float:
        """Ledger starting capital — single source for downstream metrics."""
        return self._initial_capital

        self.trade_processor = (
            TradeProcessor(
                initial_capital,
            )
        )

    def run(
        self,
        *,
        strategy,
        symbol,
        df,
        signals,
        stop_loss_func,
        target_func,
        max_holding_bars,
    ):

        # Fresh ledger per run so repeated runs
        # cannot contaminate each other.
        self.trade_processor = (
            TradeProcessor(
                self._initial_capital,
            )
        )

        trades = []

        # One position at a time per symbol: overlapping signals
        # are skipped so equity accounting matches how a single-
        # symbol system actually trades.
        last_exit_index: int | None = None

        for signal in signals:

            # Signal fires on the close of bar `signal.index`;
            # the earliest realistic fill is the NEXT bar's open.
            entry_index = signal.index + 1

            if entry_index >= len(df):
                continue

            if (
                last_exit_index is not None
                and entry_index <= last_exit_index
            ):
                continue

            direction = signal.signal

            entry_price = float(
                df["Open"].iloc[
                    entry_index
                ]
            )

            stop_loss = stop_loss_func(
                df,
                signal.index,
                entry_price,
                direction,
            )

            target = target_func(
                entry_price,
                stop_loss,
                direction,
            )

            trade = self.simulator.simulate(

                symbol=symbol,

                strategy=getattr(
                    strategy,
                    "name",
                    strategy.__class__.__name__,
                ),

                direction=direction,

                df=df,

                entry_index=entry_index,

                entry_price=entry_price,

                stop_loss=stop_loss,

                target=target,

                max_holding_bars=max_holding_bars,
            )

            trade = self.trade_processor.process(
                trade=trade,
            )

            if trade is None:
                continue

            # Only an executed trade occupies the position slot.
            last_exit_index = trade.exit_index

            trades.append(
                trade,
            )

        return trades

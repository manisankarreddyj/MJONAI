from mjonai.research.backtest.models import TradeResult
from mjonai.research.backtest.models import TransactionCost


class TradeSimulator:
    """
    Executes one completed trade from one strategy signal.

    fill_model controls how a resting profit-target (limit) order is
    assumed to fill intra-bar:

    - "touch" (legacy): a bar whose high reaches the target fills it.
      Optimistic — a resting limit needs an actual trade *through* the
      level, not merely a graze, to be filled.
    - "trade_through" (default): the bar must trade beyond the target by
      ``tick_bps`` (a modeled minimum trade-through / queue buffer) before
      the limit is considered filled. Stricter => more conservative.

    Protective stops are stop-market orders triggered by a touch, so they
    are unaffected by fill_model, and a bar that OPENS beyond a level keeps
    filling at the open (a gap through is a real through).
    """

    def __init__(
        self,
        fill_model: str = "trade_through",
        tick_bps: float = 5.0,
    ):
        if fill_model not in ("touch", "trade_through"):
            raise ValueError(
                f"Unsupported fill_model: {fill_model}"
            )
        if tick_bps < 0:
            raise ValueError(
                "tick_bps must be non-negative."
            )
        self._fill_model = fill_model
        self._tick_bps = float(tick_bps)
        self._target_buffer = self._tick_bps / 10_000.0

    def _limit_target_reached(
        self,
        *,
        direction: str,
        high: float,
        low: float,
        target: float,
    ) -> bool:
        """True when the intra-bar range fills a resting limit at ``target``.

        "touch" fills on a graze; "trade_through" requires price to trade
        beyond the level by the modeled buffer.
        """
        if direction == "LONG":
            if self._fill_model == "touch":
                return high >= target
            return high > target * (1.0 + self._target_buffer)
        if self._fill_model == "touch":
            return low <= target
        return low < target * (1.0 - self._target_buffer)

    def simulate(
        self,
        *,
        symbol,
        strategy,
        direction,
        df,
        entry_index,
        entry_price,
        stop_loss,
        target,
        max_holding_bars,
    ):

        if direction not in ("LONG", "SHORT"):
            raise ValueError(
                f"Unsupported direction: {direction}"
            )

        if not (0 <= entry_index < len(df)):
            raise ValueError(
                f"Invalid entry_index: {entry_index}"
            )

        total_bars = len(df)

        last_bar = min(
            entry_index + max_holding_bars,
            total_bars - 1,
        )

        mfe = 0.0
        mae = 0.0

        exit_index = last_bar
        exit_price = float(
            df["Close"].iloc[last_bar]
        )

        if last_bar == total_bars - 1:
            exit_reason = "END_OF_DATA"
        else:
            exit_reason = "TIMEOUT"

        # Entry fills at the open of `entry_index`, so every
        # movement in that bar happens after the fill and the
        # bar is scanned like any other.
        for i in range(
            entry_index,
            last_bar + 1,
        ):

            high = float(
                df["High"].iloc[i]
            )

            low = float(
                df["Low"].iloc[i]
            )

            open_price = (
                float(
                    df["Open"].iloc[i]
                )
                if i > entry_index
                else entry_price
            )

            if direction == "LONG":

                mfe = max(
                    mfe,
                    (high - entry_price)
                    / entry_price,
                )

                mae = min(
                    mae,
                    (low - entry_price)
                    / entry_price,
                )

                # A bar opening beyond the level fills
                # at the open, not at the level.
                if open_price <= stop_loss:

                    exit_index = i
                    exit_price = open_price
                    exit_reason = "STOPLOSS"
                    break

                if open_price >= target:

                    exit_index = i
                    exit_price = open_price
                    exit_reason = "TARGET"
                    break

                # Same-bar stop/target ambiguity is
                # resolved conservatively: stop first.
                if low <= stop_loss:

                    exit_index = i
                    exit_price = stop_loss
                    exit_reason = "STOPLOSS"
                    break

                if self._limit_target_reached(
                    direction="LONG",
                    high=high,
                    low=low,
                    target=target,
                ):

                    exit_index = i
                    exit_price = target
                    exit_reason = "TARGET"
                    break

            else:

                mfe = max(
                    mfe,
                    (entry_price - low)
                    / entry_price,
                )

                mae = min(
                    mae,
                    (entry_price - high)
                    / entry_price,
                )

                if open_price >= stop_loss:

                    exit_index = i
                    exit_price = open_price
                    exit_reason = "STOPLOSS"
                    break

                if open_price <= target:

                    exit_index = i
                    exit_price = open_price
                    exit_reason = "TARGET"
                    break

                if high >= stop_loss:

                    exit_index = i
                    exit_price = stop_loss
                    exit_reason = "STOPLOSS"
                    break

                if self._limit_target_reached(
                    direction="SHORT",
                    high=high,
                    low=low,
                    target=target,
                ):

                    exit_index = i
                    exit_price = target
                    exit_reason = "TARGET"
                    break

        if direction == "LONG":

            gross_return_pct = (
                (exit_price - entry_price)
                / entry_price
            ) * 100

        else:

            gross_return_pct = (
                (entry_price - exit_price)
                / entry_price
            ) * 100

        net_return_pct = gross_return_pct

        quantity = 1

        invested_capital = (
            entry_price * quantity
        )

        gross_pnl = (
            (exit_price - entry_price)
            * quantity
        )

        if direction == "SHORT":
            gross_pnl *= -1

        net_pnl = gross_pnl

        risk = abs(
            entry_price - stop_loss
        )

        if risk > 0:

            risk_reward = abs(
                exit_price - entry_price
            ) / risk

        else:

            risk_reward = 0.0

        return TradeResult(
            symbol=symbol,
            strategy=strategy,
            direction=direction,
            entry_index=entry_index,
            exit_index=exit_index,
            entry_date=df.index[entry_index],
            exit_date=df.index[exit_index],
            entry_price=entry_price,
            exit_price=exit_price,
            quantity=quantity,
            invested_capital=round(
                invested_capital,
                2,
            ),
            gross_pnl=round(
                gross_pnl,
                2,
            ),
            net_pnl=round(
                net_pnl,
                2,
            ),
            stop_loss=stop_loss,
            target=target,
            holding_bars=exit_index - entry_index,
            exit_reason=exit_reason,
            gross_return_pct=round(
                gross_return_pct,
                4,
            ),
            net_return_pct=round(
                net_return_pct,
                4,
            ),
            risk_reward=round(
                risk_reward,
                4,
            ),
            mfe=round(
                mfe * 100,
                4,
            ),
            mae=round(
                mae * 100,
                4,
            ),
            transaction_cost=TransactionCost(
                brokerage=0.0,
                slippage=0.0,
                taxes=0.0,
                total=0.0,
            ),
        )
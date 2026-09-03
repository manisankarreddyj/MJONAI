from research.backtest.models import TradeResult
from research.backtest.models import TransactionCost


class TradeSimulator:
    """
    Executes one completed trade from one strategy signal.
    """

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

                if high >= target:

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

                if low <= target:

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
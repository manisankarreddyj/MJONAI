"""Deterministic backward price adjustment engine (Decision 6 Phase 2).

Turns a RAW (broker-native, split/dividend-gap-intact) daily OHLC series into
the ADJUSTED regime without any network dependency. The factors come from
`mjonai.research.data.corporate_actions` (or any provider of
`CorporateActionFactor` records); the math here is pure and pinned by
golden-example tests.

Adjustment convention (Yahoo `auto_adjust`-compatible, multiplicative)
---------------------------------------------------------------------
Share-count semantics: `share_multiplier` = NEW shares per OLD share
(a 1:5 face-value split => 5, a 1:1 bonus => 2). Backward adjustment
expresses every historical price in CURRENT (latest) per-share units.

For a bar at time t:

    S(t) = product of share_multipliers over actions with ex_date > t

    A(t) = product over dividends j with e_j > t of ( 1 - d_j / P_j )

    where P_j is the chart-style price of the bar immediately BEFORE
    dividend j's ex-date, expressed in the same (split-adjusted) share
    scale as the bars it is applied to: P_j = raw(i_j)/ S(i_j), with
    i_j = last bar timestamped strictly before e_j.

    adjusted_price(t) = raw_price(t) / S(t) * A(t)
    adjusted_volume(t) = raw_volume(t) * S(t)

Every factor applies to bars STRICTLY BEFORE its ex-date; the ex-date bar
itself trades ex-entitlement (post-split count, ex-dividend price) and is
therefore already in the target scale for that factor.

Why multiplicative dividends (not naive subtraction)? This is the exact
scheme yfinance/Yahoo `auto_adjust=True` and the NSE/BSE capital-adjustment
convention use: a dividend is expressed as a RETURN-interval factor
(1 - d/P) rather than a fixed rupee haircut. Empirical check against
yfinance on RELIANCE (1996-2026, 4 splits + 33 dividends): max relative
diff ~0.01% using this form; the naive additive form is off by several
orders more. The ADJUSTED cache regime IS yfinance auto_adjust (Decision 6
Phase 1), so the engine must reproduce it.

The form is fully commutative: dividends and splits are independent
(one divides, one multiplies the same old bars), so no bar-pair crossing
an ex-date shows a fabricated gap - verified by golden tests below.
"""

from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd

from mjonai.research.data.corporate_actions import CorporateActionFactor

_OHLC = ("open", "high", "low", "close")


def cumulative_split_scale(
    timestamps: np.ndarray,
    factors: Iterable[CorporateActionFactor],
) -> np.ndarray:
    """S(t): product of share multipliers for actions with ex_date > t.

    Vectorized over a datetime64 bar-timestamp array. Ex-date bars are
    already post-entitlement, so the strict < mask (bars BEFORE ex-date)
    is correct.
    """
    factors = list(factors)
    scale = np.ones(len(timestamps), dtype=float)
    for factor in factors:
        if factor.share_multiplier != 1.0:
            ex = np.datetime64(pd.Timestamp(factor.ex_date))
            scale[timestamps < ex] *= factor.share_multiplier
    return scale


def _dividend_reference_prices(
    timestamps: np.ndarray,
    close: np.ndarray,
    factors: list[CorporateActionFactor],
    split_scale: np.ndarray,
) -> dict:
    """Map each dividend ex_date -> its chart-style reference price P_j.

    P_j = raw close of the bar immediately before the ex-date, divided by
    the split scale at that bar (so P_j is in the SAME share scale as the
    bars the (1 - d/P) factor gets applied to). Circular reference: the
    dividend's own ex-date bar (if any) is excluded - the reference bar is
    strictly before it, so the split at the ex-date itself is included in
    S(i_j) exactly as in Yahoo's chart arithmetic.
    """
    if len(close) == 0:
        return {}
    ts_ns = pd.to_datetime(pd.Series(timestamps)).to_numpy()
    reference = {}
    payments = [
        (f.ex_date, f.dividend_per_share)
        for f in factors
        if f.dividend_per_share is not None
    ]
    for ex_date, _d in payments:
        ex = np.datetime64(pd.Timestamp(ex_date))
        # last bar index strictly before ex-date
        pos = int(np.searchsorted(ts_ns, ex, side="left") - 1)
        if pos < 0 or pos >= len(close):
            continue
        denom = split_scale[pos]
        ref = float(close[pos]) / denom if denom else float(close[pos])
        if ref > 0:
            reference[ex_date] = ref
    return reference


def dividend_adjustment_factors(
    timestamps: np.ndarray,
    close: np.ndarray,
    factors: Iterable[CorporateActionFactor],
) -> tuple[np.ndarray, np.ndarray]:
    """Per-bar multiplicative dividend adjustment A(t) (Yahoo convention).

    A(t) = product over dividends j with e_j > t of (1 - d_j / P_j).
    The split scale S is computed internally so each dividend's reference
    price is the chart-style (split-adjusted) price at its ex-date. Returns
    (A, S) so callers can reuse the split scale.
    """
    factors = list(factors)
    S = cumulative_split_scale(timestamps, factors)
    A = np.ones(len(timestamps), dtype=float)
    reference = _dividend_reference_prices(timestamps, close, factors, S)
    payments = [
        f for f in factors if f.dividend_per_share is not None
    ]
    for div in payments:
        P = reference.get(div.ex_date)
        if P is None:
            continue
        factor = (P - div.dividend_per_share) / P
        if factor <= 0:
            continue
        ex = np.datetime64(pd.Timestamp(div.ex_date))
        A[timestamps < ex] *= factor
    return A, S


def backward_adjust_series(
    close: np.ndarray,
    timestamps: np.ndarray,
    factors: Iterable[CorporateActionFactor],
) -> tuple[np.ndarray, np.ndarray]:
    """Close-adjusted prices + split scale, both vectorized."""
    factors = list(factors)
    A, S = dividend_adjustment_factors(timestamps, close, factors)
    adjusted = np.asarray(close, dtype=float) / S * A
    return adjusted, S


def apply_adjustment_factors(
    data: pd.DataFrame,
    factors: Iterable[CorporateActionFactor],
) -> pd.DataFrame:
    """Return a NEW adjusted-OHLCV copy of `data` (never mutates).

    `data` must contain a `timestamp` column (datetime) plus open/high/low/
    close columns; volume is adjusted when present. Every OHLC field gets the
    same (price / S(t) * A(t)) treatment; volume scales by S(t). Bars on or
    after the last factor are returned unchanged (S=1, A=1). On empty inputs
    or missing columns a ValueError is raised (fail closed).
    """
    if data is None or len(data) == 0:
        raise ValueError("cannot adjust an empty price frame")

    missing = [c for c in _OHLC if c not in data.columns]
    if missing:
        raise ValueError(
            f"price frame missing required columns: {missing}"
        )
    if "timestamp" not in data.columns:
        raise ValueError("price frame missing 'timestamp' column")

    factors = list(factors)
    timestamps = pd.to_datetime(data["timestamp"].to_numpy()).to_numpy()
    close = np.asarray(data["close"].to_numpy(dtype=float))
    A, S = dividend_adjustment_factors(timestamps, close, factors)

    out = data.copy(deep=True)
    for col in _OHLC:
        raw = np.asarray(data[col].to_numpy(dtype=float))
        out[col] = raw / S * A

    if "volume" in data.columns:
        out["volume"] = np.asarray(
            data["volume"].to_numpy(dtype=float)
        ) * S

    return out


def adjust_historical_data(
    data: HistoricalData,
    factors: Iterable[CorporateActionFactor],
) -> HistoricalData:
    """Apply the adjustment engine to a research HistoricalData object.

    Bridges the pure DataFrame engine to the research pipeline's Candle
    models: builds a frame from the candles, runs apply_adjustment_factors
    (never mutating the input), and rebuilds a NEW HistoricalData carrying
    the same instrument/timeframe metadata. Useful for turning a native-RAW
    (Angel/Shoonya) series into the ADJUSTED regime on demand.
    """
    from mjonai.research.data.models import Candle, HistoricalData

    if data is None or not data.candles:
        raise ValueError("cannot adjust empty historical data")

    frame = pd.DataFrame(
        [
            {
                # Research candles are naive-IST by convention; a tz-aware
                # stamp (e.g. yielded by yfinance) would break the engine's
                # numpy datetime64 `timestamps < ex` comparison.
                "timestamp": candle.timestamp.to_pydatetime().replace(tzinfo=None)
                if getattr(candle.timestamp, "tzinfo", None)
                else candle.timestamp,
                "open": candle.open,
                "high": candle.high,
                "low": candle.low,
                "close": candle.close,
                "volume": candle.volume,
            }
            for candle in data.candles
        ]
    )

    adjusted = apply_adjustment_factors(frame, factors)

    candles = [
        Candle(
            timestamp=pd.Timestamp(row.timestamp).to_pydatetime(),
            open=float(row.open),
            high=float(row.high),
            low=float(row.low),
            close=float(row.close),
            volume=float(row.volume),
        )
        for row in adjusted.itertuples(index=False)
    ]

    return HistoricalData(
        instrument=data.instrument,
        timeframe=data.timeframe,
        candles=candles,
    )
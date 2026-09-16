"""Regression tests for the Decision 6 Phase 2 adjustment engine.

Pins the deterministic backward-adjust math (golden examples), the strict
free-text corporate-action parser (fail closed on any unparseable
price-altering record), and the lazy india-corp-actions wrapper (never
imported at module import time; never fabricated on dependency absence).
"""

from datetime import date, datetime

import numpy as np
import pandas as pd
import pytest

from mjonai.research.data.adjustment import (
    apply_adjustment_factors,
    backward_adjust_series,
    cumulative_split_scale,
)
from mjonai.research.data.corporate_actions import (
    CorporateActionFactor,
    CorporateActionParseError,
    CorporateActionSourceError,
    CorporateActionsClient,
    factors_from_records,
    parse_details,
)

D1 = date(2024, 1, 1)
D2 = date(2024, 2, 1)
D3 = date(2024, 3, 1)
D4 = date(2024, 4, 1)


def factor(action_type, ex_date, share_multiplier=1.0, dividend=None):
    return CorporateActionFactor(
        ex_date=ex_date,
        action_type=action_type,
        share_multiplier=share_multiplier,
        dividend_per_share=dividend,
    )


def frame(prices, start=datetime(2024, 1, 1), volume=1_000.0):
    n = len(prices)
    ts = pd.date_range(start, periods=n, freq="D")
    return pd.DataFrame(
        {
            "timestamp": ts,
            "open": prices,
            "high": [p + 1.0 for p in prices],
            "low": [p - 1.0 for p in prices],
            "close": prices,
            "volume": [volume] * n,
        }
    )


def stamped_frame(timestamps, prices, volume=1_000.0):
    n = len(timestamps)
    ts = [np.datetime64(t) for t in timestamps]
    return pd.DataFrame(
        {
            "timestamp": ts,
            "open": prices,
            "high": [p + 1.0 for p in prices],
            "low": [p - 1.0 for p in prices],
            "close": prices,
            "volume": [volume] * n,
        }
    )


class TestGoldenMath:
    def test_no_factors_identity(self):
        ts = pd.date_range(D1, periods=4)
        raw = np.array([100.0, 101.0, 102.0, 103.0])
        S = cumulative_split_scale(ts.to_numpy(), [])
        assert np.allclose(S, 1.0)
        out = apply_adjustment_factors(frame(list(raw)), [])
        assert np.allclose(out["close"], raw)

    def test_split_scales_only_pre_ex_bars(self):
        # 1:5 face-value split (multiplier 5) on 2024-03-01. Bars BEFORE the
        # ex-date divide by 5; the ex-date bar (post-split) and later bars
        # stay untouched.
        raw = np.array([500.0, 510.0, 105.0, 106.0])
        ts = np.array(
            [np.datetime64("2024-02-01"), np.datetime64("2024-02-15"),
             np.datetime64("2024-03-01"), np.datetime64("2024-03-05")],
        )
        ft = factor("split", D3, share_multiplier=5.0)
        adj, S = backward_adjust_series(raw, ts, [ft])
        assert np.allclose(S, [5.0, 5.0, 1.0, 1.0])
        assert np.allclose(adj, [100.0, 102.0, 105.0, 106.0])

    def test_bonus_same_math_as_split(self):
        raw = np.array([400.0, 402.0, 140.0])
        ts = np.array(
            [np.datetime64("2024-02-01"), np.datetime64("2024-02-15"),
             np.datetime64("2024-03-01")],
        )
        ft = factor("bonus", D3, share_multiplier=2.0)
        adj, S = backward_adjust_series(raw, ts, [ft])
        assert np.allclose(S, [2.0, 2.0, 1.0])
        assert np.allclose(adj, [200.0, 201.0, 140.0])

    def test_dividend_multiplicative_factor_before_ex(self):
        # Yahoo-style: dividend 5 on 2024-03-01 with reference price P=102
        # (close of the last bar strictly before the ex-date, split scale 1).
        # Bars strictly before the ex-date multiply by (102-5)/102; the
        # ex-date bar (already ex-dividend) is unchanged.
        raw = np.array([100.0, 101.0, 102.0, 98.0])
        ts = np.array(
            [np.datetime64("2024-02-01"), np.datetime64("2024-02-10"),
             np.datetime64("2024-02-20"), np.datetime64("2024-03-01")],
        )
        ft = factor("dividend", D3, dividend=5.0)
        adj, S = backward_adjust_series(raw, ts, [ft])
        assert np.allclose(S, [1.0, 1.0, 1.0, 1.0])
        assert np.allclose(
            adj, [100.0 * 97 / 102, 101.0 * 97 / 102, 97.0, 98.0]
        )

    def test_split_then_dividend_order_commutes(self):
        # Split (x5) on 2024-02-01, dividend 5 on 2024-03-01. The dividend
        # reference price is the last bar strictly before 03-01 (close 104,
        # split scale 1 at that bar) -> factor 99/104. Both pre-03-01 bars
        # carry it; the split also divides the 01-15 bar by 5.
        raw = np.array([500.0, 104.0, 100.0])
        ts = np.array(
            [np.datetime64("2024-01-15"), np.datetime64("2024-02-15"),
             np.datetime64("2024-03-05")],
        )
        ft = [
            factor("split", D2, share_multiplier=5.0),
            factor("dividend", D3, dividend=5.0),
        ]
        adj, S = backward_adjust_series(raw, ts, ft)
        assert np.allclose(S, [5.0, 1.0, 1.0])
        assert np.allclose(
            adj, [100.0 * 99 / 104, 99.0, 100.0]
        )

    def test_dividend_reference_price_split_scaled(self):
        # Dividend 5 on 2024-02-01 paid PER OLD share, with a later 5x split
        # on 2024-04-01. The reference price used for the (1 - d/P) factor is
        # the chart-style (split-adjusted) price at the dividend's ex-date:
        # close 100 / S(reference bar=5) = 20 -> factor (20-5)/20 = 0.75.
        # The 01-15 bar (strictly before the dividend ex-date) carries the
        # 0.75 factor AND the split division; the 02-15 bar (after dividend,
        # before split) only the split; the 05-01 post-split bar is untouched.
        raw = np.array([100.0, 94.0, 24.0])
        ts = np.array(
            [np.datetime64("2024-01-15"), np.datetime64("2024-02-15"),
             np.datetime64("2024-05-01")],
        )
        ft = [
            factor("dividend", D2, dividend=5.0),
            factor("split", D4, share_multiplier=5.0),
        ]
        adj, S = backward_adjust_series(raw, ts, ft)
        assert np.allclose(S, [5.0, 5.0, 1.0])
        assert np.allclose(adj, [15.0, 94.0 / 5, 24.0])

    def test_multiple_splits_compound(self):
        raw = np.array([1_000.0, 210.0, 45.0])
        ts = np.array(
            [np.datetime64("2024-01-15"), np.datetime64("2024-02-15"),
             np.datetime64("2024-05-01")],
        )
        ft = [
            factor("split", D2, share_multiplier=5.0),
            factor("split", D3, share_multiplier=5.0),
        ]
        adj, S = backward_adjust_series(raw, ts, ft)
        assert np.allclose(S, [25.0, 5.0, 1.0])
        assert np.allclose(adj, [40.0, 42.0, 45.0])

    def test_volume_scales_by_split_only(self):
        df = stamped_frame(
            ["2024-02-01", "2024-02-15", "2024-03-01"],
            [500.0, 510.0, 105.0],
        )
        ft = factor("split", D3, share_multiplier=5.0)
        out = apply_adjustment_factors(df, [ft])
        assert np.allclose(out["volume"], [5_000.0, 5_000.0, 1_000.0])

    def test_ohlc_all_adjusted_high_low_included(self):
        df = stamped_frame(
            ["2024-02-01", "2024-02-15", "2024-03-01"],
            [500.0, 510.0, 105.0],
        )
        ft = factor("split", D3, share_multiplier=5.0)
        out = apply_adjustment_factors(df, [ft])
        assert np.allclose(out["open"], [100.0, 102.0, 105.0])
        # high = price + 1 -> (price+1)/5 before the ex-date.
        assert np.allclose(out["high"], [100.2, 102.2, 106.0])
        assert np.allclose(out["low"], [99.8, 101.8, 104.0])

    def test_input_frame_never_mutated(self):
        df = stamped_frame(
            ["2024-02-01", "2024-02-15", "2024-03-01"],
            [500.0, 510.0, 105.0],
        )
        snapshot = df.copy(deep=True)
        ft = factor("split", D3, share_multiplier=5.0)
        apply_adjustment_factors(df, [ft])
        pd.testing.assert_frame_equal(df, snapshot)


class TestFailClosed:
    def test_empty_frame_raises(self):
        with pytest.raises(ValueError, match="empty"):
            apply_adjustment_factors(pd.DataFrame(), [])

    def test_missing_columns_raises(self):
        df = pd.DataFrame({"timestamp": [datetime(2024, 1, 1)], "close": [1.0]})
        with pytest.raises(ValueError, match="missing required columns"):
            apply_adjustment_factors(df, [])

    def test_missing_timestamp_raises(self):
        df = pd.DataFrame(
            {"open": [1.0], "high": [1.0], "low": [1.0], "close": [1.0]}
        )
        with pytest.raises(ValueError, match="timestamp"):
            apply_adjustment_factors(df, [])


class TestParser:
    def test_split_face_value(self):
        ft = parse_details("split", "FACE VALUE SPLIT from Rs 10/- to Rs 2/-", D1)
        assert ft.action_type == "split"
        assert ft.share_multiplier == pytest.approx(5.0)

    def test_split_subdivision(self):
        ft = parse_details(
            "split", "Sub Division of Equity Shares from Rs. 10 to Rs. 5", D1
        )
        assert ft.share_multiplier == pytest.approx(2.0)

    def test_split_unparseable_fails_closed(self):
        with pytest.raises(CorporateActionParseError, match="split"):
            parse_details("split", "Stock split of equity shares", D1)

    def test_split_face_value_not_decreasing_fails_closed(self):
        with pytest.raises(CorporateActionParseError, match="split"):
            parse_details("split", "from Rs 2/- to Rs 10/-", D1)

    def test_bonus_shares_for_every(self):
        ft = parse_details(
            "bonus", "1 Equity Share for every 1 Equity Share held", D1
        )
        assert ft.share_multiplier == pytest.approx(2.0)

    def test_bonus_ratio(self):
        ft = parse_details("bonus", "Bonus issue in the ratio of 1:2", D1)
        assert ft.share_multiplier == pytest.approx(1.5)

    def test_bonus_unparseable_fails_closed(self):
        with pytest.raises(CorporateActionParseError, match="bonus"):
            parse_details("bonus", "Bonus issue of equity shares", D1)

    def test_dividend_rupee_amount(self):
        ft = parse_details("dividend", "Dividend - Rs 5 Per Share", D1)
        assert ft.dividend_per_share == pytest.approx(5.0)
        assert ft.share_multiplier == 1.0

    def test_dividend_pct_with_face_value(self):
        ft = parse_details(
            "dividend", "120% Dividend", D1, face_value="2"
        )
        assert ft.dividend_per_share == pytest.approx(2.4)

    def test_dividend_pct_without_face_value_fails_closed(self):
        with pytest.raises(CorporateActionParseError, match="dividend"):
            parse_details("dividend", "120% Dividend", D1)

    def test_dividend_no_amount_fails_closed(self):
        with pytest.raises(CorporateActionParseError, match="dividend"):
            parse_details("dividend", "Dividend declared", D1)

    def test_unsupported_action_fails_closed(self):
        with pytest.raises(CorporateActionParseError, match="unsupported"):
            parse_details("rights", "Rights issue ratio 1:1", D1)

    def test_missing_ex_date_fails_closed(self):
        with pytest.raises(CorporateActionParseError, match="ex_date"):
            parse_details("split", "from Rs 10/- to Rs 2/-", None)


class _Record:
    def __init__(self, action_type, details, ex_date, face_value=None):
        self.action_type = action_type
        self.details = details
        self.ex_date = ex_date
        self.face_value = face_value


class TestFactorsFromRecords:
    def test_sorts_by_ex_date_and_skips_non_adjustable(self):
        records = [
            _Record("dividend", "Dividend - Rs 3 Per Share", D2),
            _Record("split", "FACE VALUE SPLIT from Rs 10 to Rs 2", D1),
            _Record("agm", "Annual General Meeting", D3),
            _Record("rights", "Rights issue", D4),
        ]
        factors, skipped = factors_from_records(records)
        assert [f.ex_date for f in factors] == [D1, D2]
        assert factors[0].share_multiplier == pytest.approx(5.0)
        assert factors[1].dividend_per_share == pytest.approx(3.0)
        assert skipped == ["agm", "rights"]

    def test_price_altering_unparseable_aborts_batch(self):
        records = [
            _Record("split", "FACE VALUE SPLIT from Rs 10 to Rs 2", D1),
            _Record("split", "Stock split of equity shares", D2),
        ]
        with pytest.raises(CorporateActionParseError):
            factors_from_records(records)


class TestLazyClient:
    def test_uninstalled_package_raises_source_error(self, monkeypatch):
        import sys

        monkeypatch.setitem(sys.modules, "india_corp_actions", None)
        client = CorporateActionsClient()
        with pytest.raises(CorporateActionSourceError, match="not installed"):
            client.fetch_factors("RELIANCE")

    def test_fetch_success_parses_records(self, monkeypatch):
        class FakeClient:
            def get_actions(self, **kwargs):
                assert kwargs["symbol"] == "RELIANCE"
                assert kwargs["source"] == "NSE"
                return [
                    _Record("dividend", "Dividend - Rs 5 Per Share", D1),
                ]

        client = CorporateActionsClient()
        monkeypatch.setattr(client, "_get_client", lambda: FakeClient())
        factors = client.fetch_factors("RELIANCE")
        assert len(factors) == 1
        assert factors[0].dividend_per_share == pytest.approx(5.0)

    def test_source_failure_wrapped(self, monkeypatch):
        class BrokenClient:
            def get_actions(self, **kwargs):
                raise RuntimeError("NSE endpoint refused")

        client = CorporateActionsClient()
        monkeypatch.setattr(client, "_get_client", lambda: BrokenClient())
        with pytest.raises(CorporateActionSourceError, match="RELIANCE"):
            client.fetch_factors("RELIANCE")


@pytest.mark.network
class TestYahooCrossValidation:
    """Empirical cross-check: the multiplicative engine reproduces yfinance
    ``auto_adjust=True`` on real symbols with rich split/dividend history.

    Network-dependent (yfinance chart + actions fetch) - excluded from the
    deterministic CI non-network subset. Run on the full-credentials machine
    or with research egress open.
    """

    SYMBOLS = ["RELIANCE.NS", "HDFCBANK.NS", "INFY.NS", "TCS.NS"]

    def _reconstruct_true_raw_and_adjust(
        self, ticker, start="2016-01-01", end="2026-09-16"
    ):
        import yfinance as yf

        t = yf.Ticker(ticker)
        r = t.history(start=start, end=end, interval="1d", auto_adjust=False)
        a = t.history(start=start, end=end, interval="1d", auto_adjust=True)
        acts = t.get_actions()

        splits = {
            ex.date(): float(acts.loc[ex, "Stock Splits"])
            for ex in acts.index
            if float(acts.loc[ex, "Stock Splits"]) != 0
        }
        fac = []
        for ex in acts.index:
            sp = float(acts.loc[ex, "Stock Splits"])
            dv = float(acts.loc[ex, "Dividends"])
            if sp and sp > 1:
                fac.append(CorporateActionFactor(
                    ex_date=ex.date(), action_type="split",
                    share_multiplier=sp,
                ))
            elif sp and sp < 1:
                fac.append(CorporateActionFactor(
                    ex_date=ex.date(), action_type="split",
                    share_multiplier=1.0 / sp,
                ))
            if dv and dv > 0:
                fac.append(CorporateActionFactor(
                    ex_date=ex.date(), action_type="dividend",
                    dividend_per_share=dv,
                ))

        idx = np.array([
            np.datetime64(pd.Timestamp(x).tz_localize(None))
            for x in r.index
        ])
        close_sa = r["Close"].to_numpy(dtype=float)

        def s_scale(ts):
            m = 1.0
            for ex, ratio in splits.items():
                if pd.Timestamp(ex) > pd.Timestamp(ts):
                    m *= ratio
            return m

        # Yahoo's auto_adjust=False close is already split-adjusted; undo
        # the split adjustment to recover the TRUE raw series the engine
        # expects (split + dividend gaps intact).
        true_raw = np.array(
            [close_sa[i] * s_scale(idx[i]) for i in range(len(idx))]
        )
        df = pd.DataFrame({
            "timestamp": [pd.Timestamp(x) for x in idx],
            "open": true_raw,
            "high": true_raw,
            "low": true_raw,
            "close": true_raw,
            "volume": r["Volume"].to_numpy(),
        })
        mine = apply_adjustment_factors(df, fac)["close"].to_numpy()
        return mine, a["Close"].to_numpy()

    def test_reproduces_yahoo_auto_adjust_sub_ppm(self):
        threshold = 1e-4  # 100 ppm headroom; observed values are < 1 ppm
        for sym in self.SYMBOLS:
            mine, ref = self._reconstruct_true_raw_and_adjust(sym)
            rel = np.abs(mine / ref - 1)
            assert np.max(rel) < threshold, (
                f"{sym}: max rel diff {np.max(rel):.2e} >= {threshold}"
            )
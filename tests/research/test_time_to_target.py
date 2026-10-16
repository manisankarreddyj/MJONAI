"""Regression pins for research/analytics/time_to_target.py.

Measured medians publish only above the target-hit floor; anything thinner
reads insufficient — never a number dressed as measurement.
"""
from types import SimpleNamespace

from mjonai.research.analytics.time_to_target import summarize_time_to_target


def _t(reason, bars):
    return SimpleNamespace(exit_reason=reason, holding_bars=bars)


def test_median_p25_p75_over_target_exits():
    trades = [_t("TARGET", b) for b in (4, 6, 8, 10, 12, 14, 16, 18, 20, 22)]
    out = summarize_time_to_target(trades, min_target_hits=10)
    assert out["n_trades"] == 10
    assert out["n_target"] == 10
    assert out["target_hit_rate"] == 1.0
    assert out["median_days_to_target"] == 13.0  # (12+14)/2
    assert out["p25_days_to_target"] == 8.5
    assert out["p75_days_to_target"] == 17.5
    assert out["insufficient_reason"] is None


def test_floor_withholds_thin_medians():
    trades = [_t("TARGET", b) for b in (5, 6, 7, 8, 9)]  # 5 < 10
    out = summarize_time_to_target(trades, min_target_hits=10)
    assert out["median_days_to_target"] is None
    assert out["p25_days_to_target"] is None
    assert out["p75_days_to_target"] is None
    assert "5" in out["insufficient_reason"] and "10" in out["insufficient_reason"]


def test_mixed_exit_reasons_pool_correctly():
    trades = ([_t("TARGET", b) for b in range(1, 11)]
              + [_t("STOPLOSS", 3)] * 20
              + [_t("TIMEOUT", 20)] * 5
              + [_t("END_OF_DATA", 7)] * 2)
    out = summarize_time_to_target(trades, min_target_hits=10)
    assert out["n_trades"] == 37
    assert out["n_target"] == 10
    assert out["n_stop"] == 20
    assert out["n_timeout"] == 5
    assert out["n_end_of_data"] == 2
    assert out["target_hit_rate"] == round(10 / 37, 3)
    assert out["median_days_to_target"] == 5.5
    assert out["median_days_to_stop"] == 3.0
    assert out["median_days_to_timeout"] == 20.0


def test_empty_and_garbage_never_fabricate():
    assert summarize_time_to_target([], min_target_hits=10)["median_days_to_target"] is None
    assert summarize_time_to_target([], min_target_hits=10)["target_hit_rate"] is None
    weird = [_t("TARGET", -3), _t("TARGET", "junk"), _t("BOGUS", 5), _t(None, 4)]
    out = summarize_time_to_target(weird, min_target_hits=1)
    # Negative / non-numeric bars skipped; BOGUS + None-reason count to n only.
    assert out["n_trades"] == 2
    assert out["median_days_to_target"] is None  # 0 target bars survived


def test_short_trades_pool_with_longs():
    trades = [_t("TARGET", 6)] * 5 + [_t("TARGET", 14)] * 5  # direction unrecorded here
    out = summarize_time_to_target(trades, min_target_hits=10)
    assert out["median_days_to_target"] == 10.0

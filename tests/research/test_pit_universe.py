"""Regression tests: Decision 6 Phase 3 — point-in-time (PIT) universe.

The curated Nifty 50 membership ledger (``mjonai/data/pit/``) answers
membership as-of any date inside its coverage. Survivorship contract:
never retrospectively substitute today's constituents, fail closed outside
coverage, and mask every signal to its symbol's true membership legs.

Fully offline — the ledger is a committed CSV, no network.
"""

from datetime import date, datetime, timedelta

import pandas as pd
import pytest

from mjonai.research.data.models import Candle
from mjonai.research.pit_universe import (
    NIFTY50_INDEX_NAME,
    PitUniverseLedger,
    mask_signals_by_membership,
)
from mjonai.research.universe_loader import (
    UniverseTier,
    load_universe_symbols,
)


def make_signal(index, side="BUY", symbol="RELIANCE"):
    return type(
        "Sig",
        (),
        {
            "index": index,
            "side": side,
            "symbol": symbol,
            "entry_price": 100.0,
            "stop_loss": 95.0,
        },
    )()


def make_df(dates):
    return pd.DataFrame(
        {
            "Open": [100.0] * len(dates),
            "High": [101.0] * len(dates),
            "Low": [99.0] * len(dates),
            "Close": [100.0] * len(dates),
            "Volume": [1000.0] * len(dates),
        },
        index=pd.DatetimeIndex(dates),
    )


def test_ledger_loads_vendored_nifty50_subset():
    ledger = PitUniverseLedger()
    ledger._ensure_loaded()
    assert len(ledger._rows) == 83
    # 82 distinct symbols — one re-introduction (GRASIM) legitimately
    # occupies a second row.
    symbols = {r["symbol"] for r in ledger._rows}
    assert len(symbols) == 82
    open_legs = [r for r in ledger._rows if r["valid_to"] is None]
    assert len(open_legs) == 50
    assert ledger.coverage_start == date(2014, 1, 1)


def test_membership_intervals_half_open_bounds():
    ledger = PitUniverseLedger()
    # JPASSOCIAT: 2014-01-01 -> 2014-03-28 (exited before MCDOWELL-N entered).
    legs = ledger.membership_intervals("JPASSOCIAT")
    assert legs == [(date(2014, 1, 1), date(2014, 3, 28))]
    # MCDOWELL-N: entered 2014-03-28 (a press_release leg).
    legs = ledger.membership_intervals("MCDOWELL-N")
    assert legs == [(date(2014, 3, 28), date(2014, 9, 19))]
    # Unknown symbol is [] — never treated as "always member".
    assert ledger.membership_intervals("NOTAREALSYM") == []


def test_grasim_two_legs_not_merged():
    """A re-entry must not bleed into the gap: GRASIM exited 2017-05-26 and
    re-entered 2018-04-02 — the gap is a non-membership period."""
    ledger = PitUniverseLedger()
    legs = ledger.membership_intervals("GRASIM")
    assert len(legs) == 2
    assert legs[0] == (date(2014, 1, 1), date(2017, 5, 26))
    assert legs[1] == (date(2018, 4, 2), None)

    assert ledger.is_member("GRASIM", date(2017, 1, 1)) is True
    assert ledger.is_member("GRASIM", date(2017, 12, 1)) is False
    assert ledger.is_member("GRASIM", date(2018, 6, 1)) is True


def test_is_member_boundary_semantics():
    ledger = PitUniverseLedger()
    # JPASSOCIAT exits 2014-03-28: valid up to but NOT including that day.
    assert ledger.is_member("JPASSOCIAT", date(2014, 3, 27)) is True
    assert ledger.is_member("JPASSOCIAT", date(2014, 3, 28)) is False
    # datetime accepted too.
    assert ledger.is_member(
        "JPASSOCIAT", datetime(2014, 3, 27, 15, 30)
    ) is True


def test_alias_maps_tatamotors_to_tmpv():
    """The ledger holds the post-demerger index symbol TMPV; research code
    still asks for TATAMOTORS (strategy/config.py maps TATAMOTORS->TMPV.NS)."""
    ledger = PitUniverseLedger()
    legs = ledger.membership_intervals("TATAMOTORS")
    tmpv_legs = ledger.membership_intervals("TMPV")
    assert legs == tmpv_legs
    assert ledger.is_member("TATAMOTORS", date(2016, 6, 1)) is True


def test_specific_historical_membership_snapshot():
    """2016-06-15 membership: JPASSOCIAT gone, MCDOWELL-N gone (2014), GRASIM
    in, TRENT/BEL/JIOFIN/INDIGO/MAXHEALTH NOT in yet (post-2024 flags)."""
    ledger = PitUniverseLedger()
    day = date(2016, 6, 15)
    members = set(ledger.members(day))
    assert "GRASIM" in members
    assert "JPASSOCIAT" not in members
    assert "MCDOWELL-N" not in members
    assert "RELIANCE" in members
    assert "TRENT" not in members
    assert "BEL" not in members
    assert "JIOFIN" not in members
    assert "ETERNAL" not in members


def test_current_open_list_contains_recent_entrants():
    """Today's ledger membership is STILL the current Nifty 50 — and it
    differs from the stale hardcoded SECTOR_UNIVERSES list (which has
    SIEMENS/IOC/LICI and lacks JIOFIN/ETERNAL/etc.)."""
    ledger = PitUniverseLedger()
    members = set(ledger.members(date.today()))
    assert len(members) == 50
    assert "ETERNAL" in members
    assert "JIOFIN" in members
    assert "INDIGO" in members
    assert "MAXHEALTH" in members
    assert "SIEMENS" not in members
    assert "IOC" not in members
    assert "LICI" not in members


def test_coverage_fail_closed_before_2014():
    ledger = PitUniverseLedger()
    with pytest.raises(ValueError, match="predates ledger coverage"):
        ledger.members(date(2013, 12, 31))
    with pytest.raises(ValueError, match="predates ledger coverage"):
        ledger.is_member("RELIANCE", datetime(2013, 6, 1, 10, 0))
    # 2014-01-01 is the honest floor — valid.
    assert ledger.is_member("RELIANCE", date(2014, 1, 1)) is True


def test_missing_ledger_file_raises():
    with pytest.raises(FileNotFoundError, match="membership history CSV"):
        PitUniverseLedger(csv_path="C:/definitely/not/there.csv").members(
            date(2020, 1, 1)
        )


# ── mask_signals_by_membership ─────────────────────────────────────────────


def _df_with_signal_index(df, signal_index):
    return df, make_signal(signal_index)


def test_mask_keeps_only_member_entry_bars():
    df = make_df([datetime(2024, 1, 1) + timedelta(days=i) for i in range(10)])
    legs = [(date(2024, 1, 1), date(2024, 1, 5))]  # bars index 0..4 eligible

    # Signal at bar 3 -> entry bar 4 (index+1). 2024-01-05 inside [start, end).
    # Signal at bar 4 -> entry bar 5 -> 2024-01-06 -> NOT a member (end excl).
    signals = [make_signal(1), make_signal(4)]

    masked = mask_signals_by_membership(df, signals, legs)
    assert [s.index for s in masked] == [1]


def test_mask_all_or_nothing_on_leg_boundaries():
    df = make_df([datetime(2024, 1, 1) + timedelta(days=i) for i in range(5)])
    legs = [(date(2024, 1, 3), None)]  # open leg from 2024-01-03

    signals = [make_signal(0), make_signal(3)]  # entries 01-02 and 01-04
    masked = mask_signals_by_membership(df, signals, legs)
    assert [s.index for s in masked] == [3]


def test_mask_empty_legs_yields_no_signals():
    df = make_df([datetime(2024, 1, 1) + timedelta(days=i) for i in range(5)])
    assert mask_signals_by_membership(df, [make_signal(1)], []) == []


# ── load_universe_symbols(asof=...) ─────────────────────────────────────────


def test_load_universe_asof_returns_pit_list():
    full = set(load_universe_symbols(
        tier=UniverseTier.NIFTY_50,
        asof=date(2016, 6, 15),
        max_count=100,
    ))
    symbols = load_universe_symbols(
        tier=UniverseTier.NIFTY_50,
        asof=date(2016, 6, 15),
        max_count=10,
    )
    assert isinstance(symbols, list)
    assert symbols == sorted(symbols)
    assert all(s in full for s in symbols)
    assert "RELIANCE" in full
    assert "JPASSOCIAT" not in full
    assert len(symbols) <= 10


def test_load_universe_asof_max_count():
    symbols = load_universe_symbols(
        tier=UniverseTier.NIFTY_50,
        asof=date(2020, 6, 15),
        max_count=3,
    )
    assert len(symbols) == 3


def test_load_universe_asof_unsupported_tier_fails_closed():
    with pytest.raises(ValueError, match="only covers NIFTY_50"):
        load_universe_symbols(
            tier=UniverseTier.NIFTY_500,
            asof=date(2020, 1, 1),
        )
    with pytest.raises(ValueError, match="only covers NIFTY_50"):
        load_universe_symbols(
            tier=UniverseTier.NIFTY_IT,
            asof=date(2020, 1, 1),
        )


def test_load_universe_no_asof_is_legacy_snapshot():
    """Backward compatibility: asof=None keeps the static universe."""
    symbols = load_universe_symbols(tier=UniverseTier.NIFTY_50, max_count=5)
    assert len(symbols) == 5


def test_load_universe_asof_accepts_datetime():
    symbols = load_universe_symbols(
        tier=UniverseTier.NIFTY_50,
        asof=datetime(2020, 6, 15, 9, 15),
        max_count=5,
    )
    assert len(symbols) == 5
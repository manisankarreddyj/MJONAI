"""Saved strategy-builder leg sets: validation + atomic local persistence.

OpenAlgo `/strategybuilder/portfolio` tool, clean-room — the store keeps the
operator's own builder inputs for replay only. Every test here is offline
(tmp_path store); nothing executes, nothing prices.
"""
import json

import pytest

from mjonai.research.data.strategy_portfolio import (
    delete_entry,
    get_entry,
    list_entries,
    save_entry,
    validate_legs,
)


def _legs():
    return [
        {"type": "CE", "side": "BUY", "strike": 23500, "premium": 120.5, "lots": 1},
        {"type": "PE", "side": "BUY", "strike": 23500, "premium": 110.0, "lots": 1},
    ]


def test_save_list_get_delete_round_trip(tmp_path):
    d = str(tmp_path / "pf")
    rec = save_entry("Nifty Weekly Strangle", "simulation", 23510.0, _legs(), portfolio_dir=d)
    assert rec["name"] == "Nifty Weekly Strangle" and rec["label"] == "simulation"
    assert len(rec["legs"]) == 2 and rec["saved_at_utc"]

    entries = list_entries(portfolio_dir=d)
    assert len(entries) == 1 and entries[0]["legs_count"] == 2

    got = get_entry("nifty-weekly-strangle", portfolio_dir=d)
    assert got is not None and got["spot"] == 23510.0

    assert delete_entry("Nifty Weekly Strangle", portfolio_dir=d) is True
    assert list_entries(portfolio_dir=d) == []
    assert delete_entry("Nifty Weekly Strangle", portfolio_dir=d) is False
    assert get_entry("nifty-weekly-strangle", portfolio_dir=d) is None


def test_save_overwrites_same_slug(tmp_path):
    d = str(tmp_path / "pf")
    save_entry("My Setup", "", 100.0, _legs(), portfolio_dir=d)
    save_entry("my setup", "", 200.0, _legs(), portfolio_dir=d)
    assert len(list_entries(portfolio_dir=d)) == 1
    assert get_entry("my setup", portfolio_dir=d)["spot"] == 200.0


def test_malformed_legs_are_refused_not_repaired(tmp_path):
    d = str(tmp_path / "pf")
    bad = [
        [],
        [{"type": "CE", "side": "BUY", "strike": 100}],  # missing keys
        [{"type": "XX", "side": "BUY", "strike": 100, "premium": 1, "lots": 1}],
        [{"type": "CE", "side": "HOLD", "strike": 100, "premium": 1, "lots": 1}],
        [{"type": "CE", "side": "BUY", "strike": -5, "premium": 1, "lots": 1}],
        [{"type": "CE", "side": "BUY", "strike": 100, "premium": -1, "lots": 1}],
        [{"type": "CE", "side": "BUY", "strike": 100, "premium": 1, "lots": 0}],
    ]
    for legs in bad:
        with pytest.raises(ValueError):
            save_entry("x", "", 100.0, legs, portfolio_dir=d)
    assert list_entries(portfolio_dir=d) == []


def test_blank_name_and_bad_spot_refused(tmp_path):
    d = str(tmp_path / "pf")
    with pytest.raises(ValueError):
        save_entry("   ", "", 100.0, _legs(), portfolio_dir=d)
    with pytest.raises(ValueError):
        save_entry("x", "", -100.0, _legs(), portfolio_dir=d)
    with pytest.raises(ValueError):
        save_entry("x", "", 100.0, _legs(), lot_size=0, portfolio_dir=d)


def test_corrupt_file_lists_as_error_not_crash(tmp_path):
    d = tmp_path / "pf"
    d.mkdir()
    (d / "broken.json").write_text("{oops", encoding="utf-8")
    entries = list_entries(portfolio_dir=str(d))
    assert len(entries) == 1 and "error" in entries[0]
    assert get_entry("broken", portfolio_dir=str(d)) is None


def test_no_partial_left_behind(tmp_path):
    d = str(tmp_path / "pf")
    save_entry("clean", "", 100.0, _legs(), portfolio_dir=d)
    assert list((tmp_path / "pf").glob("*.part")) == []

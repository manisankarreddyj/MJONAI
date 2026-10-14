"""CM delivery ingest: official-bhavcopy parsing, idempotent merge, fail-closed registry.

The delivery_tracker module was built but never fed; this suite pins the feed
contract (offline throughout — no test touches the network).
"""
from datetime import date

import pandas as pd

from mjonai.research.data import cm_delivery as cmd
from mjonai.data.market.delivery_tracker import (
    DeliveryZone,
    get_delivery_snapshot,
    register_delivery_data,
)


def _rows(day="2026-10-13"):
    return [
        {"trade_date": day, "symbol": "RELIANCE", "traded_qty": 1000000,
         "deliverable_qty": 680000, "deliv_per": 68.0},
        {"trade_date": day, "symbol": "IDEA", "traded_qty": 5000000,
         "deliverable_qty": 800000, "deliv_per": 16.0},
    ]


def test_merge_day_idempotent_keep_last(tmp_path):
    out = str(tmp_path / "cm")
    assert cmd.merge_day(_rows(), out) == 2
    assert cmd.merge_day(_rows(), out) == 2  # re-run fills holes, never duplicates
    frame = pd.read_parquet(str(tmp_path / "cm" / "2026-10.parquet"))
    assert len(frame) == 2
    assert set(frame["symbol"]) == {"RELIANCE", "IDEA"}


def test_bhavcopy_url_naming():
    assert cmd.bhavcopy_url(date(2026, 10, 13)).endswith(
        "sec_bhavdata_full_13102026.csv")


def test_refresh_feeds_registry_from_fetched_rows(tmp_path, monkeypatch):
    import mjonai.data.market.delivery_tracker as dt
    monkeypatch.setattr(dt, "_DELIVERY_CACHE", {})
    monkeypatch.setattr(cmd, "fetch_cm_day", lambda day: _rows(day.isoformat()))
    monkeypatch.setattr(cmd, "merge_day", lambda rows, out_dir: len(rows))
    out = cmd.refresh_delivery_cache(out_dir=str(tmp_path / "cm"))
    assert out["status"] == "ok" and out["symbols"] == 2
    snap = get_delivery_snapshot("RELIANCE")
    assert snap is not None
    assert snap.delivery_zone == DeliveryZone.INSTITUTIONAL_ACCUMULATION
    assert get_delivery_snapshot("IDEA").delivery_zone == DeliveryZone.SPECULATIVE_CHURN


def test_refresh_empty_window_is_honest(tmp_path, monkeypatch):
    monkeypatch.setattr(cmd, "fetch_cm_day", lambda day: None)
    out = cmd.refresh_delivery_cache(out_dir=str(tmp_path / "cm"))
    assert out["status"] == "no published bhavcopy in window"
    assert out["symbols"] == 0


def test_absent_symbol_is_none_not_baseline(tmp_path, monkeypatch):
    """The old 100k/45k 'Normal' baseline for unknown symbols is gone —
    unknown reads as unknown."""
    import mjonai.data.market.delivery_tracker as dt
    monkeypatch.setattr(dt, "_DELIVERY_CACHE", {})
    assert get_delivery_snapshot("NEVERSYMBOLXX") is None


def test_register_still_zones_correctly():
    snap = register_delivery_data("TCS", 1000000, 680000, "2026-10-13")
    assert snap.delivery_zone == DeliveryZone.INSTITUTIONAL_ACCUMULATION
    assert snap.delivery_percentage == 68.0

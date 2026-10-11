"""Market overview contract (Finviz pattern over the local equity panel).

Breadth math, SMA-position counts, 52w high/low flags and gainer ranking must be
correct on synthetic frames; a volume-less panel must report `volume_available:
False` rather than fabricating ratios; and a missing panel dir fails closed.
"""
import pandas as pd
import pytest

from mjonai.research.data import market_overview as mo


def _write_panel(tmp_path, symbol: str, closes, volumes=None, highs=None, lows=None):
    import os

    os.makedirs(tmp_path / "panel", exist_ok=True)
    dates = pd.date_range("2024-01-01", periods=len(closes), freq="B")
    frame = pd.DataFrame({"date": dates, "close": closes,
                          "volume": volumes if volumes is not None else [None] * len(closes)})
    frame.to_parquet(tmp_path / "panel" / f"{symbol}.parquet", index=False)
    return tmp_path / "panel"


def test_overview_breadth_and_tables(tmp_path, monkeypatch):
    monkeypatch.setattr(mo, "PANEL_DIR", str(_write_panel(
        tmp_path, "AAA", [100.0, 101.0, 102.0] * 20, volumes=[1_000_000] * 60)))
    out = mo.market_overview(top=3)
    assert out["available"] is True and out["universe"] == 1
    assert out["breadth"]["advancing"] == 1 and out["breadth"]["declining"] == 0
    assert out["breadth"]["above_sma50_pct"] == 100.0
    assert out["top_gainers"][0]["symbol"] == "AAA"
    assert len(out["heatmap"]) == 1
    # the synthetic panel carries volume -> ratio computable
    assert out["volume_available"] is True


def test_overview_volume_less_panel_is_disclosed(tmp_path, monkeypatch):
    monkeypatch.setattr(mo, "PANEL_DIR", str(_write_panel(
        tmp_path, "BBB", [50.0, 51.0] * 30)))          # volume all None
    out = mo.market_overview()
    assert out["volume_available"] is False and out["unusual_volume"] == []


def test_overview_missing_dir_fails_closed(monkeypatch):
    monkeypatch.setattr(mo, "PANEL_DIR", "storage/does-not-exist-panel")
    assert mo.market_overview() is None


def test_summary_skips_short_symbols(tmp_path, monkeypatch):
    panel = _write_panel(tmp_path, "SHORT", [100.0, 101.0])          # 2 bars < min_bars
    monkeypatch.setattr(mo, "PANEL_DIR", str(panel))
    df = mo.load_symbol_summaries(min_bars=60)
    assert df.empty

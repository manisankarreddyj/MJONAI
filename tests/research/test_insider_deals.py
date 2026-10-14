"""NSE bulk/block ingest: official-CSV parsing, idempotent merge, honest reads.

No test touches the network (fetch layer is stubbed or bypassed); the live
probe ran once by hand (bulk.csv served 2026-10-14 rows, block.csv valid-empty).
"""
import pandas as pd

from mjonai.research.data import insider_deals as ind


def _rows():
    return [
        {"trade_date": "2026-10-14", "symbol": "ADVANCE", "client": "QE SECURITIES LLP",
         "side": "BUY", "quantity": 460856, "price": 155.99},
        {"trade_date": "2026-10-14", "symbol": "ADVANCE", "client": "ALPHAGREP SECURITIES PRIVATE LIMITED",
         "side": "BUY", "quantity": 513238, "price": 156.10},
    ]


def test_merge_rows_idempotent_keep_last(tmp_path):
    out = str(tmp_path / "ins")
    assert ind.merge_rows(_rows(), out) == 2
    assert ind.merge_rows(_rows(), out) == 2
    frame = pd.read_parquet(str(tmp_path / "ins" / "2026-10.parquet"))
    assert len(frame) == 2


def test_describe_symbol_deals_names_top_buyer(tmp_path):
    out = str(tmp_path / "ins")
    ind.merge_rows(_rows(), out)
    note = ind.describe_symbol_deals("ADVANCE", out_dir=out)
    assert note is not None and "ALPHAGREP" in note and "513,238" in note
    assert ind.describe_symbol_deals("NEVERSYMBOLXX", out_dir=out) is None
    assert ind.describe_symbol_deals("", out_dir=out) is None


def test_get_symbol_deals_empty_dir_is_empty(tmp_path):
    assert ind.get_symbol_deals("ADVANCE", out_dir=str(tmp_path / "nope")) == []


def test_refresh_empty_files_is_honest(tmp_path, monkeypatch):
    monkeypatch.setattr(ind, "_fetch_csv", lambda url: None)
    out = ind.refresh_insider_deals(out_dir=str(tmp_path / "ins"))
    assert out == {"bulk_rows": 0, "block_rows": 0, "status": "empty (no deals published)"}


def test_refresh_never_raises(tmp_path, monkeypatch):
    def boom(url):
        raise RuntimeError("net down")
    monkeypatch.setattr(ind, "_fetch_csv", boom)
    out = ind.refresh_insider_deals(out_dir=str(tmp_path / "ins"))
    assert out["status"].startswith("error:")

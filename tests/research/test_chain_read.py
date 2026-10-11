"""Chain-reader contract (clean-room concept reader over OUR warehouse).

The ATM window must return the nearest N strikes to spot, pcr must be window
arithmetic (not a fabricated 1.0), and any empty read is fail-closed (None), never
a zero-OI payload.
"""
import pandas as pd
import pytest

from apps.research.run_chain_read import atm_window, chain_payload

CANON = [
    "trade_date", "underlying", "kind", "option_type", "strike", "expiry",
    "open", "high", "low", "close", "last", "settle", "prev_close",
    "underlying_price", "volume", "turnover", "trades", "oi", "oi_change",
    "lot_size",
]


def _month(tmp_path, strikes=(24400, 24500, 24600, 24700, 24800), ce_oi=1000, pe_oi=2000):
    day = pd.Timestamp("2024-06-14").normalize()
    expiry = pd.Timestamp("2024-06-27").normalize()
    rows = []
    for k in strikes:
        for opt, oi in (("CE", ce_oi), ("PE", pe_oi)):
            rows.append({
                "trade_date": day, "underlying": "NIFTY", "kind": "OPT", "option_type": opt,
                "strike": float(k), "expiry": expiry,
                "open": 0.0, "high": 0.0, "low": 0.0, "close": 120.0, "last": 120.0,
                "settle": 120.0, "prev_close": 0.0, "underlying_price": 24525.0,
                "volume": 0, "turnover": 0.0, "trades": 0, "oi": float(oi),
                "oi_change": 0, "lot_size": 25,
            })
    frame = pd.DataFrame(rows, columns=CANON)
    path = tmp_path / "eod" / f"{day:%Y-%m}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path, index=False)
    return str(tmp_path)


def test_atm_window_takes_nearest_strikes():
    day = pd.Timestamp("2024-06-14")
    win = atm_window(_load_stub(), n_strikes=3)
    # spot 24525 -> nearest three of {24400..24800} are 24500/24600/24400... by distance
    assert win["spot"] == 24525.0
    assert len(win["strikes"]) == 3
    assert win["strikes"] == sorted(win["strikes"])
    assert all(set(r) == {"strike", "ce_close", "ce_oi", "pe_close", "pe_oi"} for r in win["rows"])


def test_atm_window_missing_leg_is_null_not_zero():
    day = pd.Timestamp("2024-06-14")
    frame = _load_stub()
    frame = frame[frame["option_type"] != "CE"]  # a CE-less strike range
    win = atm_window(frame, n_strikes=2)
    assert win["rows"][0]["ce_close"] is None and win["rows"][0]["ce_oi"] is None


def test_chain_payload_pcr_is_window_arithmetic(tmp_path):
    payload = chain_payload("NIFTY", "2024-06-14", n_strikes=2, warehouse=_month(tmp_path))
    assert payload is not None
    assert payload["spot"] == 24525.0
    # window OI: each strike contributes ce=1000/pe=2000 -> pcr 2.0 exactly
    assert payload["window_ce_oi"] == 2000.0 and payload["window_pe_oi"] == 4000.0
    assert payload["window_pcr"] == 2.0
    assert payload["expiries"] == ["2024-06-27"]
    assert len(payload["rows"]) == 2


def test_chain_payload_missing_warehouse_is_none(tmp_path):
    assert chain_payload("NIFTY", "2024-06-14", 5, warehouse=str(tmp_path)) is None
    assert chain_payload("BANKNIFTY", "2024-06-14", 5, warehouse=_month(tmp_path)) is None
    assert chain_payload("NIFTY", "2024-06-15", 5, warehouse=_month(tmp_path)) is None  # non-trading day


def test_main_records_evidence(monkeypatch, capsys):
    """The read must feed the canonical evidence store, not just stdout."""
    import apps.research.run_chain_read as cli

    payload = {"underlying": "NIFTY", "as_of": "2024-06-14", "spot": 24525.0,
               "window_ce_oi": 2000.0, "window_pe_oi": 4000.0, "window_pcr": 2.0,
               "expiries": ["2024-06-27"], "strikes_window": 2,
               "rows": [{"strike": 24500.0, "ce_close": 100.0, "ce_oi": 1000.0,
                         "pe_close": 90.0, "pe_oi": 2000.0}]}
    monkeypatch.setattr(cli, "chain_payload", lambda *a, **k: payload)
    recorded = {}
    monkeypatch.setattr("mjonai.research.evidence.record_evidence",
                        lambda kind, payload: recorded.update(kind=kind, payload=payload))
    monkeypatch.setattr("sys.argv", ["x", "--date", "2024-06-14", "--json"])
    cli.main()
    assert recorded["kind"] == "chain_read" and recorded["payload"]["window_pcr"] == 2.0


def test_main_fail_closed_exit(monkeypatch, capsys):
    import apps.research.run_chain_read as cli

    monkeypatch.setattr(cli, "chain_payload", lambda *a, **k: None)
    monkeypatch.setattr("sys.argv", ["x", "--date", "2024-06-14"])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 2
    assert "fail-closed" in capsys.readouterr().err


def _load_stub() -> pd.DataFrame:
    """The loader output shape without touching disk (mirrors CANON rows)."""
    rows = []
    for k in (24400, 24500, 24600, 24700, 24800):
        for opt, oi in (("CE", 1000), ("PE", 2000)):
            rows.append({
                "option_type": opt, "strike": float(k), "close": 120.0,
                "underlying_price": 24525.0, "oi": float(oi), "expiry": pd.Timestamp("2024-06-27"),
            })
    return pd.DataFrame(rows)

"""Discovery sweep: --family filter + evidence persistence contract."""
import pandas as pd

import apps.research.run_discovery_sweep as sw


def test_family_filter_runs_only_requested_and_records_evidence(monkeypatch):
    df = pd.DataFrame(
        {"Open": 1.0, "High": 2.0, "Low": 0.5, "Close": 1.5, "Volume": 10.0},
        index=pd.date_range("2024-01-01", periods=60, freq="D"),
    )
    monkeypatch.setattr(sw.H, "load_spot", lambda u, s, e: df)
    monkeypatch.setattr(sw.H, "bench_buy_hold", lambda d, **k: d)
    monkeypatch.setattr(sw.H, "metrics", lambda b: {"CAGR": 1.0, "Sharpe": 0.1, "MaxDD": 1.0, "Total": 1.0})
    monkeypatch.setattr(sw.H, "walk_forward", lambda *a, **k: [])   # no outcomes -> no rows to print

    recorded: dict = {}
    monkeypatch.setattr(
        "mjonai.research.evidence.record_evidence",
        lambda kind, payload: recorded.update({"kind": kind, "payload": payload}),
    )

    rows = sw.run("NIFTY", families={"A8_smc_structure"})
    assert rows == []
    assert recorded["kind"] == "discovery_sweep"
    assert recorded["payload"]["families_run"] == ["A8_smc_structure"]
    assert recorded["payload"]["underlying"] == "NIFTY"
    assert "benchmark_bh_net" in recorded["payload"]


def test_unknown_family_exits(monkeypatch):
    with pytest_raises(SystemExit):
        sw.run("NIFTY", families={"NOPE"})


def pytest_raises(exc):
    import pytest

    class _Ctx:
        def __enter__(self):
            return self

        def __exit__(self, et, ev, tb):
            assert et is exc, f"expected {exc}, got {et}"
            return True

    return _Ctx()

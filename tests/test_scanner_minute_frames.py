"""Minute pipeline Phase 2: scanner on native minutes (scanner seam tests).

Pins that intraday-design strategies (attr timeframe == "INTRADAY": S08/S09/
S13/S17/S18) are evaluated on REAL archived 1m|15m frames instead of the daily
`get_stock_data` frame, and are SKIPPED fail-closed when the archive has no
history — retiring the historical "15m over 1d" fiction. Swing/positional
strategies keep the daily path untouched. All OFFLINE — synthetic frames and
patched archive only."""

from types import SimpleNamespace

import pandas as pd
import pytest

import mjonai.strategy.signal_scanner as ss


def make_strategy(name="S13_GammaFlip", timeframe="INTRADAY", active=True, min_candles=30, cadences=None):
    return SimpleNamespace(
        name=name,
        timeframe=timeframe,
        is_active=active,
        min_candles_required=min_candles,
        scan_cadences=cadences,
        execute_safe=lambda **_kw: None,
    )


def daily_frame(bars=80):
    return pd.DataFrame(
        {
            "Open": [1000.0 + i for i in range(bars)],
            "High": [1001.0 + i for i in range(bars)],
            "Low": [999.0 + i for i in range(bars)],
            "Close": [1000.5 + i for i in range(bars)],
            "Volume": [100.0] * bars,
        }
    )


def minute_frame(bars=34, tf="15min"):
    idx = pd.date_range("2026-09-21 09:15", periods=bars, freq=tf)
    return pd.DataFrame(
        {
            "Open": [1000.0 + i for i in range(bars)],
            "High": [1001.0 + i for i in range(bars)],
            "Low": [999.0 + i for i in range(bars)],
            "Close": [1000.5 + i for i in range(bars)],
            "Volume": [100.0] * bars,
        },
        index=idx,
    )


def test_is_intraday_strategy_classifies_horizon():
    assert ss._is_intraday_strategy(make_strategy("S13_GammaFlip", "INTRADAY")) is True
    assert ss._is_intraday_strategy(make_strategy("S03_TurtleBreakout", "POSITIONAL")) is False
    assert ss._is_intraday_strategy(make_strategy("S01_MomentumRSI", "SWING")) is False
    # Missing attr degrades to SWING (never treated intraday by accident)
    assert ss._is_intraday_strategy(SimpleNamespace(name="X")) is False


def test_load_intraday_frame_serves_native_minutes_when_present(monkeypatch):
    fake_archive = SimpleNamespace(load_cadence=lambda symbol, **k: minute_frame())
    monkeypatch.setattr(ss, "_MINUTE_ARCHIVE", fake_archive)

    strat = make_strategy("S13_GammaFlip", "INTRADAY", min_candles=30)
    frame = ss._load_intraday_frame(strat, "NIFTY", "15m")
    assert frame is not None
    assert list(frame.columns) == ["Open", "High", "Low", "Close", "Volume"]


def test_load_intraday_frame_none_for_daily_strategies(monkeypatch):
    called = {"load_cadence": False}

    def _load(*a, **k):
        called["load_cadence"] = True
        return minute_frame()

    monkeypatch.setattr(ss, "_MINUTE_ARCHIVE", SimpleNamespace(load_cadence=_load))

    # SWING strategy must never touch the minute archive.
    frame = ss._load_intraday_frame(make_strategy("S01_MomentumRSI", "SWING"), "RELIANCE", "15m")
    assert frame is None
    assert called["load_cadence"] is False


def test_load_intraday_frame_none_when_archive_empty(monkeypatch):
    monkeypatch.setattr(ss, "_MINUTE_ARCHIVE", SimpleNamespace(load_cadence=lambda symbol, **k: None))
    frame = ss._load_intraday_frame(make_strategy("S18_GapFillFVG", "INTRADAY", min_candles=20), "TCS", "15m")
    assert frame is None


def test_load_intraday_frame_exception_fails_closed(monkeypatch):
    def _boom(*a, **k):
        raise RuntimeError("corrupt archive")

    monkeypatch.setattr(ss, "_MINUTE_ARCHIVE", SimpleNamespace(load_cadence=_boom))
    frame = ss._load_intraday_frame(make_strategy("S18_GapFillFVG", "INTRADAY"), "TCS", "15m")
    assert frame is None


def test_scanner_skips_intraday_strategy_when_archive_empty(monkeypatch):
    executed = []

    def _fake_execute(**kw):
        executed.append(kw.get("df"))
        return {"strategy_id": "S18_GapFillFVG"}

    strat = SimpleNamespace(
        name="S18_GapFillFVG",
        timeframe="INTRADAY",
        is_active=True,
        min_candles_required=20,
        asset_class="EQUITY",
        execute_safe=_fake_execute,
    )
    monkeypatch.setattr(ss, "_ACTIVE_STRATEGIES", [strat])
    monkeypatch.setattr(ss, "get_stock_data", lambda symbol: daily_frame())
    monkeypatch.setattr(ss, "_MINUTE_ARCHIVE", SimpleNamespace(load_cadence=lambda symbol, **k: None))

    setups = ss._scan_single_symbol(
        symbol="TCS", market_state="BULL", mqi_level="HIGH",
        vix=14.0, sys_mode="RESEARCH", timeframe="15m", open_strategy_symbols=set(),
    )
    assert setups == []
    assert executed == []  # fail-closed: never evaluated on a daily frame


def test_scanner_feeds_intraday_strategy_native_minute_frame(monkeypatch):
    executed = []

    def _fake_execute(**kw):
        executed.append(kw.get("df"))
        return {"strategy_id": "S13_GammaFlip"}

    strat = SimpleNamespace(
        name="S13_GammaFlip",
        timeframe="INTRADAY",
        is_active=True,
        min_candles_required=30,
        asset_class="EQUITY",
        execute_safe=_fake_execute,
    )
    monkeypatch.setattr(ss, "_ACTIVE_STRATEGIES", [strat])
    monkeypatch.setattr(ss, "get_stock_data", lambda symbol: daily_frame())
    monkeypatch.setattr(ss, "_MINUTE_ARCHIVE", SimpleNamespace(load_cadence=lambda symbol, **k: minute_frame()))

    setups = ss._scan_single_symbol(
        symbol="TCS", market_state="BULL", mqi_level="HIGH",
        vix=14.0, sys_mode="RESEARCH", timeframe="15m", open_strategy_symbols=set(),
    )
    assert len(setups) == 1
    assert len(executed) == 1
    pd.testing.assert_frame_equal(executed[0], minute_frame())

    # The candidate tuple carries the native minute frame, never the daily one.
    _strat, result, cand_df = setups[0]
    assert len(cand_df) == 34
    assert cand_df.index.freq is not None


def test_scanner_intraday_strategy_uses_regular_daily_path(monkeypatch):
    """Swing/positional strategies keep the daily get_stock_data frame."""
    executed = []

    def _fake_execute(**kw):
        executed.append(kw.get("df"))
        return {"strategy_id": "S03_TurtleBreakout"}

    strat = SimpleNamespace(
        name="S03_TurtleBreakout",
        timeframe="POSITIONAL",
        is_active=True,
        min_candles_required=50,
        asset_class="EQUITY",
        execute_safe=_fake_execute,
    )
    monkeypatch.setattr(ss, "_ACTIVE_STRATEGIES", [strat])
    daily = daily_frame()
    monkeypatch.setattr(ss, "get_stock_data", lambda symbol: daily)
    # Even if the minute archive were populated, a swing strategy must not consume it.
    monkeypatch.setattr(ss, "_MINUTE_ARCHIVE", SimpleNamespace(load_cadence=lambda **k: minute_frame()))

    setups = ss._scan_single_symbol(
        symbol="RELIANCE", market_state="BULL", mqi_level="HIGH",
        vix=14.0, sys_mode="RESEARCH", timeframe="15m", open_strategy_symbols=set(),
    )
    assert len(setups) == 1
    assert len(executed) == 1
    assert executed[0] is daily


def test_s08_cadence_gate_excludes_15m_even_with_archive(monkeypatch):
    """S08 (scan_cadences=("5m",)) must NEVER be evaluated at 15m.

    Phase 2b: the S4 '8-bar box read as 2 hours' defect returns if S08 is fed
    a 15m resample. The scanner gate must skip the strategy even when the
    archive HAS enough bars for a 15m frame."""
    executed = []

    def _fake_execute(**kw):
        executed.append(kw.get("df"))
        return {"strategy_id": "S08_IntradayAllDay"}

    strat = make_strategy("S08_IntradayAllDay", "INTRADAY", active=True, min_candles=15, cadences=("5m",))
    strat.asset_class = "EQUITY"
    strat.execute_safe = _fake_execute
    monkeypatch.setattr(ss, "_ACTIVE_STRATEGIES", [strat])
    monkeypatch.setattr(ss, "get_stock_data", lambda symbol: daily_frame())
    # Archive is full of minute bars — a 15m resample would be available.
    monkeypatch.setattr(ss, "_MINUTE_ARCHIVE", SimpleNamespace(load_cadence=lambda symbol, **k: minute_frame()))

    setups = ss._scan_single_symbol(
        symbol="TCS", market_state="BULL", mqi_level="HIGH",
        vix=14.0, sys_mode="RESEARCH", timeframe="15m", open_strategy_symbols=set(),
    )
    assert setups == []          # cadence gate: 15m ∉ ("5m",)
    assert executed == []        # S08's signal math never ran


def test_s08_cadence_gate_runs_on_5m(monkeypatch):
    """S08 runs on the 5m slot with a real archive-derived 5m frame."""
    executed = []

    def _fake_execute(**kw):
        executed.append(kw.get("df"))
        return {"strategy_id": "S08_IntradayAllDay"}

    strat = make_strategy("S08_IntradayAllDay", "INTRADAY", active=True, min_candles=15, cadences=("5m",))
    strat.asset_class = "EQUITY"
    strat.execute_safe = _fake_execute
    monkeypatch.setattr(ss, "_ACTIVE_STRATEGIES", [strat])
    monkeypatch.setattr(ss, "get_stock_data", lambda symbol: daily_frame())
    frame = minute_frame(bars=40, tf="5min")
    monkeypatch.setattr(ss, "_MINUTE_ARCHIVE", SimpleNamespace(load_cadence=lambda symbol, **k: frame))

    setups = ss._scan_single_symbol(
        symbol="TCS", market_state="BULL", mqi_level="HIGH",
        vix=14.0, sys_mode="RESEARCH", timeframe="5m", open_strategy_symbols=set(),
    )
    assert len(setups) == 1
    assert len(executed) == 1
    pd.testing.assert_frame_equal(executed[0], frame)


def test_sibling_intraday_cadence_kept_on_15m(monkeypatch):
    """S13/S17/S18 (scan_cadences=("15m",)) are not pulled onto the 5m slot."""
    executed = []

    def _fake_execute(**kw):
        executed.append(kw.get("df"))
        return {"strategy_id": "S17_OrderFlowMicroPrice"}

    strat = make_strategy("S17_OrderFlowMicroPrice", "INTRADAY", active=True, min_candles=15, cadences=("15m",))
    strat.asset_class = "EQUITY"
    strat.execute_safe = _fake_execute
    monkeypatch.setattr(ss, "_ACTIVE_STRATEGIES", [strat])
    monkeypatch.setattr(ss, "get_stock_data", lambda symbol: daily_frame())
    monkeypatch.setattr(ss, "_MINUTE_ARCHIVE", SimpleNamespace(load_cadence=lambda symbol, **k: minute_frame()))

    setups = ss._scan_single_symbol(
        symbol="TCS", market_state="BULL", mqi_level="HIGH",
        vix=14.0, sys_mode="RESEARCH", timeframe="5m", open_strategy_symbols=set(),
    )
    assert setups == []
    assert executed == []
"""Deterministic macro-context builder tests (P1: wire intelligence factors into Gate 6).

Honesty contract under test:
  - build_macro_context never raises and never fabricates factors.
  - Absent sources â†’ factor keys simply not present (or agent-NEUTRAL), never
    confident values invented from zero/missing data.
  - Every factor that IS present carries a provenance entry.
  - The pipeline-schema calendar events normalize into macro_calendar types.
"""

from unittest.mock import patch

import pytest

from mjonai.intelligence import build_macro_context


class _FakeBreadthSnap:
    def __init__(self, *, total, pct=0.5, advancing=0, declining=0, top=None, lag=None, top_chg=None):
        self.total_sectors = total
        self.breadth_pct = pct
        self.advancing_count = advancing
        self.declining_count = declining
        self.top_sector = top
        self.lag_sector = lag
        self.top_change_pct = top_chg
        self.provenance_reason = "unit-fake"
        self.is_strong_bull = pct >= 0.6
        self.is_strong_bear = pct <= 0.4


class _FakeFlow:
    def __init__(self, fii, dii):
        self.fii_net_crores = fii
        self.dii_net_crores = dii


# â”€â”€ honesty: absent sources are excluded â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def test_no_sources_no_fabricated_factors():
    c = build_macro_context()
    # vix/market_state not provided â†’ absent; no FII/DII, no breadth, no rotation
    assert "vix" not in c
    assert "fii_regime" not in c
    assert "market_breadth" not in c
    assert "sector_rrg_quadrant" not in c
    assert c["_provenance"] == []


def test_caller_scalars_pass_through():
    c = build_macro_context(vix=18.5, market_state="BEAR")
    assert c["vix"] == 18.5
    assert c["market_state"] == "BEAR"
    assert "vix:caller" in c["_provenance"]
    assert "market_state:caller" in c["_provenance"]


# â”€â”€ FII/DII factor â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def test_fiidii_zero_fallback_is_honestly_absent():
    # fetch_fii_dii_cash_flow fabricates 0.0/0.0 when no feed exists; that fake
    # "neutral zero" must NOT surface as fii_net_cr=0 / fii_regime=NEUTRAL.
    with patch("mjonai.data.macro.fetch_fii_dii_cash_flow", return_value=_FakeFlow(0.0, 0.0)):
        c = build_macro_context()
    assert "fii_net_cr" not in c
    assert "fii_regime" not in c


def test_fiidii_real_flow_surfaces():
    with patch("mjonai.data.macro.fetch_fii_dii_cash_flow", return_value=_FakeFlow(-2450.0, 3000.0)) as m:
        c = build_macro_context()
    m.assert_called_once()
    # -2450 + 3000 = +550 net. Flow regime derived by analyze_fii_dii_flow.
    assert c["fii_net_cr"] == pytest.approx(550.0)
    assert isinstance(c["fii_regime"], str)
    assert any("fii_dii:macro_fiidii" == p for p in c["_provenance"])


def test_fiidii_exception_is_swallowed():
    def _boom():
        raise RuntimeError("feed down")
    with patch("mjonai.data.macro.fetch_fii_dii_cash_flow", side_effect=_boom):
        c = build_macro_context()  # must not raise
    assert "fii_regime" not in c


# â”€â”€ breadth factor â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@pytest.mark.parametrize("pct,expected", [(0.70, "STRONG_BULLISH"), (0.30, "STRONG_BEARISH"), (0.50, "BALANCED")])
def test_breadth_label_mapping(pct, expected):
    with patch("mjonai.data.market.calculate_sector_breadth", return_value=_FakeBreadthSnap(total=12, pct=pct, advancing=8, declining=4, top="IT", lag="BANK")):
        c = build_macro_context()
    assert c["market_breadth"] == expected
    assert "breadth:sector_breadth" in c["_provenance"]


def test_breadth_zero_sample_is_absent():
    with patch("mjonai.data.market.calculate_sector_breadth", return_value=_FakeBreadthSnap(total=0)):
        c = build_macro_context()
    assert "market_breadth" not in c


def test_breadth_exception_is_swallowed():
    with patch("mjonai.data.market.calculate_sector_breadth", side_effect=RuntimeError("no ticks")):
        c = build_macro_context()  # must not raise
    assert "market_breadth" not in c


# â”€â”€ rotation factor â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def test_rotation_label_from_breadth():
    snap = _FakeBreadthSnap(total=12, pct=0.75, top="REALTY", top_chg=2.0, advancing=9, declining=3)
    with patch("mjonai.data.market.calculate_sector_breadth", return_value=snap):
        c = build_macro_context()
    # top_change_pct=2.0 â†’ rs_ratio=110, momentum=120 â†’ LEADING
    assert c["sector_rrg_quadrant"] == "LEADING"
    assert c["sector_rrg"] == "LEADING"


def test_rotation_no_sample_is_absent():
    with patch("mjonai.data.market.calculate_sector_breadth", return_value=_FakeBreadthSnap(total=1)):
        c = build_macro_context()
    assert "sector_rrg_quadrant" not in c


# â”€â”€ macro calendar factor â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def test_event_factor_absent_without_calendar():
    c = build_macro_context()
    assert "macro_event_risk" not in c


def test_event_factor_normalizes_pipeline_schema():
    import datetime
    from mjonai.core.time_utils import today_ist
    today = today_ist().strftime("%Y-%m-%d")
    c = build_macro_context(calendar_events=[
        {"name": "RBI MPC Monetary Policy Decision", "impact": "HIGH", "hours_away": 2.0, "date": today},
    ])
    assert c["macro_event_risk"] == "EVENT_TODAY"
    assert c["macro_event_impact"] == "CRITICAL"
    assert c["macro_event_name"] == "RBI_MPC_RATE_DECISION"


def test_event_factor_non_matching_date_is_none():
    c = build_macro_context(calendar_events=[{"name": "Union Budget Presentation", "date": "2099-01-01"}])
    assert c["macro_event_risk"] == "NONE"


# â”€â”€ sentiment factor (injected only, never fetched) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def test_sentiment_from_injected_snapshot():
    c = build_macro_context(macro_snapshot={"overall": "RISK_OFF", "data_quality": "CONFIDENT", "flags": ["oil-spike"]})
    assert c["global_macro_sentiment"] == "RISK_OFF"
    assert c["global_macro_quality"] == "CONFIDENT"
    assert c["global_macro_flags"] == ["oil-spike"]
    assert "sentiment:macro_sentiment" in c["_provenance"]


def test_sentiment_absent_without_snapshot():
    c = build_macro_context()
    assert "global_macro_sentiment" not in c


# â”€â”€ provenance integrity â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def test_provenance_covers_every_present_factor():
    with patch("mjonai.data.macro.fetch_fii_dii_cash_flow", return_value=_FakeFlow(-2450.0, 3000.0)), \
         patch("mjonai.data.market.calculate_sector_breadth", return_value=_FakeBreadthSnap(total=12, pct=0.70, top="IT", top_chg=1.5, advancing=8, declining=4)):
        c = build_macro_context(vix=16.0, market_state="BULL")
    assert "vix:caller" in c["_provenance"]
    assert "market_state:caller" in c["_provenance"]
    assert any("fii_dii:" in p for p in c["_provenance"])
    assert any("breadth:" in p for p in c["_provenance"])
    assert any("rotation:" in p for p in c["_provenance"])


def test_build_is_pure_and_idempotent():
    # Two consecutive builds with identical inputs must be identical â€” no
    # hidden state or network effects leach into the result.
    with patch("mjonai.data.market.calculate_sector_breadth", return_value=_FakeBreadthSnap(total=10, pct=0.45, top="AUTO", top_chg=-0.5, advancing=4, declining=6)):
        a = build_macro_context(vix=14.0)
        b = build_macro_context(vix=14.0)
    assert a == b

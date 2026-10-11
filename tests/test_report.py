"""One-page self-contained HTML report contract (TradingAgents pattern).

The report must be offline-complete (no script/CDN references), must render the mode
label so a paper report can't be mistaken for live, must never fabricate figures, and
must surface the risk locks when they are active.
"""
from unittest.mock import patch

from apps.web.report import render_eod_report


def _status(mode="PAPER", dd=None):
    return {"system_mode": mode, "drawdown_pct": dd, "kill_line_breached": False}


def test_report_is_self_contained_and_labelled():
    with patch("apps.web.data_views.build_system_status", return_value=_status("PAPER")), \
         patch("apps.web.data_views.build_equity_series", return_value=[]), \
         patch("apps.web.data_views.build_recent_trades", return_value=[]), \
         patch("apps.web.data_views.build_signal_track_record", return_value={"overall": {}, "strategies": []}), \
         patch("apps.web.data_views.build_ai_debates", return_value=[]), \
         patch("apps.web.data_views.build_market_cockpit", return_value={"risk_guards": {"trading_allowed": True}}):
        html = render_eod_report()

    assert "<!DOCTYPE html>" in html and "</html>" in html
    assert "<script" not in html                            # offline-complete: no scripts at all
    for host in ("unpkg", "jsdelivr", "googleapis", "http://", "https://"):
        assert host not in html, f"external reference leaked: {host}"
    assert 'class="mode PAPER"' in html                    # the mode is always visible
    assert "no closed trades today" in html                 # absent data renders honestly
    assert "—" in html


def test_report_surfaces_risk_locks():
    guards = {"trading_allowed": False, "kill_line_active": True, "risk_stop_active": True,
              "behavioral_cooldown_active": True, "consecutive_losses": 3, "active_reasons": ["KILL_LINE"]}
    with patch("apps.web.data_views.build_system_status", return_value=_status("LIVE", dd=16.5)), \
         patch("apps.web.data_views.build_equity_series", return_value=[]), \
         patch("apps.web.data_views.build_recent_trades", return_value=[]), \
         patch("apps.web.data_views.build_signal_track_record", return_value={"overall": {}, "strategies": []}), \
         patch("apps.web.data_views.build_ai_debates", return_value=[]), \
         patch("apps.web.data_views.build_market_cockpit", return_value={"risk_guards": guards}):
        html = render_eod_report()
    assert "KILL LINE ACTIVE" in html and "Behavioral cooldown" in html and "Trading not allowed" in html
    assert 'class="mode LIVE"' in html and "16.5%" in html


def test_report_renders_real_rows_when_present():
    trades = [{"closed_at": "2026-10-11T15:35:00", "symbol": "INFY", "side": "BUY",
               "strategy_id": "S03_TurtleBreakout", "net_pnl": 1250.0, "exit_reason": "T1"}]
    track = {"overall": {"n": 5, "hit_rate_1d": 0.6, "mean_fwd_1d": 0.004},
             "strategies": [{"strategy_id": "S03_TurtleBreakout", "n": 5, "hit_rate_1d": 0.6,
                             "mean_fwd_1d": 0.004, "hit_rate_5d": 0.8}]}
    debates = [{"time": "2026-10-11T10:00:00", "symbol": "INFY", "signal_direction": "LONG",
                "final_confidence": 71.0, "bull_agent": {"verdict": "BUY"},
                "supervisor_cio": {"reason": "clean gates"}}]
    with patch("apps.web.data_views.build_system_status", return_value=_status("PAPER")), \
         patch("apps.web.data_views.build_equity_series", return_value=[{"date": "2026-10-11", "equity": 101250.0, "drawdown_pct": 0.0}]), \
         patch("apps.web.data_views.build_recent_trades", return_value=trades), \
         patch("apps.web.data_views.build_signal_track_record", return_value=track), \
         patch("apps.web.data_views.build_ai_debates", return_value=debates), \
         patch("apps.web.data_views.build_market_cockpit", return_value={"risk_guards": {"trading_allowed": True}}):
        html = render_eod_report()
    assert "INFY" in html and "60.0%" in html and "+0.40%" in html and "clean gates" in html
    assert "+₹1,250" in html

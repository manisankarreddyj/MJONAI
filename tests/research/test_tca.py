"""Transaction cost analysis math tests (research/analytics/tca.py).

CONCEPT-SOURCE (clean-room Bloomberg-TCA analog): realized cost/slippage analytics
from MJONAI's own ledger. The honesty contract under test: an unmeasured trade
(slippage/costs absent) is never counted as a free trade (never coerced to 0.0).
"""

import sys
from pathlib import Path

_root_dir = Path(__file__).resolve().parents[2]  # repo root (ADR-0008)
if str(_root_dir) not in sys.path:
    sys.path.insert(0, str(_root_dir))

from mjonai.research.analytics.tca import build_tca


def test_empty_ledger_is_fail_closed():
    out = build_tca([])
    assert out["available"] is False
    assert "no closed trades" in out["reason"]


def test_aggregates_realized_cost_drag():
    trades = [
        {"symbol": "RELIANCE", "gross_pnl": 1000.0, "net_pnl": 900.0, "slippage_bps": 2.5,
         "side": "LONG", "exit_reason": "TARGET"},
        {"symbol": "TCS", "gross_pnl": -500.0, "net_pnl": -560.0, "slippage_bps": 3.5,
         "side": "LONG", "exit_reason": "STOP"},
    ]
    out = build_tca(trades)
    assert out["available"] is True
    assert out["trades_total"] == 2
    assert out["trades_with_costs"] == 2
    assert out["gross_pnl"] == 500.0
    assert out["net_pnl"] == 340.0
    assert out["total_cost_drag"] == 160.0
    assert out["cost_drag_pct_of_gross"] == 32.0
    assert out["mean_slippage_bps"] == 3.0
    assert out["hit_rate_net"] == 0.5  # 1 net winner / 2
    rows = out["rows"]
    assert rows[0]["cost_drag"] == 100.0
    assert rows[1]["cost_drag"] == 60.0


def test_unmeasured_costs_stay_none_never_zero():
    # A trade with no recorded slippage/costs must NOT enter the cost means as 0.0.
    trades = [
        {"symbol": "INFY", "gross_pnl": 300.0, "net_pnl": 300.0, "slippage_bps": None},
        {"symbol": "HDFCBANK", "gross_pnl": 200.0, "net_pnl": 180.0, "slippage_bps": 1.5},
    ]
    out = build_tca(trades)
    assert out["trades_total"] == 2
    assert out["trades_with_costs"] == 2  # gross-net pair exists for both
    assert out["slippage_trades"] == 1  # but only ONE slippage reading
    assert out["mean_slippage_bps"] == 1.5  # not 0.75 (0.0 would contaminate)
    assert out["rows"][0]["slippage_bps"] is None  # stays honest null


def test_no_gross_net_pair_reports_pct_as_none():
    out = build_tca([{"symbol": "SBIN", "slippage_bps": 4.0}])
    assert out["available"] is True
    assert out["trades_with_costs"] == 0
    assert out["gross_pnl"] == 0.0
    assert out["cost_drag_pct_of_gross"] is None  # division guard: never fake 0%
    assert out["hit_rate_net"] is None

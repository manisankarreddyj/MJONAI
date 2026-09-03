"""
Unit tests for communication/eod_report.py (Automated EOD Digest & Telegram Formatter).
Verifies P&L aggregation, strategy attribution, win rate math, and HTML card generation.
"""

import pytest
from communication.eod_report import (
    generate_eod_digest,
    EODDigestResult,
)


def test_generate_eod_digest_positive_day():
    trades = [
        {"strategy_id": "S01_MOMENTUM", "status": "CLOSED", "pnl": 4500.0},
        {"strategy_id": "S05_PRICE_ACTION", "status": "CLOSED", "pnl": 2800.0},
        {"strategy_id": "S02_MEAN_REVERSION", "status": "CLOSED", "pnl": -1200.0},
        {"strategy_id": "S09_THETA_DECAY", "status": "OPEN", "unrealized_pnl": 1500.0},
    ]

    res = generate_eod_digest(
        trades=trades,
        fii_net_cr=1250.0,
        dii_net_cr=450.0,
        market_state="STRONG_BULL",
        broker_name="FINVASIA_SHOONYA",
        date_str="2026-09-01",
    )

    assert res.total_pnl == 7600.0
    assert res.realized_pnl == 6100.0
    assert res.unrealized_pnl == 1500.0
    assert res.winning_trades == 2
    assert res.losing_trades == 1
    assert res.win_rate_pct == 66.7
    assert "S01_MOMENTUM" in res.strategy_attribution
    assert "<b>Net PnL:</b> 🟢 +₹7,600.00" in res.html_card
    assert "FINVASIA_SHOONYA" in res.html_card


def test_generate_eod_digest_empty_trades():
    res = generate_eod_digest(trades=[])
    assert res.total_pnl == 0.0
    assert res.win_rate_pct == 0.0
    assert res.total_trades == 0

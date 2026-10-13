"""
Unit tests for the price-alert checker (communication/telegram.py::check_stock_alerts).

Covers the OpenStock checkStockAlerts clean-room reimplementation: market-hours
gating via the canonical session resolver, empty-table early exit, ABOVE/BELOW
triggering with soft-delete, per-alert failure isolation, and DB-outage
fail-closed. All broker/DB/time boundaries are mocked — no network, no clock.
"""

import pandas as pd
import pytest
from unittest.mock import patch, MagicMock

from mjonai.communication.telegram import check_stock_alerts


def _candles(last_close):
    return pd.DataFrame({
        "Open": [last_close], "High": [last_close],
        "Low": [last_close], "Close": [last_close], "Volume": [100],
    })


def test_checker_skips_outside_market_hours_without_touching_db():
    """Closed market -> immediate skip; the alert table is never even read."""
    with patch("mjonai.core.time_utils.is_market_open", return_value=False), \
         patch("mjonai.db.repository.get_active_price_alerts") as mock_get:
        out = check_stock_alerts()
    assert out == {"processed": 0, "triggered": 0, "skipped": "outside market hours"}
    mock_get.assert_not_called()


def test_checker_early_exit_on_empty_table():
    """No alerts -> one cheap read, no price fetches, no notifications."""
    with patch("mjonai.core.time_utils.is_market_open", return_value=True), \
         patch("mjonai.db.repository.get_active_price_alerts", return_value=[]), \
         patch("mjonai.data.angelone.historical.fetch_historical_candles") as mock_px, \
         patch("mjonai.communication.telegram.send_message") as mock_send:
        out = check_stock_alerts()
    assert out["processed"] == 0 and out["triggered"] == 0
    mock_px.assert_not_called()
    mock_send.assert_not_called()


def test_checker_triggers_above_and_marks_triggered():
    """Price >= target on ABOVE -> notify + soft-delete; BELOW stays quiet."""
    alerts = [
        {"id": "a1", "symbol": "INFY", "condition": "ABOVE", "target_price": 2000.0},
        {"id": "b2", "symbol": "TCS", "condition": "BELOW", "target_price": 100.0},
    ]
    with patch("mjonai.core.time_utils.is_market_open", return_value=True), \
         patch("mjonai.db.repository.get_active_price_alerts", return_value=alerts), \
         patch("mjonai.data.angelone.historical.fetch_historical_candles",
               side_effect=[_candles(2050.0), _candles(3000.0)]), \
         patch("mjonai.db.repository.mark_alert_triggered",
               return_value=True) as mock_mark, \
         patch("mjonai.communication.telegram.send_message") as mock_send:
        out = check_stock_alerts()
    assert out == {"processed": 2, "triggered": 1}
    mock_mark.assert_called_once_with("a1")
    assert mock_send.call_count == 1
    assert "INFY" in mock_send.call_args.args[0]


def test_checker_isolates_per_alert_failures():
    """A corrupt row (bad price) or missing candles must not kill the sweep."""
    alerts = [
        {"id": "bad", "symbol": "XXX", "condition": "ABOVE", "target_price": "nonsense"},
        {"id": "nocandles", "symbol": "YYY", "condition": "ABOVE", "target_price": 10.0},
        {"id": "good", "symbol": "INFY", "condition": "BELOW", "target_price": 99999.0},
    ]
    with patch("mjonai.core.time_utils.is_market_open", return_value=True), \
         patch("mjonai.db.repository.get_active_price_alerts", return_value=alerts), \
         patch("mjonai.data.angelone.historical.fetch_historical_candles",
               side_effect=[None, _candles(1500.0)]), \
         patch("mjonai.db.repository.mark_alert_triggered",
               return_value=True) as mock_mark, \
         patch("mjonai.communication.telegram.send_message") as mock_send:
        out = check_stock_alerts()
    # bad row: float() raises -> caught; nocandles: None frame -> skipped;
    # good row: 1500 < 99999 BELOW -> triggers.
    assert out == {"processed": 3, "triggered": 1}
    mock_mark.assert_called_once_with("good")
    assert mock_send.call_count == 1


def test_checker_db_outage_fails_closed():
    """Unreadable alert table -> error dict, no notifications, no crash."""
    with patch("mjonai.core.time_utils.is_market_open", return_value=True), \
         patch("mjonai.db.repository.get_active_price_alerts",
               side_effect=RuntimeError("DB down")), \
         patch("mjonai.communication.telegram.send_message") as mock_send:
        out = check_stock_alerts()
    assert out["processed"] == 0 and out["triggered"] == 0
    assert "error" in out
    mock_send.assert_not_called()

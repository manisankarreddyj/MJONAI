"""
Unit tests for execution/brokers/openalgo.py (OpenAlgoBrokerClient).
Verifies standardized multi-broker order payload formatting, placement, cancellation,
position book retrieval, and unconfigured fail-closed safety.
"""

from unittest.mock import MagicMock, patch
import pytest

from execution.brokers.openalgo import OpenAlgoBrokerClient, OpenAlgoOrderResult


def test_openalgo_order_result_dataclass():
    res = OpenAlgoOrderResult(
        success=True,
        order_id="OA_260901_99",
        status="PLACED",
        symbol="RELIANCE",
        action="BUY",
        quantity=25,
        price=2950.0,
        message="Order placed via Zerodha Kite",
        broker="zerodha",
    )
    d = res.to_dict()
    assert d["success"] is True
    assert d["order_id"] == "OA_260901_99"
    assert d["broker"] == "zerodha"
    assert d["action"] == "BUY"


def test_openalgo_unconfigured_rejection():
    """Client without API key must fail-closed and reject order placement."""
    client = OpenAlgoBrokerClient(api_key="")
    assert client.is_configured is False

    res = client.place_order(symbol="TCS", action="BUY", quantity=10)
    assert res.success is False
    assert res.status == "REJECTED"
    assert res.rejection_reason == "CONFIG_REQUIRED"


def test_openalgo_place_market_order_mocked_success():
    client = OpenAlgoBrokerClient(
        api_key="VALID_OPENALGO_KEY",
        host="http://127.0.0.1:5000",
        broker="dhan",
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "status": "success",
        "orderid": "DHAN_ORD_1001",
        "message": "Order submitted to exchange",
    }

    with patch("httpx.post", return_value=mock_resp) as mock_post:
        res = client.place_order(
            symbol="INFY",
            action="BUY",
            quantity=50,
            exchange="NSE",
            price_type="MARKET",
            product="MIS",
        )
        assert res.success is True
        assert res.order_id == "DHAN_ORD_1001"
        assert res.broker == "dhan"
        assert res.status == "PLACED"

        # Verify posted payload
        call_kwargs = mock_post.call_args[1]
        payload = call_kwargs["json"]
        assert payload["apikey"] == "VALID_OPENALGO_KEY"
        assert payload["symbol"] == "INFY"
        assert payload["action"] == "BUY"
        assert payload["quantity"] == 50
        assert payload["pricetype"] == "MARKET"


def test_openalgo_cancel_order_mocked():
    client = OpenAlgoBrokerClient(api_key="VALID_KEY", broker="fyers")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"status": "success", "message": "Order cancelled"}

    with patch("httpx.post", return_value=mock_resp):
        ok = client.cancel_order("FYERS_ORD_99")
        assert ok is True


def test_openalgo_get_positions_mocked():
    client = OpenAlgoBrokerClient(api_key="VALID_KEY", broker="zerodha")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "status": "success",
        "data": [
            {"symbol": "SBIN", "quantity": 100, "buy_price": 810.0, "pnl": 500.0}
        ],
    }

    with patch("httpx.post", return_value=mock_resp):
        positions = client.get_positions()
        assert len(positions) == 1
        assert positions[0]["symbol"] == "SBIN"
        assert positions[0]["pnl"] == 500.0

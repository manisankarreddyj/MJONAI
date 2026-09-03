"""
Unit tests for execution/brokers/shoonya.py (ShoonyaBrokerClient).
Verifies authentication lifecycle, order payload formatting, multi-leg execution,
and fail-closed rejection handling.
"""

from unittest.mock import MagicMock, patch
import pytest

from execution.brokers.shoonya import ShoonyaBrokerClient, ShoonyaOrderResult


def test_shoonya_order_result_dataclass():
    res = ShoonyaOrderResult(
        success=True,
        order_id="2609010001",
        status="COMPLETE",
        symbol="NIFTY26AUG24500CE",
        quantity=50,
        price=125.50,
        message="Order placed successfully",
    )
    d = res.to_dict()
    assert d["success"] is True
    assert d["order_id"] == "2609010001"
    assert d["symbol"] == "NIFTY26AUG24500CE"
    assert d["quantity"] == 50


def test_shoonya_unauthenticated_rejection():
    """Client without valid auth must fail-closed and reject order placement."""
    client = ShoonyaBrokerClient()
    assert client.is_authenticated is False

    res = client.place_order(
        symbol="NIFTY26AUG24500CE",
        exchange="NFO",
        transaction_type="SELL",
        quantity=50,
    )
    assert res.success is False
    assert res.status == "REJECTED"
    assert res.rejection_reason == "AUTH_REQUIRED"


def test_shoonya_login_mocked_success():
    client = ShoonyaBrokerClient(
        user_id="FA12345",
        password="SecretPassword",
        two_fa_token="JBSWY3DPEHPK3PXP",
        vendor_code="FA12345_U",
        api_key="API_KEY_123",
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "stat": "Ok",
        "susertoken": "mock_shoonya_session_token_xyz",
    }

    with patch("httpx.post", return_value=mock_resp),          patch("pyotp.TOTP.now", return_value="123456"):
        ok = client.login()
        assert ok is True
        assert client.is_authenticated is True
        assert client.token == "mock_shoonya_session_token_xyz"


def test_shoonya_place_multi_leg_order():
    client = ShoonyaBrokerClient(user_id="FA12345")
    client.token = "active_token"
    client._is_authenticated = True

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "stat": "Ok",
        "norenordno": "ORD_999888",
    }

    legs = [
        {"symbol": "NIFTY26AUG24500CE", "exchange": "NFO", "transaction_type": "SELL", "quantity": 50, "price": 120.0},
        {"symbol": "NIFTY26AUG24000PE", "exchange": "NFO", "transaction_type": "SELL", "quantity": 50, "price": 95.0},
    ]

    with patch("httpx.post", return_value=mock_resp):
        results = client.place_multi_leg_order(legs, strategy_id="S09_OptionsThetaDecay")
        assert len(results) == 2
        assert all(r.success for r in results)
        assert results[0].order_id == "ORD_999888"
        assert results[1].order_id == "ORD_999888"

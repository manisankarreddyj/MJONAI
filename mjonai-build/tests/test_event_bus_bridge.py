"""
Test Suite: tests/test_event_bus_bridge.py
Purpose: Verification of Web UI Event Bus Ring Buffer, High-Watermark Catchup,
         and Listener Fan-Out Bridge to WebSocket Stream.
"""

from unittest.mock import MagicMock, patch
import pytest

from communication.events import (
    publish_event,
    get_recent_events,
    get_events_since,
    register_event_listener,
    unregister_event_listener,
    clear_events_buffer,
)


def test_event_bus_publishing_and_ring_buffer_fifo():
    """Verify ring buffer stores events with monotonically increasing sequence IDs."""
    clear_events_buffer()

    ev1 = publish_event("TEST_EVENT_A", {"symbol": "INFY"})
    ev2 = publish_event("TEST_EVENT_B", {"symbol": "TCS"})

    assert ev1.event_id == 1
    assert ev2.event_id == 2
    assert ev1.event_type == "TEST_EVENT_A"
    assert ev2.event_type == "TEST_EVENT_B"

    recent = get_recent_events(limit=10)
    assert len(recent) == 2
    assert recent[0]["event_id"] == 1
    assert recent[1]["event_id"] == 2


def test_get_events_since_catchup():
    """Verify client reconnection catch-up via get_events_since."""
    clear_events_buffer()

    for i in range(1, 6):
        publish_event(f"EVENT_{i}", {"index": i})

    # Client was disconnected after event_id 3
    catchup = get_events_since(last_event_id=3)
    assert len(catchup) == 2
    assert catchup[0]["event_id"] == 4
    assert catchup[1]["event_id"] == 5


def test_listener_registration_and_fan_out():
    """Verify registered callbacks receive published events."""
    clear_events_buffer()
    received_events = []

    def mock_listener(evt):
        received_events.append(evt)

    register_event_listener(mock_listener)

    try:
        publish_event("SIGNAL_ALERT", {"symbol": "RELIANCE", "price": 2500.0})
        assert len(received_events) == 1
        assert received_events[0]["event_type"] == "SIGNAL_ALERT"
        assert received_events[0]["payload"]["symbol"] == "RELIANCE"
    finally:
        unregister_event_listener(mock_listener)

    # After unregister, should not receive further events
    publish_event("TRADE_CLOSE", {"symbol": "RELIANCE"})
    assert len(received_events) == 1

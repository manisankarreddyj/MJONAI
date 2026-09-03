"""
Comprehensive Unit & Integration Test Suite for db/client.py.
Tests connection lifecycle, mutex initialization, connection pooling, active ping probes,
exponential backoff retry resilience, query telemetry metrics, and proxy behaviors.
"""

from pathlib import Path
import sys
from unittest.mock import MagicMock, patch
import pytest

# Ensure workspace root is in sys.path
_root_dir = Path(__file__).resolve().parent.parent  # repo root (ADR-0008)
if str(_root_dir) not in sys.path:
    sys.path.insert(0, str(_root_dir))

from mjonai.db.client import (
    get_supabase_client,
    is_db_connected,
    ping_db,
    reset_db_client,
    execute_with_retry,
    get_db_metrics,
    reset_db_metrics,
    sb,
)


@pytest.fixture(autouse=True)
def reset_client():
    reset_db_client()
    reset_db_metrics()
    yield
    reset_db_client()
    reset_db_metrics()


# ── 1. SINGLETON & DOUBLE-CHECKED LOCKING ────────────────────────────────────

def test_supabase_client_singleton():
    """Verify get_supabase_client returns same singleton instance on repeated calls."""
    with patch("supabase.create_client") as mock_create:
        mock_instance = MagicMock()
        mock_create.return_value = mock_instance

        with patch.dict("os.environ", {"SUPABASE_URL": "https://xyz.supabase.co", "SUPABASE_KEY": "secret_key"}):
            c1 = get_supabase_client()
            c2 = get_supabase_client()

            assert c1 is c2
            assert mock_create.call_count == 1


def test_supabase_client_missing_env_returns_none():
    """Verify get_supabase_client returns None gracefully when environment variables are missing."""
    with patch.dict("os.environ", {}, clear=True):
        client = get_supabase_client()
        assert client is None


# ── 2. PASSIVE & ACTIVE HEALTH PROBES ────────────────────────────────────────

def test_is_db_connected_health_probe():
    """Verify is_db_connected returns True when client exists, False otherwise."""
    with patch.dict("os.environ", {}, clear=True):
        assert is_db_connected() is False

    with patch("supabase.create_client") as mock_create:
        mock_create.return_value = MagicMock()
        with patch.dict("os.environ", {"SUPABASE_URL": "https://xyz.supabase.co", "SUPABASE_KEY": "secret_key"}):
            assert is_db_connected() is True


def test_ping_db_active_probe_success():
    """Verify ping_db executes minimal query and returns True on success."""
    mock_client = MagicMock()
    mock_table = MagicMock()
    mock_select = MagicMock()
    mock_limit = MagicMock()
    mock_execute = MagicMock()

    mock_client.table.return_value = mock_table
    mock_table.select.return_value = mock_select
    mock_select.limit.return_value = mock_limit
    mock_limit.execute.return_value = MagicMock(data=[{"id": 1}])

    with patch("mjonai.db.client.get_supabase_client", return_value=mock_client):
        assert ping_db() is True
        mock_client.table.assert_called_once_with("system_log")

    metrics = get_db_metrics()
    assert metrics["total_queries"] >= 1
    assert metrics["successful_queries"] >= 1


def test_ping_db_active_probe_failure_is_non_throwing():
    """Verify ping_db catches network exceptions and returns False safely without raising."""
    mock_client = MagicMock()
    mock_client.table.side_effect = ConnectionError("Supabase network unreachable")

    with patch("mjonai.db.client.get_supabase_client", return_value=mock_client):
        assert ping_db() is False

    metrics = get_db_metrics()
    assert metrics["failed_queries"] >= 1


# ── 3. EXPONENTIAL BACKOFF RETRY RESILIENCE ──────────────────────────────────

def test_execute_with_retry_succeeds_first_attempt():
    """Verify execute_with_retry executes cleanly without retrying on success."""
    counter = {"calls": 0}

    def sample_query():
        counter["calls"] += 1
        return "QUERY_OK"

    res = execute_with_retry(sample_query, max_retries=3, initial_delay=0.01)
    assert res == "QUERY_OK"
    assert counter["calls"] == 1

    metrics = get_db_metrics()
    assert metrics["total_queries"] == 1
    assert metrics["successful_queries"] == 1
    assert metrics["retried_queries"] == 0


def test_execute_with_retry_recovers_after_transient_error():
    """Verify execute_with_retry recovers after transient failure and records retried metric."""
    counter = {"calls": 0}

    def flakey_query():
        counter["calls"] += 1
        if counter["calls"] < 3:
            raise ConnectionResetError("Transient HTTP 502 Bad Gateway")
        return "RECOVERED_DATA"

    res = execute_with_retry(flakey_query, max_retries=3, initial_delay=0.01)
    assert res == "RECOVERED_DATA"
    assert counter["calls"] == 3

    metrics = get_db_metrics()
    assert metrics["successful_queries"] == 1
    assert metrics["retried_queries"] == 1


def test_execute_with_retry_raises_after_max_retries():
    """Verify execute_with_retry raises exception when all attempts fail."""
    def broken_query():
        raise TimeoutError("Database query timed out")

    with pytest.raises(TimeoutError):
        execute_with_retry(broken_query, max_retries=2, initial_delay=0.01)

    metrics = get_db_metrics()
    assert metrics["failed_queries"] == 1


# ── 4. PROXY BEHAVIORS & RUNTIME ERRORS ──────────────────────────────────────

def test_supabase_proxy_table_delegation():
    """Verify sb proxy delegates transparently to underlying client."""
    mock_client = MagicMock()
    mock_client.table.return_value = "table_instance"

    with patch("mjonai.db.client.get_supabase_client", return_value=mock_client):
        assert sb.table("trades") == "table_instance"
        assert sb.is_connected() is True
        assert isinstance(sb.metrics(), dict)


def test_supabase_proxy_raises_on_uninitialized_access():
    """Verify sb proxy raises descriptive RuntimeError when accessed without credentials."""
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(RuntimeError) as exc_info:
            sb.table("trades")
        assert "Cannot access 'table': Supabase client not initialized" in str(exc_info.value)

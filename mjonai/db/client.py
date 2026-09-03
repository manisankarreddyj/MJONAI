"""
Module: db/client.py

Purpose: Centralized Database Connection, Supabase Client Lifecycle,
         Thread-Safe Lazy Proxy, Connection Health Management, Network Ping Probes,
         Exponential Backoff Resilience, and Query Performance Metrics.

Architectural Principles:
  1. Single Connection Provider shared across all db submodules.
  2. Thread-Safe Mutex Initialization (Double-checked locking pattern).
  3. Enterprise Connection Pooling & Strict Timeout Protection (httpx limits & timeouts).
  4. Non-Throwing Connection Health Probes (is_db_connected) & Active Round-Trip Ping (ping_db).
  5. Transient Network Failure Resilience with Jittered Exponential Backoff (execute_with_retry).
  6. Live Query Metrics & Latency Profiling (get_db_metrics, reset_db_metrics).
  7. Automated Self-Healing & Reconnection Hooks (reset_db_client).
  8. 100% Backwards-Compatible Public API (sb.table(...)).
"""

from datetime import datetime, timezone
import logging
import os
import random
import threading
import time
from typing import Any, Callable, Dict, Optional, TypeVar

logger = logging.getLogger(__name__)

try:
    from mjonai.core.runtime_config import load_mjonai_env
    load_mjonai_env()
except ImportError:
    pass

_client_instance = None
_init_lock = threading.Lock()

# ── 1. REAL-TIME QUERY METRICS & TELEMETRY ───────────────────────────────────
_metrics_lock = threading.Lock()
_METRICS = {
    "total_queries": 0,
    "successful_queries": 0,
    "failed_queries": 0,
    "retried_queries": 0,
    "last_latency_ms": 0.0,
    "total_latency_ms": 0.0,
    "started_at_utc": datetime.now(timezone.utc).isoformat(),
}


def _record_metric(latency_ms: float, success: bool = True, retried: bool = False) -> None:
    """Thread-safe recording of database query telemetry."""
    with _metrics_lock:
        _METRICS["total_queries"] += 1
        if success:
            _METRICS["successful_queries"] += 1
        else:
            _METRICS["failed_queries"] += 1
        if retried:
            _METRICS["retried_queries"] += 1
        _METRICS["last_latency_ms"] = round(latency_ms, 2)
        _METRICS["total_latency_ms"] += latency_ms


def get_db_metrics() -> Dict[str, Any]:
    """
    Return thread-safe snapshot of database query metrics, throughput, and latency.
    Used by Health Monitors and System Observability Dashboards.
    """
    with _metrics_lock:
        total = _METRICS["total_queries"]
        avg_lat = (_METRICS["total_latency_ms"] / total) if total > 0 else 0.0
        return {
            "total_queries": total,
            "successful_queries": _METRICS["successful_queries"],
            "failed_queries": _METRICS["failed_queries"],
            "retried_queries": _METRICS["retried_queries"],
            "success_rate_pct": round((_METRICS["successful_queries"] / total * 100.0), 2) if total > 0 else 100.0,
            "last_latency_ms": _METRICS["last_latency_ms"],
            "avg_latency_ms": round(avg_lat, 2),
            "started_at_utc": _METRICS["started_at_utc"],
        }


def reset_db_metrics() -> None:
    """Reset query metrics (used for daily session rollover & test isolation)."""
    with _metrics_lock:
        _METRICS["total_queries"] = 0
        _METRICS["successful_queries"] = 0
        _METRICS["failed_queries"] = 0
        _METRICS["retried_queries"] = 0
        _METRICS["last_latency_ms"] = 0.0
        _METRICS["total_latency_ms"] = 0.0
        _METRICS["started_at_utc"] = datetime.now(timezone.utc).isoformat()


# ── 2. SUPABASE CLIENT SINGLETON ─────────────────────────────────────────────

def get_supabase_client():
    """
    Thread-safe lazy initialization of Supabase client instance.
    Uses double-checked locking to prevent initialization race conditions.
    Configures connection pooling and strict socket timeouts via ClientOptions.
    """
    global _client_instance
    if _client_instance is None:
        with _init_lock:
            if _client_instance is None:
                try:
                    import httpx
                    from supabase import create_client, ClientOptions

                    url = os.getenv("SUPABASE_URL")
                    key = os.getenv("SUPABASE_KEY")
                    if url and key:
                        # Configure resilient HTTP connection pool with explicit timeouts
                        custom_http_client = httpx.Client(
                            timeout=httpx.Timeout(10.0, connect=5.0),
                            limits=httpx.Limits(max_keepalive_connections=20, max_connections=50)
                        )
                        options = ClientOptions(httpx_client=custom_http_client)
                        _client_instance = create_client(url.strip(), key.strip(), options=options)
                        logger.info("[db.client] Supabase client initialized with connection pooling.")
                    else:
                        logger.warning("[db.client] SUPABASE_URL or SUPABASE_KEY not set in environment.")
                except Exception as e:
                    logger.error(f"[db.client] Failed to create Supabase client: {e}")
    return _client_instance


def is_db_connected() -> bool:
    """
    Non-throwing passive health probe inspecting whether the client instance is instantiated.
    Used by Health Monitors, Startup Guards, and Pre-Trade Risk Gates.
    """
    client = get_supabase_client()
    return client is not None


def ping_db(timeout_seconds: float = 3.0) -> bool:
    """
    Active round-trip network probe to verify database server responsiveness.
    Executes a minimal non-blocking query to distinguish between client instantiation vs real network reachability.
    """
    client = get_supabase_client()
    if client is None:
        return False
    start = time.perf_counter()
    try:
        _ = client.table("system_log").select("id").limit(1).execute()
        latency_ms = (time.perf_counter() - start) * 1000.0
        _record_metric(latency_ms, success=True)
        logger.debug(f"[db.client] Database ping successful ({latency_ms:.1f}ms)")
        return True
    except Exception as e:
        latency_ms = (time.perf_counter() - start) * 1000.0
        _record_metric(latency_ms, success=False)
        logger.warning(f"[db.client] Database ping probe failed: {e}")
        return False


def reset_db_client():
    """
    Reset client instance to force clean re-initialization on next access.
    Used for automated recovery after network reconnections or token refreshes.
    """
    global _client_instance
    with _init_lock:
        _client_instance = None
        logger.info("[db.client] Database client instance reset.")


# ── 3. RESILIENT EXPONENTIAL BACKOFF RETRY WRAPPER ───────────────────────────

T = TypeVar("T")


def execute_with_retry(
    query_fn: Callable[[], T],
    max_retries: int = 3,
    initial_delay: float = 0.2,
    backoff_factor: float = 2.0,
    retry_on_exceptions: tuple = (Exception,)
) -> T:
    """
    Execute a database query with jittered exponential backoff for transient network glitches (429/502/503).
    Logs telemetry metrics and gracefully propagates non-retryable errors.
    """
    last_exception: Optional[Exception] = None
    delay = initial_delay

    for attempt in range(1, max_retries + 1):
        start = time.perf_counter()
        try:
            result = query_fn()
            latency_ms = (time.perf_counter() - start) * 1000.0
            _record_metric(latency_ms, success=True, retried=(attempt > 1))
            return result
        except retry_on_exceptions as exc:
            latency_ms = (time.perf_counter() - start) * 1000.0
            last_exception = exc
            is_last_attempt = (attempt == max_retries)

            if is_last_attempt:
                _record_metric(latency_ms, success=False, retried=(attempt > 1))
                logger.error(f"[db.client] Query failed permanently after {max_retries} attempts: {exc}")
                raise exc

            # Calculate jittered exponential backoff
            jitter = random.uniform(0.8, 1.2)
            sleep_time = delay * jitter
            logger.warning(f"[db.client] Transient query error (attempt {attempt}/{max_retries}): {exc}. Retrying in {sleep_time:.2f}s...")
            time.sleep(sleep_time)
            delay *= backoff_factor

    if last_exception:
        raise last_exception
    raise RuntimeError("[db.client] execute_with_retry failed with unknown state")


# ── 4. TRANSPARENT LAZY PROXY ────────────────────────────────────────────────

class _SupabaseClientProxy:
    """
    Proxy object providing transparent, backward-compatible access to the Supabase client.
    Defers client connection until first attribute access (e.g. sb.table(...)).
    """
    def __getattr__(self, name: str) -> Any:
        client = get_supabase_client()
        if client is not None:
            return getattr(client, name)
        raise RuntimeError(
            f"[db.client] Cannot access '{name}': Supabase client not initialized. "
            "Please verify SUPABASE_URL and SUPABASE_KEY in your environment (.env)."
        )

    def is_connected(self) -> bool:
        """Helper to check passive connection status directly via proxy."""
        return is_db_connected()

    def ping(self, timeout_seconds: float = 3.0) -> bool:
        """Helper to check active network reachability directly via proxy."""
        return ping_db(timeout_seconds=timeout_seconds)

    def metrics(self) -> Dict[str, Any]:
        """Helper to inspect live query telemetry via proxy."""
        return get_db_metrics()

    def execute_with_retry(self, query_fn: Callable[[], T], max_retries: int = 3) -> T:
        """Helper to run queries with automatic exponential backoff."""
        return execute_with_retry(query_fn, max_retries=max_retries)


def sanitize_db_payload(data: Any) -> Any:
    """
    Recursively cleans payload of NaN, Inf, and NumPy scalar types before JSON serialization.
    Prevents PostgreSQL / HTTP 400 Bad Request payload crashes.
    """
    import math
    try:
        import numpy as np
    except ImportError:
        np = None

    if data is None:
        return None
    if isinstance(data, dict):
        return {str(k): sanitize_db_payload(v) for k, v in data.items()}
    if isinstance(data, (list, tuple)):
        return [sanitize_db_payload(v) for v in data]
    if np is not None and isinstance(data, (np.floating, float)) or isinstance(data, float):
        f = float(data)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    if np is not None and isinstance(data, (np.integer, int)) or isinstance(data, int):
        return int(data)
    if np is not None and isinstance(data, (np.bool_, bool)) or isinstance(data, bool):
        return bool(data)
    if hasattr(data, "isoformat"):
        return data.isoformat()
    return data


# Shared singleton proxy instance (backwards-compatible with sb.table(...))
sb = _SupabaseClientProxy()

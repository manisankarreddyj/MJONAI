"""
Unit test suite for orchestration/memory_sentry.py
Validates heap compaction, garbage collection metrics, and RAM monitoring.
"""

import pytest
from apps.runtime.orchestration.memory_sentry import (
    MemoryHealthReport,
    get_process_memory_mb,
    compact_heap,
)


def test_get_process_memory_mb():
    """Verify process RSS memory returns a realistic positive number."""
    rss = get_process_memory_mb()
    assert isinstance(rss, float)
    assert rss > 0.0


def test_compact_heap():
    """Verify generational garbage collection sweeps and returns telemetry."""
    # Create circular reference
    a = []
    b = [a]
    a.append(b)
    del a, b

    rep = compact_heap(generation=2)
    assert isinstance(rep, MemoryHealthReport)
    assert rep.rss_mb > 0.0
    assert rep.tracked_objects > 0
    assert rep.is_healthy is True
    assert rep.status == "OPTIMAL"

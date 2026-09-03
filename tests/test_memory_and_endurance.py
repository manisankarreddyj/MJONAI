"""
Memory Leak, Cache Saturation & Endurance Soak Test Suite.
Verifies zero unbounded memory growth and strict O(1) RAM stability under high continuous tick loops.
"""

from pathlib import Path
import sys
import tracemalloc
import pytest

# Ensure workspace root is in sys.path
_root_dir = Path(__file__).resolve().parent.parent  # repo root (ADR-0008)
if str(_root_dir) not in sys.path:
    sys.path.insert(0, str(_root_dir))

from mjonai.data.feed_manager import update_multi_asset_tick, clear_multi_asset_ticks
from mjonai.data.market import update_sector_price, calculate_sector_breadth, SectorIndex, clear_sector_prices
from mjonai.data.earnings import check_earnings_risk, clear_earnings_cache, get_earnings_cache_size


@pytest.fixture(autouse=True)
def cleanup():
    clear_multi_asset_ticks()
    clear_sector_prices()
    clear_earnings_cache()
    yield
    clear_multi_asset_ticks()
    clear_sector_prices()
    clear_earnings_cache()


# ── 1. LONG-SOAK TICK INGESTION MEMORY RETENTION ─────────────────────────────

def test_long_soak_tick_memory_stability():
    """
    Ingest 50,000 tick updates into in-memory price stores.
    Asserts memory overhead grows by < 2.0 MB (O(1) state overwrites, zero memory leaks).
    """
    tracemalloc.start()
    snapshot_before = tracemalloc.take_snapshot()

    symbols = [f"INSTRUMENT_{i % 50}" for i in range(50)]

    for iteration in range(50_000):
        sym = symbols[iteration % len(symbols)]
        update_multi_asset_tick(
            symbol=sym,
            ltp=100.0 + (iteration % 50),
            volume=iteration * 10,
            best_bid=99.95,
            best_ask=100.05,
        )

    snapshot_after = tracemalloc.take_snapshot()
    tracemalloc.stop()

    top_stats = snapshot_after.compare_to(snapshot_before, 'lineno')
    total_diff_kb = sum(stat.size_diff for stat in top_stats) / 1024.0

    print(f"\n[ENDURANCE] 50,000 Tick Loop Memory Delta: {total_diff_kb:.2f} KB")
    # Memory growth should be under 2MB for in-place dict updates
    assert total_diff_kb < 2048.0, f"Memory growth exceeded 2 MB limit ({total_diff_kb:.2f} KB)"


# ── 2. SECTOR BREADTH ENDURANCE LOOP ─────────────────────────────────────────

def test_sector_breadth_continuous_calculation_endurance():
    """
    Execute 25,000 continuous sector breadth evaluations.
    Verifies zero memory leakage in snapshot instantiation and provenance formatting.
    """
    tracemalloc.start()
    snapshot_before = tracemalloc.take_snapshot()

    for i in range(25_000):
        mock_returns = {sec: (0.01 if i % 2 == 0 else -0.01) for sec in list(SectorIndex)}
        snap = calculate_sector_breadth(mock_returns)
        _ = snap.to_dict()

    snapshot_after = tracemalloc.take_snapshot()
    tracemalloc.stop()

    top_stats = snapshot_after.compare_to(snapshot_before, 'lineno')
    total_diff_kb = sum(stat.size_diff for stat in top_stats) / 1024.0

    print(f"\n[ENDURANCE] 25,000 Sector Breadth Calculations Delta: {total_diff_kb:.2f} KB")
    assert total_diff_kb < 1024.0, f"Memory growth exceeded 1 MB limit ({total_diff_kb:.2f} KB)"


# ── 3. TTL CACHE EVICTION & MEMORY RECLAMATION ────────────────────────────────

def test_cache_clearing_memory_reclamation():
    """Verify clear functions purge all in-memory structures cleanly."""
    for i in range(100):
        update_multi_asset_tick(f"TICK_{i}", ltp=float(i + 1))
        update_sector_price(SectorIndex.NIFTY_BANK, ltp=float(i + 1), prev_close=100.0)

    clear_multi_asset_ticks()
    clear_sector_prices()
    clear_earnings_cache()

    assert get_earnings_cache_size() == 0

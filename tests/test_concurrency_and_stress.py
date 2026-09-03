"""
High-Concurrency, Multithreading & Market Open Stress Test Suite.
Simulates high-load 09:15 AM opening spikes, concurrent reader/writer storms, and deadlock prevention.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
import random
import sys
import threading
import time
import pytest

# Ensure workspace root is in sys.path
_root_dir = Path(__file__).resolve().parent.parent  # repo root (ADR-0008)
if str(_root_dir) not in sys.path:
    sys.path.insert(0, str(_root_dir))

from mjonai.data.feed_manager import LiveFeedManager, update_multi_asset_tick, clear_multi_asset_ticks
from mjonai.data.market import update_sector_price, calculate_sector_breadth, SectorIndex, clear_sector_prices
from mjonai.data.earnings import check_earnings_risk, clear_earnings_cache


@pytest.fixture(autouse=True)
def cleanup():
    clear_multi_asset_ticks()
    clear_sector_prices()
    clear_earnings_cache()
    yield
    clear_multi_asset_ticks()
    clear_sector_prices()
    clear_earnings_cache()


# ── 1. 09:15 AM OPENING TICK BURST STRESS TEST ───────────────────────────────

def test_market_opening_concurrent_burst_stress():
    """
    Simulate 09:15 AM market opening surge:
    10 concurrent writer threads pushing 20,000 ticks into LiveFeedManager
    simultaneously with 10 concurrent reader threads querying quotes.
    Asserts zero race conditions, zero deadlocks, and zero unhandled exceptions.
    """
    num_writers = 8
    num_readers = 8
    ticks_per_writer = 2_500
    symbols = ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK", "SBIN", "BHARTIARTL", "ITC"]

    errors = []
    stop_event = threading.Event()

    def writer_worker(thread_id: int):
        try:
            for i in range(ticks_per_writer):
                sym = symbols[i % len(symbols)]
                price = 1000.0 + random.uniform(-10.0, 10.0)
                update_multi_asset_tick(
                    symbol=sym,
                    ltp=price,
                    volume=100 * (i + 1),
                    best_bid=price - 0.05,
                    best_ask=price + 0.05,
                )
        except Exception as e:
            errors.append(f"Writer {thread_id} error: {e}")

    def reader_worker(thread_id: int):
        try:
            while not stop_event.is_set():
                sym = random.choice(symbols)
                p = LiveFeedManager.get_price(sym, exchange="CRYPTO")
                if p is not None:
                    assert p > 0
                time.sleep(0.0001)
        except Exception as e:
            errors.append(f"Reader {thread_id} error: {e}")

    with ThreadPoolExecutor(max_workers=num_writers + num_readers) as executor:
        writer_futures = [executor.submit(writer_worker, i) for i in range(num_writers)]
        reader_futures = [executor.submit(reader_worker, i) for i in range(num_readers)]

        # Wait for writers to complete
        for f in as_completed(writer_futures):
            f.result()

        # Stop reader threads
        stop_event.set()
        for f in as_completed(reader_futures):
            f.result()

    assert len(errors) == 0, f"Encountered concurrency errors: {errors}"


# ── 2. SECTOR BREADTH CONCURRENT INGESTION & CALCULATION ─────────────────────

def test_sector_breadth_concurrent_read_write_stress():
    """
    Verify sector breadth engine handles simultaneous price tick updates
    and breadth calculations across multiple threads without locking contention.
    """
    errors = []
    iterations = 2_000

    def tick_updater():
        try:
            for i in range(iterations):
                sec = random.choice(list(SectorIndex))
                base = 25000.0
                ltp = base * (1.0 + random.uniform(-0.03, 0.03))
                update_sector_price(sec, ltp=ltp, prev_close=base)
        except Exception as e:
            errors.append(f"Updater error: {e}")

    def breadth_reader():
        try:
            for _ in range(iterations):
                snap = calculate_sector_breadth()
                assert 0.0 <= snap.breadth_pct <= 1.0
        except Exception as e:
            errors.append(f"Reader error: {e}")

    t1 = threading.Thread(target=tick_updater)
    t2 = threading.Thread(target=breadth_reader)
    t3 = threading.Thread(target=breadth_reader)

    t1.start()
    t2.start()
    t3.start()

    t1.join(timeout=5.0)
    t2.join(timeout=5.0)
    t3.join(timeout=5.0)

    assert not t1.is_alive(), "Updater thread timed out (deadlock detected)"
    assert not t2.is_alive(), "Reader thread 1 timed out (deadlock detected)"
    assert not t3.is_alive(), "Reader thread 2 timed out (deadlock detected)"
    assert len(errors) == 0, f"Encountered errors: {errors}"


# ── 3. DEADLOCK RESISTANCE & RLOCK RE-ENTRANCY ────────────────────────────────

def test_recursive_rlock_reentrancy():
    """
    Verify internal helper methods inside LiveFeedManager calling other locked methods
    do not trigger deadlock due to RLock re-entrancy.
    """
    update_multi_asset_tick(
        "TATAMOTORS",
        ltp=1050.0,
        best_bid=1049.95,
        best_ask=1050.05,
    )

    # Calling get_quote which internally reads bid/ask and calculates spread
    quote = LiveFeedManager.get_quote("TATAMOTORS", exchange="CRYPTO")
    assert quote is not None
    assert quote["ltp"] == 1050.0
    assert quote["spread_bps"] is not None

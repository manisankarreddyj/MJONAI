import pytest
from mjonai.execution.algo_execution import SEBIRateLimiter


def test_sebi_rate_limiter_token_bucket():
    """Verify SEBI 10-OPS token bucket rate limiter."""
    limiter = SEBIRateLimiter(max_ops=10, burst_limit=5)
    # Immediate acquire within burst limit
    assert limiter.acquire(tokens_needed=3, timeout=0.1) is True
    assert limiter.acquire(tokens_needed=2, timeout=0.1) is True

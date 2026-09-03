"""Transitional shim (Phase 2 will archive this module).

The research Strategy ABC moved to `research.strategy` during the
engine absorption. Engine-side strategies keep importing from here
so both worlds stay functional until the registry adapter lands.
"""

from research.strategy import Strategy, StrategyResult  # noqa: F401

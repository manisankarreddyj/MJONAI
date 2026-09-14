"""
Module: core/numeric.py

Purpose:
    Single-source numeric safety helpers for the kernel.

    `safe_float` consolidates the formerly duplicated `_safe_float` /
    `to_float` / `_to_float` converters that existed in >=12 modules
    (P2 maintainability consolidation, 2026-09-14): any JSON/database
    value is converted defensively — None/container values, non-numeric
    strings and NaN/Inf all collapse to the caller's default instead of
    raising or leaking non-finite floats into downstream math.
"""

from __future__ import annotations

import math
from typing import Any, Optional


def safe_float(val: Any, default: Optional[float] = 0.0) -> Optional[float]:
    """Safely convert any JSON/database value to float.

    - None / list / dict / tuple -> default
    - non-numeric strings -> default
    - NaN / ±Inf -> default
    - otherwise -> float(val)

    Callers that need "absent" (rather than 0.0) pass ``default=None``.
    """

    try:
        if val is None or isinstance(val, (list, dict, tuple)):
            return default
        f = float(val)
        return default if math.isnan(f) or math.isinf(f) else f
    except (ValueError, TypeError):
        return default
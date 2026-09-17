"""
Module: engine/research/pit_universe.py
Purpose: Point-in-time (PIT) universe ledger — Decision 6 Phase 3.

Loads the curated NIFTY 50 membership history CSV
(``mjonai/data/pit/nifty50_membership_history.csv``) and answers membership
as-of any date. Half-open intervals ``[valid_from, valid_to)``; a null
``valid_to`` means the symbol is still a member (open leg).

Survivorship contract (fail-closed):
  * Membership before the ledger's coverage start (2014-01-01) is NOT
    claimable — ``members()``/``is_member()`` raise instead of silently
    substituting today's membership.
  * ``membership_intervals()`` returns ALL legs per symbol (GRASIM has two),
    never a single merged span — a re-entry must not bleed into the gap.
"""

from __future__ import annotations

import csv
import os
from datetime import date, datetime
from typing import Optional

# Path to the curated membership history (sits next to the other curated
# data assets, ADR-0008 layout).
PIT_CSV_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "pit",
    "nifty50_membership_history.csv",
)

# NSE index long name as printed in the ledger (index_name column).
NIFTY50_INDEX_NAME = "Nifty 50"

# Index-name aliases accepted at the public API (tier key -> index_name).
INDEX_NAME_ALIASES = {
    "NIFTY_50": NIFTY50_INDEX_NAME,
}

# Research/InstrumentMaster symbol -> NSE index symbol. The only known
# divergence is the 2025 Tata Motors demerger: the index holds the PV arm
# (TMPV) while legacy/research code still asks for TATAMOTORS.
SYMBOL_ALIASES = {
    "TATAMOTORS": "TMPV",
}


class PitUniverseLedger:

    def __init__(
        self,
        csv_path: str = PIT_CSV_PATH,
    ) -> None:

        self._csv_path = csv_path
        self._rows: list[dict] = []
        self._legs_by_symbol: dict[tuple[str, str], list[tuple[date, Optional[date]]]] = {}
        self._coverage_start: Optional[date] = None
        self._loaded = False

    def _ensure_loaded(self) -> None:

        if self._loaded:
            return

        if not os.path.exists(self._csv_path):
            raise FileNotFoundError(
                f"[pit_universe] membership history CSV missing: {self._csv_path}. "
                "Generate/restore it from the upstream aditya-jha/nse-historical-membership "
                "dataset (see mjonai/data/pit/PROVENANCE.md)."
            )

        try:
            with open(self._csv_path, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    symbol = (row.get("symbol") or "").strip().upper()
                    index_name = (row.get("index_name") or "").strip()
                    valid_from = row.get("valid_from") or None
                    valid_to = row.get("valid_to") or None
                    if not symbol or not index_name or valid_from is None:
                        continue
                    start = datetime.strptime(valid_from, "%Y-%m-%d").date()
                    end = (
                        datetime.strptime(valid_to, "%Y-%m-%d").date()
                        if valid_to is not None
                        else None
                    )
                    self._rows.append(
                        {
                            "index_name": index_name,
                            "symbol": symbol,
                            "valid_from": start,
                            "valid_to": end,
                        }
                    )
        except Exception as e:
            raise RuntimeError(
                f"[pit_universe] failed reading membership CSV {self._csv_path}: {e}"
            ) from e

        for row in self._rows:
            leg = (row["valid_from"], row["valid_to"])
            self._legs_by_symbol.setdefault((row["index_name"], row["symbol"]), []).append(leg)

            if self._coverage_start is None or row["valid_from"] < self._coverage_start:
                self._coverage_start = row["valid_from"]

        self._loaded = True

    def _resolve_index_name(self, index_name: str) -> str:

        return INDEX_NAME_ALIASES.get(str(index_name).upper(), index_name)

    def _resolve_symbol(self, symbol: str) -> str:

        clean = (symbol or "").strip().upper()
        return SYMBOL_ALIASES.get(clean, clean)

    @staticmethod
    def _as_date(asof) -> date:

        if isinstance(asof, datetime):
            return asof.date()
        if isinstance(asof, date):
            return asof
        raise TypeError(
            f"[pit_universe] asof must be date/datetime, got {type(asof).__name__}"
        )

    def membership_intervals(
        self,
        symbol: str,
        index_name: str = NIFTY50_INDEX_NAME,
    ) -> list[tuple[date, Optional[date]]]:
        """All membership legs for a symbol (half-open [start, end) per leg).
        Returns [] for an unknown symbol rather than raising — an instrument
        that was never in the index simply has no eligible bars."""
        self._ensure_loaded()
        index_key = self._resolve_index_name(index_name)
        sym = self._resolve_symbol(symbol)
        return sorted(self._legs_by_symbol.get((index_key, sym), []))

    def is_member(
        self,
        symbol: str,
        asof,
        index_name: str = NIFTY50_INDEX_NAME,
    ) -> bool:
        """True when the symbol is a member on ``asof``. Raises when ``asof``
        precedes the ledger's coverage start (1914-…, i.e. it would be a
        made-up answer)."""
        self._ensure_loaded()
        day = self._as_date(asof)
        self._guard_coverage(day)
        for start, end in self.membership_intervals(symbol, index_name):
            if start <= day and (end is None or day < end):
                return True
        return False

    def members(
        self,
        asof,
        index_name: str = NIFTY50_INDEX_NAME,
    ) -> list[str]:
        """All symbols that are members on ``asof``, sorted deterministically.
        Raises when ``asof`` precedes coverage start (no silent current-list
        substitution — the 2014-01-01 floor is the honest lower bound)."""
        self._ensure_loaded()
        day = self._as_date(asof)
        self._guard_coverage(day)
        index_key = self._resolve_index_name(index_name)
        found: list[str] = []
        for (idx, symbol), legs in self._legs_by_symbol.items():
            if idx != index_key:
                continue
            if any(
                start <= day and (end is None or day < end)
                for start, end in legs
            ):
                found.append(symbol)
        return sorted(found)

    @property
    def coverage_start(self) -> date:
        """Earliest valid_from across the ledger (the PIT lower bound)."""
        self._ensure_loaded()
        if self._coverage_start is None:
            raise ValueError("[pit_universe] ledger is empty — no coverage.")
        return self._coverage_start

    def _guard_coverage(self, asof: date) -> None:

        if asof < self.coverage_start:
            raise ValueError(
                f"[pit_universe] membership as-of {asof} predates ledger coverage "
                f"(starts {self.coverage_start}). Refusing to substitute the current "
                "membership list — that is exactly the survivorship bias this ledger exists to remove."
            )


def mask_signals_by_membership(
    df,
    signals,
    legs: list[tuple[date, Optional[date]]],
):
    """Keep only signals whose ENTRY bar (index+1 — the same next-bar-open
    convention as the walk-forward interval masking) falls inside a membership
    leg. Half-open: ``valid_to`` is exclusive (the demerger/exit day is not a
    trading day for that constituent). A symbol with no legs yields no signals
    — it must not trade bars it was never a member of."""
    if not legs:
        return []

    masked = []

    for signal in signals:
        entry_index = signal.index + 1
        if entry_index >= len(df):
            continue
        entry_ts = df.index[entry_index]
        entry_date = (
            entry_ts.date()
            if hasattr(entry_ts, "date")
            else entry_ts
        )
        if any(
            start <= entry_date and (end is None or entry_date < end)
            for start, end in legs
        ):
            masked.append(signal)

    return masked
"""Corporate-action factor extraction for backward price adjustment.

Phase 2 of Decision 6: the adjustment ENGINE for raw (Angel-style) daily
bars. Splits and bonus issues change the share count and must be corrected
multiplicatively; dividends must be corrected by subtracting the per-share
amount from every price that preceded the ex-date. This module turns the
free-text corporate-action records (as published by NSE/BSE, e.g. via the
`india-corp-actions` package) into strict, typed factors — and fails
closed whenever a price-altering record cannot be parsed deterministically.

Supply-chain rule (docs §9 / audit shortlist): the underlying package is
"unofficial-fragile -> WRAP-at-need, never runtime-critical-path". The client
is therefore imported lazily inside the fetch method, never at module
import time. The kernel stays importable without the package installed.

Conventions
-----------
- share_multiplier: NEW shares per OLD share. A 1:5 face-value split
  (Rs 10 -> Rs 2) yields 5; a 1:1 bonus yields 2.
- dividend_per_share: rupee amount paid per share on the pre-ex-date share
  count. A percentage dividend is converted only when the recorded face
  value is present; otherwise the record is unparseable -> raise.
- ex_date: the NSE ex-date (first trading day WITHOUT the entitlement).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable

from mjonai.core.numeric import safe_float


class CorporateActionError(Exception):
    """Base class for corporate-action handling failures."""


class CorporateActionSourceError(CorporateActionError):
    """The external corporate-action source is unreachable or unavailable
    (package not installed, network or exchange endpoint failure)."""


class CorporateActionParseError(CorporateActionError):
    """A price-altering corporate-action record could not be parsed into a
    deterministic factor. Fail closed — never guess an adjustment."""


@dataclass(slots=True)
class CorporateActionFactor:

    ex_date: date

    action_type: str

    share_multiplier: float = 1.0

    dividend_per_share: float | None = None


_ADJUSTABLE_TYPES = frozenset({"split", "bonus", "dividend"})


def _normalize_date(value) -> date:
    if value is None:
        raise CorporateActionParseError(
            "corporate action has no ex_date — cannot place the factor"
        )
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise CorporateActionParseError(
        f"unrecognised ex_date format: {text!r}"
    )


def _parse_amount(text: str) -> float | None:
    cleaned = text.replace(",", "")
    return safe_float(cleaned, default=None)


def parse_details(
    action_type: str,
    details: str,
    ex_date,
    face_value=None,
) -> CorporateActionFactor:
    """Strictly parse one free-text record into a deterministic factor.

    Raises CorporateActionParseError for any price-altering action whose
    numeric content cannot be derived. Non-price action types (rights, agm,
    buyback, merger, ...) are not adjustment factors and never reach this
    function (factors_from_records filters them out).
    """
    import re

    normalized = action_type.strip().lower()
    target = _normalize_date(ex_date)

    if normalized == "split":
        from_to = re.search(
            r"from\s*rs\.?\s*([\d,]+(?:\.\d+)?).*?to\s*rs\.?\s*([\d,]+(?:\.\d+)?)",
            details,
            re.IGNORECASE,
        )
        if not from_to:
            raise CorporateActionParseError(
                f"split without a deterministic face-value ratio: {details!r}"
            )
        old_fv = _parse_amount(from_to.group(1))
        new_fv = _parse_amount(from_to.group(2))
        if old_fv is None or new_fv is None or old_fv <= 0 or new_fv <= 0:
            raise CorporateActionParseError(
                f"split face values out of range: {details!r}"
            )
        if old_fv <= new_fv:
            raise CorporateActionParseError(
                f"split raises face value — not a split: {details!r}"
            )
        return CorporateActionFactor(
            ex_date=target,
            action_type="split",
            share_multiplier=safe_float(old_fv / new_fv),
        )

    if normalized == "bonus":
        shares_for_every = re.search(
            r"(\d+(?:\.\d+)?)\s*(?:equity\s+)?share[s]?\s+for\s+every\s+"
            r"(\d+(?:\.\d+)?)\s*(?:equity\s+)?share[s]?",
            details,
            re.IGNORECASE,
        )
        ratio = re.search(
            r"ratio.{0,8}?(\d+(?:\.\d+)?)\s*:\s*(\d+(?:\.\d+)?)",
            details,
            re.IGNORECASE,
        )
        if shares_for_every:
            given = _parse_amount(shares_for_every.group(1))
            held = _parse_amount(shares_for_every.group(2))
        elif ratio:
            given = _parse_amount(ratio.group(1))
            held = _parse_amount(ratio.group(2))
        else:
            given = None
            held = None
        if given is None or held is None or given <= 0 or held <= 0:
            raise CorporateActionParseError(
                f"bonus without a deterministic ratio: {details!r}"
            )
        multiplier = 1.0 + safe_float(given / held)
        return CorporateActionFactor(
            ex_date=target,
            action_type="bonus",
            share_multiplier=safe_float(multiplier),
        )

    if normalized == "dividend":
        rupee_match = re.search(
            r"rs\.?\s*[\u20b9]?\s*([\d,]+(?:\.\d+)?)",
            details,
            re.IGNORECASE,
        )
        if rupee_match:
            amount = _parse_amount(rupee_match.group(1))
            if amount is not None and amount > 0:
                return CorporateActionFactor(
                    ex_date=target,
                    action_type="dividend",
                    dividend_per_share=amount,
                )
        pct_match = re.search(r"(\d+(?:\.\d+)?)\s*%", details, re.IGNORECASE)
        if pct_match:
            fv = safe_float(face_value, default=None) if face_value is not None else None
            pct = _parse_amount(pct_match.group(1))
            if fv is not None and fv > 0 and pct is not None and pct > 0:
                return CorporateActionFactor(
                    ex_date=target,
                    action_type="dividend",
                    dividend_per_share=safe_float(pct / 100.0 * fv),
                )
        raise CorporateActionParseError(
            "dividend with no parseable per-share amount "
            f"(Rs amount or % + face value): {details!r}"
        )

    raise CorporateActionParseError(
        f"unsupported price-altering action type: {action_type!r}"
    )


def factors_from_records(
    records: Iterable,
) -> tuple[list[CorporateActionFactor], list[str]]:
    """Convert a batch of corporate-action records into sorted factors.

    Accepts any objects exposing `action_type`, `details`, `ex_date` and
    optional `face_value`. Non-adjustable records (rights, agm, buyback,
    mergers, ...) are skipped, not errored — they do not change the share
    count or the per-share price. Any price-altering record that cannot be
    parsed raises (fail closed), since an unadjusted split would corrupt the
    entire absolute-price series downstream.

    Returns (factors, skipped) with factors sorted by ex_date ascending.
    """
    factors: list[CorporateActionFactor] = []
    skipped: list[str] = []
    for record in records:
        action_type = str(getattr(record, "action_type", "") or "").strip().lower()
        if action_type not in _ADJUSTABLE_TYPES:
            skipped.append(action_type or "unknown")
            continue
        factor = parse_details(
            action_type=action_type,
            details=str(getattr(record, "details", "") or ""),
            ex_date=getattr(record, "ex_date", None),
            face_value=getattr(record, "face_value", None),
        )
        factors.append(factor)
    return sorted(factors, key=lambda f: f.ex_date), skipped


class CorporateActionsClient:
    """Lazy wrapper around the `india-corp-actions` source.

    The third-party package is imported lazily inside _get_client (never at
    module import time) and the fetch path is never on the runtime-critical
    path — consistent with the docs §9 supply-chain watch.
    """

    def __init__(self) -> None:
        self._client = None

    def _get_client(self):
        if self._client is not None:
            return self._client
        try:
            from india_corp_actions import IndiaCorpActions
        except ImportError as exc:  # pragma: no cover - env-dependent
            raise CorporateActionSourceError(
                "india-corp-actions is not installed; cannot fetch "
                "corporate-action factors"
            ) from exc
        self._client = IndiaCorpActions()
        return self._client

    def fetch_factors(
        self,
        symbol: str,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> list[CorporateActionFactor]:
        """Fetch and parse corporate actions for one NSE symbol.

        from_date/to_date are ISO strings (YYYY-MM-DD). Raises
        CorporateActionSourceError on network/source failure and
        CorporateActionParseError on an unparseable price-altering record.
        """
        client = self._get_client()
        try:
            records = client.get_actions(
                symbol=symbol,
                from_date=from_date,
                to_date=to_date,
                source="NSE",
            )
        except CorporateActionError:
            raise
        except Exception as exc:
            raise CorporateActionSourceError(
                f"failed to fetch corporate actions for {symbol}: {exc}"
            ) from exc
        factors, _skipped = factors_from_records(records)
        return factors
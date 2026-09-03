"""Optional bearer-token gate for the interactive application API."""

from __future__ import annotations

import os
import secrets
from typing import Optional

from fastapi import Header, HTTPException, Query, status


def required_token() -> Optional[str]:
    return os.getenv("MJONAI_APP_TOKEN") or None


def verify_api_token(
    authorization: Optional[str] = Header(default=None),
    token: Optional[str] = Query(default=None),
) -> None:
    """
    FastAPI dependency. No-op unless MJONAI_APP_TOKEN is configured; then a
    matching credential is mandatory — Bearer header (scripts) or ?token=
    query (browser PWA, which cannot set headers on fetch). Constant-time.
    """
    expected = required_token()
    if not expected:
        return
    supplied = None
    scheme, _, credential = (authorization or "").partition(" ")
    if scheme.lower() == "bearer" and credential:
        supplied = credential
    elif token:
        supplied = token
    if not supplied:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing token",
        )
    if not secrets.compare_digest(supplied, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

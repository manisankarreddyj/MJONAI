"""Optional bearer-token gate for the interactive application API."""

from __future__ import annotations

import os
import secrets
from typing import Optional

from fastapi import Header, HTTPException, Query, status


def required_token() -> Optional[str]:
    return os.getenv("MJONAI_APP_TOKEN") or None


def _remote_exposure_configured() -> bool:
    """True when the app is deliberately bound beyond loopback (MJONAI_APP_HOST
    set to a non-loopback interface). Mirrors run_app.py's launch guard, but is
    enforced here at request time too, so direct uvicorn.docker invocations
    cannot bypass it."""
    host = os.getenv("MJONAI_APP_HOST", "127.0.0.1")
    return bool(host) and host.strip() != "" and host.strip() != "127.0.0.1"


def verify_api_token(
    authorization: Optional[str] = Header(default=None),
    token: Optional[str] = Query(default=None),
) -> None:
    """
    FastAPI dependency. No-op unless MJONAI_APP_TOKEN is configured; then a
    matching credential is mandatory — Bearer header (scripts) or ?token=
    query (browser PWA, which cannot set headers on fetch). Constant-time.

    Fail-closed (2026-09-17): when the app is exposed beyond loopback, a
    missing token is a MISCONFIGURATION (the API would otherwise be open to
    anyone who can reach the port) — the dependency raises 503 instead of
    silently serving. Local loopback with no token keeps the historical
    no-op behavior.
    """
    expected = required_token()
    if not expected:
        if _remote_exposure_configured():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Server misconfigured: MJONAI_APP_HOST enables remote access "
                       "but MJONAI_APP_TOKEN is not configured - API refused (fail-closed).",
            )
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

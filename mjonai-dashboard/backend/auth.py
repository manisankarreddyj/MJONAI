"""
ArthAI Dashboard - Authentication
Simple API key verification

FAIL CLOSED: the API key comes from the ARTHAI_API_KEY environment
variable with NO default. If it is not set, every authenticated
request is rejected and WebSocket auth always fails - there is no
fallback key anywhere in this file.
"""

import hmac
import os
import logging
from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

logger = logging.getLogger(__name__)

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

# Read once at import. No default value on purpose.
_API_KEY = os.getenv("ARTHAI_API_KEY")

# Module-level flag: is a server-side key configured at all?
_key_configured = bool(_API_KEY)

if not _key_configured:
    logger.warning("ARTHAI_API_KEY not set - all API access denied")


def get_api_key() -> str:
    """Get the expected API key from environment (empty string if unset)."""
    return _API_KEY or ""


def _keys_match(provided: str, expected: str) -> bool:
    """Constant-time comparison; never raises on odd header values."""
    try:
        return hmac.compare_digest(str(provided), str(expected))
    except TypeError:
        # Non-ASCII input cannot match any valid key
        return False


def verify_api_key(api_key: str = Security(API_KEY_HEADER)) -> str:
    """
    Verify API key from request header
    Header: X-API-Key: your-key-here

    Fails closed (HTTP 503) when ARTHAI_API_KEY is not configured.
    """
    if not _key_configured:
        raise HTTPException(
            status_code=503,
            detail="Server auth not configured (ARTHAI_API_KEY missing) - access denied",
        )

    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="API key missing. Add header: X-API-Key"
        )

    if not _keys_match(api_key, _API_KEY):
        raise HTTPException(
            status_code=403,
            detail="Invalid API key"
        )

    return api_key


def verify_ws_token(token: str) -> bool:
    """
    Verify WebSocket auth token
    Same as API key for simplicity

    Returns False always when ARTHAI_API_KEY is not configured.
    """
    if not token or not _key_configured:
        return False
    return _keys_match(token, _API_KEY)

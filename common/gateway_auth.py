"""Authentication helper for requests from the Nexus server gateway."""

from __future__ import annotations

import hmac
import os


def validate_gateway_key(supplied_key: str | None) -> bool:
    """Validate the configured gateway API key using constant-time comparison."""
    expected_key = os.getenv("NEXUS_GATEWAY_API_KEY", "").strip()
    if not expected_key or not supplied_key:
        return False
    return hmac.compare_digest(expected_key, supplied_key.strip())

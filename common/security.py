"""Cryptographic helpers for service-to-service request authentication."""

from __future__ import annotations

import hashlib
import hmac
import time
from typing import Final

INTERNAL_TIMESTAMP_HEADER: Final[str] = "X-Internal-Timestamp"
INTERNAL_SIGNATURE_HEADER: Final[str] = "X-Internal-Signature"


def sign_internal_request(secret: str, payload: bytes, timestamp: int | None = None) -> tuple[str, str]:
    """Return timestamp and HMAC-SHA256 signature for an exact request body."""
    if not secret:
        raise ValueError("INTERNAL_SERVICE_SECRET is required")

    timestamp_value = int(time.time()) if timestamp is None else int(timestamp)
    signed_payload = str(timestamp_value).encode("ascii") + b"." + payload
    signature = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
    return str(timestamp_value), signature


def verify_internal_request(
    secret: str,
    payload: bytes,
    timestamp_header: str | None,
    signature_header: str | None,
    *,
    tolerance_seconds: int = 300,
    now: int | None = None,
) -> bool:
    """Verify signature and reject stale or future-dated requests."""
    if not secret or not timestamp_header or not signature_header:
        return False

    try:
        timestamp_value = int(timestamp_header)
    except (TypeError, ValueError):
        return False

    current_time = int(time.time()) if now is None else int(now)
    if abs(current_time - timestamp_value) > tolerance_seconds:
        return False

    _, expected_signature = sign_internal_request(secret, payload, timestamp_value)
    return hmac.compare_digest(expected_signature, signature_header.strip())

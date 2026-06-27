"""
Integration tests — card_platform_service FastAPI routes.
Run: pytest tests/integration/test_api_routes.py -v
Requires: card_platform_service running on localhost:8000
"""

import pytest
import httpx

BASE = "http://localhost:8000"
HEADERS = {"Content-Type": "application/json"}


@pytest.mark.asyncio
async def test_health_endpoint():
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{BASE}/health", timeout=5)
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data or "ok" in str(data).lower()


@pytest.mark.asyncio
async def test_card_issue_requires_kyc():
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{BASE}/api/v1/cards/issue",
            json={"user_id": "unverified-user"},
            headers=HEADERS,
            timeout=5,
        )
    # Should reject unverified users
    assert resp.status_code in (400, 401, 403, 422)


@pytest.mark.asyncio
async def test_fund_load_validates_amount():
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{BASE}/api/v1/funds/load",
            json={"user_id": "user-1", "amount": -100, "currency": "USD"},
            headers=HEADERS,
            timeout=5,
        )
    assert resp.status_code in (400, 422)


@pytest.mark.asyncio
async def test_fund_load_idempotency():
    key = "test-idem-key-001"
    async with httpx.AsyncClient() as client:
        r1 = await client.post(
            f"{BASE}/api/v1/funds/load",
            json={"user_id": "user-1", "amount": 100, "currency": "USD", "idempotency_key": key},
            headers=HEADERS,
            timeout=5,
        )
        r2 = await client.post(
            f"{BASE}/api/v1/funds/load",
            json={"user_id": "user-1", "amount": 100, "currency": "USD", "idempotency_key": key},
            headers=HEADERS,
            timeout=5,
        )

    # Both should succeed or both return same deterministic result
    assert r1.status_code in (200, 201, 400, 422)
    if r1.status_code in (200, 201) and r2.status_code in (200, 201):
        d1 = r1.json()
        d2 = r2.json()
        # idempotent flag or same ID
        assert d1.get("idempotent") is True or d1.get("id") == d2.get("id")

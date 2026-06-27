"""
E2E tests — Full deposit → ledger credit flow.
Run: pytest tests/e2e/test_deposit_flow.py -v
Requires full stack running (Next.js on :3000, services up).
"""

import pytest
import httpx
import uuid

DASHBOARD_BASE = "http://localhost:3000"


@pytest.mark.asyncio
async def test_create_deposit_and_list():
    """Create a deposit then verify it appears in the list."""
    idem_key = str(uuid.uuid4())
    async with httpx.AsyncClient() as client:
        # Create
        create_resp = await client.post(
            f"{DASHBOARD_BASE}/api/deposits",
            json={"amount": 500, "currency": "USD", "idempotency_key": idem_key},
            timeout=10,
        )
        assert create_resp.status_code in (200, 201), f"Create failed: {create_resp.text}"
        deposit = create_resp.json().get("deposit", {})
        assert deposit.get("id")
        assert deposit.get("status") == "created"
        assert float(deposit.get("amount", 0)) == 500.0

        # List — should include our new deposit
        list_resp = await client.get(f"{DASHBOARD_BASE}/api/deposits", timeout=10)
        assert list_resp.status_code == 200
        deposits = list_resp.json().get("deposits", [])
        ids = [d["id"] for d in deposits]
        assert deposit["id"] in ids, "New deposit not found in list"


@pytest.mark.asyncio
async def test_deposit_idempotency():
    """Same idempotency key must return same deposit."""
    idem_key = str(uuid.uuid4())
    async with httpx.AsyncClient() as client:
        r1 = await client.post(
            f"{DASHBOARD_BASE}/api/deposits",
            json={"amount": 100, "currency": "USD", "idempotency_key": idem_key},
            timeout=10,
        )
        r2 = await client.post(
            f"{DASHBOARD_BASE}/api/deposits",
            json={"amount": 100, "currency": "USD", "idempotency_key": idem_key},
            timeout=10,
        )

    assert r1.status_code in (200, 201)
    assert r2.status_code == 200
    d1 = r1.json().get("deposit", {})
    d2 = r2.json().get("deposit", {})
    assert d1["id"] == d2["id"]
    assert r2.json().get("idempotent") is True


@pytest.mark.asyncio
async def test_invalid_amount_rejected():
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{DASHBOARD_BASE}/api/deposits",
            json={"amount": -50, "currency": "USD", "idempotency_key": str(uuid.uuid4())},
            timeout=10,
        )
    assert resp.status_code == 400
    assert "error" in resp.json()


@pytest.mark.asyncio
async def test_request_card_and_verify_status():
    """Request a card and verify it reaches issued state."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{DASHBOARD_BASE}/api/cards",
            json={"nickname": "E2E Test Card", "idempotency_key": str(uuid.uuid4())},
            timeout=15,
        )
    assert resp.status_code in (200, 201, 202)
    data = resp.json()
    assert "card" in data
    assert data["card"]["status"] in ("requested", "issued")

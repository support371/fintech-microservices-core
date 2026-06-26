"""Nexus fiat-to-BTC converter API.

All money movement defaults to deterministic sandbox behavior. Internal calls
must be signed, webhook payloads must be HMAC verified, and every transaction
is protected by an idempotency claim.
"""

from __future__ import annotations

import json
import logging
import os
import time
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, Field, ValidationError

from common.security import verify_internal_request
from .idempotency import IdempotencyStore
from .logic import ConversionLogic

logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp":"%(asctime)s","service":"converter","level":"%(levelname)s","message":"%(message)s"}',
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Nexus Fiat-to-BTC Converter Service",
    description="Authenticated, idempotent, sandbox-first conversion service.",
    version="2.0.0",
)
converter_logic = ConversionLogic()
idempotency_store = IdempotencyStore()


class InternalFundTransferRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=128)
    fiat_amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    fiat_currency: str = Field(min_length=3, max_length=3)
    trace_id: UUID


class FiatReceivedWebhook(BaseModel):
    transaction_id: str = Field(min_length=1, max_length=200)
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    currency: str = Field(min_length=3, max_length=3)
    user_id: str = Field(min_length=1, max_length=128)


def _process_transaction(
    transaction_key: str,
    *,
    amount: Decimal,
    currency: str,
    user_id: str,
) -> dict[str, Any]:
    claimed = idempotency_store.begin(transaction_key)
    if not claimed:
        completed = idempotency_store.get_completed_response(transaction_key)
        if completed is not None:
            return {"status": "success", "idempotent_replay": True, "data": completed}
        raise HTTPException(status_code=409, detail="Transaction is already processing")

    try:
        result = converter_logic.execute_conversion_and_payout(
            fiat_amount=amount,
            fiat_currency=currency,
            user_id=user_id,
        )
        idempotency_store.complete(transaction_key, result)
        return {"status": "success", "idempotent_replay": False, "data": result}
    except ValueError as exc:
        idempotency_store.release_failed(transaction_key)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        idempotency_store.release_failed(transaction_key)
        logger.error("Conversion configuration blocked transaction %s: %s", transaction_key, exc)
        raise HTTPException(status_code=503, detail="Conversion service is not configured for this operation") from exc
    except Exception as exc:
        idempotency_store.release_failed(transaction_key)
        logger.exception("Conversion failed for transaction %s", transaction_key)
        raise HTTPException(status_code=500, detail="Conversion processing failed") from exc


@app.get("/health")
def health_check() -> dict[str, Any]:
    return {
        "status": "healthy",
        "service": "converter-service",
        "payment_mode": converter_logic.payments_mode,
        "timestamp": time.time(),
    }


@app.get("/ready")
def readiness_check() -> dict[str, Any]:
    missing: list[str] = []
    if not os.getenv("INTERNAL_SERVICE_SECRET", "").strip():
        missing.append("INTERNAL_SERVICE_SECRET")
    if not converter_logic.webhook_secret:
        missing.append("STRIGA_WEBHOOK_SECRET")
    if os.getenv("APP_ENV", "development").lower() == "production" and not os.getenv("DATABASE_URL", "").strip():
        missing.append("DATABASE_URL")

    if missing:
        raise HTTPException(
            status_code=503,
            detail={"status": "not_ready", "missing_configuration": missing},
        )
    return {"status": "ready", "payment_mode": converter_logic.payments_mode}


@app.post("/internal/transfer_funds")
async def internal_transfer_funds(
    request: Request,
    x_internal_timestamp: str | None = Header(default=None, alias="X-Internal-Timestamp"),
    x_internal_signature: str | None = Header(default=None, alias="X-Internal-Signature"),
) -> dict[str, Any]:
    payload_raw = await request.body()
    secret = os.getenv("INTERNAL_SERVICE_SECRET", "").strip()
    if not verify_internal_request(
        secret,
        payload_raw,
        x_internal_timestamp,
        x_internal_signature,
    ):
        raise HTTPException(status_code=401, detail="Invalid internal request signature")

    try:
        payload = InternalFundTransferRequest(**json.loads(payload_raw))
    except (json.JSONDecodeError, UnicodeDecodeError, ValidationError) as exc:
        raise HTTPException(status_code=400, detail="Invalid transfer request") from exc

    trace_id = str(payload.trace_id)
    logger.info("Authenticated internal transfer received trace_id=%s", trace_id)
    return _process_transaction(
        f"internal:{trace_id}",
        amount=payload.fiat_amount,
        currency=payload.fiat_currency,
        user_id=payload.user_id,
    )


@app.post("/webhook/fiat_received")
async def fiat_received_webhook(request: Request) -> dict[str, Any]:
    content_type = request.headers.get("content-type", "")
    if "application/json" not in content_type.lower():
        raise HTTPException(status_code=415, detail="Content-Type must be application/json")

    payload_raw = await request.body()
    signature = (
        request.headers.get("x-striga-signature")
        or request.headers.get("x-signature")
        or ""
    )
    if not converter_logic.validate_webhook_signature(payload_raw, signature):
        logger.warning("Rejected webhook with invalid signature")
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    try:
        payload = FiatReceivedWebhook(**json.loads(payload_raw))
    except (json.JSONDecodeError, UnicodeDecodeError, ValidationError) as exc:
        raise HTTPException(status_code=400, detail="Invalid webhook payload") from exc

    logger.info("Verified fiat webhook transaction_id=%s", payload.transaction_id)
    return _process_transaction(
        f"webhook:{payload.transaction_id}",
        amount=payload.amount,
        currency=payload.currency,
        user_id=payload.user_id,
    )

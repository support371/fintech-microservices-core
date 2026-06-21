"""Nexus card platform API with KYC-gated sandbox operations."""

from __future__ import annotations

import logging
import time
from decimal import Decimal
from typing import Any

import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .clients import CardPlatformLogic

logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp":"%(asctime)s","service":"card-platform","level":"%(levelname)s","message":"%(message)s"}',
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Nexus Digital Debit Card Platform API",
    description="KYC-gated, sandbox-first card issuance and funding API.",
    version="2.0.0",
)
card_logic = CardPlatformLogic()


class CardIssuanceRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=128)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)


class FundTransferRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=128)
    fiat_amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    fiat_currency: str = Field(min_length=3, max_length=3)


def _approved_kyc_tier(user_id: str) -> int:
    try:
        kyc_tier = card_logic.get_user_kyc_tier(user_id)
    except Exception as exc:
        logger.exception("KYC lookup failed")
        raise HTTPException(status_code=503, detail="KYC service is unavailable") from exc

    if kyc_tier is None:
        raise HTTPException(status_code=404, detail="User was not found")
    if not card_logic.is_kyc_tier_approved(kyc_tier):
        raise HTTPException(
            status_code=403,
            detail=f"KYC Tier {card_logic.minimum_kyc_tier} or higher is required",
        )
    return kyc_tier


@app.get("/health")
def health_check() -> dict[str, Any]:
    return {
        "status": "healthy",
        "service": "card-platform-service",
        "card_mode": card_logic.card_mode,
        "timestamp": time.time(),
    }


@app.get("/ready")
def readiness_check() -> dict[str, Any]:
    missing: list[str] = []
    if not card_logic.converter_internal_url:
        missing.append("CONVERTER_INTERNAL_URL")
    if not card_logic.internal_service_secret:
        missing.append("INTERNAL_SERVICE_SECRET")
    if missing:
        raise HTTPException(
            status_code=503,
            detail={"status": "not_ready", "missing_configuration": missing},
        )
    if not card_logic.check_database():
        raise HTTPException(status_code=503, detail="Database is unavailable")
    return {"status": "ready", "card_mode": card_logic.card_mode}


@app.post("/api/v1/cards/issue")
def issue_card_endpoint(request: CardIssuanceRequest) -> dict[str, Any]:
    kyc_tier = _approved_kyc_tier(request.user_id)
    try:
        result = card_logic.issue_new_card(request.user_id, kyc_tier)
        return {"status": "success", "data": result}
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail="Card issuance is not permitted") from exc
    except RuntimeError as exc:
        logger.error("Card issuance blocked by configuration: %s", exc)
        raise HTTPException(status_code=503, detail="Card issuance is not configured") from exc
    except Exception as exc:
        logger.exception("Card issuance failed")
        raise HTTPException(status_code=500, detail="Card issuance failed") from exc


@app.post("/api/v1/funds/load")
def load_card_funds(request: FundTransferRequest) -> dict[str, Any]:
    _approved_kyc_tier(request.user_id)
    try:
        result = card_logic.transfer_fiat_to_crypto(
            user_id=request.user_id,
            fiat_amount=request.fiat_amount,
            fiat_currency=request.fiat_currency,
        )
        return {"status": "conversion_initiated", "details": result}
    except requests.Timeout as exc:
        raise HTTPException(status_code=504, detail="Converter service timed out") from exc
    except requests.RequestException as exc:
        logger.exception("Converter service request failed")
        raise HTTPException(status_code=503, detail="Converter service is unavailable") from exc
    except RuntimeError as exc:
        logger.error("Fund loading blocked by configuration: %s", exc)
        raise HTTPException(status_code=503, detail="Fund loading is not configured") from exc
    except Exception as exc:
        logger.exception("Fund loading failed")
        raise HTTPException(status_code=500, detail="Fund loading failed") from exc

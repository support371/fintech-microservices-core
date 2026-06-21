"""Database and provider adapters for the Nexus card platform service."""

from __future__ import annotations

import json
import logging
import os
import uuid
from decimal import Decimal
from typing import Any

import psycopg2
import requests
from dotenv import load_dotenv
from psycopg2 import sql

from common.security import (
    INTERNAL_SIGNATURE_HEADER,
    INTERNAL_TIMESTAMP_HEADER,
    sign_internal_request,
)

load_dotenv()
logger = logging.getLogger(__name__)


class CardPlatformLogic:
    """KYC policy, sandbox card issuance, and authenticated converter calls."""

    def __init__(self) -> None:
        self.database_url = os.getenv("DATABASE_URL", "").strip()
        self.converter_internal_url = os.getenv("CONVERTER_INTERNAL_URL", "").rstrip("/")
        self.internal_service_secret = os.getenv("INTERNAL_SERVICE_SECRET", "").strip()
        self.card_mode = os.getenv("CARD_ISSUANCE_MODE", "sandbox").strip().lower()
        self.allow_live_cards = os.getenv("ALLOW_LIVE_CARD_ISSUANCE", "false").strip().lower() == "true"
        self.minimum_kyc_tier = int(os.getenv("KYC_MINIMUM_TIER", "3"))
        self.request_timeout = float(os.getenv("INTERNAL_REQUEST_TIMEOUT_SECONDS", "8"))

    def _connect(self):
        if self.database_url:
            return psycopg2.connect(self.database_url)

        required = {
            "host": os.getenv("DB_HOST", "").strip(),
            "dbname": os.getenv("DB_NAME", "").strip(),
            "user": os.getenv("DB_USER", "").strip(),
            "password": os.getenv("DB_PASSWORD", "").strip(),
        }
        if not all(required.values()):
            raise RuntimeError("Database configuration is incomplete")

        return psycopg2.connect(
            host=required["host"],
            port=os.getenv("DB_PORT", "5432"),
            dbname=required["dbname"],
            user=required["user"],
            password=required["password"],
            sslmode=os.getenv("DB_SSLMODE", "require"),
        )

    def check_database(self) -> bool:
        try:
            connection = self._connect()
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    return cursor.fetchone() == (1,)
            finally:
                connection.close()
        except Exception:
            logger.exception("Database readiness check failed")
            return False

    def get_user_kyc_tier(self, user_id: str) -> int | None:
        connection = self._connect()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    sql.SQL("SELECT kyc_tier FROM users WHERE user_id = %s"),
                    (user_id,),
                )
                row = cursor.fetchone()
                return int(row[0]) if row else None
        finally:
            connection.close()

    def is_kyc_tier_approved(self, kyc_tier: int | None) -> bool:
        return kyc_tier is not None and kyc_tier >= self.minimum_kyc_tier

    def issue_new_card(self, user_id: str, kyc_tier: int) -> dict[str, str]:
        if not self.is_kyc_tier_approved(kyc_tier):
            raise PermissionError("KYC tier is not approved for card issuance")

        if self.card_mode != "sandbox":
            if not self.allow_live_cards:
                raise RuntimeError("Live card issuance is disabled")
            raise RuntimeError(
                "Live card provider adapter is not configured; keep CARD_ISSUANCE_MODE=sandbox"
            )

        return {
            "status": "simulated",
            "card_mode": "sandbox",
            "card_id": f"sandbox-card-{uuid.uuid4()}",
            "user_id": user_id,
        }

    def transfer_fiat_to_crypto(
        self,
        *,
        user_id: str,
        fiat_amount: Decimal,
        fiat_currency: str,
    ) -> dict[str, Any]:
        if not self.converter_internal_url:
            raise RuntimeError("CONVERTER_INTERNAL_URL is not configured")
        if not self.internal_service_secret:
            raise RuntimeError("INTERNAL_SERVICE_SECRET is not configured")

        trace_id = str(uuid.uuid4())
        payload = {
            "user_id": user_id,
            "fiat_amount": format(fiat_amount, "f"),
            "fiat_currency": fiat_currency.upper(),
            "trace_id": trace_id,
        }
        payload_raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        timestamp, signature = sign_internal_request(
            self.internal_service_secret,
            payload_raw,
        )

        response = requests.post(
            f"{self.converter_internal_url}/internal/transfer_funds",
            data=payload_raw,
            headers={
                "Content-Type": "application/json",
                INTERNAL_TIMESTAMP_HEADER: timestamp,
                INTERNAL_SIGNATURE_HEADER: signature,
                "X-Trace-Id": trace_id,
            },
            timeout=self.request_timeout,
        )
        response.raise_for_status()
        return response.json()

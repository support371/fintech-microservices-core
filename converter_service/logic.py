"""Core conversion policy and sandbox provider adapter.

Live money movement is deliberately fail-closed until a verified provider
contract, production credentials, and owner approval are configured.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_DOWN
from typing import Any

from dotenv import load_dotenv

load_dotenv()


class ConversionLogic:
    """Validate requests and execute fiat-to-BTC conversions in sandbox mode."""

    def __init__(self) -> None:
        self.webhook_secret = os.getenv("STRIGA_WEBHOOK_SECRET", "").strip()
        self.payments_mode = os.getenv("PAYMENTS_MODE", "sandbox").strip().lower()
        self.allow_live_payments = os.getenv("ALLOW_LIVE_PAYMENTS", "false").strip().lower() == "true"
        self.aml_limit = Decimal(os.getenv("AML_SINGLE_TRANSACTION_LIMIT", "10000"))
        self.supported_currencies = {
            item.strip().upper()
            for item in os.getenv("SUPPORTED_FIAT_CURRENCIES", "USD,EUR,GBP").split(",")
            if item.strip()
        }
        self.sandbox_rates = self._load_sandbox_rates()

    @staticmethod
    def _normalize_signature(signature_header: str) -> str:
        signature = signature_header.strip()
        if signature.startswith("sha256="):
            return signature.split("=", 1)[1]
        if "," in signature:
            parts = {
                item.split("=", 1)[0].strip(): item.split("=", 1)[1].strip()
                for item in signature.split(",")
                if "=" in item
            }
            return parts.get("v1", "")
        return signature

    def validate_webhook_signature(self, payload_raw: bytes, signature_header: str) -> bool:
        """Verify a generic HMAC-SHA256 webhook signature in constant time."""
        if not self.webhook_secret or not signature_header:
            return False
        expected = hmac.new(
            self.webhook_secret.encode("utf-8"), payload_raw, hashlib.sha256
        ).hexdigest()
        supplied = self._normalize_signature(signature_header)
        return bool(supplied) and hmac.compare_digest(expected, supplied)

    def _load_sandbox_rates(self) -> dict[str, Decimal]:
        default_rates = {"USD": "70000", "EUR": "76000", "GBP": "82000"}
        raw = os.getenv("SANDBOX_BTC_RATES_JSON", json.dumps(default_rates))
        try:
            parsed = json.loads(raw)
            rates = {str(key).upper(): Decimal(str(value)) for key, value in parsed.items()}
        except (json.JSONDecodeError, InvalidOperation, AttributeError, TypeError) as exc:
            raise RuntimeError("SANDBOX_BTC_RATES_JSON is invalid") from exc

        if not rates or any(rate <= 0 for rate in rates.values()):
            raise RuntimeError("Sandbox BTC rates must be positive")
        return rates

    def execute_conversion_and_payout(
        self, fiat_amount: Decimal | float | str, fiat_currency: str, user_id: str
    ) -> dict[str, Any]:
        """Execute a deterministic sandbox conversion or fail closed in live mode."""
        try:
            amount = Decimal(str(fiat_amount))
        except InvalidOperation as exc:
            raise ValueError("Invalid fiat amount") from exc

        if amount <= 0:
            raise ValueError("Transaction amount must be greater than zero")
        if amount > self.aml_limit:
            raise ValueError("Transaction amount exceeds the configured AML limit")

        currency = fiat_currency.strip().upper()
        if currency not in self.supported_currencies:
            raise ValueError("Unsupported fiat currency")

        if self.payments_mode != "sandbox":
            if not self.allow_live_payments:
                raise RuntimeError("Live payments are disabled")
            raise RuntimeError(
                "Live provider adapter is not configured; keep PAYMENTS_MODE=sandbox"
            )

        rate = self.sandbox_rates.get(currency)
        if rate is None:
            raise ValueError("No sandbox BTC rate configured for this currency")

        btc_amount = (amount / rate).quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)
        satoshis = int(btc_amount * Decimal("100000000"))

        return {
            "status": "simulated",
            "payment_mode": "sandbox",
            "provider_reference": f"sandbox-{uuid.uuid4()}",
            "user_id": user_id,
            "fiat_amount": format(amount, "f"),
            "fiat_currency": currency,
            "btc_amount_sent": format(btc_amount, "f"),
            "satoshis_sent": satoshis,
            "exchange_rate_used": format(rate, "f"),
            "success_time": datetime.now(timezone.utc).isoformat(),
        }

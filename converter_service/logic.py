import os
import hmac
import hashlib
import json
import time
import requests
from typing import Dict, Any
from datetime import datetime

# Load environment variables (Agent must ensure this runs in the building environment)
from dotenv import load_dotenv
load_dotenv()

# Configuration from .env
WEBHOOK_SECRET_RAW = os.environ.get("STRIGA_WEBHOOK_SECRET", "")
WEBHOOK_SECRET = WEBHOOK_SECRET_RAW.encode('utf-8') if WEBHOOK_SECRET_RAW else b""
API_KEY = os.environ.get("STRIGA_API_KEY")
API_BASE_URL = os.environ.get("STRIGA_API_BASE_URL")

class ConversionLogic:
  """Handles core security checks and the external conversion API call."""

  def __init__(self):
    # NOTE: In a real environment, this should connect to Redis or PostgreSQL
    # for a persistent idempotency check. We use a set for demonstration.
    self.processed_transactions = set()
    print("ConversionLogic initialized. Connects to Striga API.")

  # ----------------------------------------------------------------------
  # CRITICAL SECURITY
  # ----------------------------------------------------------------------
  def validate_webhook_signature(self, payload_raw: bytes, signature_header: str) -> bool:
    """[SECURITY] Verifies the HMAC-SHA256 signature against the payload."""

    # NOTE: Striga often uses a header format like 't=timestamp,v1=signature'
    # This implementation assumes the header is just the signature for simplicity.
    # AGENT MUST ADJUST based on Striga's exact specification.

    if not WEBHOOK_SECRET:
      return False

    signature_value = signature_header
    if "," in signature_header:
      parts = dict(
        item.split("=", 1)
        for item in signature_header.split(",")
        if "=" in item
      )
      signature_value = parts.get("v1", "")

    computed_signature = hmac.new(WEBHOOK_SECRET, payload_raw, hashlib.sha256).hexdigest()

    # hmac.compare_digest prevents timing attacks
    return hmac.compare_digest(computed_signature, signature_value)

  def is_already_processed(self, transaction_id: str) -> bool:
    """[IDEMPOTENCY] Prevents double-processing of the same webhook."""
    if transaction_id in self.processed_transactions:
      return True
    self.processed_transactions.add(transaction_id)
    return False

  # ----------------------------------------------------------------------
  # CORE CONVERSION FUNCTION
  # ----------------------------------------------------------------------
  def execute_conversion_and_payout(self, fiat_amount: float, fiat_currency: str, user_id: str) -> Dict[str, Any]:
    """
    [CORE LOGIC] Calls the external API to convert fiat to BTC and initiate payout.

    This is where the API call to Striga's conversion endpoint would happen.
    """

    print(f"Executing conversion for User {user_id}: {fiat_currency} {fiat_amount}")

    if fiat_amount <= 0:
      raise ValueError("Transaction amount must be greater than zero.")

    normalized_currency = fiat_currency.upper()
    supported_currencies = {"USD": 70000.0, "EUR": 76000.0, "GBP": 82000.0}
    if normalized_currency not in supported_currencies:
      raise ValueError(f"Unsupported fiat currency: {fiat_currency}")

    # --- MOCKING API CALL for safe testing ---
    # AGENT ACTION: Replace this block with actual requests.post(...) call.
    time.sleep(1) # Simulate network latency
    if fiat_amount > 10000:
      raise ValueError("Transaction amount exceeds mock limit.")

    exchange_rate = supported_currencies[normalized_currency]
    btc_amount = round(fiat_amount / exchange_rate, 8)

    return {
      "btc_amount_sent": btc_amount,
      "satoshis_sent": int(btc_amount * 100_000_000),
      "exchange_rate_used": exchange_rate,
      "fiat_currency": normalized_currency,
      "success_time": datetime.now().isoformat()
    }
    # --- END MOCKING ---

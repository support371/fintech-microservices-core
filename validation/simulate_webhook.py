import requests
import hmac
import hashlib
import json
import time
import os

# --- Configuration ---
# The URL of the deployed converter_service webhook endpoint
WEBHOOK_URL = os.environ.get("CONVERTER_STAGING_URL", "http://127.0.0.1:8000") + "/webhook/fiat_received"
# The secret used to sign the webhook payload
WEBHOOK_SECRET = os.environ.get("STRIGA_WEBHOOK_SECRET", "YOUR_HIGHLY_SECRET_WEBHOOK_KEY_HERE").encode('utf-8')

def generate_signature(payload_raw: bytes) -> str:
    """Generates the HMAC-SHA256 signature for the given payload."""
    return hmac.new(WEBHOOK_SECRET, payload_raw, hashlib.sha256).hexdigest()

def send_webhook_request(payload: dict):
    """Sends a webhook request to the converter_service with the given payload."""
    payload_raw = json.dumps(payload).encode('utf-8')
    signature = generate_signature(payload_raw)
    headers = {
        'Content-Type': 'application/json',
        'X-Signature': signature
    }

    print(f"Sending webhook to: {WEBHOOK_URL}")
    print(f"Payload: {payload}")
    print(f"Signature: {signature}")

    try:
        response = requests.post(WEBHOOK_URL, data=payload_raw, headers=headers, timeout=10)
        response.raise_for_status()
        print("Webhook sent successfully.")
        print("Response:", response.json())
    except requests.exceptions.RequestException as e:
        print(f"Error sending webhook: {e}")

if __name__ == "__main__":
    sample_payload = {
        "transaction_id": f"txn_{int(time.time())}",
        "amount": 100.50,
        "currency": "USD",
        "user_id": "user_12345"
    }
    send_webhook_request(sample_payload)

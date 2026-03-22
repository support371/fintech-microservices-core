from fastapi import FastAPI, Request, HTTPException, Header
import json
from .logic import ConversionLogic
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from pydantic import BaseModel

app = FastAPI(title="Fiat-to-BTC Converter Service", description="Project 1: Secure Webhook Handler.")
converter_logic = ConversionLogic()

class InternalFundTransferRequest(BaseModel):
    user_id: str
    fiat_amount: float
    fiat_currency: str
    trace_id: str

@app.post("/internal/transfer_funds")
async def internal_transfer_funds(request: InternalFundTransferRequest):
    """
    Internal endpoint to execute the conversion logic, called by the Card Platform Service.
    """
    trace_id = request.trace_id
    logger.info(f"Internal fund transfer received for trace_id: {trace_id}")

    # Use a combination of a prefix and trace_id for a unique, traceable transaction ID
    transaction_id = f"internal-tx-{trace_id}"

    # 2. Idempotency Check
    if converter_logic.is_already_processed(transaction_id):
        logger.warning(f"Transaction already processed (Idempotent success) for trace_id: {trace_id}")
        return {"status": "success", "message": "Transaction already processed (Idempotent success)"}

    # 3. Execute Conversion
    try:
        result = converter_logic.execute_conversion_and_payout(
            fiat_amount=request.fiat_amount,
            fiat_currency=request.fiat_currency,
            user_id=request.user_id
        )
        logger.info(f"[AUDIT LOG] Fiat-to-BTC Success: ID={transaction_id}, BTC Sent={result['btc_amount_sent']}, trace_id={trace_id}")
        return {"status": "success", "data": result}

    except Exception as e:
        logger.critical(f"[CRITICAL ERROR] Conversion failed for TX {transaction_id} (trace_id: {trace_id}): {e}")
        raise HTTPException(status_code=500, detail=f"Conversion processing failed: {e}")

@app.post("/webhook/fiat_received")
async def fiat_received_webhook(
  request: Request,
  # NOTE: Striga often uses X-Striga-Signature, adjust header name as needed.
  x_signature: str = Header(..., alias='X-Signature')
):
  """
  Receives webhook notification for fiat payment receipt, validates it, and executes conversion.
  """
  payload_raw = await request.body()
  try:
    payload = json.loads(payload_raw.decode('utf-8'))
  except json.JSONDecodeError:
    raise HTTPException(status_code=400, detail="Invalid JSON payload")

  # 1. Signature Validation [CRITICAL SECURITY]
  if not converter_logic.validate_webhook_signature(payload_raw, x_signature):
    logger.warning("Invalid webhook signature received.")
    raise HTTPException(status_code=403, detail="Invalid webhook signature")

  # Extract required fields (adjust keys based on Striga payload)
  transaction_id = payload.get("transaction_id")
  fiat_amount = payload.get("amount")
  fiat_currency = payload.get("currency")
  user_id = payload.get("user_id")

  if not all([transaction_id, fiat_amount, fiat_currency, user_id]):
    raise HTTPException(status_code=400, detail="Missing required transaction data")

  # 2. Idempotency Check
  if converter_logic.is_already_processed(transaction_id):
    logger.warning(f"Transaction {transaction_id} already processed (Idempotent success).")
    return {"status": "success", "message": "Transaction already processed (Idempotent success)"}

  # 3. Execute Conversion
  try:
    result = converter_logic.execute_conversion_and_payout(
      fiat_amount=fiat_amount,
      fiat_currency=fiat_currency,
      user_id=user_id
    )
    logger.info(f"[AUDIT LOG] Fiat-to-BTC Success: ID={transaction_id}, BTC Sent={result['btc_amount_sent']}")

    return {"status": "success", "data": result}

  except Exception as e:
    logger.critical(f"[CRITICAL ERROR] Conversion failed for TX {transaction_id}: {e}")
    raise HTTPException(status_code=500, detail=f"Conversion processing failed: {e}")

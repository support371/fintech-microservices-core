from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from .clients import CardPlatformLogic

app = FastAPI(title="Digital Debit Card Platform API", description="Project 2: Client-facing API for Card/KYC.")
card_logic = CardPlatformLogic()

class CardIssuanceRequest(BaseModel):
  user_id: str
  first_name: str
  last_name: str

class FundTransferRequest(BaseModel):
  user_id: str
  fiat_amount: float
  fiat_currency: str

@app.post("/api/v1/cards/issue")
def issue_card_endpoint(request: CardIssuanceRequest):
  """Client endpoint to request a new crypto debit card."""
  kyc_status = card_logic.get_user_kyc_status(request.user_id)

  if not card_logic.is_kyc_tier_approved(kyc_status):
    raise HTTPException(status_code=403, detail=f"KYC status is {kyc_status}. Requires Tier 3.")

  result = card_logic.issue_new_card(request.user_id, kyc_status)
  return {"status": "Card Issued", "card_id": result.get("card_id")}

@app.post("/api/v1/funds/load")
def load_card_funds(request: FundTransferRequest):
  """Client endpoint to load fiat funds, which triggers the conversion via Project 1."""

  # **DEPENDENCY CALL TO PROJECT 1**
  try:
    result = card_logic.transfer_fiat_to_crypto(request.dict())
    return {"status": "Conversion Initiated", "details": result}
  except Exception as e:
    raise HTTPException(status_code=503, detail=f"Service unavailable: {e}")

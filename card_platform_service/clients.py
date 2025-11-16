import os
import requests
from typing import Dict, Any
import uuid
import logging
import psycopg2
from psycopg2 import sql

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Configuration
CONVERTER_INTERNAL_URL = os.environ.get("CONVERTER_INTERNAL_URL")
STRIGA_API_BASE_URL = os.environ.get("STRIGA_API_BASE_URL") # Still needed for Card API
DB_HOST = os.environ.get("DB_HOST")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_NAME = os.environ.get("DB_NAME")
DB_USER = os.environ.get("DB_USER")
DB_PASSWORD = os.environ.get("DB_PASSWORD")

class CardPlatformLogic:
  """Handles client-facing features: KYC, Card Issuance, and fund transfer."""

  def __init__(self):
    self.db_conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    logger.info("CardPlatformLogic initialized. Database connection established.")

  def __del__(self):
      if self.db_conn:
          self.db_conn.close()
          logger.info("Database connection closed.")

  def get_user_kyc_status(self, user_id: str) -> str:
    """Retrieves the KYC status for a given user from the staging database."""
    try:
        with self.db_conn.cursor() as cur:
            cur.execute(
                sql.SQL("SELECT kyc_tier FROM users WHERE user_id = %s"),
                (user_id,)
            )
            result = cur.fetchone()
            if result:
                return f"Tier {result[0]}"
            else:
                return "User not found"
    except Exception as e:
        logger.error(f"Database query failed for user {user_id}: {e}")
        return "KYC status check failed"

  def issue_new_card(self, user_id: str, kyc_status: str) -> Dict[str, str]:
    """Calls the external Striga API to issue a new card after KYC confirmation."""
    if "APPROVED" not in kyc_status:
      return {"status": "error", "message": "KYC not approved for card issuance"}

    # --- MOCKING API CALL to Striga ---
    # AGENT ACTION: Replace with actual requests.post(...) to /cards endpoint
    card_id = f"card-{user_id}-123"
    print(f"Striga API: Issued new CARD {card_id} for user {user_id}")
    return {"status": "success", "card_id": card_id}

  def transfer_fiat_to_crypto(self, transaction_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    [DEPENDENCY] Calls the INTERNAL API of Project 1 (Converter Service)
    to execute the conversion logic.
    """
    trace_id = str(uuid.uuid4())
    transaction_data_with_trace = {**transaction_data, "trace_id": trace_id}
    internal_url = f"{CONVERTER_INTERNAL_URL}/internal/transfer_funds"

    logger.info(f"Initiating fund transfer with trace_id: {trace_id}")

    # NOTE: This internal call should use a separate security header (e.g., JWT or shared secret)
    # for service-to-service communication.

    try:
      response = requests.post(internal_url, json=transaction_data_with_trace, timeout=5)
      response.raise_for_status()
      return response.json()
    except requests.exceptions.RequestException as e:
      logger.error(f"Internal Converter Service call failed for trace_id {trace_id}: {e}")
      raise Exception("Failed to communicate with the core conversion service.")

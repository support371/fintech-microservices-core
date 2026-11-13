-- Striga Fiat-to-BTC Transaction Ledger
-- Run against your PostgreSQL / Supabase database

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Core transaction ledger with idempotency constraint
CREATE TABLE IF NOT EXISTS striga_ledger (
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  transaction_id  TEXT NOT NULL,
  event_type      TEXT NOT NULL,
  account_id      TEXT NOT NULL DEFAULT '',
  amount          NUMERIC(20, 8),
  currency        TEXT NOT NULL DEFAULT '',
  exchange_rate   NUMERIC(20, 8),
  tx_hash         TEXT NOT NULL DEFAULT '',
  status          TEXT NOT NULL DEFAULT 'PENDING',
  raw_payload     JSONB NOT NULL DEFAULT '{}',
  logged_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  UNIQUE (transaction_id, event_type)
);

CREATE INDEX IF NOT EXISTS idx_striga_ledger_status
  ON striga_ledger (status);

CREATE INDEX IF NOT EXISTS idx_striga_ledger_account
  ON striga_ledger (account_id);

CREATE INDEX IF NOT EXISTS idx_striga_ledger_logged_at
  ON striga_ledger (logged_at DESC);

-- User-to-Striga mapping (links your internal user IDs to Striga user IDs)
CREATE TABLE IF NOT EXISTS striga_user_map (
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  internal_user_id TEXT NOT NULL UNIQUE,
  striga_user_id   TEXT NOT NULL UNIQUE,
  wallet_id        TEXT,
  fiat_account_id  TEXT,
  btc_account_id   TEXT,
  standing_order_id TEXT,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_striga_user_map_striga_uid
  ON striga_user_map (striga_user_id);

-- Webhook delivery log for replay-attack prevention
CREATE TABLE IF NOT EXISTS striga_webhook_log (
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  signature       TEXT NOT NULL,
  event_type      TEXT NOT NULL,
  transaction_id  TEXT NOT NULL DEFAULT '',
  received_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  UNIQUE (signature)
);

CREATE INDEX IF NOT EXISTS idx_striga_webhook_log_received
  ON striga_webhook_log (received_at DESC);

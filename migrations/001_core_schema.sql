BEGIN;

CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    kyc_tier SMALLINT NOT NULL DEFAULT 0 CHECK (kyc_tier BETWEEN 0 AND 5),
    kyc_status TEXT NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS nexus_idempotency_keys (
    idempotency_key TEXT PRIMARY KEY,
    status TEXT NOT NULL CHECK (status IN ('processing', 'completed')),
    response_json JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS nexus_ledger_events (
    event_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    actor_type TEXT NOT NULL,
    actor_id TEXT,
    subject_id TEXT,
    trace_id TEXT,
    event_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_nexus_ledger_event_type_created
    ON nexus_ledger_events (event_type, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_nexus_ledger_subject_created
    ON nexus_ledger_events (subject_id, created_at DESC);

CREATE TABLE IF NOT EXISTS nexus_conversion_records (
    transaction_key TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(user_id),
    fiat_amount NUMERIC(18, 2) NOT NULL CHECK (fiat_amount > 0),
    fiat_currency CHAR(3) NOT NULL,
    btc_amount NUMERIC(24, 8) NOT NULL CHECK (btc_amount >= 0),
    satoshis BIGINT NOT NULL CHECK (satoshis >= 0),
    payment_mode TEXT NOT NULL,
    status TEXT NOT NULL,
    provider_reference TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS nexus_card_records (
    card_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(user_id),
    card_mode TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMIT;

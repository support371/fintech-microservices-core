-- =============================================================================
-- Nexus Bitcoin Banking Platform — Initial Database Schema
-- =============================================================================
-- Double-entry ledger with full audit trail, KYC compliance,
-- Bitcoin card management, and webhook event processing.
-- =============================================================================

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ─────────────────────────────────────────────────────────────────────────────
-- Users & KYC
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    auth_id         TEXT UNIQUE,
    email           TEXT UNIQUE NOT NULL,
    full_name       TEXT NOT NULL DEFAULT '',
    kyc_tier        INTEGER NOT NULL DEFAULT 0,
    kyc_status      TEXT NOT NULL DEFAULT 'pending'
                    CHECK (kyc_status IN ('pending', 'submitted', 'under_review', 'approved', 'rejected')),
    kyc_submitted_at TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_users_auth_id ON users(auth_id);
CREATE INDEX idx_users_email ON users(email);

-- ─────────────────────────────────────────────────────────────────────────────
-- Accounts (multi-currency support)
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE accounts (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id           UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    currency          TEXT NOT NULL CHECK (currency IN ('USD', 'EUR', 'GBP', 'BTC')),
    account_type      TEXT NOT NULL DEFAULT 'checking'
                      CHECK (account_type IN ('checking', 'savings', 'bitcoin')),
    balance           NUMERIC(20, 8) NOT NULL DEFAULT 0
                      CHECK (balance >= 0),
    available_balance NUMERIC(20, 8) NOT NULL DEFAULT 0
                      CHECK (available_balance >= 0),
    is_active         BOOLEAN NOT NULL DEFAULT TRUE,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, currency, account_type)
);

CREATE INDEX idx_accounts_user_id ON accounts(user_id);

-- ─────────────────────────────────────────────────────────────────────────────
-- Ledger (double-entry bookkeeping)
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE ledger_entries (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id      UUID NOT NULL REFERENCES accounts(id) ON DELETE RESTRICT,
    entry_type      TEXT NOT NULL CHECK (entry_type IN ('debit', 'credit')),
    amount          NUMERIC(20, 8) NOT NULL CHECK (amount > 0),
    balance_after   NUMERIC(20, 8) NOT NULL,
    reference_type  TEXT NOT NULL,
    reference_id    UUID NOT NULL,
    description     TEXT NOT NULL DEFAULT '',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_ledger_account_id ON ledger_entries(account_id);
CREATE INDEX idx_ledger_reference ON ledger_entries(reference_type, reference_id);
CREATE INDEX idx_ledger_created_at ON ledger_entries(created_at);

-- ─────────────────────────────────────────────────────────────────────────────
-- Deposits
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE deposits (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    account_id      UUID NOT NULL REFERENCES accounts(id) ON DELETE RESTRICT,
    amount          NUMERIC(20, 2) NOT NULL CHECK (amount > 0),
    currency        TEXT NOT NULL CHECK (currency IN ('USD', 'EUR', 'GBP')),
    status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'reversed')),
    idempotency_key TEXT UNIQUE NOT NULL,
    source          TEXT NOT NULL DEFAULT 'bank_transfer',
    failure_reason  TEXT,
    completed_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_deposits_user_id ON deposits(user_id);
CREATE INDEX idx_deposits_status ON deposits(status);
CREATE INDEX idx_deposits_idempotency ON deposits(idempotency_key);

-- ─────────────────────────────────────────────────────────────────────────────
-- Transfers (internal fund movements)
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE transfers (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id           UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    from_account_id   UUID NOT NULL REFERENCES accounts(id) ON DELETE RESTRICT,
    to_account_id     UUID NOT NULL REFERENCES accounts(id) ON DELETE RESTRICT,
    amount            NUMERIC(20, 8) NOT NULL CHECK (amount > 0),
    currency          TEXT NOT NULL,
    status            TEXT NOT NULL DEFAULT 'pending'
                      CHECK (status IN ('pending', 'completed', 'failed', 'reversed')),
    idempotency_key   TEXT UNIQUE NOT NULL,
    description       TEXT NOT NULL DEFAULT '',
    failure_reason    TEXT,
    completed_at      TIMESTAMPTZ,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_transfers_user_id ON transfers(user_id);
CREATE INDEX idx_transfers_status ON transfers(status);

-- ─────────────────────────────────────────────────────────────────────────────
-- Bitcoin Cards (GEM-ATR integration)
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE bitcoin_cards (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    card_number_masked  TEXT NOT NULL DEFAULT '',
    card_type           TEXT NOT NULL DEFAULT 'virtual'
                        CHECK (card_type IN ('virtual', 'physical')),
    status              TEXT NOT NULL DEFAULT 'requested'
                        CHECK (status IN ('requested', 'pending_kyc', 'issued', 'active', 'frozen', 'cancelled')),
    daily_limit         NUMERIC(12, 2) NOT NULL DEFAULT 5000.00,
    monthly_limit       NUMERIC(12, 2) NOT NULL DEFAULT 50000.00,
    daily_spent         NUMERIC(12, 2) NOT NULL DEFAULT 0,
    monthly_spent       NUMERIC(12, 2) NOT NULL DEFAULT 0,
    idempotency_key     TEXT UNIQUE NOT NULL,
    issued_at           TIMESTAMPTZ,
    expires_at          TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_cards_user_id ON bitcoin_cards(user_id);
CREATE INDEX idx_cards_status ON bitcoin_cards(status);

-- ─────────────────────────────────────────────────────────────────────────────
-- Exchange Orders (fiat-to-BTC conversion)
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE exchange_orders (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    fiat_amount     NUMERIC(20, 2) NOT NULL CHECK (fiat_amount > 0),
    fiat_currency   TEXT NOT NULL CHECK (fiat_currency IN ('USD', 'EUR', 'GBP')),
    btc_amount      NUMERIC(20, 8),
    exchange_rate   NUMERIC(20, 2),
    status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'executing', 'completed', 'failed')),
    idempotency_key TEXT UNIQUE NOT NULL,
    failure_reason  TEXT,
    completed_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_exchange_user_id ON exchange_orders(user_id);
CREATE INDEX idx_exchange_status ON exchange_orders(status);

-- ─────────────────────────────────────────────────────────────────────────────
-- Webhook Events (deduplication + audit)
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE webhook_events (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source          TEXT NOT NULL CHECK (source IN ('banking', 'kyc', 'cards')),
    event_type      TEXT NOT NULL,
    event_id        TEXT NOT NULL,
    payload         JSONB NOT NULL DEFAULT '{}',
    signature       TEXT NOT NULL,
    processed       BOOLEAN NOT NULL DEFAULT FALSE,
    processed_at    TIMESTAMPTZ,
    error           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(source, event_id)
);

CREATE INDEX idx_webhook_source_event ON webhook_events(source, event_id);
CREATE INDEX idx_webhook_processed ON webhook_events(processed);

-- ─────────────────────────────────────────────────────────────────────────────
-- Notification Outbox (transactional outbox pattern)
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE notification_outbox (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    channel         TEXT NOT NULL CHECK (channel IN ('email', 'sms', 'push')),
    recipient       TEXT NOT NULL,
    subject         TEXT NOT NULL DEFAULT '',
    body            TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'processing', 'sent', 'failed')),
    attempts        INTEGER NOT NULL DEFAULT 0,
    max_attempts    INTEGER NOT NULL DEFAULT 5,
    next_retry_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_error      TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_outbox_status ON notification_outbox(status, next_retry_at);

-- ─────────────────────────────────────────────────────────────────────────────
-- Operations Log (admin audit trail)
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE operations_log (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    actor           TEXT NOT NULL,
    action          TEXT NOT NULL,
    entity_type     TEXT NOT NULL,
    entity_id       TEXT NOT NULL DEFAULT '',
    details         JSONB NOT NULL DEFAULT '{}',
    ip_address      TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_ops_log_actor ON operations_log(actor);
CREATE INDEX idx_ops_log_created_at ON operations_log(created_at DESC);

-- ─────────────────────────────────────────────────────────────────────────────
-- Application Configuration
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE app_config (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO app_config (key, value) VALUES
    ('maintenance_mode', 'false'),
    ('max_deposit_amount', '1000000'),
    ('max_exchange_amount', '100000'),
    ('btc_rate_usd', '70000'),
    ('btc_rate_eur', '76000'),
    ('btc_rate_gbp', '82000');

-- ─────────────────────────────────────────────────────────────────────────────
-- Updated-at trigger function
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_accounts_updated_at
    BEFORE UPDATE ON accounts FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_deposits_updated_at
    BEFORE UPDATE ON deposits FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_transfers_updated_at
    BEFORE UPDATE ON transfers FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_cards_updated_at
    BEFORE UPDATE ON bitcoin_cards FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_exchange_updated_at
    BEFORE UPDATE ON exchange_orders FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_outbox_updated_at
    BEFORE UPDATE ON notification_outbox FOR EACH ROW EXECUTE FUNCTION update_updated_at();

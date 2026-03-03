-- =============================================================================
-- Nexus Bitcoin Banking Platform — Seed Data (Development / Mock Mode)
-- =============================================================================

-- Demo user
INSERT INTO users (id, auth_id, email, full_name, kyc_tier, kyc_status)
VALUES (
    'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11',
    'mock-user-1',
    'demo@nexus.financial',
    'Demo User',
    3,
    'approved'
);

-- Demo accounts
INSERT INTO accounts (id, user_id, currency, account_type, balance, available_balance)
VALUES
    ('b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', 'USD', 'checking', 25000.00, 24500.00),
    ('b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a12', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', 'EUR', 'checking', 10000.00, 10000.00),
    ('b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a13', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', 'BTC', 'bitcoin',  0.35000000, 0.35000000);

-- Demo deposits
INSERT INTO deposits (id, user_id, account_id, amount, currency, status, idempotency_key, completed_at)
VALUES
    ('c0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', 'b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', 10000.00, 'USD', 'completed', 'seed-dep-001', NOW() - INTERVAL '7 days'),
    ('c0eebc99-9c0b-4ef8-bb6d-6bb9bd380a12', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', 'b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', 15000.00, 'USD', 'completed', 'seed-dep-002', NOW() - INTERVAL '3 days'),
    ('c0eebc99-9c0b-4ef8-bb6d-6bb9bd380a13', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', 'b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', 500.00,   'USD', 'pending',   'seed-dep-003', NULL);

-- Demo Bitcoin card
INSERT INTO bitcoin_cards (id, user_id, card_number_masked, card_type, status, idempotency_key, issued_at)
VALUES (
    'd0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11',
    'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11',
    '**** **** **** 4289',
    'virtual',
    'active',
    'seed-card-001',
    NOW() - INTERVAL '14 days'
);

-- Demo exchange order
INSERT INTO exchange_orders (id, user_id, fiat_amount, fiat_currency, btc_amount, exchange_rate, status, idempotency_key, completed_at)
VALUES (
    'e0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11',
    'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11',
    5000.00,
    'USD',
    0.07142857,
    70000.00,
    'completed',
    'seed-exch-001',
    NOW() - INTERVAL '5 days'
);

-- Demo ledger entries (double-entry for the deposits)
INSERT INTO ledger_entries (account_id, entry_type, amount, balance_after, reference_type, reference_id, description)
VALUES
    ('b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', 'credit', 10000.00, 10000.00, 'deposit', 'c0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', 'Bank transfer deposit'),
    ('b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', 'credit', 15000.00, 25000.00, 'deposit', 'c0eebc99-9c0b-4ef8-bb6d-6bb9bd380a12', 'Bank transfer deposit'),
    ('b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a13', 'credit', 0.35000000, 0.35000000, 'exchange', 'e0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', 'BTC purchase via exchange');

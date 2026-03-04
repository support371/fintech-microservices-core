# Nexus Bitcoin Banking Platform

Production-grade Bitcoin banking platform with double-entry ledger, GEM-ATR cards, and enterprise compliance. Built with Next.js 15, Supabase, and TypeScript.

## Features

- **Multi-currency accounts** — USD, EUR, GBP, BTC with real-time balance tracking
- **Double-entry ledger** — Every financial operation creates balanced debit/credit entries
- **Bitcoin exchange** — Fiat-to-BTC conversion with configurable exchange rates
- **GEM-ATR debit cards** — Virtual and physical card issuance via provider integration
- **KYC/AML compliance** — Tiered KYC enforcement, transaction limits, audit trails
- **Jurisdiction-aware compliance** — FATF risk-based approach with per-jurisdiction CTR thresholds, velocity limits, and EDD rules (US, EU, UK, JP, AE, BR)
- **Risk scoring engine** — Weighted transaction risk assessment (0-100) with automatic flagging for manual review
- **Webhook ingestion** — HMAC-SHA256 secured handlers with timestamp validation and nonce-based replay prevention
- **Anomaly detection** — Burst pattern detection, sustained violation tracking, auth failure monitoring, and IP flagging
- **GDPR/CCPA privacy** — Data subject request API (access, rectification, deletion, portability, restriction)
- **Notification outbox** — Transactional outbox pattern with exponential backoff retry
- **Mock mode** — Full local development without external service dependencies

## Architecture

```
app/
├── api/
│   ├── health/          GET    — System health check
│   ├── accounts/        GET/POST — Account management
│   ├── deposits/        GET/POST — Deposit processing
│   ├── transfers/       POST   — Double-entry fund transfers
│   ├── cards/           GET/POST — Bitcoin card management
│   ├── exchange/        GET/POST — Fiat-to-BTC conversion
│   ├── privacy/         GET/POST — GDPR/CCPA data subject requests
│   ├── webhooks/
│   │   ├── banking/     POST   — Banking event ingestion
│   │   ├── kyc/         POST   — KYC status updates
│   │   └── cards/       POST   — Card lifecycle events
│   ├── cron/
│   │   └── email-worker/ POST  — Notification outbox processor
│   └── admin/
│       └── operations/  GET    — Operations audit log
├── layout.tsx           — Root layout (Inter font, dark theme)
├── page.tsx             — Dashboard entry point
└── globals.css          — Tailwind styles

src/
├── server/
│   ├── config.ts        — Environment config with production guards
│   ├── supabase.ts      — Supabase clients + mock data store
│   ├── auth.ts          — User authentication (Supabase JWT / mock)
│   ├── validation.ts    — Input validation (amounts, currencies, UUIDs)
│   ├── webhooks.ts      — HMAC verification + replay prevention + event dedup
│   ├── ratelimit.ts     — Token bucket rate limiter with anomaly detection
│   ├── compliance.ts    — Jurisdiction-aware compliance engine + risk scoring
│   ├── privacy.ts       — GDPR/CCPA data subject request handlers
│   └── providers.ts     — External provider clients (mock implementations)
└── ui/
    └── components/
        └── Dashboard.tsx — Full dashboard SPA

supabase/
├── migrations/
│   └── 001_initial_schema.sql — Complete database schema
└── seed.sql             — Demo data for development
```

## Quick Start

```bash
# Install dependencies
npm install

# Start development server (mock mode)
cp .env.example .env.local
# NEXT_PUBLIC_MOCK_MODE is already set to true
npm run dev

# Open http://localhost:3000
```

## Environment Variables

Copy `.env.example` to `.env.local` and configure:

| Variable | Required | Description |
|----------|----------|-------------|
| `NEXT_PUBLIC_SUPABASE_URL` | Production | Supabase project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Production | Supabase anonymous key |
| `SUPABASE_SERVICE_ROLE_KEY` | Production | Supabase service role key |
| `NEXT_PUBLIC_MOCK_MODE` | No | Set `true` for local dev (default) |
| `BANKING_WEBHOOK_SECRET` | Production | HMAC secret for banking webhooks |
| `KYC_WEBHOOK_SECRET` | Production | HMAC secret for KYC webhooks |
| `CARD_WEBHOOK_SECRET` | Production | HMAC secret for card webhooks |
| `CRON_SECRET` | Production | Bearer token for cron endpoint |

## Database

The schema uses PostgreSQL via Supabase with 10 tables:

- `users` — User profiles with KYC status and tier
- `accounts` — Multi-currency accounts with balance tracking
- `ledger_entries` — Double-entry bookkeeping (debit/credit pairs)
- `deposits` — Deposit records with idempotency keys
- `transfers` — Internal fund transfers
- `bitcoin_cards` — GEM-ATR card records
- `exchange_orders` — Fiat-to-BTC conversion orders
- `webhook_events` — Incoming webhook deduplication
- `notification_outbox` — Email/SMS notification queue
- `operations_log` — Admin audit trail

## Security

- HMAC-SHA256 webhook signature verification with `crypto.timingSafeEqual`
- Replay attack prevention: timestamp validation (5-min drift window) + nonce deduplication
- Token bucket rate limiting (30 req/60s per IP) with anomaly detection
- Anomaly detection: burst patterns (>10 req/5s), auth failure tracking, IP flagging
- Idempotency keys on all financial operations
- Bearer token authentication on cron endpoints
- Production guard: mock mode blocked on Vercel production
- Security headers: X-Content-Type-Options, X-Frame-Options, Referrer-Policy

## Global Compliance

Jurisdiction-aware compliance engine implementing the FATF risk-based approach:

| Jurisdiction | CTR Threshold | Min Card KYC | Data Protection |
|-------------|---------------|-------------|-----------------|
| US | $10,000 | Tier 2 | CCPA |
| EU | EUR 10,000 | Tier 3 | GDPR |
| UK | GBP 10,000 | Tier 3 | GDPR |
| JP | JPY 2,000,000 | Tier 3 | PIPA |
| AE | AED 55,000 | Tier 3 | - |
| BR | BRL 50,000 | Tier 2 | LGPD |

Risk scoring factors: CTR proximity, KYC tier, PEP status, transaction velocity, account age, jurisdiction EDD requirements. Scores 0-100 mapped to low/medium/high/critical.

## Data Privacy

GDPR/CCPA-compliant data subject request API (`/api/privacy`):

- **Access** (Art. 15) — Export all personal data as JSON
- **Rectification** (Art. 16) — Correct name or email
- **Deletion** (Art. 17) — Anonymise PII; retain financial records per Art. 17(3)(b)
- **Portability** (Art. 20) — Machine-readable JSON export
- **Restriction** (Art. 18) — Logged for manual processing within 30 days

Deletion anonymises PII but retains financial records required by AML regulations (5-year minimum retention).

## Deployment

See the root `DEPLOYMENT.md` for full Vercel + Supabase deployment guide.

# Nexus Bitcoin Banking Platform

Production-grade Bitcoin banking platform with double-entry ledger, GEM-ATR cards, and enterprise compliance. Built with Next.js 15, Supabase, and TypeScript.

## Features

- **Multi-currency accounts** — USD, EUR, GBP, BTC with real-time balance tracking
- **Double-entry ledger** — Every financial operation creates balanced debit/credit entries
- **Bitcoin exchange** — Fiat-to-BTC conversion with configurable exchange rates
- **GEM-ATR debit cards** — Virtual and physical card issuance via provider integration
- **KYC/AML compliance** — Tiered KYC enforcement, transaction limits, audit trails
- **Webhook ingestion** — HMAC-SHA256 secured handlers for banking, KYC, and card events
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
│   ├── webhooks.ts      — HMAC verification + event deduplication
│   ├── ratelimit.ts     — Token bucket rate limiter
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
- Token bucket rate limiting (30 req/60s per IP on mutations)
- Idempotency keys on all financial operations
- Bearer token authentication on cron endpoints
- Production guard: mock mode blocked on Vercel production
- Security headers: X-Content-Type-Options, X-Frame-Options, Referrer-Policy

## Deployment

See the root `DEPLOYMENT.md` for full Vercel + Supabase deployment guide.

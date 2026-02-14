# GEM ATR – Digital EasyWay

Production-oriented Next.js 14 App Router app for a fintech dashboard MVP.

## Release

Current app version: `0.2.1`.

## Local development

```bash
npm install
cp .env.example .env.local
npm run dev
```

Build/lint checks:

```bash
npm run lint
npm run build
```

## Vercel deploy runbook

### 1) Import settings (required)
- GitHub repo: `support371/fintech-microservices-core`
- Framework Preset: `Next.js`
- Root Directory: `apps/gem-atr-digital-easyway`
- Build Command: `npm run build`
- Install Command: `npm install`
- Output Directory: auto
- Node.js Version: 20.x recommended

### 2) Environment variables (set before first deploy)

Preview:
- `NEXT_PUBLIC_MOCK_MODE=true`
- `CRON_SECRET=<openssl rand -base64 32>`
- `BANKING_WEBHOOK_SECRET=<openssl rand -base64 32>`

Production:
- `NEXT_PUBLIC_MOCK_MODE=false` (hard requirement)
- `CRON_SECRET=<new strong secret>`
- `BANKING_WEBHOOK_SECRET=<new strong secret>`

Optional future:
- `CLERK_SECRET_KEY`
- `CLERK_PUBLISHABLE_KEY`
- `DATABASE_URL`

### 3) Guardrails
- App fails fast when `VERCEL_ENV=production` and `NEXT_PUBLIC_MOCK_MODE=true`.
- `better-sqlite3` imports are server-only.
- State-changing endpoints accept `idempotency_key`.

### 4) Health/Cron verification

```bash
curl "http://localhost:3000/api/health"
```

```bash
curl -X POST "http://localhost:3000/api/cron/email-worker" \
  -H "Authorization: Bearer $CRON_SECRET" \
  -H "x-idempotency-key: cron-$(date +%s)"
```

Without auth, cron endpoint should return `401`.
The worker processes up to 25 due outbox rows, marks successful sends as `sent`, and applies exponential backoff (`next_attempt_at`) with max-attempt failure handling on delivery errors.

### 5) Webhook signing + replay verification

```bash
RAW='{"event":"deposit.received","amount":250}'
SIG=$(printf "%s" "$RAW" | openssl dgst -sha256 -hmac "$BANKING_WEBHOOK_SECRET" -hex | sed 's/^.* //')
EID="test-$(date +%s)"

curl -X POST "http://localhost:3000/api/webhooks/banking" \
  -H "content-type: application/json" \
  -H "x-event-id: $EID" \
  -H "x-signature: $SIG" \
  --data "$RAW"

# replay (same x-event-id)
curl -X POST "http://localhost:3000/api/webhooks/banking" \
  -H "content-type: application/json" \
  -H "x-event-id: $EID" \
  -H "x-signature: $SIG" \
  --data "$RAW"
```

## 2-minute smoke checklist
- Homepage loads.
- Admin mode toggle works in mock mode.
- Create deposit works.
- Mark received and settle flow works.
- Request, issue, and freeze card flow works.
- `/api/health` returns `200`.


> Note: For Vercel, ensure Root Directory is set exactly to `apps/gem-atr-digital-easyway`.

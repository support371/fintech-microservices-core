# Nexus Banking Platform — Deployment Guide

## Prerequisites

- Node.js 18+ installed
- Supabase account and project created
- Vercel account linked to your Git provider

## Step 1: Supabase Setup

1. Create a new Supabase project at [supabase.com](https://supabase.com)
2. Run the initial migration:
   ```bash
   # Using Supabase CLI
   npx supabase db push --db-url "postgresql://..."

   # Or manually via SQL Editor
   # Copy contents of supabase/migrations/001_initial_schema.sql
   # Paste into Supabase SQL Editor and execute
   ```
3. (Optional) Load seed data for testing:
   ```bash
   # Copy contents of supabase/seed.sql into SQL Editor and execute
   ```
4. Note your project credentials:
   - Project URL: `https://xxxxx.supabase.co`
   - Anon Key: `eyJhbGci...`
   - Service Role Key: `eyJhbGci...`

## Step 2: Vercel Deployment

1. Import the repository into Vercel
2. Set the **Root Directory** to `nexus-banking-fullstack`
3. Framework Preset should auto-detect as **Next.js**
4. Add environment variables:

   | Variable | Value |
   |----------|-------|
   | `NEXT_PUBLIC_SUPABASE_URL` | Your Supabase project URL |
   | `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Your Supabase anon key |
   | `SUPABASE_SERVICE_ROLE_KEY` | Your Supabase service role key |
   | `NEXT_PUBLIC_MOCK_MODE` | `false` |
   | `BANKING_WEBHOOK_SECRET` | Generate: `openssl rand -hex 32` |
   | `KYC_WEBHOOK_SECRET` | Generate: `openssl rand -hex 32` |
   | `CARD_WEBHOOK_SECRET` | Generate: `openssl rand -hex 32` |
   | `CRON_SECRET` | Generate: `openssl rand -hex 32` |

5. Click **Deploy**

## Step 3: Verify Deployment

1. Visit `https://your-app.vercel.app/api/health`
   - Should return: `{"status":"healthy","database":"healthy",...}`

2. Check Vercel Cron Jobs dashboard:
   - `/api/cron/email-worker` should be listed
   - Schedule: every 5 minutes

## Step 4: Configure Webhooks

Set up webhook endpoints with your providers:

| Provider | Webhook URL | Secret Variable |
|----------|-------------|-----------------|
| Banking | `https://your-app.vercel.app/api/webhooks/banking` | `BANKING_WEBHOOK_SECRET` |
| KYC | `https://your-app.vercel.app/api/webhooks/kyc` | `KYC_WEBHOOK_SECRET` |
| Cards | `https://your-app.vercel.app/api/webhooks/cards` | `CARD_WEBHOOK_SECRET` |

Each provider should sign payloads with HMAC-SHA256 using the shared secret and include the signature in the `x-signature` or `x-webhook-signature` header.

## Production Checklist

- [ ] `NEXT_PUBLIC_MOCK_MODE` is set to `false`
- [ ] All Supabase credentials are configured
- [ ] All webhook secrets are unique, random 32+ byte hex strings
- [ ] Cron secret is configured and unique
- [ ] Health endpoint returns `"status":"healthy"`
- [ ] Cron job appears in Vercel dashboard
- [ ] No `.env` files committed to repository

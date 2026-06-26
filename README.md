# Nexus Fintech Microservices Core

Secure backend foundation for Alliance Trust Realty's Nexus Bitcoin banking platform.

## Current operating state

- Fiat-to-BTC conversion: **sandbox only**
- Card issuance: **sandbox only**
- Live payments: disabled unless explicitly approved and implemented through a verified provider adapter
- Live card issuance: disabled unless explicitly approved and implemented through a verified provider adapter
- KYC: Tier 3 or higher is required for card issuance and fund loading
- Internal service traffic: HMAC-SHA256 authenticated with timestamp replay protection
- Transaction processing: idempotent, with PostgreSQL required in production

## Services

### Card platform

- `POST /api/v1/cards/issue`
- `POST /api/v1/funds/load`
- `GET /health`
- `GET /ready`

### Fiat-to-BTC converter

- `POST /internal/transfer_funds`
- `POST /webhook/fiat_received`
- `GET /health`
- `GET /ready`

### Gateway health

- `GET /`
- `GET /health`

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
cp .env.example .env
pytest -q
```

Apply the PostgreSQL schema before production-style testing:

```bash
psql "$DATABASE_URL" -f migrations/001_core_schema.sql
```

Never commit real secrets. Store `INTERNAL_SERVICE_SECRET`, database credentials, webhook secrets, and future provider credentials in the deployment platform's encrypted secret store.

## Vercel deployment

The root `vercel.json` routes:

- `/api/v1/*` to the card service
- `/webhook/*` and `/internal/*` to the converter service
- `/` and `/health` to the gateway health app

Deploy from the repository root so Vercel discovers the Python entrypoints under `api/`.

## Nexus prototype and Foundry

- `prototype/nexus-demo.html` provides the existing interactive dashboard demonstration.
- `foundry/agents/` contains Compliance, Security, Ledger, Platform, and Build agent specifications.
- `foundry/schemas/` contains the policy schemas.
- `foundry/workflows/nexus-locked-build.yaml` contains the gated workflow design.

## Production gate

A production release is not complete until all of the following are independently verified:

1. CI passes on the pull request.
2. PostgreSQL migrations are applied and backed up.
3. Deployment secrets are configured outside source control.
4. Webhook signature behavior is confirmed against the chosen provider's official contract.
5. Sandbox card and conversion flows pass end-to-end tests.
6. Security and compliance reviewers approve the release.
7. The owner explicitly approves any future live-provider implementation.

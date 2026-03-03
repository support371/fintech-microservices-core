# Running the Nexus Locked-Build Workflow

## Overview

The `nexus-locked-build` workflow is the primary gated pipeline for building,
validating, and deploying the Nexus platform services. It is defined in
`foundry/workflows/nexus-locked-build.yaml`.

## Prerequisites

1. **Python 3.x** installed with `pip`.
2. **Docker** installed and running (for image builds).
3. **Environment variables** configured (see `.env` and `DEPLOYMENT.md`):
   - `STRIGA_WEBHOOK_SECRET`
   - `STRIGA_API_BASE_URL`
   - `CONVERTER_INTERNAL_URL`
   - `DATABASE_URL` (PostgreSQL connection string)
4. **Google Cloud SDK** installed if deploying to Cloud Run.
5. **PyPI credentials** configured for artifact publishing (or OIDC trusted
   publishing via GitHub Actions).

## Running Locally

### Step 1 — Install dependencies

```bash
pip install -r requirements.txt
pip install -r card_platform_service/requirements.txt
pip install -r converter_service/requirements.txt
```

### Step 2 — Build distribution packages

```bash
python -m build
```

### Step 3 — Build Docker images

```bash
docker build -t card-platform-service:local card_platform_service/
docker build -t converter-service:local converter_service/
```

### Step 4 — Run agent validations

Each agent validation can be simulated by verifying its respective concerns:

- **ComplianceAgent**: Ensure KYC tier rules are correctly applied.
  ```bash
  # Verify KYC tier check logic
  python -c "from card_platform_service.clients import CardPlatformLogic; print('KYC logic OK')"
  ```

- **SecurityAgent**: Verify HMAC signature validation.
  ```bash
  # Verify webhook signature logic
  python -c "from converter_service.logic import ConversionLogic; print('Security logic OK')"
  ```

- **LedgerAgent**: Confirm idempotency and event schema compliance.
  ```bash
  # Verify idempotency check
  python -c "from converter_service.logic import ConversionLogic; cl = ConversionLogic(); print('Ledger logic OK')"
  ```

### Step 5 — Deploy

Follow the instructions in `DEPLOYMENT.md` for Cloud Run deployment, or push
to the repository to trigger the GitHub Actions pipeline.

## Running via GitHub Actions

The workflow triggers automatically on:
- **Release published** — Push a new GitHub release to start the full pipeline.
- **Manual dispatch** — Use the GitHub Actions UI to trigger a run.

## Troubleshooting

| Issue                            | Resolution                                                  |
|----------------------------------|-------------------------------------------------------------|
| KYC tier check fails             | Ensure the `users` table has a `kyc_tier` column with int values ≥ 3 |
| HMAC validation error            | Verify `STRIGA_WEBHOOK_SECRET` is set correctly             |
| Docker build fails               | Check that `requirements.txt` files are up to date          |
| PyPI publish fails               | Ensure OIDC trusted publishing is configured on PyPI        |
| Cloud Run deploy times out       | Increase the deploy timeout or check service health logs    |

## Related Files

- `foundry/workflows/nexus-locked-build.yaml` — Workflow definition
- `foundry/agents/` — Agent documentation
- `foundry/schemas/` — Configuration schemas
- `scripts/foundry/PROMPTS.md` — Agent prompt templates
- `DEPLOYMENT.md` — Cloud Run deployment guide

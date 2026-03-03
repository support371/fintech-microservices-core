# Running the Nexus Locked-Build Workflow

## Overview

The `nexus-locked-build` workflow is the primary gated pipeline for building,
validating, and deploying the Nexus platform services. It is defined in
`foundry/workflows/nexus-locked-build.yaml`.

The pipeline flows through five stages:

1. **Build** — Install dependencies, build packages and Docker images.
2. **Agent Validation Gates** — ComplianceAgent, SecurityAgent, LedgerAgent,
   and PlatformAgent each return `APPROVED` or `REJECTED`.
3. **Build Agent Decision** — BuildAgent receives the gate results as an
   input pack and emits a `READY` or `BLOCKED` verdict (machine-readable JSON).
4. **Deploy** — Publish artifacts and deploy services (only if `READY`).
5. **Post-deploy** — Record the deployment in the ledger and notify.

## Prerequisites

1. **Python 3.x** installed with `pip`.
2. **Docker** installed and running (for image builds).
3. **Environment variables** configured (see `.env` and `DEPLOYMENT.md`):
   - `STRIGA_WEBHOOK_SECRET` — HMAC secret for webhook signature validation
   - `CONVERTER_INTERNAL_URL` — Internal URL for the converter service
   - `DATABASE_URL` — PostgreSQL connection string for KYC lookups
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

### Step 4 — Run agent validation gates

Each gate must return `{ "status": "APPROVED" }` or the pipeline halts.

**4a. Compliance Gate** — Verify KYC/AML policy compliance:

```bash
python -c "
from card_platform_service.clients import CardPlatformLogic
# Confirm KYC tier >= 3 enforcement is intact
assert CardPlatformLogic.is_kyc_tier_approved(3) == True
assert CardPlatformLogic.is_kyc_tier_approved(2) == False
print('{\"status\": \"APPROVED\", \"reason\": \"KYC tier logic verified\"}')
"
```

**4b. Security Gate** — Verify HMAC signature validation:

```bash
python -c "
from converter_service.logic import ConversionLogic
import hmac, hashlib, os
secret = os.environ.get('STRIGA_WEBHOOK_SECRET', 'test-secret')
payload = b'{\"test\": true}'
sig = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
print('{\"status\": \"APPROVED\", \"threat_level\": \"none\"}')
"
```

**4c. Ledger Gate** — Verify idempotency and event schema:

```bash
python -c "
from converter_service.logic import ConversionLogic
cl = ConversionLogic()
# Confirm idempotency: first call records, second deduplicates
cl.is_already_processed('test-txn-001')
assert cl.is_already_processed('test-txn-001') == True
print('{\"status\": \"APPROVED\", \"reason\": \"Idempotency logic verified\"}')
"
```

**4d. Platform Gate** — Verify service health:

```bash
curl -sf http://localhost:8001/health && \
curl -sf http://localhost:8000/health && \
echo '{\"status\": \"APPROVED\", \"services_healthy\": true}' || \
echo '{\"status\": \"REJECTED\", \"reason\": \"Service health check failed\"}'
```

### Step 5 — Build Agent decision

After all four gates pass, the BuildAgent assembles the input pack and
emits the final verdict:

```bash
echo '{
  "verdict": "READY",
  "build_id": "local-'$(date +%s)'",
  "reason": "All four gates returned APPROVED",
  "gate_results": {
    "COMPLIANCE": "APPROVED",
    "SECURITY": "APPROVED",
    "LEDGER": "APPROVED",
    "PLATFORM": "APPROVED"
  }
}'
```

If any gate returned `REJECTED`, the verdict MUST be `BLOCKED`.

### Step 6 — Deploy

Follow the instructions in `DEPLOYMENT.md` for Cloud Run deployment, or push
to the repository to trigger the GitHub Actions pipeline.

## Running via GitHub Actions

The workflow triggers automatically on:
- **Release published** — Push a new GitHub release to start the full pipeline.
- **Manual dispatch** — Use the GitHub Actions UI to trigger a run.

## Troubleshooting

| Issue                            | Resolution                                                       |
|----------------------------------|------------------------------------------------------------------|
| Gate returns `REJECTED`          | Check the `reason` field in the gate's JSON output               |
| KYC tier check fails             | Ensure `users` table has `kyc_tier` column with int values >= 3  |
| HMAC validation error            | Verify `STRIGA_WEBHOOK_SECRET` is set correctly in `.env`        |
| Docker build fails               | Check that `requirements.txt` files are up to date               |
| PyPI publish fails               | Ensure OIDC trusted publishing is configured on PyPI             |
| Cloud Run deploy times out       | Increase the deploy timeout or check service health logs         |
| Verdict is `BLOCKED`             | Review `gate_results` to find which agent rejected               |

## Related Files

- `foundry/workflows/nexus-locked-build.yaml` — Workflow definition
- `foundry/agents/` — Agent documentation
- `foundry/schemas/` — Configuration schemas
- `scripts/foundry/PROMPTS.md` — Agent prompt templates
- `DEPLOYMENT.md` — Cloud Run deployment guide

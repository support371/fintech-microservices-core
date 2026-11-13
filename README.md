# fintech-microservices-core

Microservices Core for Alliance Trust Realty's Crypto Debit Card Platform. Features a secure, HMAC-validated Fiat-to-Bitcoin converter and the client-facing card management API.

## Repository Structure

```
fintech-microservices-core/
├── api/                         # Lightweight health/gateway app
├── apps/                        # Application modules
├── card_platform_service/       # Card management API (FastAPI)
├── converter_service/           # Fiat-to-Bitcoin converter (FastAPI)
├── striga-auto-btc/             # Striga Fiat-to-BTC automation (Node.js/Express)
│   ├── config/env.js            # Environment validation
│   ├── services/strigaClient.js # HMAC-SHA256 signing client
│   ├── routes/                  # Onboarding, automation, webhook routes
│   ├── database/                # PostgreSQL ledger + SQL migration
│   └── test/                    # HMAC signing tests
├── validation/                  # Shared validation utilities
├── nexus-banking-fullstack/     # Nexus Bitcoin Banking Platform (Next.js)
├── prototype/                   # Interactive UI prototypes
│   └── nexus-demo.html          # Nexus dashboard prototype
├── foundry/                     # Foundry agent system
│   ├── agents/                  # Agent definitions
│   │   ├── ComplianceAgent.md   # KYC/AML compliance enforcement
│   │   ├── SecurityAgent.md     # Webhook security & access control
│   │   ├── LedgerAgent.md       # Double-entry bookkeeping integrity
│   │   ├── PlatformAgent.md     # Platform operations & monitoring
│   │   └── BuildAgent.md        # Build pipeline & deployment
│   ├── schemas/                 # JSON Schema definitions
│   │   ├── compliance.schema.json
│   │   ├── security.schema.json
│   │   ├── ledger.schema.json
│   │   ├── platform.schema.json
│   │   ├── build.schema.json
│   │   └── privacy.schema.json
│   └── workflows/               # Orchestration workflows
│       └── nexus-locked-build.yaml
├── scripts/
│   └── foundry/                 # Foundry workflow scripts
│       ├── RUN_WORKFLOW.md      # How to run the build workflow
│       └── PROMPTS.md           # Agent prompt templates
└── vercel.json                  # Vercel API gateway config
```

## Vercel Deployment (API Gateway)

This repository includes a root-level `vercel.json` that maps paths to the two FastAPI services:

- `/api/v1/*` -> `card_platform_service`
- `/webhook/*` and `/internal/*` -> `converter_service`
- `/` and `/health` -> lightweight health app (`api/index.py`)

If your Vercel deployment previously returned `404: NOT_FOUND`, redeploy from the repository root so Vercel picks up this configuration.

## Nexus Bitcoin Banking Platform

The `nexus-banking-fullstack/` directory contains a production-grade Bitcoin banking platform built with Next.js, featuring:

- **Double-entry ledger** for financial integrity
- **GEM-ATR Bitcoin debit cards** via card provider integration
- **Multi-currency accounts** (USD, EUR, GBP, BTC)
- **Fiat-to-BTC exchange** with real-time rate conversion
- **Enterprise compliance** — KYC/AML enforcement, audit trails
- **HMAC-SHA256 webhook security** with timing-safe comparison
- **Mock mode** for local development without external dependencies

See `nexus-banking-fullstack/README.md` for setup and deployment instructions.

## Striga Auto-BTC Backend

The `striga-auto-btc/` directory implements automated Fiat-to-Bitcoin conversion and on-chain settlement via the Striga v1 API:

- **HMAC-SHA256 Authentication** for all outbound Striga API requests (timestamp + method + endpoint + MD5 body digest)
- **User Onboarding** with multi-currency wallet provisioning (USD/EUR/BRL/MXN + BTC) and virtual banking enrichment (vIBAN / US ACH)
- **Standing Orders** for automated conversion (`SWAP_AND_WITHDRAW` with on-chain sweep, or `SWAP_ONLY` to hold BTC in wallet) with SCA OTP challenge verification
- **Webhook Ingestion** with raw-body signature verification (`X-Striga-Signature`), idempotent event processing, and database ledger logging
- **PostgreSQL Ledger** with replay-attack prevention and user-to-Striga mapping tables

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/onboarding/user` | Create Striga user profile |
| POST | `/api/onboarding/provision-accounts` | Create wallet + enrich accounts |
| POST | `/api/automation/standing-order` | Create auto-conversion rule |
| POST | `/api/automation/standing-order/confirm` | Confirm via SCA OTP |
| POST | `/webhooks/striga/ping` | Dashboard test ping |
| POST | `/webhooks/striga/tx` | Transaction event listener |

### Quick Start

```bash
cd striga-auto-btc
cp .env.example .env  # Configure your Striga API credentials
npm install
npm start             # Runs on port 3000
```

## Foundry — Agent Definitions & Schemas

The `foundry/` directory contains the agent specifications, configuration schemas, and workflow definitions for the Nexus platform's AI-powered agent layer.

### Agents (`foundry/agents/`)

| Agent | Description |
|-------|-------------|
| [ComplianceAgent](foundry/agents/ComplianceAgent.md) | Enforces KYC/AML regulatory requirements |
| [SecurityAgent](foundry/agents/SecurityAgent.md) | Validates HMAC signatures, rate limiting, anomaly detection |
| [LedgerAgent](foundry/agents/LedgerAgent.md) | Maintains immutable append-only event ledger |
| [PlatformAgent](foundry/agents/PlatformAgent.md) | Orchestrates workflows, health monitoring, deployments |
| [BuildAgent](foundry/agents/BuildAgent.md) | Manages CI/CD pipeline and locked-build enforcement |

### Schemas (`foundry/schemas/`)

| Schema | Description |
|--------|-------------|
| [compliance.schema.json](foundry/schemas/compliance.schema.json) | KYC tier rules, AML thresholds, reporting config |
| [security.schema.json](foundry/schemas/security.schema.json) | HMAC settings, rate limits, anomaly thresholds |
| [ledger.schema.json](foundry/schemas/ledger.schema.json) | Ledger event entry format and retention policies |
| [platform.schema.json](foundry/schemas/platform.schema.json) | Service registry, workflow settings, retry policies |
| [build.schema.json](foundry/schemas/build.schema.json) | CI pipeline, artifact config, promotion policies |

### Workflows (`foundry/workflows/`)

| Workflow | Description |
|----------|-------------|
| [nexus-locked-build.yaml](foundry/workflows/nexus-locked-build.yaml) | Gated build-and-deploy pipeline with agent validation gates |

## Scripts

| File | Description |
|------|-------------|
| [scripts/foundry/RUN_WORKFLOW.md](scripts/foundry/RUN_WORKFLOW.md) | Step-by-step guide to running the locked-build workflow |
| [scripts/foundry/PROMPTS.md](scripts/foundry/PROMPTS.md) | LLM prompt templates for invoking each Foundry agent |

## Prototype

The `prototype/nexus-demo.html` file is a standalone interactive demo of the Nexus dashboard UI. Open it directly in a browser — no build step required.

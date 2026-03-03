# fintech-microservices-core

Microservices Core for Alliance Trust Realty's Crypto Debit Card Platform. Features a secure, HMAC-validated Fiat-to-Bitcoin converter and the client-facing card management API.

## Repository Structure

```
fintech-microservices-core/
├── api/                         # Lightweight health/gateway app
├── apps/                        # Application modules
├── card_platform_service/       # Card management API (FastAPI)
├── converter_service/           # Fiat-to-Bitcoin converter (FastAPI)
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
│   │   └── build.schema.json
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

## Foundry Agent System

The `foundry/` directory defines five specialized agents that validate, audit, and orchestrate the platform:

| Agent            | Role                                              |
|------------------|---------------------------------------------------|
| ComplianceAgent  | KYC/AML enforcement, transaction limits, audit     |
| SecurityAgent    | Webhook HMAC, rate limiting, auth validation       |
| LedgerAgent      | Double-entry integrity, balance reconciliation     |
| PlatformAgent    | Health monitoring, cron jobs, notifications        |
| BuildAgent       | Build validation, deployment, environment checks   |

The `nexus-locked-build.yaml` workflow orchestrates all agents in sequence. See `scripts/foundry/RUN_WORKFLOW.md` for execution instructions and `scripts/foundry/PROMPTS.md` for agent prompt templates.

## Prototype

The `prototype/nexus-demo.html` file is a standalone interactive demo of the Nexus dashboard UI. Open it directly in a browser — no build step required.

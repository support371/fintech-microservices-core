# fintech-microservices-core

Microservices Core for Alliance Trust Realty's Crypto Debit Card Platform. Features a secure, HMAC-validated Fiat-to-Bitcoin converter and the client-facing card management API.

## Vercel Deployment (API Gateway)

This repository now includes a root-level `vercel.json` that maps paths to the two FastAPI services:

- `/api/v1/*` -> `card_platform_service`
- `/webhook/*` and `/internal/*` -> `converter_service`
- `/` and `/health` -> lightweight health app (`api/index.py`)

If your Vercel deployment previously returned `404: NOT_FOUND`, redeploy from the repository root so Vercel picks up this configuration.

## Nexus Prototype

An interactive HTML demo of the Nexus platform dashboard is available at:

- `prototype/nexus-demo.html` — Simulates card issuance, fund loading, compliance checks, and displays system status for all agents.

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

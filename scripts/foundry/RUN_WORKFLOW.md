# Running the Nexus Locked Build Workflow

## Overview

The `nexus-locked-build` workflow orchestrates all five foundry agents to validate, audit, and deploy the Nexus Banking Platform. Each stage runs sequentially with dependency checks and failure handling.

## Prerequisites

1. **Environment variables** configured (see `.env.example`)
2. **Supabase project** created with migrations applied
3. **Vercel project** linked to the repository
4. **Node.js 18+** installed

## Workflow Stages

```
build-validation → schema-validation ─┐
                 → security-audit ─────┤
                                       ├→ compliance-check → platform-health → deploy
```

### Stage 1: Build Validation (BuildAgent)
- TypeScript strict compilation
- Dependency audit
- Vercel config validation
- Environment variable check

### Stage 2: Schema Validation (LedgerAgent)
- Migration SQL syntax check
- Double-entry ledger invariants
- Idempotency key constraints
- Seed data referential integrity

### Stage 3: Security Audit (SecurityAgent)
- HMAC-SHA256 webhook verification
- Authentication and admin guards
- Rate limiting on mutation endpoints
- Response header security
- Secret exposure scan

### Stage 4: Compliance Check (ComplianceAgent)
- KYC tier enforcement (tier 3+ for cards)
- Transaction limit validation
- Audit trail completeness (operations log, webhook dedup, ledger references)

### Stage 5: Platform Health (PlatformAgent)
- Health endpoint verification
- Cron job registration
- Notification outbox configuration
- Admin dashboard availability

### Stage 6: Deploy (BuildAgent)
- Vercel production deployment
- Smoke tests on deployed endpoints

## Running Manually

```bash
# From the repository root:

# 1. Validate the build
cd nexus-banking-fullstack
npm run build

# 2. Check schema
npx supabase db lint --schema supabase/migrations/

# 3. Run security audit (manual checklist)
# - Verify webhook handlers use HMAC-SHA256
# - Verify rate limiting on POST endpoints
# - Verify .gitignore covers .env files

# 4. Deploy
npx vercel --prod
```

## Failure Handling

| Stage              | On Failure | Action                              |
|--------------------|------------|-------------------------------------|
| build-validation   | abort      | Fix build errors before proceeding  |
| schema-validation  | abort      | Fix migration SQL or constraints    |
| security-audit     | abort      | Resolve security vulnerabilities    |
| compliance-check   | warn       | Review warnings, may proceed        |
| platform-health    | warn       | Review warnings, may proceed        |
| deploy             | rollback   | Revert to previous deployment       |

## Agent Reports

After each run, agents produce reports in the workflow outputs:
- `build_report` — Build validation results
- `security_report` — Security audit findings
- `compliance_report` — Compliance verification results
- `deployment_url` — Deployed application URL

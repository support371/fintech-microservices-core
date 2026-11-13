# Production Readiness Checklist — fintech-microservices-core

**Status:** Pre-production (APP_MODE=staging ready; production pending external provider onboarding)

---

## ✅ Completed

### Architecture
- [x] Microservices separation: card_platform_service, converter_service, compliance_agents, gem-atr-digital-easyway
- [x] Docker Compose for local development
- [x] Kubernetes manifests (namespace, deployments, services, ingress, gateway, configmaps, secrets)
- [x] Terraform infrastructure modules (VPC, EKS, RDS, ECR, S3, WAF, CloudWatch, Secrets Manager)
- [x] Monitoring stack: Prometheus + Grafana + Alertmanager

### Security
- [x] HMAC-SHA256 webhook signature verification (constant-time)
- [x] Replay attack protection (event ID deduplication)
- [x] Rate limiting (in-memory; Redis upgrade path documented)
- [x] Admin/user role separation enforced at API layer
- [x] Secrets via environment variables (never hardcoded)
- [x] APP_MODE production guard (blocks mock mode in production)
- [x] Input validation on all API routes

### Compliance
- [x] 16/16 governance controls satisfied (COBIT, COSO, GAO, IIA)
- [x] Immutable HMAC-chained audit log
- [x] LLM provider cascade (OpenAI → Groq → Mistral)
- [x] Automated daily governance sweep (07:00 WAT)
- [x] Compliance evidence document
- [x] AML threshold screening rules

### Data
- [x] SQLite-backed persistence (all in-memory Maps replaced)
- [x] Double-entry ledger
- [x] Idempotency on all financial operations
- [x] Database schema with indexes
- [x] Soft-quarantine for corrupt audit entries

### Testing
- [x] Unit tests: GovernanceEngine, AuditChain, ScreeningRules
- [x] Integration tests: card and deposit API routes
- [x] Security tests: webhook HMAC verification
- [x] E2E tests: deposit → ledger flow

### Developer Experience
- [x] Makefile with all common commands
- [x] CHANGELOG.md
- [x] .env.example files
- [x] Architecture and deployment docs

---

## 🔲 Pending (Pre-launch requirements)

### External Provider Onboarding
- [ ] Real card provider API key (`CARD_PROVIDER_API_KEY`)
- [ ] Real banking webhook secret (`BANKING_WEBHOOK_SECRET`)
- [ ] Real converter service secret (`CONVERTER_SERVICE_SECRET`)

### Authentication
- [ ] Clerk (or alternative) auth wired in `auth.ts` — currently returns mock user
- [ ] JWT/session validation on all API routes
- [ ] User registration and KYC onboarding flow

### Infrastructure
- [ ] AWS account provisioned and Terraform applied
- [ ] EKS cluster running
- [ ] RDS PostgreSQL (replace SQLite in production)
- [ ] Upstash Redis for production rate limiting
- [ ] GitHub Actions CI/CD pipeline with test gates

### Compliance
- [ ] KYC provider integration (identity verification API)
- [ ] Sanctions/PEP screening list connected
- [ ] SAR submission workflow to financial intelligence unit
- [ ] Data retention policy implemented (GDPR / local regulation)

### Monitoring
- [ ] Sentry DSN configured for error tracking
- [ ] Grafana dashboards deployed on EKS
- [ ] PagerDuty/Opsgenie alert routing configured

---

## Deployment Sequence (when ready)

1. Set `APP_MODE=staging`, run full test suite
2. Deploy to staging EKS cluster
3. Run E2E tests against staging
4. Wire real provider credentials (Vault/Secrets Manager)
5. Set `APP_MODE=production`, re-run config guard tests
6. Deploy to production EKS cluster
7. Verify governance sweep runs at 07:00 WAT on first day
8. Confirm audit chain integrity after first 24h

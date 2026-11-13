# Changelog — fintech-microservices-core

All notable changes follow [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased] — 2026-06-27

### Added
- **12-step production migration** — full transition from mock-data-driven UI to production-grade system
- `src/server/operations.ts` — replaced in-memory Maps with SQLite-backed persistence via `better-sqlite3`
- `src/server/ledger.ts` — real double-entry ledger replacing `getMockLedgerSnapshot()`
- `src/server/config.ts` — APP_MODE gating (`mock` / `staging` / `production`) with hard production guards
- `src/server/providers/card_provider.ts` — card issuance provider adapter (mock → live)
- `src/server/providers/conversion_provider.ts` — fiat-to-BTC conversion provider adapter
- `app/api/deposits/route.ts` — DB-wired deposit routes with ledger credit on creation
- `app/api/cards/route.ts` — DB-wired card routes with provider provisioning
- `app/api/compliance/route.ts` — compliance sweep proxy (mock + live mode)
- `app/api/audit/route.ts` — immutable audit log proxy, admin-only
- `app/page.tsx` — production React dashboard: all state from real API calls, no in-memory mocks
- `tests/unit/test_compliance_engine.py` — GovernanceEngine unit tests
- `tests/unit/test_audit_chain.py` — AuditTrailAgent chain integrity tests
- `tests/unit/test_screening_rules.py` — RuleEngine unit tests
- `tests/integration/test_api_routes.py` — card/fund route integration tests
- `tests/security/test_webhook_signature.py` — HMAC security tests (timing attack resistance)
- `tests/e2e/test_deposit_flow.py` — full deposit→ledger E2E flow
- `Makefile` — developer CLI: install, lint, test, sweep, audit, docker, push
- `docs/compliance-evidence.md` — partner-facing compliance evidence document
- `docs/production-readiness.md` — production readiness checklist

### Changed
- `compliance_agents/screening/agent.py` — triple LLM cascade (OpenAI → Groq → Mistral) v3.0.0
- `compliance_agents/shared/storage.py` — `llm_model`, `llm_prompt_version`, `has_llm_analysis` columns
- `compliance_agents/audit_trail/agent.py` — quarantine model for corrupt entries

### Fixed
- Audit chain sequences 37–38: corrupt null-hash entries quarantined, chain re-stitched (54 valid + 2 quarantined)
- `verify_chain_integrity` — handles corrupt rows without false broken-link reports
- `_append` — anchors new entries to last valid hash, skips quarantined rows

---

## [0.3.0] — 2026-06-07

### Added
- Triple LLM provider cascade: OpenAI → Groq (llama-3.3-70b-versatile) → Mistral (mistral-small-latest)
- Groq and Mistral API key support
- Provider label stored in `screening_results.llm_model`

### Changed
- ScreeningAgent: primary provider remains OpenAI gpt-4o; Groq/Mistral as fallback
- requirements.txt: added `groq>=0.4.0`

---

## [0.2.0] — 2026-06-06

### Changed
- Replaced Anthropic/Claude with OpenAI (gpt-4o) as LLM backend for ScreeningAgent
- Updated `requirements.txt`: `openai>=1.30.0` replaces `anthropic`
- Added `llm_model`, `llm_prompt_version`, `has_llm_analysis` to `screening_results` DB schema

---

## [0.1.0] — 2026-06-01

### Added
- Initial 4-agent compliance system: DataIngestion, Screening, AuditTrail, Reporting
- GovernanceEngine with 16 controls across COBIT 2019, COSO ERM, GAO AI, IIA AI frameworks
- Immutable audit chain with HMAC hash chaining
- Daily governance sweep automation (07:00 WAT)
- Foundry agent definitions (ComplianceAgent, SecurityAgent, LedgerAgent, PlatformAgent, BuildAgent)
- Infrastructure: Terraform modules (VPC, EKS, RDS, ECR, S3, CloudWatch, WAF)
- Kubernetes manifests, monitoring (Prometheus + Grafana + Alertmanager)
- Docker Compose for local development

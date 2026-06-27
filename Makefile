# ─────────────────────────────────────────────────────────────────────────────
# GEM ATR / fintech-microservices-core — Developer Makefile
# ─────────────────────────────────────────────────────────────────────────────

.PHONY: help install lint test test-unit test-integration test-security test-e2e \
        sweep audit build docker-up docker-down push clean

PYTHON        := python3
PIP           := pip3
PYTEST        := pytest
APP_DIR       := apps/gem-atr-digital-easyway
COMPLIANCE    := compliance_agents
BRANCH        := production-infrastructure

help:   ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'

# ── Dependencies ──────────────────────────────────────────────────────────────

install:   ## Install all Python dependencies
	$(PIP) install -r $(COMPLIANCE)/requirements.txt -q
	$(PIP) install pytest pytest-asyncio httpx -q
	cd $(APP_DIR) && npm install

# ── Code quality ──────────────────────────────────────────────────────────────

lint:   ## Run linters (flake8 + tsc)
	flake8 $(COMPLIANCE) --max-line-length=120 --ignore=E501,W503
	cd $(APP_DIR) && npx tsc --noEmit

# ── Tests ─────────────────────────────────────────────────────────────────────

test:   ## Run all tests
	$(PYTEST) tests/ -v --tb=short

test-unit:   ## Run unit tests only
	$(PYTEST) tests/unit/ -v --tb=short

test-integration:   ## Run integration tests (requires services running)
	$(PYTEST) tests/integration/ -v --tb=short

test-security:   ## Run security tests
	$(PYTEST) tests/security/ -v --tb=short

test-e2e:   ## Run E2E tests (requires full stack on localhost)
	$(PYTEST) tests/e2e/ -v --tb=short

# ── Compliance ────────────────────────────────────────────────────────────────

sweep:   ## Run a full governance sweep across all 16 controls
	$(PYTHON) -c "from $(COMPLIANCE).governance.engine import GovernanceEngine; \
	  r = GovernanceEngine().run_full_sweep(); \
	  [print(f'  {fw.framework.value}: {sum(1 for c in fw.controls if c[\"status\"]==\"satisfied\")}/{len(fw.controls)}') for fw in r.frameworks]"

audit:   ## Verify audit chain integrity
	$(PYTHON) -c "from $(COMPLIANCE).audit_trail.agent import AuditTrailAgent; \
	  r = AuditTrailAgent().verify_chain_integrity(); \
	  print(f'Chain OK: {r[\"integrity_ok\"]} | Verified: {r[\"verified_entries\"]} | Quarantined: {r[\"quarantined_entries\"]}')"

# ── Local development ─────────────────────────────────────────────────────────

build:   ## Build Next.js app
	cd $(APP_DIR) && npm run build

dev:   ## Start Next.js dev server
	cd $(APP_DIR) && npm run dev

docker-up:   ## Start all services via Docker Compose
	docker compose -f docker/docker-compose.yml up -d --build

docker-down:   ## Stop all Docker services
	docker compose -f docker/docker-compose.yml down

# ── Git ───────────────────────────────────────────────────────────────────────

push:   ## Commit and push to production-infrastructure branch
	git add -A
	git commit -m "chore: production build update $$(date +'%Y-%m-%d')"
	git push origin $(BRANCH)

# ── Clean ─────────────────────────────────────────────────────────────────────

clean:   ## Remove build artifacts
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	rm -f gem-atr.db
	cd $(APP_DIR) && rm -rf .next node_modules 2>/dev/null || true

# fintech-microservices-core

Production-ready monorepo for a fintech app.

## Repo Structure
- `apps/web` — Next.js frontend
- `services/api` — Core API service
- `packages/shared` — Shared types/validation
- `infra` — Local infrastructure (Postgres)

## Local Development (baseline)
1. Copy env
   - `cp .env.example .env`
2. Start Postgres
   - `docker compose -f infra/docker-compose.yml up -d postgres`

> API and Web placeholders will be wired in subsequent steps.

## Docker
- Postgres runs on `5432`
- API planned on `4000`
- Web planned on `3000`

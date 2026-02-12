# fintech-microservices-core
Microservices Core for Alliance Trust Realty's Crypto Debit Card Platform. Features a secure, HMAC-validated Fiat-to-Bitcoin converter and the client-facing card management API.


## Vercel Deployment (API Gateway)

This repository now includes a root-level `vercel.json` that maps paths to the two FastAPI services:

- `/api/v1/*` -> `card_platform_service`
- `/webhook/*` and `/internal/*` -> `converter_service`
- `/` and `/health` -> lightweight health app (`api/index.py`)

If your Vercel deployment previously returned `404: NOT_FOUND`, redeploy from the repository root so Vercel picks up this configuration.

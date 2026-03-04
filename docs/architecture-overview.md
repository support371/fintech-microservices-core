# Architecture Overview

## System Architecture

The Fintech Microservices Platform is a bank-grade, compliance-ready system designed for secure financial operations including crypto debit card issuance, fiat-to-BTC conversion, and banking event processing.

## Microservices Architecture

```
                    ┌─────────────────────┐
                    │   AWS WAF + ALB      │
                    │   (TLS Termination)  │
                    └─────────┬───────────┘
                              │
                    ┌─────────▼───────────┐
                    │   Kubernetes Ingress │
                    │   (Path-based routing│
                    └──┬──────┬──────┬────┘
                       │      │      │
         ┌─────────────┤      │      ├─────────────┐
         │             │      │      │             │
         ▼             ▼      │      ▼             │
┌────────────────┐ ┌──────────┴──┐ ┌──────────────┐│
│ Card Platform  │ │  Converter  │ │    GEM       ││
│ Service        │ │  Service    │ │  Dashboard   ││
│ (FastAPI:8001) │ │ (FastAPI:8000)│ │ (Next.js:3000)│
└───────┬────────┘ └──────┬──────┘ └──────────────┘│
        │                 │                         │
        │  Internal HTTP  │                         │
        ├────────────────►│                         │
        │                 │                         │
        ▼                 ▼                         │
┌────────────────┐ ┌──────────────┐                │
│   PostgreSQL   │ │  Striga API  │                │
│   (AWS RDS)    │ │  (External)  │                │
└────────────────┘ └──────────────┘                │
```

## Service Descriptions

### Card Platform Service (port 8001)
- **Purpose**: Client-facing API for card issuance and fund loading
- **Endpoints**:
  - `POST /api/v1/cards/issue` - Issue a new crypto debit card (KYC Tier 3+ required)
  - `POST /api/v1/funds/load` - Load fiat funds, triggering conversion
  - `GET /health` - Kubernetes liveness probe
  - `GET /ready` - Kubernetes readiness probe (checks DB connectivity)
- **Dependencies**: PostgreSQL (KYC data), Converter Service (fund transfers), Striga API (card issuance)

### Converter Service (port 8000)
- **Purpose**: Fiat-to-BTC conversion and webhook processing
- **Endpoints**:
  - `POST /internal/transfer_funds` - Internal endpoint for fund conversion
  - `POST /webhook/fiat_received` - External webhook from Striga (HMAC-SHA256 validated)
  - `GET /health` - Kubernetes liveness probe
  - `GET /ready` - Kubernetes readiness probe
- **Security**: HMAC-SHA256 webhook signature validation with constant-time comparison

### GEM Dashboard (port 3000)
- **Purpose**: Next.js fintech dashboard for end users
- **Features**: Deposit management, card operations, admin dashboard, banking webhooks
- **API Routes**: Health checks, cron email worker, banking webhooks, admin operations

## Compliance Architecture

### KYC (Know Your Customer)
- Minimum KYC tier enforced via `KYC_MINIMUM_TIER` environment variable (default: Tier 3)
- KYC status stored in PostgreSQL `users` table
- Card issuance gated by KYC tier validation

### AML (Anti-Money Laundering)
- Transaction limits enforced via environment variables:
  - `AML_SINGLE_TRANSACTION_LIMIT` (default: $10,000)
  - `AML_DAILY_TRANSACTION_LIMIT` (default: $50,000)
  - `AML_MONTHLY_TRANSACTION_LIMIT` (default: $200,000)
- Idempotency checks prevent duplicate transaction processing

### Audit Logging
- All compliance events logged as structured JSON
- Log retention: 5 years (1,827 days) via CloudWatch and S3 Glacier
- Events logged: KYC decisions, AML checks, webhook verification, transaction attempts, authentication events

## Security Layers

1. **Network**: AWS WAF, VPC private subnets, Network Policies
2. **Transport**: TLS 1.3 everywhere, ALB SSL termination
3. **Application**: HMAC-SHA256 webhook validation, JWT authentication
4. **Data**: AES-256 encryption at rest (RDS, S3, EKS secrets via KMS)
5. **Secrets**: AWS Secrets Manager with automatic rotation
6. **Access Control**: IAM least privilege, Kubernetes RBAC, non-root containers
7. **Compliance**: OFAC geo-blocking, rate limiting, SQL injection protection

## Deployment Model

- **Cloud Provider**: AWS (EKS, RDS, ECR, S3, CloudWatch, WAF, Secrets Manager)
- **Container Orchestration**: Kubernetes on EKS
- **Infrastructure as Code**: Terraform modules
- **CI/CD**: GitHub Actions (lint → test → security scan → build → push → deploy)
- **Monitoring**: Prometheus + Grafana + AlertManager + CloudWatch

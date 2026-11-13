# Developer Guide

## Prerequisites

- Python 3.11+
- Node.js 20+
- Docker & Docker Compose
- AWS CLI v2
- kubectl
- Terraform >= 1.5

## Local Development Setup

### 1. Clone the Repository

```bash
git clone https://github.com/support371/fintech-microservices-core.git
cd fintech-microservices-core
```

### 2. Environment Configuration

```bash
# Copy the example env file
cp .env.example .env

# Edit with your local values
# Required variables:
#   STRIGA_WEBHOOK_SECRET - Webhook signing secret
#   STRIGA_API_KEY        - Striga API key
#   STRIGA_API_BASE_URL   - Striga API endpoint
#   CONVERTER_INTERNAL_URL - URL to converter service
#   DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD - Database
```

### 3. Running Services with Docker Compose

```bash
# Start all services (includes PostgreSQL)
cd docker
docker compose up -d

# View logs
docker compose logs -f

# Stop all services
docker compose down
```

### 4. Running Services Locally (without Docker)

```bash
# Install Python dependencies
pip install -r requirements.txt

# Start the Converter Service
uvicorn converter_service.main:app --host 0.0.0.0 --port 8000 --reload

# In a separate terminal, start the Card Platform Service
uvicorn card_platform_service.main:app --host 0.0.0.0 --port 8001 --reload
```

### 5. Running the GEM Dashboard

```bash
cd apps/gem-atr-digital-easyway
npm install
npm run dev
# Dashboard available at http://localhost:3000
```

## Testing

### Unit Tests

```bash
# Python services
pip install pytest pytest-cov httpx
python -m pytest tests/ -v --cov

# Next.js dashboard
cd apps/gem-atr-digital-easyway
npm run lint
```

### Webhook Simulation

```bash
# Use the validation script to test webhook processing
python validation/simulate_webhook.py
```

### Load Testing

```bash
# Using Locust for load testing
pip install locust
locust -f validation/locustfile.py --host=http://localhost:8000
```

### Health Checks

```bash
# Card Platform Service
curl http://localhost:8001/health
curl http://localhost:8001/ready

# Converter Service
curl http://localhost:8000/health
curl http://localhost:8000/ready

# GEM Dashboard
curl http://localhost:3000/api/health
```

## Project Structure

```
fintech-microservices-core/
├── api/                       # Vercel serverless entrypoints
├── card_platform_service/     # Card issuance + KYC service
├── converter_service/         # Fiat-to-BTC conversion service
├── apps/gem-atr-digital-easyway/ # Next.js dashboard
├── docker/                    # Production Dockerfiles
├── kubernetes/                # Kubernetes manifests
├── infrastructure/            # Terraform IaC
├── monitoring/                # Prometheus, Grafana, AlertManager
├── docs/                      # Documentation
├── validation/                # Testing scripts
└── .github/workflows/         # CI/CD pipelines
```

## Code Conventions

- **Python**: Follow PEP 8, max line length 120
- **TypeScript**: ESLint + Prettier (Next.js config)
- **Logging**: Structured JSON format for all services
- **Error Handling**: All API errors return structured JSON responses
- **Security**: Never hardcode secrets; use environment variables

## Branch Strategy

- `main` - Production-ready code
- `production-infrastructure` - Infrastructure and deployment configurations
- Feature branches: `feature/<description>`
- Hotfix branches: `hotfix/<description>`

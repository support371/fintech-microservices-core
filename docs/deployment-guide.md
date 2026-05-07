# Deployment Guide

## AWS Account Setup

### Prerequisites

1. AWS account with administrative access
2. AWS CLI configured with appropriate credentials
3. Terraform >= 1.5 installed
4. kubectl installed
5. Docker installed

### Step 1: Create Terraform Backend

```bash
# Create S3 bucket for Terraform state
aws s3api create-bucket \
  --bucket fintech-terraform-state \
  --region us-east-1

# Enable versioning
aws s3api put-bucket-versioning \
  --bucket fintech-terraform-state \
  --versioning-configuration Status=Enabled

# Enable encryption
aws s3api put-bucket-encryption \
  --bucket fintech-terraform-state \
  --server-side-encryption-configuration '{
    "Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]
  }'

# Create DynamoDB table for state locking
aws dynamodb create-table \
  --table-name fintech-terraform-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST
```

### Step 2: Configure Terraform Variables

```bash
cd infrastructure
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your values
```

### Step 3: Deploy Infrastructure

```bash
cd infrastructure

# Initialize Terraform
terraform init

# Review the plan
terraform plan -out=tfplan

# Apply the infrastructure
terraform apply tfplan
```

### Step 4: Configure kubectl

```bash
# Update kubeconfig for the new EKS cluster
aws eks update-kubeconfig \
  --name fintech-production \
  --region us-east-1
```

### Step 5: Store Secrets in AWS Secrets Manager

```bash
# Store Striga API credentials
aws secretsmanager put-secret-value \
  --secret-id fintech/production/striga-api \
  --secret-string '{
    "STRIGA_WEBHOOK_SECRET": "<your-webhook-secret>",
    "STRIGA_API_KEY": "<your-api-key>",
    "STRIGA_API_BASE_URL": "https://api.striga.com/v1"
  }'

# Database credentials are auto-managed by RDS
```

### Step 6: Deploy Kubernetes Resources

```bash
# Apply namespace
kubectl apply -f kubernetes/namespace.yaml

# Apply secrets and configmaps
kubectl apply -f kubernetes/secrets.yaml
kubectl apply -f kubernetes/configmaps.yaml

# Deploy services
kubectl apply -f kubernetes/deployments/
kubectl apply -f kubernetes/services/

# Apply network policies
kubectl apply -f kubernetes/gateway.yaml

# Apply ingress
kubectl apply -f kubernetes/ingress.yaml
```

### Step 7: Verify Deployment

```bash
# Check all pods are running
kubectl get pods -n fintech-production

# Check services
kubectl get svc -n fintech-production

# Check health endpoints
kubectl port-forward svc/card-platform-service 8001:8001 -n fintech-production
curl http://localhost:8001/health

kubectl port-forward svc/converter-service 8000:8000 -n fintech-production
curl http://localhost:8000/health
```

## CI/CD Pipeline

The GitHub Actions workflow (`.github/workflows/production-deploy.yml`) automates:

1. **Lint & Static Analysis** - flake8, bandit, ESLint
2. **Tests** - pytest with coverage
3. **Security Scan** - Trivy vulnerability scan, TruffleHog secrets detection
4. **Build** - Multi-stage Docker builds pushed to ECR
5. **Deploy** - Rolling update to EKS with smoke tests

### Required GitHub Secrets

| Secret | Description |
|--------|-------------|
| `AWS_DEPLOY_ROLE_ARN` | IAM role ARN for GitHub OIDC authentication |

### Required GitHub Environments

- `production` - With deployment protection rules

## Environment Variables Reference

| Variable | Service | Description | Default |
|----------|---------|-------------|---------|
| `STRIGA_WEBHOOK_SECRET` | Converter | Webhook signing secret | Required |
| `STRIGA_API_KEY` | Both | Striga API key | Required |
| `STRIGA_API_BASE_URL` | Both | Striga API endpoint | Required |
| `CONVERTER_INTERNAL_URL` | Card Platform | Internal converter URL | Required |
| `DB_HOST` | Card Platform | PostgreSQL host | Required |
| `DB_PORT` | Card Platform | PostgreSQL port | 5432 |
| `DB_NAME` | Card Platform | Database name | fintech |
| `DB_USER` | Card Platform | Database username | Required |
| `DB_PASSWORD` | Card Platform | Database password | Required |
| `KYC_MINIMUM_TIER` | Card Platform | Minimum KYC tier | 3 |
| `AML_SINGLE_TRANSACTION_LIMIT` | Both | Max single transaction | 10000 |
| `AML_DAILY_TRANSACTION_LIMIT` | Both | Max daily transactions | 50000 |
| `AML_MONTHLY_TRANSACTION_LIMIT` | Both | Max monthly transactions | 200000 |
| `CRON_SECRET` | Dashboard | Cron job auth token | Required |
| `BANKING_WEBHOOK_SECRET` | Dashboard | Banking webhook secret | Required |
| `LOG_LEVEL` | All | Logging level | INFO |

## Monitoring

After deployment, monitoring is available via:

- **Grafana Dashboard**: Deployed via Kubernetes (port-forward to access)
- **CloudWatch**: AWS Console > CloudWatch > Dashboards > fintech-production-overview
- **Prometheus Alerts**: Configured in `monitoring/prometheus/alerts/`
- **AlertManager**: Email notifications to configured teams

## Rollback Procedure

```bash
# View deployment history
kubectl rollout history deployment/card-platform-service -n fintech-production

# Rollback to previous version
kubectl rollout undo deployment/card-platform-service -n fintech-production
kubectl rollout undo deployment/converter-service -n fintech-production
kubectl rollout undo deployment/gem-dashboard -n fintech-production

# Verify rollback
kubectl rollout status deployment/card-platform-service -n fintech-production
```

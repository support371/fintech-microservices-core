# Staging Deployment Guide

This document provides instructions for deploying the `converter_service` and `card_platform_service` to a staging environment on Google Cloud Run.

## 1. Prerequisites

- Google Cloud SDK (`gcloud`) installed and configured.
- Docker installed and configured to push to Google Container Registry (GCR).
- Access to the GCP project and the necessary permissions to deploy to Cloud Run and access Secret Manager.

## 2. Environment Variables

The following environment variables must be configured for the services to run correctly. Secrets should be stored in GCP Secret Manager and injected into the Cloud Run instances as environment variables.

### Converter Service (`converter_service`)

| Environment Variable      | Description                                     | Secret |
| ------------------------- | ----------------------------------------------- | ------ |
| `STRIGA_WEBHOOK_SECRET`   | The secret key used to validate Striga webhooks. | Yes    |
| `STRIGA_API_KEY`          | The API key for the Striga API.                 | Yes    |
| `STRIGA_API_BASE_URL`     | The base URL for the Striga API.                | No     |
| `CONVERTER_INTERNAL_URL`  | The internal URL of the converter service.      | No     |

### Card Platform Service (`card_platform_service`)

| Environment Variable     | Description                                       | Secret |
| ------------------------ | ------------------------------------------------- | ------ |
| `CONVERTER_INTERNAL_URL` | The internal URL of the converter service.        | No     |
| `STRIGA_API_BASE_URL`    | The base URL for the Striga API.                  | No     |
| `DB_HOST`                | The hostname or IP address of the PostgreSQL DB.  | Yes    |
| `DB_PORT`                | The port of the PostgreSQL DB.                    | No     |
| `DB_NAME`                | The name of the PostgreSQL DB.                    | Yes    |
| `DB_USER`                | The username for the PostgreSQL DB.               | Yes    |
| `DB_PASSWORD`            | The password for the PostgreSQL DB.               | Yes    |

## 3. Building and Deploying

### Build the Docker Images

For each service, navigate to the service's directory and run the following commands to build the Docker image and push it to GCR:

```bash
# For the converter_service
cd converter_service
docker build -t gcr.io/[PROJECT-ID]/converter-service:latest .
docker push gcr.io/[PROJECT-ID]/converter-service:latest
cd ..

# For the card_platform_service
cd card_platform_service
docker build -t gcr.io/[PROJECT-ID]/card-platform-service:latest .
docker push gcr.io/[PROJECT-ID]/card-platform-service:latest
cd ..
```

### Deploy to Cloud Run

Deploy the services to Cloud Run using the `gcloud` command-line tool. You will need to replace `[PROJECT-ID]` with your GCP project ID and set the environment variables accordingly.

```bash
# Deploy the converter_service
gcloud run deploy converter-service \
  --image gcr.io/[PROJECT-ID]/converter-service:latest \
  --platform managed \
  --region [REGION] \
  --allow-unauthenticated \
  --set-env-vars="STRIGA_API_BASE_URL=https://api.striga.com/v1" \
  --update-secrets=STRIGA_WEBHOOK_SECRET=[SECRET-NAME]:latest,STRIGA_API_KEY=[SECRET-NAME]:latest

# Deploy the card_platform_service
gcloud run deploy card-platform-service \
  --image gcr.io/[PROJECT-ID]/card-platform-service:latest \
  --platform managed \
  --region [REGION] \
  --allow-unauthenticated \
  --set-env-vars="STRIGA_API_BASE_URL=https://api.striga.com/v1,CONVERTER_INTERNAL_URL=http://converter-service" \
  --update-secrets=DB_HOST=[SECRET-NAME]:latest,DB_NAME=[SECRET-NAME]:latest,DB_USER=[SECRET-NAME]:latest,DB_PASSWORD=[SECRET-NAME]:latest
```

## 4. Validation

After deployment, you can use the provided validation scripts to test the services.

### Simulate a Webhook

Run the `simulate_webhook.py` script to test the `converter_service`'s webhook endpoint.

```bash
python3 validation/simulate_webhook.py
```

### Load Test the Converter Service

Use Locust to load test the `converter_service`'s internal transfer endpoint.

```bash
locust -f validation/locustfile.py --host https://[CONVERTER-STAGING-URL]
```

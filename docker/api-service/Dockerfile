# API Gateway Service - Production Dockerfile
# Multi-stage build for minimal image size

FROM python:3.11-slim AS builder

WORKDIR /build

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# -----------------------------------------------------------
FROM python:3.11-slim

# Security: run as non-root
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

WORKDIR /app

COPY --from=builder /install /usr/local
COPY api/ ./api/
COPY card_platform_service/ ./card_platform_service/
COPY converter_service/ ./converter_service/

# Health check endpoint is provided by FastAPI at /health
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

USER appuser

EXPOSE 8080

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

CMD ["uvicorn", "api.index:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "4", "--access-log"]

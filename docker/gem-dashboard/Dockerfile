# GEM Dashboard (Next.js) - Production Dockerfile
# Multi-stage build for minimal image size

FROM node:20-alpine AS builder

WORKDIR /app

COPY apps/gem-atr-digital-easyway/package.json apps/gem-atr-digital-easyway/package-lock.json ./
RUN npm ci --production=false

COPY apps/gem-atr-digital-easyway/ .
RUN npm run build

# -----------------------------------------------------------
FROM node:20-alpine

# Security: run as non-root
RUN addgroup -S appgroup && adduser -S appuser -G appgroup

WORKDIR /app

COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD wget -qO- http://localhost:3000/api/health || exit 1

USER appuser

EXPOSE 3000

ENV NODE_ENV=production \
    PORT=3000 \
    HOSTNAME=0.0.0.0

CMD ["node", "server.js"]

# Placeholder Dockerfile for API service
FROM node:20-alpine AS base
WORKDIR /app
COPY services/api/package*.json ./
RUN npm ci --omit=dev
COPY services/api ./
EXPOSE 4000
CMD ["node", "dist/index.js"]

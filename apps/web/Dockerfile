# Placeholder Dockerfile for Next.js app
FROM node:20-alpine AS base
WORKDIR /app
COPY apps/web/package*.json ./
RUN npm ci --omit=dev
COPY apps/web ./
EXPOSE 3000
CMD ["npm", "start"]

# syntax=docker/dockerfile:1

# Stage 1: Dependency resolution and build
FROM node:22-alpine AS builder

WORKDIR /app

# Install build dependencies
COPY package*.json tsconfig.json ./
RUN npm ci

# Copy application source and compile TypeScript
COPY src/ ./src/
RUN npm run build

# Prune development dependencies to keep production footprint minimal
RUN npm prune --production

# Stage 2: Minimal, secure production runtime
FROM node:22-alpine AS runner

WORKDIR /app

# Run as non-root user for security best practices
USER node

# Copy production node_modules and compiled output
COPY --chown=node:node --from=builder /app/node_modules ./node_modules
COPY --chown=node:node --from=builder /app/dist ./dist
COPY --chown=node:node --from=builder /app/package.json ./package.json

# Environment defaults
ENV NODE_ENV=production
ENV PORT=3000
ENV HOST=0.0.0.0

EXPOSE 3000

# Health check to ensure readiness
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://localhost:3000/health || exit 1

CMD ["node", "dist/server.js"]

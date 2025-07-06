# Multi-stage build for Ceneca Enterprise
# Stage 1: Build the React frontend
FROM node:18-alpine AS frontend-build

WORKDIR /app/frontend

# Copy frontend source
COPY server/web/package*.json ./
COPY server/web/bun.lockb ./

# Install dependencies
RUN npm install

# Copy frontend source code
COPY server/web/ ./

# Build production frontend
RUN npm run build

# Verify build output
RUN ls -la /app/frontend/dist/

# Stage 2: Build the Python backend
FROM python:3.11-slim AS backend-build

WORKDIR /app/backend

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy Python requirements
COPY server/agent/requirements.txt ./

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source
COPY server/agent/ ./

# Stage 3: Final production image
FROM python:3.11-slim

# Install nginx and system dependencies
RUN apt-get update && apt-get install -y \
    nginx \
    curl \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy backend from build stage
COPY --from=backend-build /app/backend ./agent
COPY --from=backend-build /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=backend-build /usr/local/bin /usr/local/bin

# Copy frontend build from build stage
COPY --from=frontend-build /app/frontend/dist ./static

# Create directories
RUN mkdir -p /app/config /app/data /app/logs /app/certs /app/cache

# Copy nginx configuration template
COPY deploy/config/nginx.conf /etc/nginx/nginx.conf

# Copy supervisor configuration
COPY deploy/config/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Copy startup script
COPY deploy/scripts/start.sh /app/start.sh
RUN chmod +x /app/start.sh

# Create nginx user and set permissions
RUN chown -R www-data:www-data /app/static && \
    chown -R www-data:www-data /var/log/nginx && \
    chown -R root:root /app/agent

# Expose ports
EXPOSE 80 443

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:80/health || exit 1

# Start services using supervisor
CMD ["/app/start.sh"] 
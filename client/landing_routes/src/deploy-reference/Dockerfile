FROM python:3.10-slim

WORKDIR /app

# Copy requirements file from parent directory (root of the project)
COPY server/requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create config directory
RUN mkdir -p /root/.data-connector

# Copy application code from parent directory (root of the project)
COPY server /app/server

# Expose the agent port
EXPOSE 8787

# Install curl for health check
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8787/health || exit 1

# Set environment variables
ENV AGENT_PORT=8787
ENV PYTHONUNBUFFERED=1

# Run the agent
CMD ["python", "server/main.py"] 
#!/bin/bash

# Start the Ceneca stack
cd "$(dirname "$0")"

# Build local Docker images
echo "Building Docker images locally..."
if [ -f "Dockerfile" ] && [ -f "Dockerfile.mcp" ]; then
  docker build -t ceneca/agent:latest -f Dockerfile .
  docker build -t ceneca/slack-mcp:latest -f Dockerfile.mcp .
else
  echo "Dockerfiles not found. Skipping build step."
  echo "Make sure you have the required images available."
fi

# Get API key
if [ -z "${LLM_API_KEY}" ]; then
  # Try to extract from config.yaml
  if command -v yq &> /dev/null; then
    export LLM_API_KEY=$(yq e '.llm.api_key' ~/.data-connector/config.yaml 2>/dev/null)
    echo "Using LLM API key from config.yaml"
  else
    echo "⚠️  WARNING: LLM_API_KEY is not set. You must set this for the agent to work properly."
    echo "Example: export LLM_API_KEY=your-api-key"
    export LLM_API_KEY="set-your-api-key"
  fi
fi

# Start only the required services
echo "Starting required services..."
# Start Postgres first (base requirement)
docker-compose up -d postgres

# Start the agent last so dependencies are ready
echo "Starting Ceneca agent..."
docker-compose up -d ceneca-agent

# Show status
echo "Service status:"
docker-compose ps

echo ""
echo "Ceneca is now running!"
AGENT_PORT=$(docker-compose port ceneca-agent 8787 2>/dev/null | cut -d: -f2 || echo "8787")
echo "Web interface available at: http://localhost:${AGENT_PORT}"
echo ""
echo "To view logs: docker-compose logs -f ceneca-agent"
echo "To stop: docker-compose down" 
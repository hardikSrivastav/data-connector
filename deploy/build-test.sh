#!/bin/bash

# Build Ceneca Enterprise for Testing
set -e

echo "=== Building Ceneca Enterprise for Testing ==="

# Check if we're in the right directory
if [[ ! -f "docker-compose.yml" ]]; then
    echo "❌ Error: docker-compose.yml not found"
    echo "Please run this script from the root project directory"
    exit 1
fi

# Build the Docker image
echo "🔨 Building Docker image..."
docker build -f deploy/Dockerfile -t ceneca/enterprise:latest .

echo "✅ Build complete!"
echo ""
echo "Next steps for testing:"
echo "1. cd deploy/"
echo "2. ./scripts/setup.sh"
echo "3. docker-compose up -d"
echo "4. ./scripts/test-deployment.sh --domain localhost"

echo ""
echo "Or for quick local testing:"
echo "1. cd deploy/"
echo "2. ./scripts/generate-self-signed.sh localhost"
echo "3. Copy your config files to deploy/config/"
echo "4. docker-compose up -d" 
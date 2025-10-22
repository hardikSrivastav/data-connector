#!/bin/bash

# Template Editor Service Startup Script

echo "🚀 Starting Template Editor Service..."

# Check if .env file exists
if [ ! -f .env ]; then
    echo "❌ .env file not found!"
    echo "Please copy .env.example to .env and configure your Anthropic API key"
    exit 1
fi

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running!"
    echo "Please start Docker and try again"
    exit 1
fi

# Build and start services
echo "🔧 Building and starting services..."
docker-compose up --build -d

echo "✅ Services started successfully!"
echo "🌐 Frontend: http://localhost:8500"
echo "🔧 Backend API: http://localhost:8501"
echo "📚 API Documentation: http://localhost:8501/docs"

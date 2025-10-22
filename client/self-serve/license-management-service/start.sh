#!/bin/bash

echo "🚀 Starting Ceneca License Management Service..."

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker and try again."
    exit 1
fi

# Build and start services
echo "📦 Building and starting services..."
docker-compose up --build -d

# Wait for services to be ready
echo "⏳ Waiting for services to start..."
sleep 10

# Check service health
echo "🔍 Checking service health..."

# Check database
if docker-compose exec -T license-db pg_isready -U license_user -d license_db > /dev/null 2>&1; then
    echo "✅ Database is ready"
else
    echo "❌ Database is not ready"
fi

# Check API
if curl -f http://localhost:8020/health > /dev/null 2>&1; then
    echo "✅ API is ready"
else
    echo "❌ API is not ready"
fi

# Show status
echo ""
echo "🎉 Ceneca License Management Service is starting!"
echo ""
echo "📊 Access the services:"
echo "   Frontend:  http://localhost:3020"
echo "   API:       http://localhost:8020"
echo "   Agent:     http://localhost:9020"
echo ""
echo "🔧 Useful commands:"
echo "   View logs:     docker-compose logs -f"
echo "   Stop services: docker-compose down"
echo "   Restart:       docker-compose restart"
echo ""

# Follow logs
echo "📋 Following logs (Ctrl+C to exit)..."
docker-compose logs -f
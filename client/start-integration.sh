#!/bin/bash

echo "🚀 Starting Ceneca Integration Environment"
echo "========================================="

# Check if .env.integration exists
if [ ! -f .env.integration ]; then
    echo "📝 Creating .env.integration file..."
    cp .env.integration.example .env.integration
    echo "❗ Please edit .env.integration with your API keys before proceeding"
    echo ""
    echo "Required variables:"
    echo "- ANTHROPIC_API_KEY (for AI template editing)"
    echo "- RAZORPAY_KEY_ID & RAZORPAY_KEY_SECRET (for payments)"
    echo ""
    read -p "Have you configured your API keys in .env.integration? (y/n): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Please configure .env.integration and run this script again."
        exit 1
    fi
fi

# Load environment variables (filter out comments and empty lines)
export $(grep -v '^#' .env.integration | grep -v '^$' | xargs)

echo "🐳 Starting Docker services..."
echo ""
echo "Services that will be started:"
echo "- Main Frontend:      http://localhost:3000"
echo "- Main Backend:       http://localhost:3001" 
echo "- Template Editor:    http://localhost:8500"
echo "- Template API:       http://localhost:8501"
echo "- PostgreSQL:         localhost:5460"
echo ""

# Build and start services
docker-compose -f docker-compose.integration.yml up --build -d

echo ""
echo "🎉 Integration environment started successfully!"
echo ""
echo "📍 Access Points:"
echo "   Main App:           http://localhost:3000"
echo "   Deployment Portal:  http://localhost:3000/deployment"
echo "   Template Editor:    http://localhost:8500"
echo "   API Documentation:  http://localhost:8501/docs"
echo ""
echo "🔧 To stop the environment:"
echo "   docker-compose -f docker-compose.integration.yml down"
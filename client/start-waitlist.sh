#!/bin/bash

# Stop any running containers
docker-compose -f docker/docker-compose.yml down

# Start the backend and database
docker-compose -f docker/docker-compose.yml up -d

# Wait for backend to be ready
echo "Waiting for backend to be ready..."
sleep 5

# Start the Next.js development server
echo "Starting Next.js development server..."
npm run dev 
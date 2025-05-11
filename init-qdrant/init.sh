#!/bin/bash

# Wait for Qdrant to be ready
echo "Waiting for Qdrant to be ready..."
while ! curl -s http://localhost:6333/readiness > /dev/null; do
    sleep 2
done
echo "Qdrant is ready!"

# Run the Python initialization script
echo "Running initialization script..."
cd /qdrant/init
python3 -m setup_corporate_data

echo "Qdrant initialization completed!" 
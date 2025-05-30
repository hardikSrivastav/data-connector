#!/bin/bash

# Development startup script for Ceneca Data Connector
# This script starts both the web client and agent server

set -e

echo "🚀 Starting Ceneca Data Connector Development Environment"
echo "=================================================="

# Function to check if a port is in use
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo "⚠️  Port $port is already in use"
        return 1
    fi
    return 0
}

# Function to start the agent server
start_agent() {
    echo "🤖 Starting Agent Server..."
    cd server
    
    # Set environment variables for development
    export VITE_AGENT_BASE_URL="http://localhost:8787"
    export DATABASE_URL="${DATABASE_URL:-postgresql://notion_user:notion_password@localhost:5432/notion_clone}"
    
    # Check if Python virtual environment exists
    if [ ! -d "venv" ]; then
        echo "📦 Creating Python virtual environment..."
        python3 -m venv venv
    fi
    
    # Activate virtual environment
    source venv/bin/activate
    
    # Install dependencies if requirements.txt exists
    if [ -f "requirements.txt" ]; then
        echo "📦 Installing Python dependencies..."
        pip install -r requirements.txt
    fi
    
    echo "🎯 Agent server starting on http://localhost:8787"
    echo "📖 API docs available at http://localhost:8787/docs"
    
    # Start the agent server
    python agent_server.py &
    AGENT_PID=$!
    echo $AGENT_PID > agent.pid
    echo "✅ Agent server started (PID: $AGENT_PID)"
}

# Function to start the web client
start_web() {
    echo "🌐 Starting Web Client..."
    cd server/web
    
    # Set environment variables
    export VITE_AGENT_BASE_URL="http://localhost:8787"
    export VITE_API_BASE="http://localhost:8787"
    export VITE_EDITION="enterprise"
    
    # Install dependencies
    if [ ! -d "node_modules" ]; then
        echo "📦 Installing Node.js dependencies..."
        npm install
    fi
    
    echo "🎯 Web client starting on http://localhost:5173"
    
    # Start the web client
    npm run dev &
    WEB_PID=$!
    echo $WEB_PID > web.pid
    echo "✅ Web client started (PID: $WEB_PID)"
}

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "🛑 Shutting down servers..."
    
    # Kill agent server
    if [ -f "server/agent.pid" ]; then
        AGENT_PID=$(cat server/agent.pid)
        if kill -0 $AGENT_PID 2>/dev/null; then
            kill $AGENT_PID
            echo "✅ Agent server stopped"
        fi
        rm -f server/agent.pid
    fi
    
    # Kill web client
    if [ -f "server/web/web.pid" ]; then
        WEB_PID=$(cat server/web/web.pid)
        if kill -0 $WEB_PID 2>/dev/null; then
            kill $WEB_PID
            echo "✅ Web client stopped"
        fi
        rm -f server/web/web.pid
    fi
    
    echo "👋 Development environment stopped"
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

# Check if ports are available
echo "🔍 Checking port availability..."
if ! check_port 8787; then
    echo "❌ Agent server port (8787) is in use. Please stop the conflicting service."
    exit 1
fi

if ! check_port 5173; then
    echo "❌ Web client port (5173) is in use. Please stop the conflicting service."
    exit 1
fi

# Start services
start_agent
sleep 3  # Give agent server time to start

start_web
sleep 2  # Give web client time to start

echo ""
echo "🎉 Development environment is ready!"
echo "=================================================="
echo "🤖 Agent Server: http://localhost:8787"
echo "🌐 Web Client:   http://localhost:5173"
echo "📖 API Docs:     http://localhost:8787/docs"
echo ""
echo "💡 Tips:"
echo "   - Use the '@' command in the editor to query the AI agent"
echo "   - Click 'Test AI Agent' button to test the connection"
echo "   - Check the browser console for debugging info"
echo ""
echo "Press Ctrl+C to stop all servers"
echo "=================================================="

# Wait for user interrupt
wait 
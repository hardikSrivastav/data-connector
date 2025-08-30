#!/bin/bash

# Ceneca Schema Watcher Startup Script
# This script starts the schema watcher with appropriate environment variables

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
SERVER_DIR="$PROJECT_ROOT/server"

# Default values
INTERVAL=${SCHEMA_WATCHER_INTERVAL:-1800}  # 30 minutes default
ONE_TIME=${SCHEMA_WATCHER_ONE_TIME:-false}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🔍 Starting Ceneca Schema Watcher${NC}"
echo -e "${BLUE}📁 Project root: $PROJECT_ROOT${NC}"
echo -e "${BLUE}📊 Check interval: $INTERVAL seconds ($(($INTERVAL / 60)) minutes)${NC}"

# Check if virtual environment exists
if [ -f "$PROJECT_ROOT/venv311/bin/activate" ]; then
    echo -e "${GREEN}✅ Found virtual environment${NC}"
    source "$PROJECT_ROOT/venv311/bin/activate"
else
    echo -e "${YELLOW}⚠️ Virtual environment not found at $PROJECT_ROOT/venv311${NC}"
    echo -e "${YELLOW}   Using system Python${NC}"
fi

# Set environment variables
export PYTHONPATH="$SERVER_DIR"
export SCHEMA_REGISTRY_PATH="$SERVER_DIR/agent/db/registry/schema_registry.db"
export SCHEMA_WATCHER_INTERVAL="$INTERVAL"

# Check if config exists
CONFIG_PATH="$HOME/.data-connector/config.yaml"
if [ ! -f "$CONFIG_PATH" ]; then
    echo -e "${RED}❌ Configuration file not found at $CONFIG_PATH${NC}"
    echo -e "${RED}   Please create your configuration file first${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Configuration found${NC}"

# Change to server directory
cd "$SERVER_DIR"

# Start the schema watcher
if [ "$ONE_TIME" = "true" ]; then
    echo -e "${BLUE}🔄 Running one-time schema check...${NC}"
    python -m agent.db.registry.schema_watcher --one-time
else
    echo -e "${BLUE}🚀 Starting continuous schema watcher...${NC}"
    echo -e "${YELLOW}   Press Ctrl+C to stop${NC}"
    python -m agent.db.registry.schema_watcher --interval "$INTERVAL"
fi

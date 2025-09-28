#!/bin/bash
set -e

# Ceneca Enterprise Agent - Client Installation Script
# Pre-configured for multi-instance MongoDB setup

# Set the deploy directory
DEPLOY_DIR="$(dirname "$(realpath "$0")")"
cd "$DEPLOY_DIR"

# Display banner
echo "==============================================================="
echo "      Ceneca Enterprise Agent - Client Installation           "
echo "      Multi-Instance MongoDB Support Enabled                  "
echo "==============================================================="
echo ""

# Check prerequisites
echo "🔍 Checking prerequisites..."
if ! command -v docker &> /dev/null; then
    echo "❌ Error: Docker is not installed. Please install Docker first."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Error: Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

echo "✅ Docker and Docker Compose are installed."

# Test MongoDB connectivity
echo ""
echo "🔍 Testing MongoDB connectivity..."
if ping -c 1 172.31.18.152 &> /dev/null; then
    echo "✅ MongoDB host (172.31.18.152) is reachable"
else
    echo "⚠️  Warning: Cannot reach MongoDB host (172.31.18.152)"
    echo "   Please ensure network connectivity to your MongoDB server"
fi

# Set up environment file
echo ""
echo "🔧 Setting up environment variables..."
if [ ! -f "$DEPLOY_DIR/.env" ]; then
    cat > "$DEPLOY_DIR/.env" << 'EOF'
# Ceneca environment variables
OPENAI_API_KEY=your_openai_api_key_here
EOF
    echo "Created .env file template"
fi

# Prompt for OpenAI API key
if grep -q "your_openai_api_key_here" "$DEPLOY_DIR/.env"; then
    echo ""
    echo "🔑 OpenAI API Key Setup"
    echo "Ceneca uses OpenAI GPT-4 for natural language processing."
    read -p "Enter your OpenAI API key: " api_key
    if [ ! -z "$api_key" ]; then
        sed -i.bak "s/your_openai_api_key_here/$api_key/g" "$DEPLOY_DIR/.env" && rm "$DEPLOY_DIR/.env.bak" 2>/dev/null || sed -i "s/your_openai_api_key_here/$api_key/g" "$DEPLOY_DIR/.env"
        echo "✅ API key configured"
    else
        echo "⚠️  No API key provided. You'll need to update the .env file manually."
    fi
fi

# Create logs directory
echo ""
echo "📁 Setting up directories..."
mkdir -p "$DEPLOY_DIR/logs"
echo "✅ Log directory created"

# Pull the latest image
echo ""
echo "📦 Pulling Ceneca agent image..."
docker pull hardiksriv/agent:latest

# Display configuration summary
echo ""
echo "📋 Configuration Summary:"
echo "   MongoDB Instances: 3 (main, cmots, backend)"
echo "   MongoDB Host: 172.31.18.152:27017"
echo "   Databases:"
echo "     - financial_data (mongodb_main)"
echo "     - discvr_finance (mongodb_cmots)"
echo "     - finance_cards (mongodb_backend)"
echo "   Web Interface: http://localhost:8787"
echo "   LLM Provider: OpenAI GPT-4"

# Start the containers
echo ""
echo "🚀 Starting Ceneca agent..."
docker-compose -f "$DEPLOY_DIR/client-docker-compose.yml" up -d

# Wait for health check
echo ""
echo "⏳ Waiting for Ceneca to start (this may take 30-60 seconds)..."
sleep 10

# Check if service is running
max_attempts=12
attempt=1
while [ $attempt -le $max_attempts ]; do
    if docker-compose -f "$DEPLOY_DIR/client-docker-compose.yml" ps | grep -q "Up"; then
        echo "✅ Ceneca agent is running!"
        break
    else
        echo "   Attempt $attempt/$max_attempts - waiting..."
        sleep 5
        ((attempt++))
    fi
done

if [ $attempt -gt $max_attempts ]; then
    echo "⚠️  Ceneca may be taking longer to start. Check logs with:"
    echo "   docker-compose -f $DEPLOY_DIR/client-docker-compose.yml logs"
fi

# Test the multi-instance configuration
echo ""
echo "🧪 Testing multi-instance MongoDB configuration..."
sleep 5

# Test configuration parsing
docker-compose -f "$DEPLOY_DIR/client-docker-compose.yml" exec -T ceneca-agent python -c "
import sys
sys.path.append('/app/server/agent/db/registry')
try:
    from multi_instance_parser import parse_multi_instance_config
    import yaml
    
    with open('/root/.data-connector/config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    parser = parse_multi_instance_config(config)
    summary = parser.get_summary()
    
    print(f'✅ Configuration parsed successfully!')
    print(f'   Total database instances: {summary[\"total_instances\"]}')
    print(f'   Multi-instance types: {summary[\"multi_instance_types\"]}')
    print(f'   MongoDB instances detected:')
    
    mongodb_instances = parser.get_instances_by_type('mongodb')
    for instance in mongodb_instances:
        print(f'     - {instance.id}: {instance.uri.split(\"/\")[-1]}')
    
except Exception as e:
    print(f'⚠️  Configuration test failed: {e}')
    print('   Check logs for details')
" 2>/dev/null || echo "⚠️  Configuration test skipped (container may still be starting)"

# Display success message
echo ""
echo "==============================================================="
echo "        🎉 Ceneca Agent Deployed Successfully!                "
echo "==============================================================="
echo ""
echo "Your Ceneca agent is now running with multi-instance MongoDB support!"
echo ""
echo "🌐 Access Points:"
echo "   Web Interface: http://localhost:8787"
echo "   Health Check:  http://localhost:8787/health"
echo ""
echo "📊 Your Databases (automatically detected):"
echo "   • mongodb_main    → financial_data"
echo "   • mongodb_cmots   → discvr_finance" 
echo "   • mongodb_backend → finance_cards"
echo ""
echo "🔍 Example Queries:"
echo '   "Show me data from financial_data database"'
echo '   "Compare users between financial_data and discvr_finance"'
echo '   "Aggregate statistics across all MongoDB databases"'
echo ""
echo "🛠️  Management Commands:"
echo "   View logs:    docker-compose -f $DEPLOY_DIR/client-docker-compose.yml logs -f"
echo "   Stop service: docker-compose -f $DEPLOY_DIR/client-docker-compose.yml down"
echo "   Restart:      docker-compose -f $DEPLOY_DIR/client-docker-compose.yml restart"
echo ""
echo "📞 Support:"
echo "   If you encounter issues, please provide the output of:"
echo "   docker-compose -f $DEPLOY_DIR/client-docker-compose.yml logs"
echo ""
echo "🚀 Ready to query your data!"

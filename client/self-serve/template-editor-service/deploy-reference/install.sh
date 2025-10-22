#!/bin/bash
set -e

# Ceneca Agent Installation Script
# This script installs and configures the Ceneca agent to connect to existing databases

# Set the deploy directory (where all our files are located)
DEPLOY_DIR="$(dirname "$(realpath "$0")")"
cd "$DEPLOY_DIR"
echo "Working from deploy directory: $DEPLOY_DIR"

# Display banner
echo "==============================================================="
echo "        Ceneca Enterprise Agent - Simplified Installer         "
echo "==============================================================="
echo ""

# Check if Docker and Docker Compose are installed
echo "Checking prerequisites..."
if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed. Please install Docker first."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "Error: Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

echo "Docker and Docker Compose are installed."
echo ""

# Check for config.yaml
if [ ! -f "$DEPLOY_DIR/config.yaml" ]; then
    echo "Warning: config.yaml not found in the deploy directory."
    echo "Creating a template config.yaml file. Please update it with your database credentials."
    cp "$DEPLOY_DIR/sample-config.yaml" "$DEPLOY_DIR/config.yaml" 2>/dev/null || cat > "$DEPLOY_DIR/config.yaml" << 'EOF'
# Ceneca Agent Configuration - PLEASE UPDATE WITH YOUR VALUES
default_database: postgres

postgres:
  uri: "postgresql://user:password@your-postgres-host:5432/your_database"

mongodb:
  uri: "mongodb://user:password@your-mongodb-host:27017/your_database?authSource=admin"

qdrant:
  uri: "http://your-qdrant-host:6333"
EOF
    echo "Created config.yaml template in $DEPLOY_DIR"
fi

# Set environment variables
echo "Setting up environment variables..."
if [ ! -f "$DEPLOY_DIR/.env" ]; then
    cat > "$DEPLOY_DIR/.env" << 'EOF'
# Ceneca environment variables
LLM_API_KEY=your_openai_api_key_here
EOF
    echo "Created .env file template in $DEPLOY_DIR. Please update it with your API keys."
fi

# Prompt user for LLM API key if not set
if grep -q "your_openai_api_key_here" "$DEPLOY_DIR/.env"; then
    read -p "Enter your OpenAI API key: " api_key
    if [ ! -z "$api_key" ]; then
        sed -i.bak "s/your_openai_api_key_here/$api_key/g" "$DEPLOY_DIR/.env" && rm "$DEPLOY_DIR/.env.bak" 2>/dev/null || sed -i "s/your_openai_api_key_here/$api_key/g" "$DEPLOY_DIR/.env"
        echo "Updated API key in .env file"
    else
        echo "No API key provided. You'll need to update the .env file manually."
    fi
fi

# Check if we need to join existing Docker networks
echo ""
echo "Available Docker networks:"
docker network ls --format "{{.Name}}"
echo ""
read -p "Do you need to connect to existing networks? (y/n): " join_networks

if [ "$join_networks" = "y" ] || [ "$join_networks" = "Y" ]; then
    read -p "Enter network names (space-separated): " networks
    
    if [ ! -z "$networks" ]; then
        # Update docker-compose.yml for networks
        echo "Updating docker-compose.yml to join specified networks..."
        
        # Make a backup
        cp "$DEPLOY_DIR/ceneca-docker-compose.yml" "$DEPLOY_DIR/ceneca-docker-compose.yml.bak" 2>/dev/null || echo "Warning: Could not create backup, file may not exist"
        
        # Add networks to the service
        for network in $networks; do
            # Uncomment the network in services section
            sed -i.bak "s/# - $network/- $network/g" "$DEPLOY_DIR/ceneca-docker-compose.yml" 2>/dev/null || sed -i "s/# - $network/- $network/g" "$DEPLOY_DIR/ceneca-docker-compose.yml"
            
            # Uncomment and update the external network definition
            sed -i.bak "s/# $network:/$network:/g" "$DEPLOY_DIR/ceneca-docker-compose.yml" 2>/dev/null || sed -i "s/# $network:/$network:/g" "$DEPLOY_DIR/ceneca-docker-compose.yml"
            sed -i.bak "s/#   external: true/  external: true/g" "$DEPLOY_DIR/ceneca-docker-compose.yml" 2>/dev/null || sed -i "s/#   external: true/  external: true/g" "$DEPLOY_DIR/ceneca-docker-compose.yml"
        done
        
        # Clean up backup files
        rm "$DEPLOY_DIR/ceneca-docker-compose.yml.bak" 2>/dev/null || true
        echo "Networks added to configuration"
    fi
fi

# Check if we need to add DNS entries
echo ""
read -p "Do you need to add host mappings for DNS resolution? (y/n): " add_hosts

if [ "$add_hosts" = "y" ] || [ "$add_hosts" = "Y" ]; then
    hosts=()
    
    echo "Enter host mappings (hostname IP), one per line (empty line to finish):"
    while true; do
        read -p "> " host_entry
        if [ -z "$host_entry" ]; then
            break
        fi
        hosts+=("$host_entry")
    done
    
    if [ ${#hosts[@]} -gt 0 ]; then
        # Update docker-compose.yml for extra_hosts
        echo "Updating docker-compose.yml to add host mappings..."
        
        # Make a backup
        cp "$DEPLOY_DIR/ceneca-docker-compose.yml" "$DEPLOY_DIR/ceneca-docker-compose.yml.bak" 2>/dev/null || echo "Warning: Could not create backup, file may not exist"
        
        # Uncomment extra_hosts section and replace comment with proper mapping
        sed -i.bak "s/# extra_hosts:/extra_hosts:/g" "$DEPLOY_DIR/ceneca-docker-compose.yml" 2>/dev/null || sed -i "s/# extra_hosts:/extra_hosts:/g" "$DEPLOY_DIR/ceneca-docker-compose.yml"
        
        # Add the new hosts (ensure proper formatting as a mapping)
        for host in "${hosts[@]}"; do
            hostname=$(echo $host | awk '{print $1}')
            ip=$(echo $host | awk '{print $2}')
            sed -i.bak "/extra_hosts:/a\\      - \"$hostname:$ip\"" "$DEPLOY_DIR/ceneca-docker-compose.yml" 2>/dev/null || sed -i "/extra_hosts:/a\\      - \"$hostname:$ip\"" "$DEPLOY_DIR/ceneca-docker-compose.yml"
        done
        
        # Remove the sample commented hosts
        sed -i.bak "s/#   - \"db-postgres.internal:192.168.1.100\"//g" "$DEPLOY_DIR/ceneca-docker-compose.yml" 2>/dev/null || sed -i "s/#   - \"db-postgres.internal:192.168.1.100\"//g" "$DEPLOY_DIR/ceneca-docker-compose.yml"
        sed -i.bak "s/#   - \"db-mongo.internal:192.168.1.101\"//g" "$DEPLOY_DIR/ceneca-docker-compose.yml" 2>/dev/null || sed -i "s/#   - \"db-mongo.internal:192.168.1.101\"//g" "$DEPLOY_DIR/ceneca-docker-compose.yml"
        sed -i.bak "s/#   - \"db-qdrant.internal:192.168.1.102\"//g" "$DEPLOY_DIR/ceneca-docker-compose.yml" 2>/dev/null || sed -i "s/#   - \"db-qdrant.internal:192.168.1.102\"//g" "$DEPLOY_DIR/ceneca-docker-compose.yml"
        
        # Clean up backup files
        rm "$DEPLOY_DIR/ceneca-docker-compose.yml.bak" 2>/dev/null || true
        echo "Host mappings added to configuration"
    fi
fi

# Build and start the containers
echo ""
echo "Building and starting Ceneca agent..."
docker-compose -f "$DEPLOY_DIR/ceneca-docker-compose.yml" up -d

# Display success message and next steps
echo ""
echo "==============================================================="
echo "        Ceneca Agent Deployed Successfully!                    "
echo "==============================================================="
echo ""
echo "The Ceneca agent is now running and connecting to your databases."
echo ""
echo "Next steps:"
echo "1. Verify your configuration in $DEPLOY_DIR/config.yaml"
echo "2. Check container logs: docker-compose -f $DEPLOY_DIR/ceneca-docker-compose.yml logs"
echo "3. Access the web interface at http://localhost:8787"
echo ""
echo "If you need to update your configuration:"
echo "1. Edit $DEPLOY_DIR/config.yaml"
echo "2. Restart the agent: docker-compose -f $DEPLOY_DIR/ceneca-docker-compose.yml restart"
echo "" 
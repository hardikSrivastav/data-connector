#!/bin/bash
set -e

# Ceneca Agent Installation Script
# This script installs and configures the Ceneca agent to connect to existing databases

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
if [ ! -f "config.yaml" ]; then
    echo "Warning: config.yaml not found."
    echo "Creating a template config.yaml file. Please update it with your database credentials."
    cp config.yaml.template config.yaml 2>/dev/null || cat > config.yaml << 'EOF'
# Ceneca Agent Configuration - PLEASE UPDATE WITH YOUR VALUES
default_database: postgres

postgres:
  uri: "postgresql://user:password@your-postgres-host:5432/your_database"

mongodb:
  uri: "mongodb://user:password@your-mongodb-host:27017/your_database?authSource=admin"

qdrant:
  uri: "http://your-qdrant-host:6333"
EOF
    echo "Created config.yaml template"
fi

# Set environment variables
echo "Setting up environment variables..."
if [ ! -f ".env" ]; then
    cat > .env << 'EOF'
# Ceneca environment variables
LLM_API_KEY=your_openai_api_key_here
EOF
    echo "Created .env file template. Please update it with your API keys."
fi

# Prompt user for LLM API key if not set
if grep -q "your_openai_api_key_here" .env; then
    read -p "Enter your OpenAI API key: " api_key
    if [ ! -z "$api_key" ]; then
        sed -i.bak "s/your_openai_api_key_here/$api_key/g" .env && rm .env.bak 2>/dev/null || sed -i "s/your_openai_api_key_here/$api_key/g" .env
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
        cp ceneca-docker-compose.yml ceneca-docker-compose.yml.bak
        
        # Add networks to the service
        for network in $networks; do
            # Uncomment the network in services section
            sed -i.bak "s/# - $network/- $network/g" ceneca-docker-compose.yml 2>/dev/null || sed -i "s/# - $network/- $network/g" ceneca-docker-compose.yml
            
            # Uncomment and update the external network definition
            sed -i.bak "s/# $network:/$network:/g" ceneca-docker-compose.yml 2>/dev/null || sed -i "s/# $network:/$network:/g" ceneca-docker-compose.yml
            sed -i.bak "s/#   external: true/  external: true/g" ceneca-docker-compose.yml 2>/dev/null || sed -i "s/#   external: true/  external: true/g" ceneca-docker-compose.yml
        done
        
        # Clean up backup files
        rm ceneca-docker-compose.yml.bak 2>/dev/null || true
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
        cp ceneca-docker-compose.yml ceneca-docker-compose.yml.bak
        
        # Uncomment extra_hosts section
        sed -i.bak "s/# extra_hosts:/extra_hosts:/g" ceneca-docker-compose.yml 2>/dev/null || sed -i "s/# extra_hosts:/extra_hosts:/g" ceneca-docker-compose.yml
        
        # Replace sample entries with provided ones
        sed -i.bak "s/#   - \"db-postgres.internal:192.168.1.100\"/#/g" ceneca-docker-compose.yml 2>/dev/null || sed -i "s/#   - \"db-postgres.internal:192.168.1.100\"/#/g" ceneca-docker-compose.yml
        sed -i.bak "s/#   - \"db-mongo.internal:192.168.1.101\"/#/g" ceneca-docker-compose.yml 2>/dev/null || sed -i "s/#   - \"db-mongo.internal:192.168.1.101\"/#/g" ceneca-docker-compose.yml
        sed -i.bak "s/#   - \"db-qdrant.internal:192.168.1.102\"/#/g" ceneca-docker-compose.yml 2>/dev/null || sed -i "s/#   - \"db-qdrant.internal:192.168.1.102\"/#/g" ceneca-docker-compose.yml
        
        # Add the new hosts
        for host in "${hosts[@]}"; do
            hostname=$(echo $host | awk '{print $1}')
            ip=$(echo $host | awk '{print $2}')
            sed -i.bak "/extra_hosts:/a\\      - \"$hostname:$ip\"" ceneca-docker-compose.yml 2>/dev/null || sed -i "/extra_hosts:/a\\      - \"$hostname:$ip\"" ceneca-docker-compose.yml
        done
        
        # Clean up backup files
        rm ceneca-docker-compose.yml.bak 2>/dev/null || true
        echo "Host mappings added to configuration"
    fi
fi

# Build and start the containers
echo ""
echo "Building and starting Ceneca agent..."
docker-compose -f ceneca-docker-compose.yml up -d

# Display success message and next steps
echo ""
echo "==============================================================="
echo "        Ceneca Agent Deployed Successfully!                    "
echo "==============================================================="
echo ""
echo "The Ceneca agent is now running and connecting to your databases."
echo ""
echo "Next steps:"
echo "1. Verify your configuration in config.yaml"
echo "2. Check container logs: docker-compose -f ceneca-docker-compose.yml logs"
echo "3. Access the web interface at http://localhost:8787"
echo ""
echo "If you need to update your configuration:"
echo "1. Edit config.yaml"
echo "2. Restart the agent: docker-compose -f ceneca-docker-compose.yml restart"
echo "" 
#!/bin/bash
set -e

# Ceneca Enterprise Agent Installation Script
# This script configures and deploys the Ceneca agent to connect to existing databases
# Uses pre-built container images rather than building from source

# Set the deploy directory (where all our files are located)
DEPLOY_DIR="$(dirname "$(realpath "$0")")"
cd "$DEPLOY_DIR"
echo "Working from deploy directory: $DEPLOY_DIR"

# Display banner
echo "==============================================================="
echo "      Ceneca Enterprise Agent - Enterprise Installer           "
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

# Create NGINX directories if they don't exist
mkdir -p "$DEPLOY_DIR/nginx/ssl"

# Check for auth-config.yaml
echo ""
echo "Checking for authentication configuration..."
read -p "Do you want to set up SSO authentication? (y/n): " setup_sso

if [ "$setup_sso" = "y" ] || [ "$setup_sso" = "Y" ]; then
    echo "Setting up SSO with NGINX as reverse proxy..."
    
    # Prompt for domain name
    read -p "Enter your domain name (e.g., ceneca.yourcompany.com): " domain_name
    [ -z "$domain_name" ] && domain_name="localhost"
    
    # Choose SSO provider
    echo "Choose your SSO provider:"
    echo "1. Okta"
    echo "2. Azure AD"
    echo "3. Google"
    echo "4. Custom OIDC Provider"
    read -p "Select provider (1-4): " provider_choice
    
    case $provider_choice in
        1)
            provider="okta"
            ;;
        2)
            provider="azure"
            ;;
        3)
            provider="google"
            ;;
        *)
            provider="custom"
            ;;
    esac
    
    # Get SSO details
    read -p "Enter client ID: " client_id
    read -p "Enter client secret: " client_secret
    read -p "Enter issuer URL: " issuer_url
    read -p "Enter discovery URL (leave blank for standard URL): " discovery_url
    [ -z "$discovery_url" ] && discovery_url="${issuer_url}/.well-known/openid-configuration"
    
    # Get role mappings
    echo "Enter role mappings (e.g., 'HR-Analysts:hr_read', empty line to finish):"
    role_mappings=()
    while true; do
        read -p "> " role_mapping
        if [ -z "$role_mapping" ]; then
            break
        fi
        role_mappings+=("$role_mapping")
    done
    
    # Generate auth-config.yaml from template
    echo "Generating auth-config.yaml..."
    cat > "$DEPLOY_DIR/auth-config.yaml" << EOF
sso:
  # Common settings
  enabled: true
  default_protocol: "oidc"
  
  # OIDC Configuration
  oidc:
    provider: "$provider"
    client_id: "$client_id"
    client_secret: "$client_secret"
    issuer: "$issuer_url"
    discovery_url: "$discovery_url"
    redirect_uri: "https://$domain_name/authorization-code/callback"
    scopes: ["openid", "email", "profile", "groups"]
    # Map claims to user attributes
    claims_mapping:
      email: "email"
      name: "name" 
      groups: "groups"

# Role mappings from IdP groups to Ceneca roles
role_mappings:
EOF

    # Add role mappings to auth-config.yaml
    for mapping in "${role_mappings[@]}"; do
        group=$(echo $mapping | cut -d':' -f1)
        role=$(echo $mapping | cut -d':' -f2)
        echo "  \"$group\": \"$role\"" >> "$DEPLOY_DIR/auth-config.yaml"
    done
    
    # If no role mappings were provided, add a sample
    if [ ${#role_mappings[@]} -eq 0 ]; then
        echo "  # Add your role mappings here, for example:" >> "$DEPLOY_DIR/auth-config.yaml"
        echo "  # \"HR-Analysts\": \"hr_read\"" >> "$DEPLOY_DIR/auth-config.yaml"
        echo "  # \"Finance-Team\": \"finance_read\"" >> "$DEPLOY_DIR/auth-config.yaml"
        echo "  # \"Data-Admins\": \"admin\"" >> "$DEPLOY_DIR/auth-config.yaml"
    fi
    
    # Generate NGINX configuration
    echo "Generating NGINX configuration..."
    cat > "$DEPLOY_DIR/nginx/nginx.conf" << EOF
server {
    listen 80;
    server_name $domain_name;
    
    # Redirect HTTP to HTTPS
    location / {
        return 301 https://\$host\$request_uri;
    }
}

server {
    listen 443 ssl;
    server_name $domain_name;
    
    # SSL Configuration
    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;
    
    # SSL Security Settings
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers on;
    ssl_ciphers 'ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256';
    ssl_session_timeout 1d;
    ssl_session_cache shared:SSL:50m;
    
    # Security Headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options nosniff always;
    add_header X-Frame-Options SAMEORIGIN always;
    add_header X-XSS-Protection "1; mode=block" always;
    
    # Main Application
    location / {
        proxy_pass http://ceneca-agent:8787;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
    
    # OIDC Auth Callback
    location /authorization-code/callback {
        proxy_pass http://ceneca-agent:8787/authorization-code/callback;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
    
    # WebSocket Support (if needed)
    location /ws {
        proxy_pass http://ceneca-agent:8787/ws;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF
    
    # Generate SSL certificates
    echo "Generating SSL certificates for development..."
    echo "Note: For production, replace these with proper certificates from a trusted CA."
    
    # Generate private key
    openssl genrsa -out "$DEPLOY_DIR/nginx/ssl/key.pem" 2048
    
    # Generate certificate signing request
    openssl req -new -key "$DEPLOY_DIR/nginx/ssl/key.pem" -out "$DEPLOY_DIR/nginx/ssl/csr.pem" -subj "/CN=$domain_name/O=Ceneca/C=US"
    
    # Generate self-signed certificate
    openssl x509 -req -days 365 -in "$DEPLOY_DIR/nginx/ssl/csr.pem" -signkey "$DEPLOY_DIR/nginx/ssl/key.pem" -out "$DEPLOY_DIR/nginx/ssl/cert.pem"
    
    # Remove CSR as it's no longer needed
    rm "$DEPLOY_DIR/nginx/ssl/csr.pem"
    
    echo "SSL certificates generated for $domain_name (self-signed, valid for 365 days)"
    
    # Update the .env file to enable auth
    echo "AUTH_ENABLED=true" >> "$DEPLOY_DIR/.env"
    
    echo "SSO configuration completed. NGINX will handle SSL and proxy to the Ceneca agent."
    echo "Please ensure your DNS points $domain_name to this server's IP address."
fi

# Set environment variables
echo ""
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
        cp "$DEPLOY_DIR/enterprise-docker-compose.yml" "$DEPLOY_DIR/enterprise-docker-compose.yml.bak" 2>/dev/null || echo "Warning: Could not create backup, file may not exist"
        
        # Add networks to the service
        for network in $networks; do
            # Uncomment the network in services section
            sed -i.bak "s/# - $network/- $network/g" "$DEPLOY_DIR/enterprise-docker-compose.yml" 2>/dev/null || sed -i "s/# - $network/- $network/g" "$DEPLOY_DIR/enterprise-docker-compose.yml"
            
            # Uncomment and update the external network definition
            sed -i.bak "s/# $network:/$network:/g" "$DEPLOY_DIR/enterprise-docker-compose.yml" 2>/dev/null || sed -i "s/# $network:/$network:/g" "$DEPLOY_DIR/enterprise-docker-compose.yml"
            sed -i.bak "s/#   external: true/  external: true/g" "$DEPLOY_DIR/enterprise-docker-compose.yml" 2>/dev/null || sed -i "s/#   external: true/  external: true/g" "$DEPLOY_DIR/enterprise-docker-compose.yml"
        done
        
        # Clean up backup files
        rm "$DEPLOY_DIR/enterprise-docker-compose.yml.bak" 2>/dev/null || true
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
        cp "$DEPLOY_DIR/enterprise-docker-compose.yml" "$DEPLOY_DIR/enterprise-docker-compose.yml.bak" 2>/dev/null || echo "Warning: Could not create backup, file may not exist"
        
        # Uncomment extra_hosts section and replace comment with proper mapping
        sed -i.bak "s/# extra_hosts:/extra_hosts:/g" "$DEPLOY_DIR/enterprise-docker-compose.yml" 2>/dev/null || sed -i "s/# extra_hosts:/extra_hosts:/g" "$DEPLOY_DIR/enterprise-docker-compose.yml"
        
        # Add the new hosts (ensure proper formatting as a mapping)
        for host in "${hosts[@]}"; do
            hostname=$(echo $host | awk '{print $1}')
            ip=$(echo $host | awk '{print $2}')
            sed -i.bak "/extra_hosts:/a\\      - \"$hostname:$ip\"" "$DEPLOY_DIR/enterprise-docker-compose.yml" 2>/dev/null || sed -i "/extra_hosts:/a\\      - \"$hostname:$ip\"" "$DEPLOY_DIR/enterprise-docker-compose.yml"
        done
        
        # Remove the sample commented hosts
        sed -i.bak "s/#   - \"db-postgres.internal:192.168.1.100\"//g" "$DEPLOY_DIR/enterprise-docker-compose.yml" 2>/dev/null || sed -i "s/#   - \"db-postgres.internal:192.168.1.100\"//g" "$DEPLOY_DIR/enterprise-docker-compose.yml"
        sed -i.bak "s/#   - \"db-mongo.internal:192.168.1.101\"//g" "$DEPLOY_DIR/enterprise-docker-compose.yml" 2>/dev/null || sed -i "s/#   - \"db-mongo.internal:192.168.1.101\"//g" "$DEPLOY_DIR/enterprise-docker-compose.yml"
        sed -i.bak "s/#   - \"db-qdrant.internal:192.168.1.102\"//g" "$DEPLOY_DIR/enterprise-docker-compose.yml" 2>/dev/null || sed -i "s/#   - \"db-qdrant.internal:192.168.1.102\"//g" "$DEPLOY_DIR/enterprise-docker-compose.yml"
        
        # Clean up backup files
        rm "$DEPLOY_DIR/enterprise-docker-compose.yml.bak" 2>/dev/null || true
        echo "Host mappings added to configuration"
    fi
fi

# Pull the latest images
echo ""
echo "Pulling the latest Ceneca agent image..."
docker pull hardiksriv/agent:latest
echo "Pulling NGINX image..."
docker pull nginx:latest

# Start the containers
echo ""
echo "Starting Ceneca agent and NGINX..."
docker-compose -f "$DEPLOY_DIR/enterprise-docker-compose.yml" up -d

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
echo "2. Check container logs: docker-compose -f $DEPLOY_DIR/enterprise-docker-compose.yml logs"

# Show the appropriate access URLs based on SSO setup
if [ "$setup_sso" = "y" ] || [ "$setup_sso" = "Y" ]; then
    echo "3. Access the web interface at https://$domain_name"
    echo "   Note: You'll need to add a hosts file entry or configure DNS for $domain_name"
else
    echo "3. Access the web interface at http://localhost:8787"
fi

echo ""
echo "If you need to update your configuration:"
echo "1. Edit $DEPLOY_DIR/config.yaml"
echo "2. Restart the agent: docker-compose -f $DEPLOY_DIR/enterprise-docker-compose.yml restart"
echo ""

# If SSO is set up, add SSO-specific instructions
if [ "$setup_sso" = "y" ] || [ "$setup_sso" = "Y" ]; then
    echo "SSO Authentication Setup:"
    echo "1. Ensure $domain_name points to this server's IP address in your DNS or hosts file"
    echo "2. Verify the callback URL is correctly configured in your IdP: https://$domain_name/authorization-code/callback"
    echo "3. Assign users to the application in your IdP"
    echo "4. Test the login by accessing https://$domain_name"
    echo ""
    echo "If you need to update SSO configuration:"
    echo "1. Edit $DEPLOY_DIR/auth-config.yaml"
    echo "2. Restart the services: docker-compose -f $DEPLOY_DIR/enterprise-docker-compose.yml restart"
fi 
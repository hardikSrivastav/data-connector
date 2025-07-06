#!/bin/bash

# Ceneca Enterprise Setup Script
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
INTERACTIVE=true

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --non-interactive)
            INTERACTIVE=false
            shift
            ;;
        --help|-h)
            echo "Ceneca Enterprise Setup Script"
            echo ""
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  --non-interactive    Run without prompts (use environment variables)"
            echo "  --help, -h          Show this help"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Input functions
prompt_input() {
    local prompt="$1"
    local default="$2"
    local var_name="$3"
    
    if [[ "$INTERACTIVE" == "false" ]]; then
        # Use environment variable or default
        local env_value="${!var_name}"
        if [[ -n "$env_value" ]]; then
            eval "$var_name=\"$env_value\""
        else
            eval "$var_name=\"$default\""
        fi
        echo "Using $var_name: ${!var_name}"
        return
    fi
    
    while true; do
        if [[ -n "$default" ]]; then
            read -p "$prompt [$default]: " input
            input=${input:-$default}
        else
            read -p "$prompt: " input
        fi
        
        if [[ -n "$input" ]]; then
            eval "$var_name=\"$input\""
            break
        else
            echo "This field is required."
        fi
    done
}

prompt_secret() {
    local prompt="$1"
    local var_name="$2"
    
    if [[ "$INTERACTIVE" == "false" ]]; then
        local env_value="${!var_name}"
        if [[ -n "$env_value" ]]; then
            eval "$var_name=\"$env_value\""
            echo "Using $var_name from environment"
        else
            log_error "Environment variable $var_name is required in non-interactive mode"
            exit 1
        fi
        return
    fi
    
    while true; do
        read -s -p "$prompt: " input
        echo ""
        if [[ -n "$input" ]]; then
            eval "$var_name=\"$input\""
            break
        else
            echo "This field is required."
        fi
    done
}

# Setup functions
setup_directories() {
    log_info "Creating directory structure..."
    
    mkdir -p config
    mkdir -p certs
    mkdir -p docs
    
    # Create .gitkeep for empty directories
    touch certs/.gitkeep
    
    log_success "Directory structure created"
}

setup_config_file() {
    log_info "Setting up configuration file..."
    
    if [[ -f "config/config.yaml" ]]; then
        log_warning "config.yaml already exists. Backing up to config.yaml.backup"
        cp config/config.yaml config/config.yaml.backup
    fi
    
    # Gather configuration
    prompt_input "Enter your domain (e.g., ceneca.yourcompany.com)" "ceneca.yourcompany.com" "DOMAIN"
    prompt_input "Enter PostgreSQL host" "localhost" "PG_HOST"
    prompt_input "Enter PostgreSQL port" "5432" "PG_PORT"
    prompt_input "Enter PostgreSQL database name" "ceneca" "PG_DATABASE"
    prompt_input "Enter PostgreSQL username" "ceneca_user" "PG_USER"
    prompt_secret "Enter PostgreSQL password" "PG_PASSWORD"
    
    # LLM Configuration
    echo ""
    log_info "LLM Configuration"
    prompt_input "Enter LLM provider (openai/anthropic/bedrock)" "openai" "LLM_PROVIDER"
    
    case "$LLM_PROVIDER" in
        "openai")
            prompt_secret "Enter OpenAI API key" "OPENAI_API_KEY"
            prompt_input "Enter OpenAI model" "gpt-4" "OPENAI_MODEL"
            ;;
        "anthropic")
            prompt_secret "Enter Anthropic API key" "ANTHROPIC_API_KEY"
            prompt_input "Enter Anthropic model" "claude-3-opus-20240229" "ANTHROPIC_MODEL"
            ;;
        "bedrock")
            prompt_input "Enter AWS region" "us-east-1" "AWS_REGION"
            prompt_secret "Enter AWS access key ID" "AWS_ACCESS_KEY_ID"
            prompt_secret "Enter AWS secret access key" "AWS_SECRET_ACCESS_KEY"
            prompt_input "Enter Bedrock model ID" "anthropic.claude-3-sonnet-20240229-v1:0" "BEDROCK_MODEL"
            ;;
    esac
    
    # Generate config file
    cat > config/config.yaml << EOF
# Ceneca Enterprise Configuration
# Generated on $(date)

default_database: postgres

postgres:
  host: $PG_HOST
  port: $PG_PORT
  database: $PG_DATABASE
  user: $PG_USER
  password: $PG_PASSWORD
  ssl_mode: prefer

EOF

    # Add LLM configuration
    case "$LLM_PROVIDER" in
        "openai")
            cat >> config/config.yaml << EOF
llm:
  api_url: https://api.openai.com/v1
  api_key: $OPENAI_API_KEY
  model_name: $OPENAI_MODEL

vector_db:
  embedding:
    provider: openai
    model: text-embedding-ada-002
    api_key: $OPENAI_API_KEY
EOF
            ;;
        "anthropic")
            cat >> config/config.yaml << EOF
llm:
  anthropic:
    api_url: https://api.anthropic.com
    api_key: $ANTHROPIC_API_KEY
    model_name: $ANTHROPIC_MODEL
EOF
            ;;
        "bedrock")
            cat >> config/config.yaml << EOF
aws:
  access_key_id: $AWS_ACCESS_KEY_ID
  secret_access_key: $AWS_SECRET_ACCESS_KEY
  region: $AWS_REGION

bedrock:
  enabled: true
  model_id: $BEDROCK_MODEL
  runtime_region: $AWS_REGION
EOF
            ;;
    esac
    
    cat >> config/config.yaml << EOF

enterprise:
  deployment_name: "Ceneca at $(echo $DOMAIN | cut -d. -f2-)"
  contact_email: admin@$(echo $DOMAIN | cut -d. -f2-)

logging:
  level: info
EOF
    
    log_success "Configuration file created"
}

setup_auth_config() {
    log_info "Setting up authentication configuration..."
    
    if [[ -f "config/auth-config.yaml" ]]; then
        log_warning "auth-config.yaml already exists. Backing up to auth-config.yaml.backup"
        cp config/auth-config.yaml config/auth-config.yaml.backup
    fi
    
    echo ""
    log_info "SSO Configuration"
    prompt_input "Enter SSO provider (okta/azure/google/auth0)" "okta" "SSO_PROVIDER"
    prompt_input "Enter OAuth client ID" "" "OAUTH_CLIENT_ID"
    prompt_secret "Enter OAuth client secret" "OAUTH_CLIENT_SECRET"
    
    case "$SSO_PROVIDER" in
        "okta")
            prompt_input "Enter Okta domain (e.g., yourcompany.okta.com)" "" "SSO_DOMAIN"
            ISSUER="https://$SSO_DOMAIN"
            ;;
        "azure")
            prompt_input "Enter Azure tenant ID" "" "AZURE_TENANT_ID"
            ISSUER="https://login.microsoftonline.com/$AZURE_TENANT_ID/v2.0"
            ;;
        "google")
            ISSUER="https://accounts.google.com"
            ;;
        "auth0")
            prompt_input "Enter Auth0 domain (e.g., yourcompany.auth0.com)" "" "AUTH0_DOMAIN"
            ISSUER="https://$AUTH0_DOMAIN"
            ;;
    esac
    
    # Generate auth config
    cat > config/auth-config.yaml << EOF
# Ceneca Enterprise Authentication Configuration
# Generated on $(date)

sso:
  enabled: true
  default_protocol: oidc
  
  oidc:
    provider: "$SSO_PROVIDER"
    client_id: "$OAUTH_CLIENT_ID"
    client_secret: "$OAUTH_CLIENT_SECRET"
    issuer: "$ISSUER"
    redirect_uri: "https://$DOMAIN/auth/callback"
    scopes:
      - "openid"
      - "email"
      - "profile"
      - "groups"
    claims_mapping:
      user_id: "sub"
      email: "email"
      name: "name"
      groups: "groups"

role_mappings:
  "ceneca-admins": "admin"
  "ceneca-users": "user"
  "all-employees": "user"
EOF
    
    log_success "Authentication configuration created"
}

setup_ssl_certificates() {
    log_info "Setting up SSL certificates..."
    
    if [[ -f "certs/certificate.crt" && -f "certs/private.key" ]]; then
        log_warning "SSL certificates already exist"
        if [[ "$INTERACTIVE" == "true" ]]; then
            read -p "Do you want to replace them? (y/N): " replace
            if [[ "$replace" != "y" && "$replace" != "Y" ]]; then
                log_info "Keeping existing certificates"
                return
            fi
        fi
    fi
    
    echo ""
    echo "SSL Certificate Options:"
    echo "1. Use existing certificate files"
    echo "2. Generate self-signed certificate (for testing only)"
    echo "3. Skip for now (configure manually later)"
    
    if [[ "$INTERACTIVE" == "true" ]]; then
        read -p "Choose option (1-3): " ssl_option
    else
        ssl_option=${SSL_OPTION:-3}
        echo "Using SSL option: $ssl_option"
    fi
    
    case "$ssl_option" in
        "1")
            prompt_input "Enter path to certificate file" "" "CERT_PATH"
            prompt_input "Enter path to private key file" "" "KEY_PATH"
            
            if [[ -f "$CERT_PATH" && -f "$KEY_PATH" ]]; then
                cp "$CERT_PATH" certs/certificate.crt
                cp "$KEY_PATH" certs/private.key
                chmod 600 certs/private.key
                log_success "SSL certificates copied"
            else
                log_error "Certificate files not found"
                return 1
            fi
            ;;
        "2")
            ./scripts/generate-self-signed.sh "$DOMAIN"
            log_warning "Self-signed certificate generated - only use for testing!"
            ;;
        "3")
            log_info "SSL certificate setup skipped"
            log_warning "You must provide SSL certificates before deployment"
            ;;
        *)
            log_error "Invalid option"
            return 1
            ;;
    esac
}

setup_environment() {
    log_info "Creating environment file..."
    
    cat > .env << EOF
# Ceneca Enterprise Environment
# Generated on $(date)

CENECA_DOMAIN=$DOMAIN
CENECA_SESSION_SECRET=$(openssl rand -hex 32)
LOG_LEVEL=info
EOF
    
    log_success "Environment file created"
}

# Main setup function
main() {
    echo "=== Ceneca Enterprise Setup ==="
    echo ""
    
    if [[ "$INTERACTIVE" == "false" ]]; then
        log_info "Running in non-interactive mode"
        log_info "Required environment variables: DOMAIN, PG_HOST, PG_PASSWORD, etc."
        echo ""
    fi
    
    # Check if we're in the right directory
    if [[ ! -f "docker-compose.yml" ]]; then
        log_error "docker-compose.yml not found. Please run this script from the deployment directory."
        exit 1
    fi
    
    setup_directories
    setup_config_file
    setup_auth_config
    setup_ssl_certificates
    setup_environment
    
    echo ""
    log_success "Setup complete!"
    echo ""
    echo "Next steps:"
    echo "1. Review and customize config/config.yaml"
    echo "2. Review and customize config/auth-config.yaml"
    echo "3. Ensure SSL certificates are in place"
    echo "4. Run: docker-compose up -d"
    echo "5. Test: ./scripts/test-deployment.sh"
    echo ""
    echo "For detailed documentation, see docs/"
}

# Check dependencies
if ! command -v openssl &> /dev/null; then
    log_error "openssl is required but not installed"
    exit 1
fi

# Run setup
main 
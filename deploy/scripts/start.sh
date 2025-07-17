#!/bin/bash
set -e

echo "=== Ceneca Enterprise Starting ==="

# Function to log with timestamp
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Function to check if file exists and is readable
check_file() {
    if [[ ! -f "$1" ]]; then
        log "ERROR: Required file not found: $1"
        exit 1
    fi
    if [[ ! -r "$1" ]]; then
        log "ERROR: Cannot read file: $1"
        exit 1
    fi
}

# Function to wait for a service to be ready
wait_for_service() {
    local service_name=$1
    local check_cmd=$2
    local max_attempts=30
    local attempt=1
    
    log "Waiting for $service_name to be ready..."
    
    while [ $attempt -le $max_attempts ]; do
        if eval "$check_cmd" &>/dev/null; then
            log "$service_name is ready!"
            return 0
        fi
        
        log "Attempt $attempt/$max_attempts: $service_name not ready yet..."
        sleep 2
        ((attempt++))
    done
    
    log "ERROR: $service_name failed to start within timeout"
    return 1
}

# Set default environment variables if not provided
export CENECA_MODE=${CENECA_MODE:-enterprise}
export CENECA_CONFIG_PATH=${CENECA_CONFIG_PATH:-/app/config/config.yaml}
export CENECA_AUTH_CONFIG_PATH=${CENECA_AUTH_CONFIG_PATH:-/app/config/auth-config.yaml}
export CENECA_DOMAIN=${CENECA_DOMAIN:-ceneca.yourcompany.com}
export SSL_CERT_PATH=${SSL_CERT_PATH:-/app/certs/certificate.crt}
export SSL_KEY_PATH=${SSL_KEY_PATH:-/app/certs/private.key}

log "Starting Ceneca Enterprise v1.0"
log "Domain: $CENECA_DOMAIN"
log "Mode: $CENECA_MODE"

# Validate required configuration files
log "Validating configuration files..."
check_file "$CENECA_CONFIG_PATH"
check_file "$CENECA_AUTH_CONFIG_PATH"

# Validate SSL certificates
log "Validating SSL certificates..."
check_file "$SSL_CERT_PATH"
check_file "$SSL_KEY_PATH"

# Validate certificate and key match
if ! openssl x509 -noout -modulus -in "$SSL_CERT_PATH" | openssl md5 | cut -d' ' -f2 > /tmp/cert.md5; then
    log "ERROR: Invalid SSL certificate"
    exit 1
fi

if ! openssl rsa -noout -modulus -in "$SSL_KEY_PATH" | openssl md5 | cut -d' ' -f2 > /tmp/key.md5; then
    log "ERROR: Invalid SSL private key"
    exit 1
fi

if ! diff -q /tmp/cert.md5 /tmp/key.md5 > /dev/null; then
    log "ERROR: SSL certificate and private key do not match"
    exit 1
fi

log "SSL certificates validated successfully"

# Create required directories
log "Creating required directories..."
mkdir -p /app/logs /app/data /app/cache
chown -R www-data:www-data /app/static
chown -R root:root /app/agent

# Generate session secret if not provided
if [[ -z "$CENECA_SESSION_SECRET" ]]; then
    export CENECA_SESSION_SECRET=$(openssl rand -hex 32)
    log "Generated session secret"
fi

# Validate nginx configuration
log "Validating nginx configuration..."
if ! nginx -t 2>/dev/null; then
    log "ERROR: Invalid nginx configuration"
    nginx -t
    exit 1
fi

# Test FastAPI application startup
log "Testing FastAPI application..."
cd /app/agent
if ! python -c "from api.endpoints import app; print('FastAPI app loaded successfully')" 2>/dev/null; then
    log "ERROR: FastAPI application failed to load"
    python -c "from api.endpoints import app; print('FastAPI app loaded successfully')"
    exit 1
fi

log "FastAPI application validated successfully"

# Start supervisor to manage all services
log "Starting services with supervisor..."
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf 
#!/bin/bash

# Ceneca Enterprise Deployment Test Script
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
DOMAIN=${CENECA_DOMAIN:-ceneca.yourcompany.com}
VERBOSE=false
TIMEOUT=30

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --domain)
            DOMAIN="$2"
            shift 2
            ;;
        --verbose|-v)
            VERBOSE=true
            shift
            ;;
        --timeout)
            TIMEOUT="$2"
            shift 2
            ;;
        --help|-h)
            echo "Ceneca Enterprise Deployment Test"
            echo ""
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  --domain DOMAIN    Test against specific domain (default: ceneca.yourcompany.com)"
            echo "  --verbose, -v      Show detailed output"
            echo "  --timeout SECONDS  Timeout for tests (default: 30)"
            echo "  --help, -h         Show this help"
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
    echo -e "${GREEN}[PASS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[FAIL]${NC} $1"
}

log_verbose() {
    if [[ "$VERBOSE" == "true" ]]; then
        echo -e "${NC}[DEBUG] $1"
    fi
}

# Test functions
test_docker_status() {
    log_info "Testing Docker container status..."
    
    if ! docker-compose ps | grep -q "ceneca-enterprise"; then
        log_error "Ceneca container is not running"
        return 1
    fi
    
    if docker-compose ps | grep -q "Exit"; then
        log_error "Ceneca container has exited"
        docker-compose logs --tail=20
        return 1
    fi
    
    log_success "Docker container is running"
    return 0
}

test_http_redirect() {
    log_info "Testing HTTP to HTTPS redirect..."
    
    local response=$(curl -s -I -w "%{http_code}" -o /dev/null "http://$DOMAIN" --connect-timeout $TIMEOUT || echo "000")
    
    if [[ "$response" =~ ^30[1-8]$ ]]; then
        log_success "HTTP redirects to HTTPS (status: $response)"
        return 0
    else
        log_error "HTTP redirect failed (status: $response)"
        return 1
    fi
}

test_https_connection() {
    log_info "Testing HTTPS connection..."
    
    local response=$(curl -s -I -k -w "%{http_code}" -o /dev/null "https://$DOMAIN" --connect-timeout $TIMEOUT || echo "000")
    
    if [[ "$response" == "200" ]]; then
        log_success "HTTPS connection successful"
        return 0
    else
        log_error "HTTPS connection failed (status: $response)"
        return 1
    fi
}

test_ssl_certificate() {
    log_info "Testing SSL certificate..."
    
    local cert_info=$(openssl s_client -connect "$DOMAIN:443" -servername "$DOMAIN" </dev/null 2>/dev/null | openssl x509 -noout -dates 2>/dev/null)
    
    if [[ -n "$cert_info" ]]; then
        log_success "SSL certificate is valid"
        if [[ "$VERBOSE" == "true" ]]; then
            log_verbose "$cert_info"
        fi
        return 0
    else
        log_error "SSL certificate validation failed"
        return 1
    fi
}

test_frontend_loading() {
    log_info "Testing frontend loading..."
    
    local response=$(curl -s -k "https://$DOMAIN" --connect-timeout $TIMEOUT | grep -o "<title>.*</title>" || echo "")
    
    if [[ -n "$response" ]]; then
        log_success "Frontend loads successfully"
        log_verbose "Page title: $response"
        return 0
    else
        log_error "Frontend failed to load"
        return 1
    fi
}

test_api_health() {
    log_info "Testing API health endpoint..."
    
    local response=$(curl -s -k "https://$DOMAIN/api/health" --connect-timeout $TIMEOUT)
    local status=$(echo "$response" | jq -r '.status' 2>/dev/null || echo "unknown")
    
    if [[ "$status" == "healthy" ]]; then
        log_success "API health check passed"
        if [[ "$VERBOSE" == "true" ]]; then
            log_verbose "API response: $response"
        fi
        return 0
    else
        log_error "API health check failed"
        log_verbose "Response: $response"
        return 1
    fi
}

test_auth_endpoint() {
    log_info "Testing authentication endpoint..."
    
    local response=$(curl -s -k -w "%{http_code}" -o /dev/null "https://$DOMAIN/auth/health" --connect-timeout $TIMEOUT || echo "000")
    
    if [[ "$response" == "200" ]]; then
        log_success "Authentication endpoint accessible"
        return 0
    else
        log_warning "Authentication endpoint returned status: $response"
        return 1
    fi
}

test_database_connections() {
    log_info "Testing database connections..."
    
    local response=$(curl -s -k "https://$DOMAIN/api/capabilities" --connect-timeout $TIMEOUT)
    local databases=$(echo "$response" | jq -r '.databases[]?' 2>/dev/null | wc -l)
    
    if [[ "$databases" -gt 0 ]]; then
        log_success "Database connections configured ($databases databases)"
        if [[ "$VERBOSE" == "true" ]]; then
            echo "$response" | jq '.databases' 2>/dev/null || echo "$response"
        fi
        return 0
    else
        log_warning "No database connections detected"
        return 1
    fi
}

test_configuration_files() {
    log_info "Testing configuration files..."
    
    if [[ ! -f "config/config.yaml" ]]; then
        log_error "config.yaml not found"
        return 1
    fi
    
    if [[ ! -f "config/auth-config.yaml" ]]; then
        log_error "auth-config.yaml not found"
        return 1
    fi
    
    # Test YAML syntax
    if ! python3 -c "import yaml; yaml.safe_load(open('config/config.yaml'))" 2>/dev/null; then
        log_error "config.yaml has invalid YAML syntax"
        return 1
    fi
    
    if ! python3 -c "import yaml; yaml.safe_load(open('config/auth-config.yaml'))" 2>/dev/null; then
        log_error "auth-config.yaml has invalid YAML syntax"
        return 1
    fi
    
    log_success "Configuration files are valid"
    return 0
}

test_ssl_certificates() {
    log_info "Testing SSL certificate files..."
    
    if [[ ! -f "certs/certificate.crt" ]]; then
        log_error "SSL certificate not found: certs/certificate.crt"
        return 1
    fi
    
    if [[ ! -f "certs/private.key" ]]; then
        log_error "SSL private key not found: certs/private.key"
        return 1
    fi
    
    # Test certificate validity
    if ! openssl x509 -in certs/certificate.crt -noout 2>/dev/null; then
        log_error "SSL certificate is invalid"
        return 1
    fi
    
    if ! openssl rsa -in certs/private.key -check -noout 2>/dev/null; then
        log_error "SSL private key is invalid"
        return 1
    fi
    
    log_success "SSL certificate files are valid"
    return 0
}

# Main test execution
main() {
    echo "=== Ceneca Enterprise Deployment Test ==="
    echo "Domain: $DOMAIN"
    echo "Timeout: ${TIMEOUT}s"
    echo "Verbose: $VERBOSE"
    echo ""
    
    local failed_tests=0
    local total_tests=0
    
    # Pre-flight checks
    tests=(
        "test_configuration_files"
        "test_ssl_certificates"
        "test_docker_status"
    )
    
    # Network tests
    tests+=(
        "test_http_redirect"
        "test_https_connection"
        "test_ssl_certificate"
    )
    
    # Application tests
    tests+=(
        "test_frontend_loading"
        "test_api_health"
        "test_auth_endpoint"
        "test_database_connections"
    )
    
    for test in "${tests[@]}"; do
        ((total_tests++))
        if ! $test; then
            ((failed_tests++))
        fi
        echo ""
    done
    
    # Summary
    echo "=== Test Summary ==="
    echo "Total tests: $total_tests"
    echo "Passed: $((total_tests - failed_tests))"
    echo "Failed: $failed_tests"
    
    if [[ $failed_tests -eq 0 ]]; then
        log_success "All tests passed! 🎉"
        echo ""
        echo "Your Ceneca deployment is ready:"
        echo "👉 https://$DOMAIN"
        exit 0
    else
        log_error "Some tests failed"
        echo ""
        echo "Troubleshooting:"
        echo "1. Check logs: docker-compose logs"
        echo "2. Verify configuration files"
        echo "3. Check DNS and firewall settings"
        echo "4. Consult troubleshooting guide: docs/troubleshooting.md"
        exit 1
    fi
}

# Check dependencies
if ! command -v curl &> /dev/null; then
    log_error "curl is required but not installed"
    exit 1
fi

if ! command -v jq &> /dev/null; then
    log_warning "jq is not installed - some tests will have limited output"
fi

if ! command -v docker-compose &> /dev/null; then
    log_error "docker-compose is required but not installed"
    exit 1
fi

# Run tests
main 
# Template Editor Service - Testing Environment Setup

## Overview

This document describes the testing environment setup for the Template Editor Service, including the deploy-reference files that demonstrate the full scope of template types that need to be supported.

## Deploy Reference Files

The `deploy-reference/` directory contains real-world deployment files from the Ceneca project that represent the target complexity for the Template Editor Service extensibility.

### File Inventory

#### Configuration Files
- **`config.yaml`** - Main application configuration with database URIs, LLM settings, logging
- **`sample-config.yaml`** - Template version with placeholder values
- **`auth-config.yaml`** - SSO authentication configuration
- **`auth-config-auth0.yaml`** - Auth0-specific authentication configuration
- **`auth-config-azure.yaml`** - Azure AD authentication configuration  
- **`auth-config-google.yaml`** - Google OAuth authentication configuration
- **`auth-config.yaml.template`** - Template version of auth config

#### Container Orchestration
- **`ceneca-docker-compose.yml`** - Basic deployment with agent only
- **`enterprise-docker-compose.yml`** - Full enterprise setup with NGINX SSL termination
- **`Dockerfile`** - Container definition for Ceneca agent

#### Infrastructure Templates
- **`nginx/nginx.conf`** - Production NGINX reverse proxy configuration
- **`nginx/nginx.conf.template`** - Templated version with variable substitution
- **`nginx/ssl/cert.pem`** - SSL certificate file
- **`nginx/ssl/key.pem`** - SSL private key file

#### Installation & Build Scripts
- **`install.sh`** - Interactive deployment script with network/DNS configuration
- **`enterprise-install.sh`** - Enterprise-specific installation
- **`build-and-publish.sh`** - Container build and registry push
- **`generate-ssl-cert.sh`** - SSL certificate generation

#### Backup Files
- Multiple `config.yaml.backup.*` and `auth-config.yaml.backup.*` files showing version history

## Template Patterns Analysis

### Variable Substitution Patterns Found

#### Shell-Style Variables (`${VARIABLE}`)
Found in nginx templates, shell scripts:
```bash
server_name ${DOMAIN_NAME};
ssl_certificate ${SSL_CERT_PATH};
```

#### Environment Variable Expansion
Found in Docker Compose files:
```yaml
environment:
  - LLM_API_KEY=${LLM_API_KEY_VALUE}
  - POSTGRES_HOST=${POSTGRES_HOST}
```

#### YAML Configuration Patterns
Found in config.yaml files:
```yaml
postgres:
  uri: "postgresql://username:password@host:5432/database"
  pool:
    max_connections: 10
    ssl: true
```

### Cross-File Dependencies Identified

1. **config.yaml ↔ docker-compose.yml**
   - Database configurations must match service definitions
   - API keys and secrets must be consistent

2. **auth-config.yaml ↔ docker-compose.yml**
   - Authentication provider settings affect container environment variables
   - SSO redirect URLs must match exposed ports/domains

3. **nginx.conf ↔ docker-compose.yml**
   - Service names in nginx upstream must match compose service names
   - SSL certificate paths must match volume mounts

4. **Installation scripts ↔ All configs**
   - Scripts must generate configs consistent with template patterns
   - Environment variable names must match across all files

## Testing Scenarios

### Scenario 1: Basic Deployment
**Target Files:**
- `config.yaml`
- `ceneca-docker-compose.yml`

**Test Case:** Configure basic Ceneca deployment with PostgreSQL connection

### Scenario 2: Enterprise Deployment with Authentication
**Target Files:**
- `config.yaml`
- `auth-config-okta.yaml` (to be generated)
- `enterprise-docker-compose.yml`
- `nginx/nginx.conf`

**Test Case:** Set up full enterprise stack with Okta SSO and SSL termination

### Scenario 3: Provider-Specific Authentication
**Target Files:**
- `auth-config-azure.yaml`
- `auth-config-auth0.yaml`
- `auth-config-google.yaml`

**Test Case:** Switch between different authentication providers

### Scenario 4: SSL Certificate Management
**Target Files:**
- `nginx/nginx.conf.template`
- `generate-ssl-cert.sh`
- `nginx/ssl/cert.pem`
- `nginx/ssl/key.pem`

**Test Case:** Enable SSL with certificate generation and nginx configuration

## Current Template Editor Service Gaps

### Format Support Gaps
- ❌ **YAML files** - Currently only supports JavaScript/Node.js configs
- ❌ **Docker Compose** - No support for service orchestration files
- ❌ **NGINX configs** - No support for web server configurations
- ❌ **Shell scripts** - No support for installation/setup scripts

### Template Processing Gaps
- ❌ **Shell variable substitution** (`${VARIABLE}`) - Currently only supports Mustache (`{{VARIABLE}}`)
- ❌ **Multi-file coordination** - No understanding of cross-file dependencies
- ❌ **Complex validation** - No syntax validation for YAML, Docker Compose, NGINX
- ❌ **Scenario-based templates** - No pre-configured deployment packages

### AI Agent Capability Gaps
- ❌ **Multi-file awareness** - Can't understand relationships between configs
- ❌ **Domain expertise** - No specialized knowledge of Docker, NGINX, SSL, etc.
- ❌ **Deployment intelligence** - Can't suggest complementary configurations
- ❌ **Security validation** - No enterprise-grade security checks

## Development Priorities

### Phase 1: Multi-Format Support
1. Add YAML template processor
2. Add Docker Compose template processor
3. Add NGINX configuration processor
4. Extend variable substitution to support `${VARIABLE}` pattern

### Phase 2: Cross-File Intelligence
1. Implement dependency tracking between templates
2. Add validation for cross-file consistency
3. Enable intelligent cross-file updates

### Phase 3: Scenario-Based Templates
1. Create deployment scenario packages
2. Implement scenario-aware AI agent
3. Add pre-configured template combinations

### Phase 4: Enterprise Features
1. Advanced security validation
2. SSL certificate management
3. Infrastructure-as-Code generation

## Testing Environment Usage

### For Development
Use these files to test new template processors and validation logic:

```bash
# Test YAML processing
./test-yaml-processor.py deploy-reference/config.yaml

# Test Docker Compose processing  
./test-compose-processor.py deploy-reference/ceneca-docker-compose.yml

# Test cross-file dependencies
./test-dependencies.py deploy-reference/config.yaml deploy-reference/ceneca-docker-compose.yml
```

### For AI Agent Testing
Use these files to test enhanced AI agent capabilities:

```bash
# Test multi-file workspace
curl -X POST /api/sessions -d '{"template_version": "enterprise-v1.0.0"}'

# Test scenario-based configuration
echo "Set up enterprise deployment with Okta auth" | ./test-ai-agent.py
```

### For Integration Testing
Use complete scenarios to test end-to-end functionality:

```bash
# Test complete enterprise setup
./test-enterprise-scenario.py
```

This testing environment provides a comprehensive foundation for extending the Template Editor Service to handle real-world enterprise deployment complexity.
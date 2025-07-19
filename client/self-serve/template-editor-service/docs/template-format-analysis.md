# Template Format Analysis - Deploy Reference Files

## Overview

Analysis of deploy-reference files to identify template formatting requirements and conversions needed to match our `{{ VARIABLE }}` template system.

## Current Template Format Standards

Our Template Editor Service uses **Mustache-style** variable substitution: `{{ VARIABLE_NAME }}`

## File Analysis Results

### ✅ Files Already Using Correct Format `{{ VARIABLE }}`

#### **config.yaml**
- **Status**: ✅ Already templated correctly
- **Variables**: `{{ POSTGRES_USERNAME }}`, `{{ POSTGRES_PASSWORD }}`, `{{ POSTGRES_HOST }}`, `{{ POSTGRES_DATABASE }}`, `{{ MONGODB_USERNAME }}`, `{{ MONGODB_PASSWORD }}`, `{{ MONGODB_HOST }}`, `{{ MONGODB_DATABASE }}`, `{{ QDRANT_HOST }}`, `{{ QDRANT_API_KEY }}`
- **Ready for**: Direct use in template system

#### **ceneca-docker-compose.yml**
- **Status**: ✅ Already templated correctly  
- **Variables**: `{{ LLM_API_KEY_VALUE }}`, `{{ POSTGRES_HOST }}`, `{{ POSTGRES_HOST_IP }}`, `{{ MONGODB_HOST }}`, `{{ MONGODB_HOST_IP }}`
- **Ready for**: Direct use in template system

#### **enterprise-docker-compose.yml**
- **Status**: ✅ Already templated correctly
- **Variables**: `{{ LLM_API_KEY_VALUE }}`, `{{ POSTGRES_HOST }}`, `{{ POSTGRES_HOST_IP }}`, `{{ MONGODB_HOST }}`, `{{ MONGODB_HOST_IP }}`, `{{ QDRANT_HOST }}`, `{{ QDRANT_HOST_IP }}`
- **Ready for**: Direct use in template system

### ✅ Files Converted to Correct Format

#### **auth-config.yaml.template** 
- **Status**: ✅ Converted from `${VARIABLE}` to `{{ VARIABLE }}`
- **Previous format**: `${OIDC_PROVIDER}`, `${OIDC_CLIENT_ID}`, etc.
- **Current format**: `{{ OIDC_PROVIDER }}`, `{{ OIDC_CLIENT_ID }}`, etc.
- **Variables**: 
  - `{{ OIDC_PROVIDER }}`
  - `{{ OIDC_CLIENT_ID }}`
  - `{{ OIDC_CLIENT_SECRET }}`
  - `{{ OIDC_ISSUER }}`
  - `{{ OIDC_DISCOVERY_URL }}`
  - `{{ DOMAIN_NAME }}`
  - `{{ ROLE_GROUP_1 }}`, `{{ ROLE_VALUE_1 }}`
  - `{{ ROLE_GROUP_2 }}`, `{{ ROLE_VALUE_2 }}`
  - `{{ ROLE_GROUP_3 }}`, `{{ ROLE_VALUE_3 }}`

#### **nginx/nginx.conf.template**
- **Status**: ✅ Converted from `${VARIABLE}` to `{{ VARIABLE }}`
- **Previous format**: `${DOMAIN_NAME}`
- **Current format**: `{{ DOMAIN_NAME }}`
- **Variables**: `{{ DOMAIN_NAME }}`

### 🔄 Files That Could Be Templated (Currently Hardcoded)

#### **auth-config-azure.yaml**
- **Status**: 🔄 Hardcoded values, could benefit from templating
- **Potential templates**: Azure tenant ID, client ID, client secret, redirect URIs
- **Recommendation**: Create `auth-config-azure.yaml.template`

#### **auth-config-auth0.yaml**
- **Status**: 🔄 Hardcoded values, could benefit from templating  
- **Potential templates**: Auth0 domain, client ID, client secret, callback URLs
- **Recommendation**: Create `auth-config-auth0.yaml.template`

#### **auth-config-google.yaml**
- **Status**: 🔄 Hardcoded values, could benefit from templating
- **Potential templates**: Google client ID, client secret, redirect URIs
- **Recommendation**: Create `auth-config-google.yaml.template`

#### **nginx/nginx.conf**
- **Status**: 🔄 Hardcoded configuration
- **Potential templates**: Domain name, SSL certificate paths, upstream server names
- **Recommendation**: Use existing `nginx.conf.template` as primary template

### ✅ Script Files (No Templating Needed)

#### **install.sh, enterprise-install.sh, build-and-publish.sh, generate-ssl-cert.sh**
- **Status**: ✅ Executable scripts, no template variables needed
- **Purpose**: Installation automation, certificate generation
- **Template usage**: Could be enhanced to use config files generated from templates

## Template Variable Inventory

### Database Configuration
- `{{ POSTGRES_USERNAME }}`, `{{ POSTGRES_PASSWORD }}`, `{{ POSTGRES_HOST }}`, `{{ POSTGRES_DATABASE }}`
- `{{ MONGODB_USERNAME }}`, `{{ MONGODB_PASSWORD }}`, `{{ MONGODB_HOST }}`, `{{ MONGODB_DATABASE }}`
- `{{ QDRANT_HOST }}`, `{{ QDRANT_API_KEY }}`

### Authentication Configuration
- `{{ OIDC_PROVIDER }}`, `{{ OIDC_CLIENT_ID }}`, `{{ OIDC_CLIENT_SECRET }}`
- `{{ OIDC_ISSUER }}`, `{{ OIDC_DISCOVERY_URL }}`
- `{{ ROLE_GROUP_1 }}`, `{{ ROLE_VALUE_1 }}`, `{{ ROLE_GROUP_2 }}`, `{{ ROLE_VALUE_2 }}`, `{{ ROLE_GROUP_3 }}`, `{{ ROLE_VALUE_3 }}`

### Infrastructure Configuration
- `{{ DOMAIN_NAME }}`
- `{{ LLM_API_KEY_VALUE }}`
- `{{ POSTGRES_HOST_IP }}`, `{{ MONGODB_HOST_IP }}`, `{{ QDRANT_HOST_IP }}`

## Ready-to-Use Template Files

The following files are now ready for integration into the Template Editor Service:

### Core Configuration Templates
1. **`config.yaml`** - Main application configuration
2. **`auth-config.yaml.template`** - OIDC authentication configuration

### Deployment Templates  
3. **`ceneca-docker-compose.yml`** - Basic deployment
4. **`enterprise-docker-compose.yml`** - Enterprise deployment with NGINX

### Infrastructure Templates
5. **`nginx/nginx.conf.template`** - NGINX reverse proxy configuration

## Integration Recommendations

### Phase 1: Core Templates
Start with the 5 ready-to-use template files above:
- Main config (database connections, LLM settings)
- Basic and enterprise Docker Compose deployments
- NGINX reverse proxy with SSL
- OIDC authentication configuration

### Phase 2: Provider-Specific Templates
Create template versions of provider-specific auth configs:
- `auth-config-azure.yaml.template`
- `auth-config-auth0.yaml.template` 
- `auth-config-google.yaml.template`

### Phase 3: Advanced Scenarios
- Multi-environment configurations (dev, staging, prod)
- Kubernetes deployment templates
- Advanced SSL/certificate management

## Template Dependencies

### Cross-File Relationships
1. **config.yaml ↔ docker-compose.yml**
   - Database host names must match
   - API keys must be consistent

2. **auth-config.yaml ↔ nginx.conf**
   - Redirect URIs must match exposed domains
   - Authentication endpoints must be proxied correctly

3. **nginx.conf ↔ docker-compose.yml**
   - Service names in nginx upstream must match compose service names
   - SSL certificate volume mounts must be consistent

## Validation Requirements

### Syntax Validation
- **YAML**: config.yaml, auth-config.yaml files
- **Docker Compose**: docker-compose.yml files  
- **NGINX**: nginx.conf files

### Cross-File Validation
- Database connection strings consistency
- Service name matching between compose and nginx
- SSL certificate path consistency
- Authentication callback URL matching

### Security Validation
- No hardcoded secrets in template files
- Secure SSL configuration
- Proper authentication flow configuration

This analysis shows that the deploy-reference files are largely ready for integration into the Template Editor Service, with most key files already using the correct `{{ VARIABLE }}` template format.
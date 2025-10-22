# Template Editor Service - Extensibility Design

## Overview

The Template Editor Service needs to evolve from a simple auth template editor to a comprehensive deployment configuration management system that can handle the full complexity of Ceneca's enterprise-grade containerized application deployment.

## Project Context: Ceneca Architecture

**Ceneca** is a sophisticated **on-premises AI data analyst** that enables natural language querying across multiple enterprise data sources while keeping all data within the client's security perimeter.

### Core Components
- **Multi-tier LLM Infrastructure**: Smart routing between fast (Grok-3-Mini, AWS Nova) and powerful (GPT-4o, Claude) models
- **Cross-Database Orchestration**: Unified querying across PostgreSQL, MongoDB, Qdrant, Slack, and GA4
- **Enterprise Authentication**: OIDC/SAML SSO integration with major providers (Azure AD, Okta, Google, Auth0)
- **Deployment Flexibility**: Docker, Kubernetes, and direct installation options
- **Adapter Architecture**: Extensible system for adding new data sources

### Key Architectural Patterns
- **Planning Agent**: Generates optimized cross-database query plans
- **Implementation Agent**: Executes plans with parallelism and error handling
- **Configuration-Driven**: Single `config.yaml` file controls all integrations
- **Template-Based Deployment**: Production-ready files with placeholder substitution

## Current State vs. Required Extensions

### Current Template Editor Service (Limited)
- Only handles basic auth templates (JWT, OAuth, local auth)
- Single template version (`auth-v1.0.0`)
- Simple JavaScript/Node.js configuration files
- Basic placeholder substitution (`{{VARIABLE}}`)

### Required Extensions (Comprehensive)

#### Multi-Format Template Support
- **YAML configurations** (config.yaml, auth-config.yaml variants)
- **Docker Compose files** (multiple orchestration scenarios)
- **NGINX configurations** (reverse proxy, SSL, security headers)
- **Shell scripts** (installation, setup, SSL generation)
- **Environment files** (.env with various variable patterns)

#### Variable Substitution Patterns
- **Mustache-style**: `{{VARIABLE}}` (current auth templates)
- **Shell-style**: `${VARIABLE}` (nginx templates, scripts)
- **Docker Compose**: Environment variable expansion
- **Complex substitution**: Conditional blocks, loops, nested objects

#### Deployment Scenario Templates
- **Basic**: Single agent with external databases
- **Enterprise**: Full stack with NGINX, SSL, monitoring
- **Cloud**: Kubernetes manifests, ingress configurations
- **Hybrid**: Mix of on-prem and cloud components

## Template Categories Analysis

### Configuration Templates
- `config.yaml` - Main application configuration with database URIs, LLM settings, logging
- `sample-config.yaml` - Template version with placeholder values
- `auth-config.yaml` - SSO authentication configuration
- Provider-specific auth configs: `auth-config-azure.yaml`, `auth-config-auth0.yaml`, `auth-config-google.yaml`

### Container Orchestration
- `ceneca-docker-compose.yml` - Basic deployment with agent only
- `enterprise-docker-compose.yml` - Full enterprise setup with NGINX SSL termination
- `Dockerfile` - Container definition for Ceneca agent

### Infrastructure Templates
- `nginx/nginx.conf` - Production NGINX reverse proxy configuration
- `nginx/nginx.conf.template` - Templated version with variable substitution
- SSL certificates: `nginx/ssl/cert.pem`, `nginx/ssl/key.pem`

### Installation Scripts
- `install.sh` - Interactive deployment script with network/DNS configuration
- `enterprise-install.sh` - Enterprise-specific installation
- `build-and-publish.sh` - Container build and registry push
- `generate-ssl-cert.sh` - SSL certificate generation

## System Design Approach

### 1. Multi-Dimensional Template Architecture

Implement a hierarchical template registry:

```
Templates/
├── deployment-scenarios/
│   ├── basic/
│   ├── enterprise/
│   └── cloud-native/
├── configuration-types/
│   ├── application/
│   ├── authentication/
│   └── infrastructure/
└── file-formats/
    ├── yaml/
    ├── docker-compose/
    └── nginx/
```

### 2. Template Processing Engine Abstraction

Create pluggable template processors for different formats:

```python
class TemplateProcessor:
    def supports_file_type(self, file_path: str) -> bool
    def validate_syntax(self, content: str) -> ValidationResult
    def extract_variables(self, content: str) -> List[Variable]
    def apply_substitutions(self, content: str, values: Dict) -> str
    def get_dependencies(self, content: str) -> List[FileDependency]
```

**Processor Types:**
- **YAML Processor**: Handle `config.yaml`, auth configs with complex nested structures
- **Docker Compose Processor**: Service definitions, networks, volumes
- **NGINX Processor**: Server blocks, SSL configurations, proxying rules
- **Shell Script Processor**: Installation scripts with conditional logic

### 3. Intelligent Template Orchestration

#### Cross-Template Dependencies
- Changes to `config.yaml` → Auto-update corresponding `docker-compose.yml`
- Auth provider selection → Generate matching `auth-config-{provider}.yaml`
- SSL enablement → Update NGINX config + generate certificates

#### Scenario-Based Templates
- "Basic Deployment" → `config.yaml` + `ceneca-docker-compose.yml`
- "Enterprise Setup" → Full stack with NGINX, SSL, monitoring
- "Okta Integration" → Auth configs + SSO-enabled docker compose

### 4. Enhanced AI Agent Capabilities

#### Multi-File Workspace Management
- Understand relationships between configuration files
- Validate cross-file consistency (database URLs, service names, etc.)
- Suggest complementary configurations

#### Domain-Specific Intelligence
- **Database Specialist**: PostgreSQL, MongoDB connection optimization
- **Auth Specialist**: OIDC/SAML configuration best practices
- **Infrastructure Specialist**: Docker networking, SSL, security headers
- **Deployment Specialist**: Installation scripts, environment setup

### 5. Variable Substitution Framework

Support multiple templating patterns:
- **Mustache**: `{{VARIABLE}}` (current auth templates)
- **Shell**: `${VARIABLE}` (nginx templates, scripts)
- **Environment**: Docker Compose variable expansion
- **Conditional**: Jinja2-style logic for complex scenarios

### 6. Validation & Security Framework

#### Multi-Layer Validation
- **Syntax**: YAML, Docker Compose, NGINX configuration
- **Schema**: JSON Schema validation for structured configs
- **Security**: No hardcoded secrets, secure defaults, SSL enforcement
- **Deployment**: Service connectivity, port conflicts, resource allocation

## Extensibility Strategy

### Template Plugin Architecture

```python
TEMPLATE_TYPES = {
    "deployment": {
        "docker-compose": {
            "basic": ["ceneca-docker-compose.yml"],
            "enterprise": ["enterprise-docker-compose.yml"],
            "custom": ["user-defined-compose.yml"]
        },
        "kubernetes": ["ceneca-deployment.yaml"],
        "scripts": ["install.sh", "enterprise-install.sh"]
    },
    "configuration": {
        "application": ["config.yaml", "sample-config.yaml"],
        "authentication": ["auth-config*.yaml"],
        "infrastructure": ["nginx.conf", "ssl certificates"]
    }
}
```

### Scenario-Based Template Packages

Pre-configured template combinations:
- **"Add Slack Integration"** → Update config.yaml + docker-compose + auth
- **"Enable SSL"** → Generate certificates + update NGINX + docker volumes
- **"Switch to Okta"** → Auth config + environment variables + restart sequence

### Progressive Complexity

- **Level 1**: Simple variable substitution (current capability)
- **Level 2**: Multi-file coordination (config ↔ compose ↔ nginx)
- **Level 3**: Scenario-based deployment packages
- **Level 4**: Infrastructure-as-Code generation (Kubernetes, Terraform)

## AI Agent Enhancement Strategy

### Context-Aware Intelligence

Transform from generic "Auth File Editor Agent" to deployment scenario specialists:

- **"Deployment Architect"**: Understands full-stack requirements
- **"Security Engineer"**: SSL, auth, network security configurations
- **"Database Administrator"**: Connection pooling, SSL, performance tuning
- **"Infrastructure Engineer"**: Container orchestration, networking, scaling

### Conversational Deployment

Enable natural language deployment planning:
- *"Set up enterprise deployment with Okta auth and PostgreSQL"*
- *"Add Slack integration to existing setup"*
- *"Enable SSL with auto-renewal"*
- *"Migrate from basic to enterprise configuration"*

## Implementation Roadmap

### Phase 1: Multi-Format Template Support
- Extend template manager to handle YAML, Docker Compose, NGINX configs
- Implement format-specific processors
- Add syntax validation for each format

### Phase 2: Cross-File Dependency Management
- Build dependency graph between templates
- Implement consistency validation across files
- Add intelligent cross-file updates

### Phase 3: Scenario-Based Template Packages
- Create pre-configured deployment scenarios
- Implement scenario-aware AI agent
- Add deployment package management

### Phase 4: Advanced AI Deployment Intelligence
- Multi-agent specialization system
- Natural language deployment planning
- Infrastructure-as-Code generation

## Key Design Principles

1. **Extensibility**: Plugin architecture for new template types
2. **Intelligence**: AI understands deployment relationships
3. **Safety**: Multi-layer validation and security checks
4. **Usability**: Conversational interface for complex configurations
5. **Scalability**: Handle enterprise-grade deployment complexity

## Success Metrics

- **Template Coverage**: Support for all Ceneca deployment file types
- **Cross-File Intelligence**: Automatic dependency management
- **Deployment Success Rate**: Validated, production-ready configurations
- **User Experience**: Natural language deployment configuration
- **Extensibility**: Easy addition of new template types and scenarios

This design transforms the Template Editor Service into a comprehensive deployment configuration management system while maintaining the intuitive conversational interface that makes complex enterprise deployment accessible to all users.
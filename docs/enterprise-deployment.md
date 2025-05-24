# Ceneca Enterprise Deployment Guide

This guide provides detailed instructions for deploying and using Ceneca in an enterprise environment. It is divided into two main sections:
1. **Enterprise Admin Guide**: For IT administrators and DevOps teams deploying and configuring Ceneca
2. **Enterprise Client Guide**: For end-users accessing Ceneca via SSO and running queries

## Enterprise Admin Guide (0 → 1 → 100)

### Phase 0: Prerequisites

Before deploying Ceneca, ensure the following prerequisites are met:

- Host system with one of the following:
  - Docker and Docker Compose (simplest option)
  - Kubernetes cluster
  - Linux/Unix machine with Python 3.10+
- Network connectivity to enterprise data sources
- Outbound internet connectivity (for LLM API calls, unless using local LLMs)
- SSL certificates (for production deployments)
- SSO provider details (SAML or OIDC compliant)

### Phase 1: Basic Deployment

#### Step 1: Prepare Configuration

1. Create a deployment directory:
   ```bash
   mkdir -p /opt/ceneca
   cd /opt/ceneca
   ```

2. Prepare the `config.yaml` file:
   ```bash
   mkdir -p ~/.data-connector
   cp /path/to/sample-config.yaml ~/.data-connector/config.yaml
   ```

3. Edit the configuration to include your database credentials:
   ```bash
   nano ~/.data-connector/config.yaml
   ```
   
   Update the following sections:
   - Database credentials (Postgres, MongoDB, etc.)
   - LLM provider settings
   - Optional integrations (Slack, GA4, etc.)

#### Step 2: Docker Deployment (Recommended)

1. Create a `docker-compose.yml` file:
   ```bash
   cat > docker-compose.yml << 'EOF'
   version: '3.8'
   
   services:
     ceneca-agent:
       image: ceneca/agent:latest
       container_name: ceneca-agent
       ports:
         - "8787:8787"
       volumes:
         - ~/.data-connector:/root/.data-connector
       environment:
         - AGENT_PORT=8787
         - LLM_API_KEY=${LLM_API_KEY}
       restart: unless-stopped
       networks:
         - ceneca-network
       depends_on:
         - postgres
         - mongodb
         - qdrant
     
     postgres:
       image: postgres:16
       container_name: ceneca-postgres
       environment:
         POSTGRES_USER: dataconnector
         POSTGRES_PASSWORD: dataconnector
         POSTGRES_DB: dataconnector
       ports:
         - "6000:5432"
       volumes:
         - postgres-data:/var/lib/postgresql/data
       networks:
         - ceneca-network
   
     mongodb:
       image: mongo:7
       container_name: ceneca-mongodb
       environment:
         MONGO_INITDB_ROOT_USERNAME: dataconnector
         MONGO_INITDB_ROOT_PASSWORD: dataconnector
         MONGO_INITDB_DATABASE: dataconnector_mongo
       ports:
         - "27000:27017"
       volumes:
         - mongodb-data:/data/db
       networks:
         - ceneca-network
   
     qdrant:
       image: qdrant/qdrant:latest
       container_name: ceneca-qdrant
       ports:
         - "7500:6333"
         - "7501:6334"
       volumes:
         - qdrant-data:/qdrant/storage
       networks:
         - ceneca-network
   
     # Include only if Slack integration is needed
     slack-mcp-server:
       image: ceneca/slack-mcp:latest
       container_name: ceneca-slack-mcp
       ports:
         - "8500:8500"
       environment:
         - MCP_HOST=0.0.0.0
         - MCP_PORT=8500
         - MCP_DB_HOST=postgres-mcp
         - MCP_DB_PORT=5432
         - MCP_DB_NAME=slackoauth
         - MCP_DB_USER=slackoauth
         - MCP_DB_PASSWORD=slackoauth
         - MCP_SLACK_CLIENT_ID=${MCP_SLACK_CLIENT_ID}
         - MCP_SLACK_CLIENT_SECRET=${MCP_SLACK_CLIENT_SECRET}
         - MCP_SLACK_SIGNING_SECRET=${MCP_SLACK_SIGNING_SECRET}
       depends_on:
         - postgres-mcp
       networks:
         - ceneca-network
   
     # Postgres for Slack OAuth (only if using Slack)
     postgres-mcp:
       image: postgres:16
       container_name: ceneca-postgres-mcp
       environment:
         POSTGRES_USER: slackoauth
         POSTGRES_PASSWORD: slackoauth
         POSTGRES_DB: slackoauth
       ports:
         - "6500:5432"
       volumes:
         - postgres-mcp-data:/var/lib/postgresql/data
       networks:
         - ceneca-network
   
   networks:
     ceneca-network:
       driver: bridge
   
   volumes:
     postgres-data:
     mongodb-data:
     qdrant-data:
     postgres-mcp-data:
   EOF
   ```

2. Create a startup script:
   ```bash
   cat > deploy.sh << 'EOF'
   #!/bin/bash
   
   # Export necessary environment variables
   export LLM_API_KEY="your-openai-api-key"
   
   # If using Slack, uncomment and fill these
   # export MCP_SLACK_CLIENT_ID="your-slack-client-id"
   # export MCP_SLACK_CLIENT_SECRET="your-slack-client-secret"
   # export MCP_SLACK_SIGNING_SECRET="your-slack-signing-secret"
   
   # Start the Ceneca stack
   docker-compose up -d
   
   echo "Ceneca is starting up..."
   echo "Web interface will be available at http://localhost:8787"
   
   # Optional: Wait and check if services are healthy
   sleep 5
   docker-compose ps
   EOF
   ```

3. Make the script executable and run it:
   ```bash
   chmod +x deploy.sh
   ./deploy.sh
   ```

#### Step 3: Kubernetes Deployment (Alternative)

1. Create a Kubernetes manifest:
   ```bash
   mkdir -p k8s
   cat > k8s/ceneca-deployment.yaml << 'EOF'
   apiVersion: v1
   kind: ConfigMap
   metadata:
     name: ceneca-config
   data:
     config.yaml: |
       # Copy your config.yaml contents here, properly indented
       default_database: postgres
       
       postgres:
         uri: postgresql://dataconnector:dataconnector@ceneca-postgres:5432/dataconnector
       
       # Additional configuration...
   ---
   apiVersion: apps/v1
   kind: Deployment
   metadata:
     name: ceneca-agent
     labels:
       app: ceneca
       role: agent
   spec:
     replicas: 1
     selector:
       matchLabels:
         app: ceneca
         role: agent
     template:
       metadata:
         labels:
           app: ceneca
           role: agent
       spec:
         containers:
         - name: agent
           image: ceneca/agent:latest
           imagePullPolicy: IfNotPresent
           ports:
           - containerPort: 8787
             name: http
           env:
           - name: AGENT_PORT
             value: "8787"
           - name: LLM_API_KEY
             valueFrom:
               secretKeyRef:
                 name: ceneca-secrets
                 key: LLM_API_KEY
           volumeMounts:
           - name: config-volume
             mountPath: /root/.data-connector/
         volumes:
         - name: config-volume
           configMap:
             name: ceneca-config
             items:
               - key: config.yaml
                 path: config.yaml
   ---
   apiVersion: v1
   kind: Service
   metadata:
     name: ceneca-agent-service
   spec:
     type: ClusterIP
     selector:
       app: ceneca
       role: agent
     ports:
       - port: 8787
         targetPort: 8787
         protocol: TCP
         name: http
   
   # Additional services for Postgres, MongoDB, etc. would be defined here
   EOF
   ```

2. Create a secret for sensitive data:
   ```bash
   kubectl create secret generic ceneca-secrets \
     --from-literal=LLM_API_KEY="your-openai-api-key"
   ```

3. Apply the Kubernetes manifest:
   ```bash
   kubectl apply -f k8s/ceneca-deployment.yaml
   ```

4. Verify the deployment:
   ```bash
   kubectl get pods
   kubectl get services
   ```

#### Step 4: Local Development Deployment

1. Set up a Python virtual environment:
   ```bash
   cd /path/to/data-connector
   python -m venv venv
   source venv/bin/activate
   ```

2. Install dependencies:
   ```bash
   cd server
   pip install -r requirements.txt
   ```

3. Run the Ceneca agent:
   ```bash
   export AGENT_PORT=8787
   export LLM_API_KEY="your-openai-api-key"
   python main.py
   ```

### Phase 2: Integration with SSO

Single Sign-On (SSO) integration allows your enterprise users to authenticate using your existing identity provider. Ceneca supports both OIDC and SAML protocols, allowing integration with virtually any enterprise identity system.

#### Step 1: Understanding SSO Components

1. **Identity Protocols Overview**:

   * **OIDC (OpenID Connect)**: Modern JSON-based protocol built on OAuth 2.0
     * Used by: Azure AD, Okta, Google Workspace, Auth0
     * Advantages: Simpler implementation, better for mobile/API access
     * Flow: Authorization code flow with PKCE for web applications

   * **SAML 2.0**: XML-based enterprise protocol
     * Used by: ADFS, Okta, Ping Identity, older enterprise systems
     * Advantages: Widespread enterprise adoption, mature standard
     * Flow: Browser-based with signed XML assertions

   Ceneca supports both protocols simultaneously, so you can choose the one that best matches your existing infrastructure.

2. **NGINX's Role in SSO**:

   NGINX serves as a reverse proxy that:
   * Provides SSL termination (handles HTTPS)
   * Presents a consistent, secure endpoint for the SSO provider
   * Manages security headers and routes authentication traffic
   * Shields your application from direct internet exposure

   Without NGINX, you would need to handle SSL, security headers, and traffic routing directly in your application.

#### Step 2: Custom Domain Configuration

Ceneca can be accessed through various domain patterns depending on your needs:

1. **Determine Your Domain Strategy**:
   * **Cloud-hosted subdomain**: `your-company.ceneca.ai`
   * **Custom domain**: `ceneca.your-company.com` or `data-analytics.your-company.com`
   * **Internal domain**: `ceneca.internal.your-company.local`

2. **Configure DNS for Your Domain**:
   ```bash
   # For a custom domain like ceneca.your-company.com:
   # Add this to your DNS configuration
   ceneca.your-company.com.  IN  CNAME  <load-balancer-name>.ceneca.ai.
   
   # For on-premise, point to your internal IP
   ceneca.internal.your-company.local.  IN  A  192.168.1.100
   ```

3. **SSL Certificate Acquisition**:
   * **Option 1**: Generate a certificate signing request (CSR):
     ```bash
     openssl req -new -newkey rsa:2048 -nodes -keyout ceneca.key -out ceneca.csr
     ```
   * **Option 2**: Use Let's Encrypt for automated certificates (if publicly accessible)
   * **Option 3**: Use your enterprise CA for internal deployments

4. **Place SSL Certificates**:
   ```bash
   mkdir -p /opt/ceneca/ssl
   cp your-cert.pem /opt/ceneca/ssl/cert.pem
   cp your-key.pem /opt/ceneca/ssl/key.pem
   ```

#### Step 3: Configure SSO Provider

1. **Register Ceneca in Your SSO Provider**:

   **For OIDC (e.g., Azure AD, Okta)**:
   * Register a new application
   * Application type: Web
   * Redirect URI: `https://your-ceneca-domain.com/oauth/callback`
   * Required scopes: `openid email profile groups`
   * Grant types: Authorization Code
   * Note the Client ID and Secret

   **For SAML (e.g., ADFS, Okta SAML)**:
   * Add a new SAML application
   * Assertion Consumer Service (ACS) URL: `https://your-ceneca-domain.com/saml/callback`
   * Entity ID / Audience: `https://your-ceneca-domain.com`
   * Requested attributes: `email`, `firstname`, `lastname`, `groups`
   * Download the Identity Provider metadata XML

2. **Configure Attribute/Claim Mappings**:
   
   Ensure your IdP sends these claims/attributes:
   * User identifier (email or ID)
   * User name (display name)
   * Group memberships or roles
   * Email address

   **Example Azure AD claim mapping**:
   ```json
   {
     "email": "preferred_username",
     "name": "name",
     "groups": "groups"
   }
   ```

   **Example SAML attribute mapping**:
   ```xml
   <saml:AttributeStatement>
     <saml:Attribute Name="http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress">
       <saml:AttributeValue>user@company.com</saml:AttributeValue>
     </saml:Attribute>
     <saml:Attribute Name="groups">
       <saml:AttributeValue>HR-Analysts</saml:AttributeValue>
     </saml:Attribute>
   </saml:AttributeStatement>
   ```

#### Step 4: Configure Ceneca for SSO

1. **Create an Authentication Configuration File**:
   ```bash
   cat > ~/.data-connector/auth-config.yaml << 'EOF'
   sso:
     # Common settings
     enabled: true
     default_protocol: "oidc"  # or "saml"
     domain: "your-ceneca-domain.com"
     
     # OIDC Configuration (for providers like Okta, Azure AD, etc.)
     oidc:
       provider: "azure"  # or "okta", "google", etc.
       client_id: "your-client-id"
       client_secret: "your-client-secret"
       discovery_url: "https://login.microsoftonline.com/tenant-id/v2.0/.well-known/openid-configuration"
       redirect_uri: "https://your-ceneca-domain.com/oauth/callback"
       scopes: ["openid", "email", "profile", "groups"]
       # Map provider claims to Ceneca user attributes
       claims_mapping:
         email: "preferred_username"
         name: "name"
         groups: "groups"
     
     # SAML Configuration (for providers like ADFS, Okta SAML, etc.)
     saml:
       entity_id: "https://your-ceneca-domain.com"
       acs_url: "https://your-ceneca-domain.com/saml/callback"
       idp_metadata_path: "/path/to/idp-metadata.xml"
       # Or provide metadata URL instead
       # idp_metadata_url: "https://your-idp.com/metadata"
       # Certificate for validating SAML assertions
       idp_cert_path: "/path/to/idp-certificate.pem"
       # Attribute mapping from SAML to Ceneca
       attribute_mapping:
         email: "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress"
         name: "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name"
         groups: "groups"
   
   # Role mappings from IdP groups to Ceneca roles
   role_mappings:
     "HR-Analysts": "hr_read"
     "Finance-Team": "finance_read"
     "Data-Admins": "admin"
   EOF
   ```

2. **Configure NGINX**:

   Create a templated NGINX configuration:
   ```bash
   cat > nginx.conf.template << 'EOF'
   server {
       listen 443 ssl;
       server_name ${DOMAIN_NAME};
       
       # SSL Configuration
       ssl_certificate /etc/nginx/ssl/cert.pem;
       ssl_certificate_key /etc/nginx/ssl/key.pem;
       
       # Strong SSL settings
       ssl_protocols TLSv1.2 TLSv1.3;
       ssl_prefer_server_ciphers on;
       ssl_ciphers 'ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256';
       ssl_session_timeout 1d;
       ssl_session_cache shared:SSL:50m;
       
       # Security headers
       add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
       add_header X-Content-Type-Options nosniff always;
       add_header X-Frame-Options SAMEORIGIN always;
       add_header X-XSS-Protection "1; mode=block" always;
       
       # Proxy settings
       location / {
           proxy_pass http://ceneca-agent:8787;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }
       
       # OAuth callback endpoint
       location /oauth/callback {
           proxy_pass http://ceneca-agent:8787/oauth/callback;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }
       
       # SAML callback endpoint
       location /saml/callback {
           proxy_pass http://ceneca-agent:8787/saml/callback;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }
   }
   EOF
   ```

   Generate the actual configuration by replacing the placeholder:
   ```bash
   export DOMAIN_NAME="your-ceneca-domain.com"
   cat nginx.conf.template | envsubst '${DOMAIN_NAME}' > nginx.conf
   ```

3. **Update Docker Compose**:
   ```yaml
   services:
     ceneca-agent:
       # ... existing configuration ...
       volumes:
         - ~/.data-connector:/root/.data-connector
       environment:
         - AUTH_CONFIG_PATH=/root/.data-connector/auth-config.yaml
         - AUTH_ENABLED=true
         
     nginx:
       image: nginx:latest
       ports:
         - "443:443"
       volumes:
         - ./nginx.conf:/etc/nginx/conf.d/default.conf
         - ./ssl:/etc/nginx/ssl
       depends_on:
         - ceneca-agent
       networks:
         - ceneca-network
   ```

#### Step 5: Testing SSO Integration

1. **Start the Updated Stack**:
   ```bash
   docker-compose up -d
   ```

2. **Verify NGINX Configuration**:
   ```bash
   docker-compose exec nginx nginx -t
   ```

3. **Test SSO Flow**:
   * Open `https://your-ceneca-domain.com/login` in a browser
   * Click the SSO login option
   * Authenticate with your identity provider
   * Verify you're redirected back to Ceneca with proper authentication

4. **Troubleshooting**:
   * Check NGINX logs: `docker-compose logs nginx`
   * Check Ceneca agent logs: `docker-compose logs ceneca-agent`
   * Verify network connectivity between components
   * Check for certificate issues (proper chain, expiration)

#### Step 6: Advanced SSO Configurations

1. **Multi-Tenant Setup**:
   For supporting multiple organizations with different SSO providers:
   ```yaml
   tenants:
     acme-corp:
       sso:
         protocol: "oidc"
         # OIDC-specific settings
     widget-inc:
       sso:
         protocol: "saml"
         # SAML-specific settings
   ```

2. **Just-in-Time Provisioning**:
   Configure automatic user creation based on SSO attributes:
   ```yaml
   jit_provisioning:
     enabled: true
     default_role: "reader"
     create_from: 
       - "oidc"
       - "saml"
   ```

3. **Session Management**:
   Configure session timeouts and refresh behavior:
   ```yaml
   session:
     lifetime: 8h
     idle_timeout: 1h
     refresh_token_lifetime: 30d
   ```

### Phase 3: Production Hardening

1. Set up monitoring:
   ```bash
   # Add Prometheus and Grafana to your docker-compose.yml
   # or configure existing monitoring solutions
   ```

2. Set up logging:
   ```bash
   # Add centralized logging solutions like ELK stack
   # or configure logging to your existing log aggregation service
   ```

3. Configure regular backups of your configuration and database volumes.

4. Implement a CI/CD pipeline for updates.

### Phase 4: Integration with Existing Infrastructure

Many enterprises already have database infrastructure they want to leverage with Ceneca instead of deploying new database containers.

#### Step 1: Configure Connections to Existing Databases

1. **Identify Your Existing Services**:
   - PostgreSQL: `acme_pg` (e.g., running on internal host `db-postgres.acme.internal`)
   - MongoDB: `acme_mongo` (e.g., running on internal host `db-mongo.acme.internal`)
   - Qdrant: `acme_qdrant` (e.g., running on internal host `vector-db.acme.internal`)

2. **Update config.yaml with External Connections**:
   ```yaml
   # Configuration for existing enterprise databases
   
   postgres:
     # Connect to existing PostgreSQL
     uri: "postgresql://user:password@db-postgres.acme.internal:5432/analytics_db"
   
   mongodb:
     # Connect to existing MongoDB
     uri: "mongodb://user:password@db-mongo.acme.internal:27017/analytics_db?authSource=admin"
   
   qdrant:
     # Connect to existing Qdrant
     uri: "http://vector-db.acme.internal:6333"
   ```

3. **Generate Minimalist Deployment**:
   ```bash
   # Run generation script - it will detect external URIs
   cd /opt/ceneca
   ./generate-compose.sh --external-dbs
   ```
   The generator will create a docker-compose.yml that only includes the Ceneca agent, not the database services.

#### Step 2: Network Connectivity

1. **Ensure Network Access**:
   
   The Ceneca agent container needs network access to your existing databases:
   
   ```bash
   # Test connectivity to each database
   docker run --rm ceneca/agent:latest ping -c 1 db-postgres.acme.internal
   docker run --rm ceneca/agent:latest nc -zv db-postgres.acme.internal 5432
   ```

2. **Configure Docker Network**:
   
   If your databases are in a specific Docker network:
   
   ```yaml
   # In docker-compose.yml
   services:
     ceneca-agent:
       # ... other settings ...
       networks:
         - ceneca-network
         - acme-database-network  # Add existing network
   
   # External networks section
   networks:
     ceneca-network:
       driver: bridge
     acme-database-network:
       external: true
   ```

3. **DNS Resolution**:
   
   If using hostnames, ensure proper DNS resolution:
   
   ```yaml
   # In docker-compose.yml
   services:
     ceneca-agent:
       # ... other settings ...
       extra_hosts:
         - "db-postgres.acme.internal:192.168.1.100"
         - "db-mongo.acme.internal:192.168.1.101"
   ```

#### Step 3: Database Access Considerations

1. **Database Permissions**:
   
   Ensure the database users specified in URIs have appropriate permissions:
   
   - PostgreSQL: `CONNECT`, `SELECT` on relevant tables
   - MongoDB: Read access to collections
   - Qdrant: Read access to collections

2. **Connection Pooling**:
   
   Configure connection pooling in `config.yaml`:
   
   ```yaml
   postgres:
     uri: "postgresql://user:password@db-postgres.acme.internal:5432/analytics_db"
     pool:
       max_connections: 10
       min_connections: 2
   ```

3. **Security Best Practices**:
   
   - Use read-only database users when possible
   - Consider using database connection secrets
   - Enable SSL/TLS for database connections

By following this approach, you can deploy Ceneca with minimal infrastructure, leveraging your existing enterprise database investments.

## Enterprise Client Guide (0 → 1 → 100)

### Phase 0: Prerequisites

- Access credentials for your organization's SSO provider
- Network access to your Ceneca deployment
- Authorization to access specific data sources (check with your admin)

### Phase 1: First Access

#### Step 1: Initial Login

1. Open your web browser and navigate to your organization's Ceneca URL:
   ```
   https://your-ceneca-domain.com
   ```

2. Click "Login with SSO" and follow the prompts.

3. Authenticate using your organization's SSO provider:
   - Enter your username/email
   - Enter your password
   - Complete any MFA challenges if required

4. You will be redirected to the Ceneca dashboard.

#### Step 2: Understand Your Access Level

1. Navigate to the "Profile" section to see your role and permissions.

2. You will have access to data sources based on your assigned role:
   - `hr_read`: Access to HR-related data
   - `finance_read`: Access to finance-related data
   - etc.

### Phase 2: Running Queries

#### Step 1: Basic Querying

1. From the dashboard, click on "New Query".

2. Enter your question in natural language:
   ```
   Show me the total sales by region for Q1 2023
   ```

3. The system will:
   - Identify the relevant data source(s)
   - Translate your query to the appropriate query language
   - Execute the query against your on-premise data
   - Return and visualize the results

4. You can save frequent queries for later use.

#### Step 2: Advanced Features

1. **Cross-Database Queries**: Combine data from multiple sources:
   ```
   Compare website traffic from GA4 with sales data from our database for the last 30 days
   ```

2. **Slack Analytics**: If configured, query Slack data:
   ```
   What topics were most discussed in our #customer-support channel last week?
   ```

3. **Data Visualizations**: Request specific visualizations:
   ```
   Show me a bar chart of monthly user signups for 2023
   ```

### Phase 3: Collaboration and Integration

1. **Sharing Insights**: Share query results with colleagues:
   - Click "Share" on any result
   - Select users or groups to share with
   - Add optional comments

2. **Exporting Data**: Export results in various formats:
   - CSV for spreadsheet analysis
   - JSON for programmatic use
   - PDF for reporting

3. **Scheduled Reports**: Set up recurring queries:
   - Configure a query to run on a schedule
   - Results can be automatically emailed to stakeholders

## Recommended Directory Structure

Based on the current codebase structure, here is a recommended directory layout to support the enterprise deployment features:

```
data-connector/
├── docs/
│   ├── web-client.md
│   ├── deployment.md
│   ├── enterprise-deployment.md (this document)
│   └── ... (other existing docs)
│
├── server/
│   ├── agent/
│   │   ├── db/
│   │   │   ├── adapters/
│   │   │   │   ├── base.py
│   │   │   │   ├── postgres.py
│   │   │   │   ├── mongo.py
│   │   │   │   ├── qdrant.py
│   │   │   │   ├── slack.py
│   │   │   │   ├── ga4.py
│   │   │   │   └── __init__.py
│   │   │   └── ... (other DB-related modules)
│   │   │
│   │   ├── auth/                     # New directory for authentication
│   │   │   ├── __init__.py
│   │   │   ├── oidc.py               # OIDC/OAuth implementation
│   │   │   ├── saml.py               # SAML implementation
│   │   │   └── middleware.py         # Auth middleware
│   │   │
│   │   ├── mcp/                      # Existing MCP for Slack
│   │   │   └── ...
│   │   │
│   │   ├── web/                      # New directory for web interface
│   │   │   ├── __init__.py
│   │   │   ├── api/                  # API routes
│   │   │   │   ├── __init__.py
│   │   │   │   ├── auth.py           # Auth endpoints
│   │   │   │   └── query.py          # Query endpoints
│   │   │   │
│   │   │   ├── ui/                   # UI components
│   │   │   │   ├── __init__.py
│   │   │   │   ├── static/
│   │   │   │   └── templates/
│   │   │   │
│   │   │   └── app.py                # Web app initialization
│   │   │
│   │   └── ... (other agent modules)
│   │
│   ├── main.py                       # Entry point
│   └── requirements.txt
│
├── deploy/                           # New deployment directory
│   ├── docker/
│   │   ├── Dockerfile
│   │   ├── Dockerfile.mcp
│   │   ├── docker-compose.yml
│   │   └── deploy.sh
│   │
│   ├── kubernetes/
│   │   ├── ceneca-deployment.yaml
│   │   ├── ceneca-service.yaml
│   │   └── ceneca-ingress.yaml
│   │
│   └── scripts/
│       ├── setup-local.sh
│       ├── generate-config.sh
│       └── setup-ssl.sh
│
├── config-templates/
│   ├── config.yaml.template
│   ├── auth-config.yaml.template
│   └── nginx.conf.template
│
└── README.md
```

Key additions to the codebase:

1. **Authentication Module**: New `auth/` directory with OIDC and SAML implementations
2. **Web Interface**: Expanded `web/` directory with API and UI components
3. **Deployment Resources**: Dedicated `deploy/` directory with Docker, K8s, and setup scripts
4. **Configuration Templates**: Standard templates for various configuration files

This structure organizes the codebase to support both the deployment aspects (admin-focused) and the user interface aspects (client-focused) while maintaining compatibility with the existing adapter architecture.

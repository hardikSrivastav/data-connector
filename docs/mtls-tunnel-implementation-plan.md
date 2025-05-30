# mTLS Tunnel Implementation Plan

This document provides a comprehensive implementation plan for establishing a secure mTLS (mutual TLS) tunnel between the **@web client** and **@agent FastAPI server**. This implementation follows the enterprise storage architecture outlined in the previous documents and ensures secure communication for both Enterprise and Zero-Sync editions.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Current State Analysis](#current-state-analysis)
3. [mTLS Tunnel Design](#mtls-tunnel-design)
4. [Certificate Management](#certificate-management)
5. [Implementation Phases](#implementation-phases)
6. [Code Structure Changes](#code-structure-changes)
7. [Security Considerations](#security-considerations)
8. [Deployment & Testing](#deployment--testing)

---

## Architecture Overview

### **Target Architecture**

```
┌─────────────────────────────────────────────────────────────┐
│                    Enterprise Network                       │
│                                                             │
│  ┌─────────────────┐    mTLS Tunnel     ┌─────────────────┐ │
│  │   Web Client    │◄──────────────────►│  FastAPI Agent  │ │
│  │   (React)       │  Mutual Auth +     │   (Python)      │ │
│  │   - Storage UI  │  Cert Validation   │   - Query Proc  │ │
│  │   - Editor      │                    │   - DB Adapters │ │
│  │   - Sessions    │                    │   - LLM Client  │ │
│  └─────────────────┘                    └─────────────────┘ │
│           │                                        │        │
│           ▼                                        ▼        │
│  ┌─────────────────┐                    ┌─────────────────┐ │
│  │ Browser Storage │                    │ Enterprise DBs  │ │
│  │ - IndexedDB     │                    │ - PostgreSQL    │ │
│  │ - Local Cache   │                    │ - MongoDB       │ │
│  │ - Client Certs  │                    │ - Qdrant        │ │
│  └─────────────────┘                    │ - Slack/Shopify │ │
│                                         └─────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### **Communication Flow**

1. **Web Client → FastAPI Agent**: Natural language queries, sync requests
2. **FastAPI Agent → Web Client**: Query results, schema metadata, sync responses
3. **Both Directions**: Health checks, authentication tokens, audit logs

---

## Current State Analysis

### **Web Client (@web)**

**Current API Integration Points:**
```typescript
// hooks/sync-strategies.ts
class EnterpriseSyncStrategy {
  async syncToServer<T>(endpoint: string, data: T): Promise<T> {
    const url = `${this.config.apiBaseUrl}/api/${endpoint}`;
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    return response.json();
  }
}
```

**Configuration:**
```typescript
// hooks/index.ts
const config: EnterpriseStorageConfig = {
  apiBaseUrl: import.meta.env.VITE_API_BASE || 'http://localhost:8787',
  // ...other config
};
```

### **FastAPI Agent (@agent)**

**Current API Endpoints:**
```python
# agent/api/endpoints.py
@router.post("/query", response_model=QueryResponse)
@router.get("/health")
@router.get("/metadata")

# application/routes/storage.py  
@router.post("/sync", response_model=SyncResponse)
@router.get("/workspaces/{workspace_id}")
@router.post("/workspaces/{workspace_id}")
```

**Current CLI Access:**
```python
# agent/cmd/query.py - Currently accessed via CLI
await orchestrator.execute(validated_sql)
```

### **Gap Analysis**

**Missing Components:**
1. ❌ **mTLS Configuration**: No mutual TLS setup
2. ❌ **Certificate Management**: No cert generation/rotation
3. ❌ **Agent HTTP Server**: Agent only accessible via CLI
4. ❌ **Secure Headers**: No TLS-specific security headers
5. ❌ **Certificate Validation**: No client cert verification

---

## mTLS Tunnel Design

### **Certificate Hierarchy**

```
Enterprise Root CA (Self-Signed)
├── Intermediate CA (Web Services)
│   ├── Web Client Certificate
│   └── FastAPI Agent Certificate
└── Intermediate CA (Database Services)
    ├── PostgreSQL Client Certificate
    └── MongoDB Client Certificate
```

### **Certificate Properties**

```yaml
# Root CA Certificate
subject: "CN=Ceneca Enterprise Root CA,O=Enterprise,C=US"
key_usage: [keyCertSign, cRLSign]
validity: 10 years

# Web Client Certificate
subject: "CN=ceneca-web-client,OU=Web Services,O=Enterprise"
key_usage: [digitalSignature, keyEncipherment]
extended_key_usage: [clientAuth]
san: ["DNS:ceneca.enterprise.internal", "IP:10.0.50.100"]
validity: 1 year

# FastAPI Agent Certificate
subject: "CN=ceneca-agent,OU=Agent Services,O=Enterprise"
key_usage: [digitalSignature, keyEncipherment]
extended_key_usage: [serverAuth, clientAuth]
san: ["DNS:ceneca-agent.enterprise.internal", "IP:10.0.50.101"]
validity: 1 year
```

### **Connection Flow**

```mermaid
sequenceDiagram
    participant WC as Web Client
    participant FA as FastAPI Agent
    
    Note over WC,FA: mTLS Handshake
    WC->>FA: Client Hello + Client Certificate
    FA->>WC: Server Hello + Server Certificate
    FA->>WC: Certificate Request
    WC->>FA: Client Certificate + Certificate Verify
    
    Note over WC,FA: Mutual Authentication Complete
    
    WC->>FA: POST /api/query (encrypted)
    FA->>WC: Query Response (encrypted)
    
    WC->>FA: POST /api/sync (encrypted) 
    FA->>WC: Sync Response (encrypted)
```

---

## Certificate Management

### **Certificate Generation Scripts**

**File: `scripts/generate-certs.sh`**
```bash
#!/bin/bash
set -euo pipefail

CERT_DIR="${1:-/etc/ceneca/certs}"
VALIDITY_DAYS="${2:-365}"

# Create certificate directory
mkdir -p "$CERT_DIR"/{ca,web,agent}

# Generate Root CA
openssl genrsa -out "$CERT_DIR/ca/ca-key.pem" 4096
openssl req -new -x509 -key "$CERT_DIR/ca/ca-key.pem" \
    -out "$CERT_DIR/ca/ca-cert.pem" \
    -days $((VALIDITY_DAYS * 10)) \
    -subj "/CN=Ceneca Enterprise Root CA/O=Enterprise/C=US"

# Generate Web Client Certificate
openssl genrsa -out "$CERT_DIR/web/web-key.pem" 2048
openssl req -new -key "$CERT_DIR/web/web-key.pem" \
    -out "$CERT_DIR/web/web-csr.pem" \
    -subj "/CN=ceneca-web-client/OU=Web Services/O=Enterprise"

# Generate Agent Server Certificate  
openssl genrsa -out "$CERT_DIR/agent/agent-key.pem" 2048
openssl req -new -key "$CERT_DIR/agent/agent-key.pem" \
    -out "$CERT_DIR/agent/agent-csr.pem" \
    -subj "/CN=ceneca-agent/OU=Agent Services/O=Enterprise"

# Sign certificates
openssl x509 -req -in "$CERT_DIR/web/web-csr.pem" \
    -CA "$CERT_DIR/ca/ca-cert.pem" \
    -CAkey "$CERT_DIR/ca/ca-key.pem" \
    -CAcreateserial \
    -out "$CERT_DIR/web/web-cert.pem" \
    -days "$VALIDITY_DAYS" \
    -extensions client_cert \
    -extfile <(cat <<EOF
[client_cert]
basicConstraints=CA:FALSE
keyUsage=digitalSignature,keyEncipherment
extendedKeyUsage=clientAuth
subjectAltName=@alt_names
[alt_names]
DNS.1=ceneca.enterprise.internal
IP.1=10.0.50.100
EOF
)

openssl x509 -req -in "$CERT_DIR/agent/agent-csr.pem" \
    -CA "$CERT_DIR/ca/ca-cert.pem" \
    -CAkey "$CERT_DIR/ca/ca-key.pem" \
    -CAcreateserial \
    -out "$CERT_DIR/agent/agent-cert.pem" \
    -days "$VALIDITY_DAYS" \
    -extensions server_cert \
    -extfile <(cat <<EOF
[server_cert]
basicConstraints=CA:FALSE
keyUsage=digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth,clientAuth
subjectAltName=@alt_names
[alt_names]  
DNS.1=ceneca-agent.enterprise.internal
IP.1=10.0.50.101
EOF
)

# Set proper permissions
chmod 600 "$CERT_DIR"/{ca,web,agent}/*-key.pem
chmod 644 "$CERT_DIR"/{ca,web,agent}/*-cert.pem

echo "✅ Certificates generated successfully in $CERT_DIR"
```

### **Certificate Rotation Script**

**File: `scripts/rotate-certs.sh`**
```bash
#!/bin/bash
set -euo pipefail

CERT_DIR="${1:-/etc/ceneca/certs}"
GRACE_PERIOD_DAYS="${2:-30}"

check_cert_expiry() {
    local cert_file="$1"
    local grace_days="$2"
    
    if ! openssl x509 -in "$cert_file" -checkend $((grace_days * 86400)) -noout; then
        echo "⚠️  Certificate $cert_file expires within $grace_days days"
        return 1
    fi
    return 0
}

# Check all certificates
web_cert="$CERT_DIR/web/web-cert.pem"
agent_cert="$CERT_DIR/agent/agent-cert.pem"

if ! check_cert_expiry "$web_cert" "$GRACE_PERIOD_DAYS" || ! check_cert_expiry "$agent_cert" "$GRACE_PERIOD_DAYS"; then
    echo "🔄 Rotating certificates..."
    
    # Backup old certificates
    backup_dir="$CERT_DIR/backup-$(date +%Y%m%d-%H%M%S)"
    mkdir -p "$backup_dir"
    cp -r "$CERT_DIR"/{web,agent} "$backup_dir/"
    
    # Generate new certificates
    ./generate-certs.sh "$CERT_DIR"
    
    # Restart services (will be implemented based on deployment method)
    echo "🔧 Please restart web and agent services to load new certificates"
else
    echo "✅ All certificates are valid for at least $GRACE_PERIOD_DAYS days"
fi
```

---

## Implementation Phases

### **Phase 1: FastAPI Agent HTTP Server** ⭐ **CRITICAL**

**Objective**: Convert CLI-only agent to HTTP server with mTLS support

**Files to Create/Modify:**

1. **`server/agent/web_server.py`** (NEW)
```python
import ssl
import uvicorn
from fastapi import FastAPI, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer
import os
from pathlib import Path

from .api.endpoints import router as agent_router
from .application.routes.storage import router as storage_router
from .config.settings import Settings

# TLS Configuration
def create_ssl_context(cert_dir: str) -> ssl.SSLContext:
    """Create SSL context for mTLS"""
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    
    # Load server certificate and key
    cert_file = Path(cert_dir) / "agent" / "agent-cert.pem"
    key_file = Path(cert_dir) / "agent" / "agent-key.pem"
    ca_file = Path(cert_dir) / "ca" / "ca-cert.pem"
    
    context.load_cert_chain(str(cert_file), str(key_file))
    context.load_verify_locations(str(ca_file))
    
    # Require client certificates
    context.verify_mode = ssl.CERT_REQUIRED
    
    # Security settings
    context.set_ciphers('ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20:!aNULL:!MD5:!DSS')
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    
    return context

# Create FastAPI app
app = FastAPI(
    title="Ceneca Data Connector Agent",
    description="Secure mTLS API for data processing and query execution",
    version="1.0.0"
)

# CORS configuration for enterprise
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://ceneca.enterprise.internal"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Include routers
app.include_router(agent_router, prefix="/api/agent", tags=["agent"])
app.include_router(storage_router, prefix="/api", tags=["storage"])

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "ceneca-agent"}

def start_server():
    """Start the mTLS server"""
    settings = Settings()
    cert_dir = os.getenv("CENECA_CERT_DIR", "/etc/ceneca/certs")
    
    # Create SSL context
    ssl_context = create_ssl_context(cert_dir)
    
    # Start server
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8787,
        ssl_keyfile=None,  # Handled by ssl_context
        ssl_certfile=None,  # Handled by ssl_context
        ssl_context=ssl_context,
        log_level="info"
    )

if __name__ == "__main__":
    start_server()
```

2. **`server/agent/cmd/serve.py`** (NEW)
```python
import typer
import asyncio
from ..web_server import start_server

app = typer.Typer(help="Start Ceneca Agent HTTP Server")

@app.command()
def start(
    cert_dir: str = typer.Option("/etc/ceneca/certs", help="Certificate directory"),
    port: int = typer.Option(8787, help="Server port"),
    host: str = typer.Option("0.0.0.0", help="Server host")
):
    """Start the mTLS-enabled HTTP server"""
    import os
    os.environ["CENECA_CERT_DIR"] = cert_dir
    
    console.print(f"🚀 Starting Ceneca Agent Server on {host}:{port}")
    console.print(f"📂 Using certificates from: {cert_dir}")
    console.print(f"🔐 mTLS enabled for secure communication")
    
    start_server()

if __name__ == "__main__":
    app()
```

### **Phase 2: Web Client mTLS Integration** ⭐ **CRITICAL**

**Objective**: Configure web client to use client certificates for mTLS

**Files to Create/Modify:**

1. **`server/web/src/lib/mtls-client.ts`** (NEW)
```typescript
export interface MTLSConfig {
  agentBaseUrl: string;
  clientCertPath?: string;
  clientKeyPath?: string;
  caCertPath?: string;
  validateServerCert: boolean;
}

export class MTLSClient {
  private config: MTLSConfig;
  private clientCert: string | null = null;
  private clientKey: string | null = null;
  private caCert: string | null = null;

  constructor(config: MTLSConfig) {
    this.config = config;
    this.loadCertificates();
  }

  private async loadCertificates(): Promise<void> {
    try {
      // In browser environment, certificates would be loaded from secure storage
      // or provided via environment variables for the build
      this.clientCert = import.meta.env.VITE_CLIENT_CERT || null;
      this.clientKey = import.meta.env.VITE_CLIENT_KEY || null;
      this.caCert = import.meta.env.VITE_CA_CERT || null;
      
      if (!this.clientCert || !this.clientKey) {
        console.warn('⚠️ mTLS certificates not configured for web client');
      }
    } catch (error) {
      console.error('❌ Failed to load mTLS certificates:', error);
      throw new Error('mTLS certificate loading failed');
    }
  }

  async makeSecureRequest<T>(
    endpoint: string, 
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.config.agentBaseUrl}${endpoint}`;
    
    // Configure request with mTLS
    const secureOptions: RequestInit = {
      ...options,
      // Note: In browser, client cert auth is handled by browser's cert store
      // This would be different in Node.js environment
      headers: {
        'Content-Type': 'application/json',
        'X-Client-Cert-CN': 'ceneca-web-client', // For logging/audit
        ...options.headers,
      },
      // Additional security headers
      credentials: 'include',
    };

    try {
      console.log('🔐 Making secure mTLS request to:', url);
      const response = await fetch(url, secureOptions);
      
      if (!response.ok) {
        const errorText = await response.text();
        console.error('❌ mTLS request failed:', response.status, errorText);
        throw new Error(`mTLS request failed: ${response.status} - ${errorText}`);
      }
      
      console.log('✅ mTLS request successful');
      return await response.json();
    } catch (error) {
      console.error('❌ mTLS request error:', error);
      throw error;
    }
  }

  // Health check method
  async healthCheck(): Promise<{ status: string; timestamp: string }> {
    return this.makeSecureRequest('/health');
  }

  // Agent query method
  async query(question: string, analyze: boolean = false): Promise<any> {
    return this.makeSecureRequest('/api/agent/query', {
      method: 'POST',
      body: JSON.stringify({ question, analyze })
    });
  }

  // Storage sync method
  async sync(changes: any[], lastSync: Date | null): Promise<any> {
    return this.makeSecureRequest('/api/sync', {
      method: 'POST',
      body: JSON.stringify({ changes, lastSync })
    });
  }
}

// Factory function
export const createMTLSClient = (): MTLSClient => {
  const config: MTLSConfig = {
    agentBaseUrl: import.meta.env.VITE_AGENT_BASE_URL || 'https://ceneca-agent.enterprise.internal:8787',
    validateServerCert: import.meta.env.VITE_VALIDATE_SERVER_CERT !== 'false',
  };
  
  return new MTLSClient(config);
};
```

2. **Modify `server/web/src/hooks/sync-strategies.ts`**
```typescript
import { MTLSClient, createMTLSClient } from '@/lib/mtls-client';

export class EnterpriseSyncStrategy implements SyncStrategy {
  private mtlsClient: MTLSClient;
  
  constructor(private config: EnterpriseStorageConfig) {
    // Use mTLS client instead of regular fetch
    this.mtlsClient = createMTLSClient();
  }
  
  async syncToServer<T>(endpoint: string, data: T): Promise<T> {
    console.log('🔄 Syncing via mTLS tunnel:', endpoint);
    
    try {
      // Use mTLS client for secure communication
      const result = await this.mtlsClient.sync(
        data.changes || [], 
        data.lastSync || null
      );
      
      console.log('✅ mTLS sync successful:', result);
      return result;
    } catch (error) {
      console.error('❌ mTLS sync failed:', error);
      throw new Error(`mTLS sync failed: ${error.message}`);
    }
  }
  
  async fetchFromServer<T>(endpoint: string): Promise<T> {
    console.log('📥 Fetching via mTLS tunnel:', endpoint);
    
    try {
      // Use mTLS client for secure fetch
      const result = await this.mtlsClient.makeSecureRequest(endpoint);
      
      console.log('✅ mTLS fetch successful');
      return result;
    } catch (error) {
      console.error('❌ mTLS fetch failed:', error);
      throw error;
    }
  }

  validateData(data: any): void {
    // Enhanced validation for enterprise edition
    this.logDataAccess(data);
    
    // Validate data doesn't contain forbidden patterns
    const dataString = JSON.stringify(data);
    const forbiddenPatterns = [
      /password/i,
      /secret/i,
      /token/i,
      /key/i
    ];
    
    forbiddenPatterns.forEach(pattern => {
      if (pattern.test(dataString)) {
        console.warn('⚠️ Potentially sensitive data detected in sync');
      }
    });
  }
  
  private logDataAccess(data: any): void {
    const auditEntry = {
      timestamp: new Date(),
      action: 'mtls_sync',
      dataType: data.entity || 'unknown',
      userId: this.getAuthToken() || 'anonymous',
      certificateUsed: true,
    };
    
    // Send audit log to agent
    this.sendAuditLog(auditEntry);
  }
  
  private async sendAuditLog(auditEntry: any): Promise<void> {
    try {
      await this.mtlsClient.makeSecureRequest('/api/audit', {
        method: 'POST',
        body: JSON.stringify(auditEntry)
      });
    } catch (error) {
      console.error('❌ Failed to send audit log:', error);
      // Store locally as fallback
      const localAudit = JSON.parse(localStorage.getItem('ceneca_audit_log') || '[]');
      localAudit.push(auditEntry);
      localStorage.setItem('ceneca_audit_log', JSON.stringify(localAudit));
    }
  }
}
```

### **Phase 3: Container & Deployment Configuration** 🐳

**Objective**: Configure Docker/Kubernetes deployment with mTLS

**Files to Create/Modify:**

1. **`server/docker-compose.mtls.yml`** (NEW)
```yaml
version: '3.8'

services:
  ceneca-agent:
    build:
      context: ./agent
      dockerfile: Dockerfile.mtls
    container_name: ceneca-agent
    ports:
      - "8787:8787"
    volumes:
      - /etc/ceneca/certs:/etc/ceneca/certs:ro
      - ./agent:/app
    environment:
      - CENECA_CERT_DIR=/etc/ceneca/certs
      - DATABASE_URL=postgresql://user:pass@postgres:5432/ceneca
      - PYTHONPATH=/app
    networks:
      - ceneca-network
    depends_on:
      - postgres
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-k", "--cert", "/etc/ceneca/certs/agent/agent-cert.pem", "--key", "/etc/ceneca/certs/agent/agent-key.pem", "https://localhost:8787/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  ceneca-web:
    build:
      context: ./web
      dockerfile: Dockerfile.mtls
    container_name: ceneca-web
    ports:
      - "3000:3000"
    volumes:
      - /etc/ceneca/certs:/etc/ceneca/certs:ro
    environment:
      - VITE_AGENT_BASE_URL=https://ceneca-agent:8787
      - VITE_EDITION=enterprise
      - VITE_CLIENT_CERT_PATH=/etc/ceneca/certs/web/web-cert.pem
      - VITE_CLIENT_KEY_PATH=/etc/ceneca/certs/web/web-key.pem
      - VITE_CA_CERT_PATH=/etc/ceneca/certs/ca/ca-cert.pem
    networks:
      - ceneca-network
    depends_on:
      - ceneca-agent
    restart: unless-stopped

  postgres:
    image: postgres:15-alpine
    environment:
      - POSTGRES_DB=ceneca
      - POSTGRES_USER=ceneca_user
      - POSTGRES_PASSWORD=ceneca_password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - ceneca-network

  nginx:
    image: nginx:alpine
    ports:
      - "443:443"
      - "80:80"
    volumes:
      - ./nginx/mtls.conf:/etc/nginx/nginx.conf:ro
      - /etc/ceneca/certs:/etc/ceneca/certs:ro
    networks:
      - ceneca-network
    depends_on:
      - ceneca-web
    restart: unless-stopped

networks:
  ceneca-network:
    driver: bridge
    ipam:
      config:
        - subnet: 172.20.0.0/16

volumes:
  postgres_data:
```

2. **`server/agent/Dockerfile.mtls`** (NEW)
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    openssl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user for security
RUN useradd -m -u 1000 ceneca && \
    chown -R ceneca:ceneca /app
USER ceneca

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -k --cert /etc/ceneca/certs/agent/agent-cert.pem \
              --key /etc/ceneca/certs/agent/agent-key.pem \
              https://localhost:8787/health || exit 1

# Expose mTLS port
EXPOSE 8787

# Start the mTLS server
CMD ["python", "-m", "agent.web_server"]
```

3. **`server/nginx/mtls.conf`** (NEW)
```nginx
events {
    worker_connections 1024;
}

http {
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;
    
    # Logging
    log_format main '$remote_addr - $remote_user [$time_local] "$request" '
                   '$status $body_bytes_sent "$http_referer" '
                   '"$http_user_agent" "$http_x_forwarded_for" '
                   'cert_subject="$ssl_client_s_dn" cert_issuer="$ssl_client_i_dn"';
    
    access_log /var/log/nginx/access.log main;
    error_log /var/log/nginx/error.log warn;
    
    # Security headers
    add_header X-Frame-Options DENY always;
    add_header X-Content-Type-Options nosniff always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    
    # Web UI (HTTPS only)
    server {
        listen 443 ssl http2;
        server_name ceneca.enterprise.internal;
        
        # SSL Configuration
        ssl_certificate /etc/ceneca/certs/web/web-cert.pem;
        ssl_certificate_key /etc/ceneca/certs/web/web-key.pem;
        ssl_client_certificate /etc/ceneca/certs/ca/ca-cert.pem;
        ssl_verify_client optional;  # Allow both cert and non-cert clients
        
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers 'ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384';
        ssl_prefer_server_ciphers off;
        
        # Proxy to web container
        location / {
            proxy_pass http://ceneca-web:3000;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            
            # Pass client certificate info
            proxy_set_header X-SSL-Client-Cert $ssl_client_cert;
            proxy_set_header X-SSL-Client-Subject $ssl_client_s_dn;
            proxy_set_header X-SSL-Client-Issuer $ssl_client_i_dn;
        }
        
        # API routes (require client certificate)
        location /api/ {
            # Require client certificate for API access
            if ($ssl_client_verify != SUCCESS) {
                return 403;
            }
            
            proxy_pass https://ceneca-agent:8787;
            proxy_ssl_certificate /etc/ceneca/certs/web/web-cert.pem;
            proxy_ssl_certificate_key /etc/ceneca/certs/web/web-key.pem;
            proxy_ssl_trusted_certificate /etc/ceneca/certs/ca/ca-cert.pem;
            proxy_ssl_verify on;
            proxy_ssl_verify_depth 2;
            
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    }
    
    # Redirect HTTP to HTTPS
    server {
        listen 80;
        server_name ceneca.enterprise.internal;
        return 301 https://$server_name$request_uri;
    }
}
```

### **Phase 4: Security & Monitoring** 🔒

**Objective**: Add comprehensive security monitoring and audit logging

**Files to Create/Modify:**

1. **`server/agent/security/mtls_middleware.py`** (NEW)
```python
from fastapi import Request, HTTPException
from fastapi.security import HTTPBearer
import ssl
import logging
from datetime import datetime
from typing import Optional
import re

logger = logging.getLogger(__name__)

class MTLSSecurityMiddleware:
    """Middleware for mTLS security validation and audit logging"""
    
    def __init__(self):
        self.allowed_client_cns = [
            "ceneca-web-client",
            "ceneca-admin-client"
        ]
        self.required_cert_fields = [
            "CN", "O", "OU"
        ]
    
    async def __call__(self, request: Request, call_next):
        # Extract client certificate information
        client_cert_info = self.extract_client_cert_info(request)
        
        # Validate client certificate
        if not self.validate_client_certificate(client_cert_info):
            logger.warning(f"Invalid client certificate: {client_cert_info}")
            raise HTTPException(status_code=403, detail="Invalid client certificate")
        
        # Log access for audit
        self.log_access(request, client_cert_info)
        
        # Add cert info to request state
        request.state.client_cert = client_cert_info
        
        # Continue processing
        response = await call_next(request)
        
        # Log response for audit
        self.log_response(request, response, client_cert_info)
        
        return response
    
    def extract_client_cert_info(self, request: Request) -> Optional[dict]:
        """Extract client certificate information from request"""
        cert_subject = request.headers.get("X-SSL-Client-Subject")
        cert_issuer = request.headers.get("X-SSL-Client-Issuer")
        cert_verify = request.headers.get("X-SSL-Client-Verify")
        
        if not cert_subject or cert_verify != "SUCCESS":
            return None
            
        # Parse certificate subject
        cert_info = {
            "subject": cert_subject,
            "issuer": cert_issuer,
            "verify_status": cert_verify,
            "parsed_subject": self.parse_cert_subject(cert_subject)
        }
        
        return cert_info
    
    def parse_cert_subject(self, subject: str) -> dict:
        """Parse certificate subject string into components"""
        components = {}
        
        # Extract common certificate fields
        patterns = {
            "CN": r"CN=([^,]+)",
            "O": r"O=([^,]+)", 
            "OU": r"OU=([^,]+)",
            "C": r"C=([^,]+)"
        }
        
        for field, pattern in patterns.items():
            match = re.search(pattern, subject)
            if match:
                components[field] = match.group(1).strip()
        
        return components
    
    def validate_client_certificate(self, cert_info: Optional[dict]) -> bool:
        """Validate client certificate meets security requirements"""
        if not cert_info:
            return False
            
        parsed_subject = cert_info.get("parsed_subject", {})
        
        # Check if CN is in allowed list
        client_cn = parsed_subject.get("CN")
        if client_cn not in self.allowed_client_cns:
            logger.warning(f"Unauthorized client CN: {client_cn}")
            return False
        
        # Check required fields are present
        for field in self.required_cert_fields:
            if field not in parsed_subject:
                logger.warning(f"Missing required certificate field: {field}")
                return False
                
        # Additional security checks can be added here
        
        return True
    
    def log_access(self, request: Request, cert_info: Optional[dict]):
        """Log access attempt for audit trail"""
        audit_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event": "mtls_access",
            "client_ip": request.client.host,
            "method": request.method,
            "path": str(request.url.path),
            "user_agent": request.headers.get("User-Agent"),
            "client_cert": {
                "cn": cert_info.get("parsed_subject", {}).get("CN") if cert_info else None,
                "issuer": cert_info.get("issuer") if cert_info else None,
                "verify_status": cert_info.get("verify_status") if cert_info else "FAILED"
            }
        }
        
        logger.info(f"mTLS Access: {audit_entry}")
        
        # Store in audit database (implement as needed)
        # await self.store_audit_log(audit_entry)
    
    def log_response(self, request: Request, response, cert_info: Optional[dict]):
        """Log response for audit trail"""
        audit_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event": "mtls_response",
            "status_code": response.status_code,
            "path": str(request.url.path),
            "client_cert_cn": cert_info.get("parsed_subject", {}).get("CN") if cert_info else None
        }
        
        logger.info(f"mTLS Response: {audit_entry}")
```

2. **`server/agent/api/audit.py`** (NEW)
```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

class AuditLogEntry(BaseModel):
    timestamp: datetime
    action: str
    dataType: str
    userId: str
    certificateUsed: bool
    additionalData: Optional[Dict[str, Any]] = None

class AuditLogResponse(BaseModel):
    success: bool
    message: str

@router.post("/audit", response_model=AuditLogResponse)
async def log_audit_entry(audit_entry: AuditLogEntry):
    """
    Receive and store audit log entries from web client
    
    Args:
        audit_entry: Audit log entry to store
        
    Returns:
        Success/failure response
    """
    try:
        # Log the audit entry
        logger.info(f"Audit Log: {audit_entry.dict()}")
        
        # Store in database (implement based on your database choice)
        # await store_audit_entry(audit_entry)
        
        return AuditLogResponse(
            success=True,
            message="Audit entry logged successfully"
        )
    except Exception as e:
        logger.error(f"Failed to log audit entry: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to log audit entry")

@router.get("/audit/recent")
async def get_recent_audit_logs(
    hours: int = 24,
    user_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Retrieve recent audit log entries
    
    Args:
        hours: Number of hours to look back
        user_id: Optional filter by user ID
        
    Returns:
        List of recent audit log entries
    """
    try:
        # Implement based on your audit storage
        # This is a placeholder implementation
        recent_logs = [
            {
                "timestamp": datetime.utcnow().isoformat(),
                "action": "mtls_sync",
                "user_id": "admin",
                "status": "success"
            }
        ]
        
        return recent_logs
    except Exception as e:
        logger.error(f"Failed to retrieve audit logs: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve audit logs")
```

---

## Code Structure Changes

### **Directory Structure After Implementation**

```
server/
├── agent/
│   ├── api/
│   │   ├── endpoints.py          # Existing
│   │   └── audit.py              # NEW: Audit logging endpoints
│   ├── security/
│   │   └── mtls_middleware.py    # NEW: mTLS security middleware
│   ├── web_server.py             # NEW: mTLS-enabled HTTP server
│   └── cmd/
│       ├── query.py              # Existing CLI
│       └── serve.py              # NEW: Server start command
├── web/
│   └── src/
│       ├── lib/
│       │   └── mtls-client.ts    # NEW: mTLS client implementation
│       └── hooks/
│           └── sync-strategies.ts # MODIFIED: Use mTLS client
├── nginx/
│   └── mtls.conf                 # NEW: NGINX mTLS configuration
├── scripts/
│   ├── generate-certs.sh         # NEW: Certificate generation
│   └── rotate-certs.sh           # NEW: Certificate rotation
└── docker-compose.mtls.yml       # NEW: mTLS deployment config
```

### **Environment Variables**

```bash
# Agent
CENECA_CERT_DIR=/etc/ceneca/certs
CENECA_AGENT_PORT=8787
CENECA_MTLS_ENABLED=true

# Web Client
VITE_AGENT_BASE_URL=https://ceneca-agent.enterprise.internal:8787
VITE_EDITION=enterprise
VITE_CLIENT_CERT_PATH=/etc/ceneca/certs/web/web-cert.pem
VITE_CLIENT_KEY_PATH=/etc/ceneca/certs/web/web-key.pem
VITE_CA_CERT_PATH=/etc/ceneca/certs/ca/ca-cert.pem
VITE_VALIDATE_SERVER_CERT=true
```

---

## Security Considerations

### **Certificate Security**

1. **Private Key Protection**
   - Store private keys with 600 permissions
   - Use hardware security modules (HSM) in production
   - Implement key rotation every 90 days

2. **Certificate Validation**
   - Verify certificate chain integrity
   - Check certificate revocation lists (CRL)
   - Validate certificate expiration dates

3. **Certificate Pinning**
   - Pin expected certificate fingerprints
   - Implement certificate change detection
   - Alert on unexpected certificate changes

### **Network Security**

1. **TLS Configuration**
   - Disable weak ciphers and protocols
   - Use forward secrecy (ECDHE, DHE)
   - Implement HTTP Strict Transport Security (HSTS)

2. **Access Control**
   - Implement IP allowlisting where appropriate
   - Use network segmentation
   - Monitor for unusual traffic patterns

### **Audit & Monitoring**

1. **Comprehensive Logging**
   - Log all mTLS handshakes
   - Track certificate usage patterns
   - Monitor failed authentication attempts

2. **Security Alerts**
   - Alert on certificate expiration
   - Detect unusual access patterns
   - Monitor for potential security breaches

---

## Deployment & Testing

### **Testing Strategy**

1. **Unit Tests**
```bash
# Test certificate generation
./scripts/generate-certs.sh /tmp/test-certs 30

# Test mTLS client connection
python -m pytest tests/test_mtls_client.py

# Test web client mTLS integration
npm test src/lib/mtls-client.test.ts
```

2. **Integration Tests**
```bash
# Start test environment
docker-compose -f docker-compose.mtls.yml up -d

# Test end-to-end mTLS communication
curl -k --cert /etc/ceneca/certs/web/web-cert.pem \
       --key /etc/ceneca/certs/web/web-key.pem \
       https://ceneca-agent.enterprise.internal:8787/health

# Test web client connection
curl -k https://ceneca.enterprise.internal
```

3. **Security Tests**
```bash
# Test certificate validation
openssl verify -CAfile /etc/ceneca/certs/ca/ca-cert.pem \
               /etc/ceneca/certs/web/web-cert.pem

# Test TLS configuration
nmap --script ssl-enum-ciphers -p 8787 ceneca-agent.enterprise.internal

# Test mTLS requirement
curl -k https://ceneca-agent.enterprise.internal:8787/health  # Should fail without cert
```

### **Production Deployment**

1. **Certificate Management**
   - Set up automated certificate rotation
   - Configure monitoring for certificate expiration
   - Implement backup and recovery procedures

2. **Monitoring & Alerting**
   - Monitor mTLS handshake success rates
   - Alert on authentication failures
   - Track certificate usage patterns

3. **Performance Optimization**
   - Enable TLS session resumption
   - Optimize cipher suites for performance
   - Monitor latency impact of mTLS

### **Rollback Plan**

1. **Graceful Fallback**
   - Maintain both HTTP and HTTPS endpoints during transition
   - Implement feature flags for mTLS enablement
   - Prepare rollback scripts for quick reversion

2. **Emergency Procedures**
   - Document emergency certificate replacement
   - Maintain offline certificate generation capability
   - Prepare alternative communication channels

---

## Summary

This implementation plan provides a comprehensive approach to establishing secure mTLS communication between the web client and FastAPI agent. The plan follows enterprise security best practices while maintaining the existing functionality and supporting both Enterprise and Zero-Sync deployment modes.

**Key Benefits:**
- ✅ **End-to-End Encryption**: All communication secured with mutual TLS
- ✅ **Certificate-Based Authentication**: Strong identity verification for both client and server
- ✅ **Comprehensive Audit Logging**: Full traceability of all mTLS communications
- ✅ **Enterprise-Ready**: Suitable for high-security enterprise environments
- ✅ **Automated Certificate Management**: Streamlined certificate generation and rotation
- ✅ **Production-Ready Deployment**: Docker/Kubernetes ready with NGINX load balancing

**Next Steps:**
1. Review and approve the implementation plan
2. Begin Phase 1: FastAPI Agent HTTP Server implementation
3. Set up certificate generation and testing environment
4. Proceed through phases systematically with thorough testing at each stage 
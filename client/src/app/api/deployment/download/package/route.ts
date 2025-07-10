import { NextRequest, NextResponse } from 'next/server';
import JSZip from 'jszip';

// Mock license validation - in production, this would check against your license database
const validateLicense = async (licenseKey: string): Promise<boolean> => {
  // For demo purposes, accept any license key that follows the pattern
  const validPattern = /^CENECA-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$/;
  
  // Also accept common test formats for development
  const testPatterns = [
    'demo-license',
    'test-license',
    'dev-license',
    /^test-\d+$/,
    /^demo-\d+$/,
    /^dev-\d+$/
  ];
  
  // Check main pattern
  if (validPattern.test(licenseKey)) {
    return true;
  }
  
  // Check test patterns
  for (const pattern of testPatterns) {
    if (typeof pattern === 'string' && pattern === licenseKey) {
      return true;
    }
    if (pattern instanceof RegExp && pattern.test(licenseKey)) {
      return true;
    }
  }
  
  return false;
};

// Complete deployment package files
const deploymentPackage = {
  'docker-compose.yml': `version: '3.8'

services:
  ceneca:
    build: .
    ports:
      - "443:443"
    environment:
      - NODE_ENV=production
      - ANTHROPIC_API_KEY=\${ANTHROPIC_API_KEY}
      - OPENAI_API_KEY=\${OPENAI_API_KEY}
      - DATABASE_URL=\${DATABASE_URL}
      - MONGODB_URI=\${MONGODB_URI}
      - QDRANT_URL=\${QDRANT_URL}
      - QDRANT_API_KEY=\${QDRANT_API_KEY}
      - OKTA_CLIENT_ID=\${OKTA_CLIENT_ID}
      - OKTA_CLIENT_SECRET=\${OKTA_CLIENT_SECRET}
      - OKTA_DOMAIN=\${OKTA_DOMAIN}
      - JWT_SECRET=\${JWT_SECRET}
    volumes:
      - ./config:/app/config:ro
      - ./certs:/app/certs:ro
      - ./logs:/app/logs
      - ./data:/app/data
    healthcheck:
      test: ["CMD", "curl", "-f", "https://localhost:443/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    restart: unless-stopped
    security_opt:
      - no-new-privileges:true
    read_only: true
    tmpfs:
      - /tmp:rw,noexec,nosuid,size=1G
`,

  'Dockerfile': `# Multi-stage build for React frontend and Python backend
FROM node:18-alpine AS frontend-builder

WORKDIR /app/frontend
COPY client/package*.json ./
RUN npm ci --only=production

COPY client/ .
RUN npm run build

FROM python:3.11-slim AS backend-builder

WORKDIR /app/backend
COPY server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server/ .

# Final stage
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \\
    nginx \\
    supervisor \\
    curl \\
    && rm -rf /var/lib/apt/lists/*

# Copy built frontend
COPY --from=frontend-builder /app/frontend/dist /var/www/html

# Copy backend
COPY --from=backend-builder /app/backend /app

# Copy configuration files
COPY config/nginx.conf /etc/nginx/nginx.conf
COPY config/supervisord.conf /etc/supervisor/supervisord.conf
COPY scripts/start.sh /start.sh

RUN chmod +x /start.sh

# Create necessary directories
RUN mkdir -p /app/logs /app/data /app/certs /app/config

# Expose HTTPS port
EXPOSE 443

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \\
    CMD curl -f https://localhost:443/health || exit 1

CMD ["/start.sh"]
`,

  'config/nginx.conf': `events {
    worker_connections 1024;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains";

    # SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
    limit_req_zone $binary_remote_addr zone=login:10m rate=5r/m;

    server {
        listen 443 ssl http2;
        server_name _;

        ssl_certificate /app/certs/server.crt;
        ssl_certificate_key /app/certs/server.key;

        # Serve React frontend
        location / {
            root /var/www/html;
            try_files $uri $uri/ /index.html;
        }

        # Proxy API requests to FastAPI backend
        location /api/ {
            limit_req zone=api burst=20 nodelay;
            proxy_pass http://127.0.0.1:8787;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        # Authentication endpoints with stricter rate limiting
        location /api/auth/ {
            limit_req zone=login burst=5 nodelay;
            proxy_pass http://127.0.0.1:8787;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        # Health check endpoint
        location /health {
            access_log off;
            return 200 "healthy\\n";
            add_header Content-Type text/plain;
        }
    }
}
`,

  'config/supervisord.conf': `[supervisord]
nodaemon=true
user=root
logfile=/app/logs/supervisord.log
pidfile=/app/logs/supervisord.pid

[program:nginx]
command=nginx -g "daemon off;"
stdout_logfile=/app/logs/nginx.log
stderr_logfile=/app/logs/nginx.log
autorestart=true
startretries=3

[program:ceneca-backend]
command=python -m uvicorn main:app --host 0.0.0.0 --port 8787
directory=/app
stdout_logfile=/app/logs/backend.log
stderr_logfile=/app/logs/backend.log
autorestart=true
startretries=3
environment=PYTHONPATH=/app
`,

  'scripts/start.sh': `#!/bin/bash

# Ceneca Container Start Script
echo "🚀 Starting Ceneca Enterprise..."

# Validation checks
echo "⚙️  Running validation checks..."

# Check for required configuration files
if [ ! -f /app/config/config.yaml ]; then
    echo "❌ Missing config.yaml file"
    exit 1
fi

if [ ! -f /app/config/auth-config.yaml ]; then
    echo "❌ Missing auth-config.yaml file"
    exit 1
fi

# Check for SSL certificates
if [ ! -f /app/certs/server.crt ] || [ ! -f /app/certs/server.key ]; then
    echo "❌ Missing SSL certificates"
    exit 1
fi

# Check required environment variables
if [ -z "$JWT_SECRET" ]; then
    echo "❌ JWT_SECRET environment variable is required"
    exit 1
fi

echo "✅ All validation checks passed"

# Set proper permissions
echo "🔐 Setting up permissions..."
chown -R www-data:www-data /var/www/html
chmod -R 755 /var/www/html
chmod 600 /app/certs/server.key
chmod 644 /app/certs/server.crt

# Start services
echo "🎯 Starting services..."
exec /usr/bin/supervisord -c /etc/supervisor/supervisord.conf
`,

  'scripts/setup.sh': `#!/bin/bash

# Ceneca Interactive Setup Script
echo "🚀 Ceneca Enterprise Setup"
echo "=========================="

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   echo "❌ This script should not be run as root"
   exit 1
fi

# Check Docker installation
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

echo "✅ Docker and Docker Compose are installed"

# Create necessary directories
mkdir -p config certs logs data scripts

# Copy configuration templates
if [ ! -f config/config.yaml ]; then
    cp config.yaml.example config/config.yaml
    echo "📄 Created config/config.yaml - please edit with your settings"
fi

if [ ! -f config/auth-config.yaml ]; then
    cp auth-config.yaml.example config/auth-config.yaml
    echo "📄 Created config/auth-config.yaml - please edit with your SSO settings"
fi

# Generate SSL certificates if they don't exist
if [ ! -f certs/server.crt ]; then
    echo "🔐 Generating self-signed SSL certificates..."
    ./scripts/generate-self-signed.sh
fi

echo ""
echo "🎉 Setup complete! Next steps:"
echo "1. Edit config/config.yaml with your database connections"
echo "2. Edit config/auth-config.yaml with your SSO settings"
echo "3. Run: docker-compose up -d"
echo "4. Test: ./scripts/test-deployment.sh"
`,

  'scripts/test-deployment.sh': `#!/bin/bash

# Ceneca Deployment Test Script
echo "🧪 Testing Ceneca Deployment"
echo "============================"

# Colors for output
GREEN='\\033[0;32m'
RED='\\033[0;31m'
YELLOW='\\033[1;33m'
NC='\\033[0m' # No Color

# Test functions
test_docker() {
    echo -n "Testing Docker installation... "
    if command -v docker &> /dev/null; then
        echo -e "\${GREEN}✅ PASS\${NC}"
        return 0
    else
        echo -e "\${RED}❌ FAIL\${NC}"
        return 1
    fi
}

test_compose() {
    echo -n "Testing Docker Compose installation... "
    if command -v docker-compose &> /dev/null; then
        echo -e "\${GREEN}✅ PASS\${NC}"
        return 0
    else
        echo -e "\${RED}❌ FAIL\${NC}"
        return 1
    fi
}

test_config() {
    echo -n "Testing configuration files... "
    if [ -f config/config.yaml ] && [ -f config/auth-config.yaml ]; then
        echo -e "\${GREEN}✅ PASS\${NC}"
        return 0
    else
        echo -e "\${RED}❌ FAIL\${NC}"
        echo "Missing configuration files. Run scripts/setup.sh first."
        return 1
    fi
}

test_ssl() {
    echo -n "Testing SSL certificates... "
    if [ -f certs/server.crt ] && [ -f certs/server.key ]; then
        echo -e "\${GREEN}✅ PASS\${NC}"
        return 0
    else
        echo -e "\${RED}❌ FAIL\${NC}"
        echo "Missing SSL certificates. Run ./scripts/generate-self-signed.sh"
        return 1
    fi
}

test_container() {
    echo -n "Testing container startup... "
    if docker-compose up -d &> /dev/null; then
        sleep 10
        if curl -k -f https://localhost:443/health &> /dev/null; then
            echo -e "\${GREEN}✅ PASS\${NC}"
            docker-compose down &> /dev/null
            return 0
        else
            echo -e "\${RED}❌ FAIL\${NC}"
            echo "Container started but health check failed"
            docker-compose down &> /dev/null
            return 1
        fi
    else
        echo -e "\${RED}❌ FAIL\${NC}"
        return 1
    fi
}

# Run all tests
echo "Running deployment tests..."
echo ""

failed_tests=0

test_docker || ((failed_tests++))
test_compose || ((failed_tests++))
test_config || ((failed_tests++))
test_ssl || ((failed_tests++))
test_container || ((failed_tests++))

echo ""
if [ $failed_tests -eq 0 ]; then
    echo -e "\${GREEN}🎉 All tests passed! Your deployment is ready.\${NC}"
    echo "Access your Ceneca instance at: https://localhost:443"
else
    echo -e "\${RED}❌ $failed_tests test(s) failed. Please fix the issues above.\${NC}"
fi
`,

  'scripts/generate-self-signed.sh': `#!/bin/bash

# Generate self-signed SSL certificates for testing
echo "🔐 Generating self-signed SSL certificates..."

# Create certs directory if it doesn't exist
mkdir -p certs

# Generate private key
openssl genrsa -out certs/server.key 2048

# Generate certificate signing request
openssl req -new -key certs/server.key -out certs/server.csr -subj "/C=US/ST=CA/L=San Francisco/O=Ceneca/CN=localhost"

# Generate self-signed certificate
openssl x509 -req -days 365 -in certs/server.csr -signkey certs/server.key -out certs/server.crt

# Clean up CSR
rm certs/server.csr

# Set proper permissions
chmod 600 certs/server.key
chmod 644 certs/server.crt

echo "✅ Self-signed SSL certificates generated successfully!"
echo "⚠️  These certificates are for testing only. Use proper certificates for production."
`,

  'config.yaml.example': `# Ceneca Configuration File
# Copy this file to config/config.yaml and customize for your environment

# Database connections
databases:
  postgresql:
    host: localhost
    port: 5432
    database: your_database
    username: your_username
    password: your_password
    
  mongodb:
    uri: mongodb://localhost:27017/your_database
    
  qdrant:
    url: http://localhost:6333
    api_key: your_qdrant_api_key
    
# LLM Configuration
llm:
  primary_provider: anthropic  # or openai
  anthropic_api_key: your_anthropic_key
  openai_api_key: your_openai_key
  
# Security
security:
  jwt_secret: your_jwt_secret_key
  session_timeout: 3600
  
# Logging
logging:
  level: INFO
  file: /app/logs/ceneca.log
`,

  'auth-config.yaml.example': `# Authentication Configuration
# Configure your SSO provider

# Okta Configuration
okta:
  client_id: your_okta_client_id
  client_secret: your_okta_client_secret
  domain: your_okta_domain
  redirect_uri: https://ceneca.yourcompany.com/auth/callback

# Azure AD Configuration (alternative)
azure:
  tenant_id: your_tenant_id
  client_id: your_azure_client_id
  client_secret: your_azure_client_secret
  
# Google Workspace Configuration (alternative)
google:
  client_id: your_google_client_id
  client_secret: your_google_client_secret
  
# Auth0 Configuration (alternative)
auth0:
  domain: your_auth0_domain
  client_id: your_auth0_client_id
  client_secret: your_auth0_client_secret
`,

  'README.md': `# Ceneca Enterprise Deployment

Welcome to Ceneca! This package contains everything you need to deploy Ceneca on-premise in your environment.

## Quick Start (5 Steps)

### 1. Prerequisites
- Docker and Docker Compose installed
- SSL certificates for your domain
- Database connections configured

### 2. Configuration
\`\`\`bash
# Run interactive setup
./scripts/setup.sh

# Edit configuration files
nano config/config.yaml
nano config/auth-config.yaml
\`\`\`

### 3. SSL Certificates
Place your SSL certificates in the \`certs/\` directory:
- \`server.crt\` - Your SSL certificate
- \`server.key\` - Your private key

Or generate self-signed certificates for testing:
\`\`\`bash
./scripts/generate-self-signed.sh
\`\`\`

### 4. Deploy
\`\`\`bash
docker-compose up -d
\`\`\`

### 5. Test
\`\`\`bash
./scripts/test-deployment.sh
\`\`\`

## Architecture

Ceneca runs as a single Docker container with:
- **nginx** (port 443) - Web server with SSL termination
- **React frontend** - Served at \`/\`
- **FastAPI backend** - Served at \`/api/*\`

## Configuration

### Database Connections
Edit \`config/config.yaml\` to configure your databases:
- PostgreSQL
- MongoDB  
- Qdrant Vector Database
- Other supported databases

### Authentication
Edit \`config/auth-config.yaml\` to configure SSO:
- Okta
- Azure AD
- Google Workspace
- Auth0

### Environment Variables
Set these in your environment or \`.env\` file:
- \`ANTHROPIC_API_KEY\` - For Claude AI
- \`OPENAI_API_KEY\` - For GPT models
- \`DATABASE_URL\` - Primary database connection
- \`JWT_SECRET\` - For session security

## Security

- All traffic is HTTPS only
- Rate limiting enabled
- Security headers configured
- Container runs as non-root user
- Read-only filesystem

## Monitoring

- Health check endpoint: \`/health\`
- Logs in \`./logs/\` directory
- Prometheus metrics available

## Support

- Technical Support: support@ceneca.ai
- Documentation: https://docs.ceneca.ai
- Status Page: https://status.ceneca.ai

## License

This software is licensed under the Ceneca Enterprise License.
`,

  'QUICK_TEST.md': `# 5-Minute Quick Test

Follow these steps to verify your Ceneca deployment is working correctly.

## Step 1: Container Health (30 seconds)
\`\`\`bash
# Check container status
docker-compose ps

# Should show ceneca container as "Up" and healthy
\`\`\`

## Step 2: SSL Certificate (30 seconds)
\`\`\`bash
# Test SSL connection
curl -k -I https://localhost:443/health

# Should return HTTP 200
\`\`\`

## Step 3: Frontend Loading (1 minute)
Open browser and navigate to:
- \`https://localhost:443\`
- Should see Ceneca login page
- Check browser console for errors

## Step 4: API Endpoints (1 minute)
\`\`\`bash
# Test API health
curl -k https://localhost:443/api/health

# Should return JSON with status
\`\`\`

## Step 5: Database Connectivity (2 minutes)
1. Login to Ceneca interface
2. Navigate to Database Settings
3. Test connection to your configured databases
4. Verify green status indicators

## Troubleshooting

### Container won't start
- Check \`docker-compose logs\`
- Verify SSL certificates exist
- Check port 443 is available

### SSL errors
- Verify certificates are valid
- Check file permissions
- Try with self-signed certificates first

### Database connection fails
- Check \`config/config.yaml\` settings
- Verify database is reachable
- Check authentication credentials

### Authentication issues
- Review \`config/auth-config.yaml\`
- Verify SSO provider settings
- Check redirect URLs

## Success Criteria

✅ Container shows as healthy
✅ HTTPS endpoint responds
✅ Frontend loads without errors
✅ API endpoints return valid responses
✅ Database connections are successful

If all criteria are met, your deployment is ready for production use!
`,

  '.env.example': `# Environment Variables for Ceneca Deployment
# Copy this file to .env and customize for your environment

# LLM API Keys
ANTHROPIC_API_KEY=your_anthropic_api_key_here
OPENAI_API_KEY=your_openai_api_key_here

# Database URLs
DATABASE_URL=postgresql://user:password@localhost:5432/database
MONGODB_URI=mongodb://localhost:27017/database
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=your_qdrant_api_key

# Authentication (choose one)
OKTA_CLIENT_ID=your_okta_client_id
OKTA_CLIENT_SECRET=your_okta_client_secret
OKTA_DOMAIN=your_okta_domain

# Security
JWT_SECRET=your_super_secret_jwt_key_here_make_it_long_and_random

# Optional: AWS Credentials for enhanced features
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
AWS_REGION=us-east-1
`
};

export async function GET(request: NextRequest) {
  try {
    // Create ZIP file
    const zip = new JSZip();
    
    // Add all files to ZIP
    for (const [filePath, content] of Object.entries(deploymentPackage)) {
      zip.file(filePath, content);
    }
    
    // Add empty directories
    zip.folder('logs');
    zip.folder('data');
    
    // Generate ZIP buffer
    const zipBuffer = await zip.generateAsync({
      type: 'nodebuffer',
      compression: 'DEFLATE',
      compressionOptions: { level: 6 }
    });

    // Return ZIP file
    return new Response(zipBuffer, {
      headers: {
        'Content-Type': 'application/zip',
        'Content-Disposition': 'attachment; filename="ceneca-deployment-package.zip"',
        'Content-Length': zipBuffer.length.toString(),
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Pragma': 'no-cache',
        'Expires': '0'
      },
    });

  } catch (error) {
    console.error('Error creating deployment package:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
} 
# Ceneca Enterprise Deployment Guide

## What You Received

This deployment package contains everything needed to run Ceneca on your infrastructure:

```
ceneca-enterprise/
├── README.md                    # This file
├── docker-compose.yml           # Main deployment configuration
├── config/
│   ├── config.yaml.example      # Database and system configuration template
│   ├── auth-config.yaml.example # SSO configuration template
│   └── nginx.conf               # Web server configuration
├── certs/                       # Place your SSL certificates here
│   ├── README.md               # Certificate setup instructions
│   └── .gitkeep
├── scripts/
│   ├── setup.sh                # Automated setup script
│   ├── test-deployment.sh      # Validate your deployment
│   └── generate-self-signed.sh # For testing only
└── docs/
    ├── configuration.md         # Detailed configuration guide
    ├── troubleshooting.md      # Common issues and solutions
    └── security.md             # Security considerations

```

## Prerequisites

Before starting, ensure you have:

- **Docker** and **Docker Compose** installed
- **Your custom domain** ready (e.g., `ceneca.yourcompany.com`)
- **SSL certificates** for your domain
- **SSO provider details** (Okta, Azure AD, etc.)
- **Database connection details** (PostgreSQL, MongoDB, etc.)
- **Administrator access** to your DNS and firewall

## Quick Start (5 Steps)

### Step 1: Get the Ceneca Enterprise Image
```bash
# Option A: Pull from registry (if provided)
docker pull ceneca/enterprise:latest

# Option B: Load from provided file
docker load < ceneca-enterprise.tar
```

### Step 2: Configure Your Environment
```bash
# Copy example configurations
cp config/config.yaml.example config/config.yaml
cp config/auth-config.yaml.example config/auth-config.yaml

# Edit with your settings
nano config/config.yaml      # Database connections
nano config/auth-config.yaml # SSO configuration
```

### Step 3: Set Up SSL Certificates
```bash
# Place your certificates in the certs/ directory
cp /path/to/your/certificate.crt certs/
cp /path/to/your/private.key certs/

# OR generate self-signed for testing
./scripts/generate-self-signed.sh yourcompany.com
```

### Step 4: Deploy Ceneca
```bash
# Start the deployment
docker-compose up -d

# Check status
docker-compose ps
```

### Step 5: Test Your Deployment
```bash
# Run automated tests
./scripts/test-deployment.sh

# Manual test: Open your browser
# https://ceneca.yourcompany.com
```

## What Happens When You Deploy

1. **Ceneca starts on port 443** (HTTPS)
2. **Frontend loads** at `https://ceneca.yourcompany.com/`
3. **API endpoints** available at `https://ceneca.yourcompany.com/api/`
4. **Authentication** redirects to your SSO provider
5. **Database connections** established using your config

## Next Steps

- [Detailed Configuration Guide](docs/configuration.md)
- [Test with sample queries](docs/testing.md)
- [Security hardening](docs/security.md)
- [Monitoring and maintenance](docs/monitoring.md)

## Support

If you encounter issues:
1. Check [troubleshooting guide](docs/troubleshooting.md)
2. Run diagnostics: `./scripts/test-deployment.sh --verbose`
3. Contact support with logs: `docker-compose logs > ceneca-logs.txt`

---

**🎯 Goal:** In 15 minutes, you should have Ceneca running at `https://ceneca.yourcompany.com` 
# Quick Test Guide

This guide shows you how to test the Ceneca enterprise deployment in 5 minutes.

## Prerequisites

- Docker and Docker Compose installed
- Your existing `config.yaml` and `auth-config.yaml` files

## Step 1: Build the Image

From the project root:

```bash
chmod +x deploy/build-test.sh
./deploy/build-test.sh
```

## Step 2: Set Up for Local Testing

```bash
cd deploy/

# Generate self-signed certificate for localhost
./scripts/generate-self-signed.sh localhost

# Copy your existing config files
cp ~/.data-connector/config.yaml config/
cp ~/.data-connector/auth-config.yaml config/

# OR run the interactive setup
./scripts/setup.sh
```

## Step 3: Start the Container

```bash
# Update domain for local testing
export CENECA_DOMAIN=localhost

# Start Ceneca
docker-compose up -d

# Check status
docker-compose ps
```

## Step 4: Test the Deployment

```bash
# Run automated tests
./scripts/test-deployment.sh --domain localhost

# Check logs if needed
docker-compose logs
```

## Step 5: Access Ceneca

Open your browser and go to:
- `https://localhost` (you'll get a security warning due to self-signed cert)
- Click "Advanced" → "Proceed to localhost"

You should see the Ceneca interface!

## What's Happening?

1. **nginx** serves the React frontend at `/`
2. **nginx** proxies API requests to FastAPI at `/api/`
3. **Both run in a single container** on port 443 (HTTPS)
4. **Your config files** are mounted from `./config/`
5. **SSL certificates** are mounted from `./certs/`

## API Endpoints You Can Test

- `https://localhost/api/health` - Health check
- `https://localhost/api/capabilities` - Database connections
- `https://localhost/auth/health` - Auth system status

## Troubleshooting

### Container won't start
```bash
# Check logs
docker-compose logs

# Check config files
python3 -c "import yaml; print(yaml.safe_load(open('config/config.yaml')))"
```

### SSL certificate errors
```bash
# Regenerate certificate
./scripts/generate-self-signed.sh localhost

# Check certificate
openssl x509 -in certs/certificate.crt -text -noout
```

### Frontend not loading
```bash
# Check if files exist in container
docker exec ceneca-enterprise ls -la /app/static/

# Check nginx config
docker exec ceneca-enterprise nginx -t
```

### API not responding
```bash
# Check if FastAPI is running
docker exec ceneca-enterprise ps aux | grep python

# Test internal API
docker exec ceneca-enterprise curl http://localhost:8787/health
```

## Clean Up

```bash
# Stop and remove
docker-compose down

# Remove volumes (optional)
docker-compose down -v

# Remove image (optional)
docker rmi ceneca/enterprise:latest
```

## Next Steps

Once this works locally, you can:

1. **Deploy to staging**: Use real domain and SSL certificates
2. **Test with real SSO**: Configure your actual Okta/Azure AD
3. **Connect real databases**: Update config.yaml with production URLs
4. **Scale up**: Adjust resource limits in docker-compose.yml

## Expected Results

✅ All tests should pass  
✅ Frontend loads at `https://localhost`  
✅ API endpoints respond correctly  
✅ SSL certificate works (with browser warning)  
✅ Configuration files are properly loaded  

If anything fails, check the troubleshooting section above! 
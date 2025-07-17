# Ceneca Enterprise Deployment Overview

## What We Built

A complete enterprise deployment package that lets customers run Ceneca on their infrastructure in under 15 minutes.

## Customer Experience

1. **Receive**: Docker image + deployment package
2. **Configure**: Customize 2 config files  
3. **Deploy**: Run `docker-compose up -d`
4. **Test**: Run automated validation
5. **Access**: Visit `https://ceneca.theircompany.com`

## Architecture

Single container with nginx + React + FastAPI:
- `https://company.com/` → React frontend
- `https://company.com/api/` → FastAPI backend  
- SSL termination, authentication, monitoring included

## Files Created

- `docker-compose.yml` - Main deployment
- `Dockerfile` - Multi-stage container build
- `config/*.example` - Configuration templates
- `scripts/setup.sh` - Interactive configuration
- `scripts/test-deployment.sh` - Validation testing
- `QUICK_TEST.md` - 5-minute testing guide

## Test It Now

```bash
./deploy/build-test.sh
cd deploy/
./scripts/generate-self-signed.sh localhost
cp ~/.data-connector/config.yaml config/
docker-compose up -d
./scripts/test-deployment.sh --domain localhost
```

Open `https://localhost` - you should see Ceneca running! 
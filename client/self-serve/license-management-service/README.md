# Ceneca License Management Service

A simplified on-premise licensing system with telemetry and per-seat billing capabilities.

## Architecture

### Components
- **License Portal**: React frontend for license management and dashboard
- **License API**: FastAPI backend for license generation and validation  
- **License Agent**: Go service for on-premise deployments (embedded in customer systems)
- **Telemetry Service**: Usage tracking and analytics

### Key Features
- ✅ Simple JWT-based licensing
- ✅ Per-seat enforcement and billing
- ✅ Usage telemetry collection
- ✅ 7-day offline grace period
- ✅ Self-service license management
- ✅ Docker-friendly deployment

## Quick Start

### Development
```bash
# Start all services
docker-compose up -d

# Access services
Frontend: http://localhost:3020
API: http://localhost:8020
```

### Customer Deployment
```bash
# Customer gets a simple license file and agent
./ceneca-agent --license-file=license.jwt --app-port=8080
```

## Ports
- Frontend: 3020
- Backend API: 8020  
- License Agent: 9020
- Database: 5434

## Environment Variables
- `DATABASE_URL`: PostgreSQL connection string
- `JWT_SECRET`: JWT signing secret
- `PHONE_HOME_URL`: Cloud service URL for telemetry
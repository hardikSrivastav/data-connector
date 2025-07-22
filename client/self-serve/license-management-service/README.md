# License Management Service

Enterprise license management system with JWT-based licensing, validation, and usage tracking.

## Architecture

This microservice follows the same pattern as the template-editor-service with:

- **Backend**: FastAPI service with PostgreSQL
- **Frontend**: React/TypeScript with Tailwind CSS  
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Security**: JWT-based licenses with RSA-4096 signing
- **Docker**: Multi-container setup with docker-compose

## Features

### Core Components
- **License Generation Service**: Creates JWT-based license tokens
- **License Validation Engine**: Validates licenses with hardware binding
- **Customer Management**: Customer registration and management
- **Usage Analytics**: Telemetry collection and reporting
- **Admin Portal**: Web interface for license management

### Security Features
- RSA-4096 cryptographic signing
- Hardware fingerprinting and binding
- Export control compliance checks
- Audit logging for all operations
- Rate limiting and DDoS protection

## Quick Start

### Prerequisites
- Docker and Docker Compose
- Node.js 18+ (for development)
- Python 3.11+ (for development)

### Development Setup

1. **Start the services**:
```bash
docker-compose up -d
```

2. **Access the application**:
- Frontend: http://localhost:3010
- Backend API: http://localhost:8010
- API Documentation: http://localhost:8010/docs

3. **Database Migration** (if needed):
```bash
docker-compose exec license-backend python -m alembic upgrade head
```

### Production Deployment

1. **Environment Configuration**:
```bash
cp backend/.env.example backend/.env
# Edit backend/.env with production values
```

2. **Generate Production Keys**:
```bash
# Generate RSA private key
openssl genpkey -algorithm RSA -out backend/keys/private_key.pem -pkcs8 -aes256
```

3. **Deploy**:
```bash
docker-compose -f docker-compose.prod.yml up -d
```

## API Documentation

### Core Endpoints

**Health Check**
- `GET /health/` - Service health status
- `GET /health/db` - Database connectivity check

**Customer Management**
- `POST /api/customers/` - Create customer
- `GET /api/customers/` - List customers  
- `GET /api/customers/{id}` - Get customer details
- `PUT /api/customers/{id}` - Update customer
- `DELETE /api/customers/{id}` - Delete customer

**License Management**
- `POST /api/licenses/` - Generate new license
- `GET /api/licenses/` - List licenses
- `GET /api/licenses/{id}` - Get license details
- `GET /api/licenses/{id}/token` - Download license token
- `PUT /api/licenses/{id}/revoke` - Revoke license

**License Validation**
- `POST /api/validation/validate` - Validate license token
- `GET /api/validation/public-key` - Get public key for client validation
- `POST /api/validation/usage` - Report usage telemetry
- `GET /api/validation/license/{id}/status` - Get license status

## License Token Format

JWT tokens contain:

```json
{
  "customer": {
    "company_name": "Example Corp",
    "customer_id": "uuid",
    "contact_email": "admin@example.com",
    "industry_classification": "software"
  },
  "license": {
    "license_id": "uuid",
    "product_sku": "enterprise-v1",
    "edition_tier": "premium",
    "license_type": "subscription"
  },
  "constraints": {
    "start_date": "2024-01-01T00:00:00Z",
    "expiration_date": "2025-01-01T00:00:00Z",
    "user_limit": 100,
    "feature_flags": {"advanced_analytics": true}
  },
  "hardware_binding": {
    "binding_type": "flexible",
    "tolerance_level": 2
  },
  "operational": {
    "phone_home_frequency": 24,
    "offline_grace_period": 72
  }
}
```

## Development

### Backend Development
```bash
cd backend
python -m venv venv
source venv/bin/activate  # or venv\\Scripts\\activate on Windows
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8010
```

### Frontend Development  
```bash
cd frontend
npm install
npm run dev
```

### Running Tests
```bash
# Backend tests
cd backend
pytest

# Frontend tests
cd frontend  
npm test
```

## Configuration

### Environment Variables

**Backend (.env)**
```bash
DATABASE_URL=postgresql://user:pass@localhost:5433/license_db
PRIVATE_KEY_PATH=/path/to/private_key.pem
JWT_ALGORITHM=RS256
HSM_ENABLED=false
EXPORT_CONTROL_ENABLED=true
LOG_LEVEL=INFO
```

**Frontend (.env)**
```bash
VITE_API_URL=http://localhost:8010
```

## Security Considerations

### Production Setup
- Use Hardware Security Module (HSM) for key storage
- Enable mutual TLS for API communications
- Configure proper firewall rules
- Enable audit logging
- Set up monitoring and alerting
- Regular key rotation
- Backup and disaster recovery procedures

### Compliance
- Export control validation
- GDPR compliance features
- Industry-specific requirements (HIPAA, SOX, etc.)
- Audit trail maintenance

## Monitoring

Key metrics to monitor:
- License validation success rate
- API response times  
- Database performance
- Key management system health
- Failed validation attempts
- Usage reporting rates

## Support

For issues and questions:
1. Check the API documentation at `/docs`
2. Review logs in `docker-compose logs`
3. Validate configuration in `.env` files
4. Ensure all required services are running

## License

Enterprise License Management System - Internal Use Only
# Template Editor Service Integration Analysis

## Current Architecture Overview

### Main Application
- **Location**: `/client/`
- **Deployment**: `docker-compose.prod.yml`
- **Services**:
  - Frontend (Next.js): Port 3000
  - Backend (Node.js): Port 3001  
  - PostgreSQL: Port 5432
- **Purpose**: Main waitlist/landing application with payment processing

### Template Editor Service (Microservice)
- **Location**: `/client/self-serve/template-editor-service/`
- **Deployment**: Independent `docker-compose.yml`
- **Services**:
  - Frontend (React/Vite): Port 8500
  - Backend (FastAPI/Python): Port 8501
  - Database: SQLite (`app.db`)
- **Purpose**: AI-powered template customization for deployment configurations

## Current Integration Status

### ❌ No Existing Integration Found
After comprehensive analysis, **no webhook or integration points** exist between services:

- No API calls between main app (ports 3000/3001) and template service (ports 8500/8501)
- No shared environment variables or configuration
- No cross-service communication mechanisms
- Template service CORS only allows `localhost:8500`
- No authentication integration (template service has no auth requirements)

### Template Service Capabilities
- **AI-Powered Editing**: Claude API integration for intelligent template customization
- **Workspace Isolation**: Session-based isolated editing environments
- **Template Management**: Version control and validation for deployment templates
- **Real-time Chat**: WebSocket-based AI assistant for template guidance
- **Multi-Format Support**: YAML, Docker Compose, Nginx configs, Auth configs

### Template Categories Available
- Authentication (Auth0, Azure, Google, OIDC)
- Deployment (Docker Compose, Enterprise setups)  
- Infrastructure (Nginx proxy configurations)
- Configuration (Environment variables, SSL setup)

## Integration Architecture Options

### Option 1: Subdomain Deployment (`deploy.ceneca.ai`)

**Benefits**:
- True microservice independence
- Separate scaling and deployment
- Clean service boundaries
- Independent SSL and CDN setup

**Implementation**:
```yaml
# DNS Setup
deploy.ceneca.ai -> template-editor-service (ports 8500/8501)
ceneca.ai -> main-application (ports 3000/3001)
```

**Required Changes**:
1. Update CORS configuration in template service
2. Implement session handoff mechanism
3. Add completion callbacks to main app
4. Set up shared user context

### Option 2: Reverse Proxy Integration (`/deployment` route)

**Implementation**:
- Main frontend proxies `/deployment/*` to template service
- Embed template editor via iframe or direct integration
- Maintain single domain experience

**Required Infrastructure**:
- Nginx/proxy configuration updates
- Network bridge between services
- Authentication token passing

## Integration Requirements

### 1. Session Management
```typescript
// Main App -> Template Service
interface SessionHandoff {
  user_id: string;
  deployment_requirements: DeploymentSpec;
  callback_url: string;
  context: ProjectContext;
}

// Template Service -> Main App  
interface DeploymentComplete {
  session_id: string;
  generated_configs: ConfigFile[];
  deployment_status: 'ready' | 'failed';
  metadata: DeploymentMetadata;
}
```

### 2. API Integration Points
- **Session Creation**: `POST /api/sessions` with user context
- **Status Updates**: Webhook callbacks for deployment progress  
- **Config Retrieval**: Download generated deployment packages
- **History Tracking**: Link deployments to user accounts

### 3. Data Flow Architecture
```
Main App (ceneca.ai)
    ↓ (user initiates deployment)
Template Service (deploy.ceneca.ai)  
    ↓ (generates configs via AI)
Main App (receives completion webhook)
    ↓ (stores deployment record)
User Dashboard (shows deployment history)
```

## Implementation Roadmap

### Phase 1: Basic Integration
1. **Environment Setup**
   - Configure subdomain DNS (`deploy.ceneca.ai`)
   - Update CORS settings in template service
   - Set up SSL certificates for subdomain

2. **Session Handoff**
   - Add user context API to template service
   - Implement redirect mechanism from main app
   - Create session linking between services

### Phase 2: Callback Integration  
1. **Webhook Endpoints**
   - Add webhook receiver in main app backend
   - Implement deployment completion notifications
   - Set up retry/reliability mechanisms

2. **State Synchronization**
   - Track deployment sessions in main app database
   - Store generated configurations
   - Link deployments to user accounts

### Phase 3: Enhanced UX
1. **Shared Authentication** (if needed in future)
   - Implement JWT token passing
   - Add user validation in template service
   - Set up session timeout coordination

2. **Progress Tracking**
   - Real-time deployment status updates
   - Integration with main app notifications
   - Deployment history dashboard

## Environment Variables Required

### Template Service Updates
```bash
CORS_ORIGINS=https://ceneca.ai,https://deploy.ceneca.ai
MAIN_APP_CALLBACK_URL=https://ceneca.ai/api/deployment/webhook
MAIN_APP_API_KEY=<secure_api_key>
```

### Main App Updates  
```bash
TEMPLATE_SERVICE_URL=https://deploy.ceneca.ai
TEMPLATE_SERVICE_API_KEY=<secure_api_key>
WEBHOOK_SECRET=<webhook_verification_secret>
```

## Security Considerations

### Inter-Service Communication
- API key authentication for service-to-service calls
- Webhook signature verification  
- Rate limiting on integration endpoints
- Secure session token passing

### Data Protection
- User context sanitization
- Secure config file transmission
- Audit trail for deployment actions
- Data retention policies for generated configs

## Monitoring & Observability

### Key Metrics
- Session handoff success rate
- Deployment completion time  
- Template generation success rate
- Inter-service communication latency

### Logging Strategy
- Correlation IDs across services
- User journey tracking
- Integration failure alerts
- Performance monitoring

## Next Steps

1. **Immediate**: Set up subdomain DNS and SSL
2. **Week 1**: Implement basic session handoff mechanism
3. **Week 2**: Add webhook integration for deployment completion  
4. **Week 3**: Test end-to-end user journey
5. **Week 4**: Production deployment and monitoring setup

## Technical Notes

- Template service uses SQLite - consider PostgreSQL for production scale
- Current AI agent uses Anthropic Claude API - monitor usage/costs
- WebSocket connections are session-based - plan for horizontal scaling
- Generated workspace files stored locally - consider cloud storage integration

---
*Document created: January 2025*
*Last updated: January 2025*
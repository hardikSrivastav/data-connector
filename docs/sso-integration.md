# SSO Integration Architecture for Ceneca Web Frontend

## Executive Summary

This document outlines the SSO integration strategy for Ceneca's web frontend, prioritizing maximum security through a **backend-mediated authentication architecture**. This approach keeps all sensitive SSO logic server-side while providing seamless user experience through secure session management.

## Chosen Architecture: Backend-Mediated Authentication

### Why This Approach

After evaluating three potential SSO integration strategies, **backend-mediated authentication** is the optimal choice for Ceneca because:

1. **Maximum Security**: No sensitive tokens exposed to frontend JavaScript
2. **Enterprise-Ready**: Aligns with enterprise security best practices
3. **Reduced Attack Surface**: All SSO logic contained within secure agent server
4. **Simplified Frontend**: Web client only manages presentation layer
5. **Compliance-Friendly**: Easier to audit and meets strict security requirements

### Architecture Overview

```
┌─────────────────┐    HTTPS    ┌─────────────────┐    OIDC/SAML    ┌─────────────────┐
│   Web Browser   │◄──────────►│  Agent Server   │◄──────────────►│   SSO Provider  │
│                 │             │                 │                 │  (Okta, etc.)   │
│ - React UI      │             │ - FastAPI       │                 │                 │
│ - httpOnly      │             │ - SSO Logic     │                 │                 │
│   Cookies Only  │             │ - Session Mgmt  │                 │                 │
└─────────────────┘             └─────────────────┘                 └─────────────────┘
         │                               │
         │                               │
         ▼                               ▼
┌─────────────────┐             ┌─────────────────┐
│ Session Storage │             │ User/Role Store │
│ (Browser)       │             │ (Server-side)   │
└─────────────────┘             └─────────────────┘
```

## Authentication Flow

### 1. Initial Access Flow

```
User → Web App → Check Session → Redirect to SSO → Authenticate → Return to App
  │        │           │              │              │            │
  │        │           │              │              │            │
  ▼        ▼           ▼              ▼              ▼            ▼
Browser  Next.js   Agent Server   SSO Provider   Agent Server  Web App
         Frontend   /auth/check   (Okta/SAML)    /auth/callback (Authenticated)
```

### 2. Session Management Flow

```
Authenticated Request → Agent Server → Validate Session → Process Request → Return Response
                    │               │                 │                │
                    ▼               ▼                 ▼                ▼
               Check httpOnly    Verify JWT       Execute Query    Send Data + 
                  Cookie        in Session        with User        Refresh
                                   Store           Context           Session
```

## Implementation Components

### Agent Server Authentication Module

**New Files to Create:**
- `server/agent/auth/` - Authentication module directory
- `server/agent/auth/__init__.py` - Module initialization  
- `server/agent/auth/oidc_handler.py` - OIDC/OAuth2 implementation
- `server/agent/auth/saml_handler.py` - SAML 2.0 implementation
- `server/agent/auth/session_manager.py` - Session management
- `server/agent/auth/middleware.py` - Authentication middleware
- `server/agent/auth/config_loader.py` - Auth config loader

**Key Endpoints to Add:**
```python
# Authentication endpoints
POST /api/auth/login              # Initiate SSO flow
GET  /api/auth/callback           # Handle SSO callback  
POST /api/auth/logout             # Terminate session
GET  /api/auth/me                 # Get current user info
POST /api/auth/refresh            # Refresh session
GET  /api/auth/status             # Check auth status
```

### Frontend Authentication Integration

**Modified Files:**
- `server/web/src/lib/auth/` - Auth context and hooks
- `server/web/src/components/auth/` - Login/logout components  
- `server/web/src/middleware.ts` - Route protection
- `server/web/src/app/layout.tsx` - Auth provider wrapper

**Core Frontend Pattern:**
```typescript
// Authentication happens entirely server-side
// Frontend only manages UI state and redirects

const useAuth = () => {
  // No tokens stored in frontend
  // Only authentication status and user info
  const [user, setUser] = useState(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  
  const login = () => {
    // Redirect to agent server auth endpoint
    window.location.href = '/api/auth/login';
  };
  
  const logout = () => {
    // Call agent server logout
    fetch('/api/auth/logout', { method: 'POST' })
      .then(() => window.location.href = '/');
  };
};
```

## Security Architecture

### Session Security

**httpOnly Cookies Approach:**
```python
# Agent server session management
@router.post("/auth/callback")
async def auth_callback(request: Request, response: Response):
    # Process SSO callback
    user_info = await process_sso_callback(request)
    
    # Create secure session
    session_token = create_session_token(user_info)
    
    # Set secure cookie
    response.set_cookie(
        "ceneca_session",
        value=session_token,
        httponly=True,        # Cannot be accessed by JavaScript
        secure=True,          # HTTPS only
        samesite="strict",    # CSRF protection
        max_age=28800,        # 8 hours
        domain=None,          # Current domain only
        path="/"
    )
    
    return RedirectResponse("/dashboard")
```

**Token Storage Strategy:**
- ❌ **No tokens in localStorage/sessionStorage** - Vulnerable to XSS
- ❌ **No tokens in JavaScript variables** - Accessible to malicious scripts  
- ✅ **httpOnly cookies only** - Cannot be accessed by client-side code
- ✅ **Server-side session store** - All sensitive data server-side

### CSRF Protection

**Implementation:**
```python
# CSRF token generation and validation
@router.get("/auth/csrf-token")
async def get_csrf_token(request: Request):
    session = get_session(request)
    csrf_token = generate_csrf_token(session["user_id"])
    return {"csrf_token": csrf_token}

# Middleware for CSRF validation
async def csrf_middleware(request: Request, call_next):
    if request.method in ["POST", "PUT", "DELETE", "PATCH"]:
        csrf_token = request.headers.get("X-CSRF-Token")
        if not validate_csrf_token(csrf_token, request):
            raise HTTPException(401, "Invalid CSRF token")
    return await call_next(request)
```

### Role-Based Access Control (RBAC)

**User Context Injection:**
```python
# Middleware to inject user context
async def auth_middleware(request: Request, call_next):
    session = get_session(request)
    if session:
        user_context = {
            "user_id": session["user_id"],
            "email": session["email"], 
            "roles": session["roles"],
            "permissions": session["permissions"]
        }
        request.state.user = user_context
    return await call_next(request)

# Query execution with user context
async def execute_query(query: str, request: Request):
    user = request.state.user
    
    # Apply role-based data filtering
    filtered_query = apply_role_filters(query, user["roles"])
    
    # Log access with user context
    audit_logger.log_query_access(
        user_id=user["user_id"],
        query=filtered_query,
        timestamp=datetime.utcnow()
    )
    
    return await orchestrator.execute(filtered_query, user_context=user)
```

## Integration with Existing Okta Configuration

### Using Your auth-config.yaml

**Configuration Loader:**
```python
# server/agent/auth/config_loader.py
import yaml
from pathlib import Path

class AuthConfig:
    def __init__(self, config_path: str = None):
        if not config_path:
            config_path = Path.home() / ".data-connector" / "auth-config.yaml"
        
        with open(config_path) as f:
            self.config = yaml.safe_load(f)
    
    @property
    def oidc_config(self):
        return self.config["sso"]["oidc"]
    
    @property
    def role_mappings(self):
        return self.config.get("role_mappings", {})
    
    @property 
    def is_sso_enabled(self):
        return self.config["sso"]["enabled"]

# Usage in OIDC handler
auth_config = AuthConfig()
oidc_settings = auth_config.oidc_config

client = WebApplicationClient(oidc_settings["client_id"])
```

### Okta Integration Specifics

**OIDC Flow Implementation:**
```python
# server/agent/auth/oidc_handler.py
class OktaOIDCHandler:
    def __init__(self, config: dict):
        self.client_id = config["client_id"]
        self.client_secret = config["client_secret"] 
        self.discovery_url = config["discovery_url"]
        self.redirect_uri = config["redirect_uri"]
        self.scopes = config["scopes"]
        
    async def initiate_auth(self) -> str:
        """Generate authorization URL"""
        discovery_doc = await self.get_discovery_document()
        
        state = secrets.token_urlsafe(32)
        nonce = secrets.token_urlsafe(32)
        
        auth_url = (
            f"{discovery_doc['authorization_endpoint']}"
            f"?client_id={self.client_id}"
            f"&response_type=code"
            f"&scope={' '.join(self.scopes)}"
            f"&redirect_uri={self.redirect_uri}"
            f"&state={state}"
            f"&nonce={nonce}"
        )
        
        # Store state/nonce for validation
        await self.store_auth_state(state, nonce)
        
        return auth_url
    
    async def handle_callback(self, code: str, state: str) -> dict:
        """Process authorization code"""
        # Validate state
        await self.validate_auth_state(state)
        
        # Exchange code for tokens
        token_response = await self.exchange_code_for_tokens(code)
        
        # Validate and decode ID token
        user_info = await self.validate_id_token(token_response["id_token"])
        
        # Map Okta groups to Ceneca roles
        user_roles = self.map_groups_to_roles(user_info.get("groups", []))
        
        return {
            "user_id": user_info["sub"],
            "email": user_info["email"],
            "name": user_info["name"],
            "roles": user_roles,
            "permissions": self.get_permissions_for_roles(user_roles)
        }
```

## Implementation Phases

### Phase 1: Core Authentication (Week 1)

**Day 1-2: Agent Server Auth Module**
- Create authentication module structure
- Implement OIDC handler for Okta
- Set up session management
- Create authentication middleware

**Day 3-4: Frontend Integration** 
- Create auth context and hooks
- Implement login/logout components
- Add route protection middleware
- Update navigation components

**Day 5-7: Testing & Security**
- End-to-end authentication testing
- Security review and hardening
- CSRF protection implementation
- Session timeout handling

### Phase 2: Enhanced Security (Week 2)

**Day 1-3: RBAC Implementation**
- Role-based query filtering
- Permission system
- Audit logging
- Admin user management

**Day 4-5: Session Hardening**
- Session invalidation on logout
- Concurrent session limits
- Suspicious activity detection
- Token refresh mechanisms

**Day 6-7: Monitoring & Compliance**
- Authentication metrics
- Failed login tracking
- Compliance logging
- Security dashboard

### Phase 3: Advanced Features (Week 3)

**Day 1-3: SAML Support**
- SAML 2.0 handler implementation
- Multi-protocol support
- Provider configuration UI

**Day 4-7: Enterprise Features**
- Multi-tenant support
- Custom role definitions
- SSO provider failover
- Advanced audit trails

## Security Considerations

### Data Protection

**Sensitive Data Handling:**
- All SSO tokens stored server-side only
- User session data encrypted in storage
- PII encrypted with enterprise keys
- Audit logs include access patterns

**Transport Security:**
- All communications over HTTPS/TLS 1.3
- Certificate pinning for SSO providers
- HSTS headers for browser security
- CSP headers to prevent XSS

### Monitoring & Incident Response

**Security Monitoring:**
- Failed authentication attempts
- Unusual access patterns
- Token manipulation attempts
- Session hijacking detection

**Incident Response:**
- Automatic session invalidation on threats
- Security team notifications
- User notification on suspicious activity
- Forensic logging for investigations

## Conclusion

The backend-mediated authentication approach provides enterprise-grade security while maintaining a seamless user experience. By keeping all sensitive authentication logic server-side and using secure session management, Ceneca can meet the strictest enterprise security requirements while providing powerful data analytics capabilities.

This implementation leverages your existing Okta configuration in `auth-config.yaml` and integrates seamlessly with the current agent server architecture, requiring minimal changes to the existing codebase while adding robust SSO capabilities. 
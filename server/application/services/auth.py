"""
Authentication services module.
This is a placeholder that can be expanded to include SSO integration later.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from ..config import get_settings

# Simple placeholder security scheme - can be replaced with real JWT or OAuth2 later
security = HTTPBearer(auto_error=False)

# This function will be replaced with real SSO validation later
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """
    Placeholder for future SSO integration.
    
    This function will:
    1. Validate the token with the SSO provider
    2. Return user info from the token
    3. Check access permissions
    
    When AUTH_ENABLED=False, this will simply pass through without checking.
    """
    settings = get_settings()
    
    # When auth is disabled, allow all requests
    if not settings.AUTH_ENABLED:
        return {"id": "anonymous", "roles": ["user"]}
    
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    # In the future, this will validate with your SSO provider
    # token = credentials.credentials
    # user_data = await verify_token(token)
    
    # For now, just a stub
    return {"id": "user123", "roles": ["user"]}

# This can be used for role-based permissions
def require_role(required_role: str):
    """
    Dependency for endpoints that require specific role.
    Use like: @router.get("/admin", dependencies=[Depends(require_role("admin"))])
    """
    async def _require_role(user: dict = Depends(get_current_user)):
        settings = get_settings()
        
        # When auth is disabled, allow all requests
        if not settings.AUTH_ENABLED:
            return
            
        if required_role not in user.get("roles", []):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role {required_role} required"
            )
    
    return _require_role 
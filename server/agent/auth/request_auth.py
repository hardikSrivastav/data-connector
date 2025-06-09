"""
Request-level authentication for Ceneca Agent Server

Provides authentication checking without requiring FastAPI middleware.
Used as dependencies in route handlers.
"""

import logging
from typing import Optional, List
from fastapi import Request, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from .session_manager import SessionData
from .config import AuthConfig

logger = logging.getLogger(__name__)

# Security scheme for bearer token
security = HTTPBearer(auto_error=False)

def get_auth_config(request: Request) -> Optional[AuthConfig]:
    """Get auth config from app state"""
    return getattr(request.app.state, 'auth_config', None)

def is_auth_enabled(request: Request) -> bool:
    """Check if authentication is enabled"""
    return getattr(request.app.state, 'auth_enabled', False)

async def get_session_manager(request: Request):
    """Get session manager from auth manager"""
    try:
        from .auth_manager import auth_manager
        return auth_manager.session_manager
    except Exception:
        return None

async def extract_session_id(request: Request) -> Optional[str]:
    """
    Extract session ID from request
    
    Tries cookie first, then Authorization header
    """
    # Try cookie first
    session_id = request.cookies.get('ceneca_session')
    
    if session_id:
        return session_id
    
    # Try authorization header
    auth_header = request.headers.get('authorization')
    if auth_header and auth_header.startswith('Bearer '):
        return auth_header.split(' ', 1)[1]
    
    return None

async def get_current_user_optional(request: Request) -> Optional[SessionData]:
    """
    Get current user if authenticated, None otherwise
    
    Does not raise exceptions - returns None for unauthenticated requests
    """
    # Skip if auth is disabled
    if not is_auth_enabled(request):
        return None
    
    try:
        session_manager = await get_session_manager(request)
        if not session_manager:
            return None
        
        session_id = await extract_session_id(request)
        if not session_id:
            return None
        
        session_data = await session_manager.get_session(session_id)
        if not session_data or not session_data.is_valid():
            return None
        
        # Update session activity
        try:
            session_data.update_last_accessed()
            await session_manager._store_session(session_id, session_data)
        except Exception as e:
            logger.warning(f"Failed to update session activity: {e}")
        
        return session_data
        
    except Exception as e:
        logger.error(f"Error getting current user: {e}")
        return None

async def get_current_user(request: Request) -> SessionData:
    """
    Get current authenticated user
    
    Raises HTTPException if not authenticated
    """
    # Skip auth if disabled
    if not is_auth_enabled(request):
        # Create a dummy user for development
        return SessionData(
            session_id="dev-session",
            user_id="dev-user",
            email="dev@example.com",
            name="Development User",
            groups=["dev"],
            roles=["admin"],
            provider="development"
        )
    
    user = await get_current_user_optional(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user

async def require_role(required_roles: List[str]):
    """
    Create a dependency that requires specific roles
    
    Args:
        required_roles: List of roles that are allowed
        
    Returns:
        Dependency function
    """
    async def role_checker(request: Request, current_user: SessionData = Depends(get_current_user)) -> SessionData:
        if not is_auth_enabled(request):
            return current_user  # Skip role check if auth disabled
        
        if not any(role in current_user.roles for role in required_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required roles: {required_roles}"
            )
        
        return current_user
    
    return role_checker

async def require_admin(request: Request, current_user: SessionData = Depends(get_current_user)) -> SessionData:
    """
    Require admin role
    
    Args:
        request: HTTP request
        current_user: Current authenticated user
        
    Returns:
        SessionData if user is admin
        
    Raises:
        HTTPException: If user is not admin
    """
    if not is_auth_enabled(request):
        return current_user  # Skip role check if auth disabled
    
    if 'admin' not in current_user.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required"
        )
    
    return current_user

def is_public_route(path: str) -> bool:
    """
    Check if route is public (doesn't require authentication)
    
    Args:
        path: Request path
        
    Returns:
        True if route is public
    """
    public_routes = {
        '/health',
        '/auth/login',
        '/auth/callback',
        '/auth/health',
        '/auth/status',
        '/docs',
        '/openapi.json',
        '/favicon.ico'
    }
    
    # Exact match
    if path in public_routes:
        return True
    
    # Prefix match for auth routes
    if path.startswith('/auth/'):
        return True
    
    # Allow static assets
    if path.startswith('/static/') or path.startswith('/assets/'):
        return True
        
    return False 
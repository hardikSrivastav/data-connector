"""
Authentication middleware for Ceneca Agent Server

Provides FastAPI middleware for session validation and route protection.
All authentication logic is handled server-side for maximum security.
"""

import logging
from typing import Dict, Optional, List, Callable, Any
from datetime import datetime
import time

from fastapi import Request, Response, HTTPException, status, Depends
from fastapi.security import HTTPBearer
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from .session_manager import SessionManager, SessionData
from .config import AuthConfig

logger = logging.getLogger(__name__)

class AuthMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for authentication and session management
    """
    
    def __init__(self, app, auth_config: AuthConfig, session_manager: SessionManager):
        """
        Initialize authentication middleware
        
        Args:
            app: FastAPI application instance
            auth_config: Authentication configuration
            session_manager: Session manager instance
        """
        super().__init__(app)
        self.auth_config = auth_config
        self.session_manager = session_manager
        
        # Routes that don't require authentication
        self.public_routes = {
            '/health',
            '/auth/login',
            '/auth/callback',
            '/auth/health',
            '/docs',
            '/openapi.json',
            '/favicon.ico'
        }
        
        # Routes that require specific roles
        self.role_protected_routes = {
            '/admin': ['admin'],
            '/sessions': ['admin'],  # Session management requires admin role
        }
        
        logger.info("Initialized authentication middleware")
    
    async def dispatch(self, request: Request, call_next):
        """
        Process request through authentication middleware
        
        Args:
            request: Incoming HTTP request
            call_next: Next middleware/handler in chain
            
        Returns:
            HTTP response
        """
        # Skip authentication for public routes
        if self._is_public_route(request.url.path):
            return await call_next(request)
        
        # Skip authentication if SSO is disabled
        if not self.auth_config.enabled:
            logger.debug(f"SSO disabled, allowing access to: {request.url.path}")
            return await call_next(request)
        
        try:
            # Extract session from request
            session_data = await self._extract_session(request)
            
            if not session_data:
                return self._unauthorized_response("No valid session found")
            
            # Check role-based access
            if not self._check_role_access(request.url.path, session_data.roles):
                return self._forbidden_response(f"Insufficient permissions for {request.url.path}")
            
            # Add user context to request
            request.state.user = session_data
            request.state.authenticated = True
            
            # Process request
            response = await call_next(request)
            
            # Update session activity
            await self._update_session_activity(session_data.session_id)
            
            return response
            
        except Exception as e:
            logger.error(f"Authentication middleware error: {e}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"error": "Authentication system error", "detail": str(e)}
            )
    
    def _is_public_route(self, path: str) -> bool:
        """
        Check if route is public (doesn't require authentication)
        
        Args:
            path: Request path
            
        Returns:
            True if route is public
        """
        # Exact match
        if path in self.public_routes:
            return True
        
        # Prefix match for auth routes
        if path.startswith('/auth/'):
            return True
        
        # Allow static assets
        if path.startswith('/static/') or path.startswith('/assets/'):
            return True
            
        return False
    
    def _check_role_access(self, path: str, user_roles: List[str]) -> bool:
        """
        Check if user has required roles for the path
        
        Args:
            path: Request path
            user_roles: User's roles
            
        Returns:
            True if user has access
        """
        # Check for exact role requirements
        for protected_path, required_roles in self.role_protected_routes.items():
            if path.startswith(protected_path):
                # User must have at least one of the required roles
                if not any(role in user_roles for role in required_roles):
                    logger.warning(f"Role access denied: {path} requires {required_roles}, user has {user_roles}")
                    return False
        
        return True
    
    async def _extract_session(self, request: Request) -> Optional[SessionData]:
        """
        Extract and validate session from request
        
        Args:
            request: HTTP request
            
        Returns:
            SessionData if valid session exists, None otherwise
        """
        # Try to get session ID from cookie
        session_id = request.cookies.get('ceneca_session')
        
        if not session_id:
            # Try Authorization header as fallback
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                session_id = auth_header[7:]  # Remove 'Bearer ' prefix
        
        if not session_id:
            logger.debug("No session ID found in request")
            return None
        
        # Validate session
        session_data = await self.session_manager.get_session(session_id)
        
        if not session_data:
            logger.debug(f"Invalid session ID: {session_id[:8]}...")
            return None
        
        if not session_data.is_valid():
            logger.debug(f"Expired session: {session_id[:8]}...")
            await self.session_manager.delete_session(session_id)
            return None
        
        logger.debug(f"Valid session found for user: {session_data.email}")
        return session_data
    
    async def _update_session_activity(self, session_id: str) -> None:
        """
        Update session last accessed time
        
        Args:
            session_id: Session identifier
        """
        try:
            session_data = await self.session_manager.get_session(session_id)
            if session_data:
                session_data.update_last_accessed()
                await self.session_manager._store_session(session_id, session_data)
        except Exception as e:
            logger.warning(f"Failed to update session activity: {e}")
    
    def _unauthorized_response(self, message: str) -> JSONResponse:
        """
        Create unauthorized response
        
        Args:
            message: Error message
            
        Returns:
            401 Unauthorized response
        """
        logger.info(f"Unauthorized access: {message}")
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "error": "Authentication required",
                "message": message,
                "login_url": "/auth/login"
            }
        )
    
    def _forbidden_response(self, message: str) -> JSONResponse:
        """
        Create forbidden response
        
        Args:
            message: Error message
            
        Returns:
            403 Forbidden response
        """
        logger.info(f"Access forbidden: {message}")
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "error": "Insufficient permissions",
                "message": message
            }
        )


# Dependency for protected routes
async def get_current_user(request: Request) -> SessionData:
    """
    FastAPI dependency to get current authenticated user
    
    Args:
        request: HTTP request
        
    Returns:
        SessionData for authenticated user
        
    Raises:
        HTTPException: If user is not authenticated
    """
    if not hasattr(request.state, 'user') or not request.state.user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    return request.state.user


async def require_role(required_roles: List[str]) -> Callable:
    """
    FastAPI dependency factory for role-based access control
    
    Args:
        required_roles: List of roles that are allowed access
        
    Returns:
        Dependency function
    """
    async def role_checker(current_user: SessionData = Depends(get_current_user)) -> SessionData:
        """
        Check if current user has required roles
        
        Args:
            current_user: Current authenticated user
            
        Returns:
            SessionData if user has required roles
            
        Raises:
            HTTPException: If user doesn't have required roles
        """
        if not any(role in current_user.roles for role in required_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {required_roles}, User roles: {current_user.roles}"
            )
        
        return current_user
    
    return role_checker


async def require_admin(current_user: SessionData = Depends(get_current_user)) -> SessionData:
    """
    FastAPI dependency to require admin role
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        SessionData if user is admin
        
    Raises:
        HTTPException: If user is not admin
    """
    if 'admin' not in current_user.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    return current_user


class AuthenticationError(Exception):
    """Custom authentication error"""
    pass


class AuthorizationError(Exception):
    """Custom authorization error"""
    pass 
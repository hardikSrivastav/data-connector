"""
Authentication endpoints for Ceneca Agent Server

Provides SSO login, callback, logout, and user info endpoints.
All authentication logic is kept server-side for maximum security.
ENTERPRISE MODE ONLY - No development fallbacks.
"""

import logging
from typing import Dict, Any, Optional, List
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Request, Response, Depends, status
from fastapi.responses import RedirectResponse, JSONResponse
from pydantic import BaseModel

from .config import AuthConfig
from .oidc_handler import OIDCHandler
from .session_manager import SessionManager, SessionData
from .request_auth import get_current_user_strict, require_admin

logger = logging.getLogger(__name__)

# Response models
class LoginResponse(BaseModel):
    """Login initiation response"""
    authorization_url: str
    state: str
    message: str = "Redirect to authorization URL to complete login"

class UserInfoResponse(BaseModel):
    """Current user information"""
    user_id: str
    email: str
    name: str
    groups: List[str]
    roles: List[str]
    provider: str
    session_created: float
    session_expires: float
    authenticated: bool = True

class LogoutResponse(BaseModel):
    """Logout response"""
    success: bool
    message: str

class AuthHealthResponse(BaseModel):
    """Authentication system health"""
    status: str
    sso_enabled: bool
    provider: str
    session_manager: Dict[str, Any]
    oidc_handler: Dict[str, Any]
    message: Optional[str] = None
    mode: str = "enterprise"

def create_auth_router(auth_config: AuthConfig, oidc_handler: OIDCHandler, session_manager: SessionManager) -> APIRouter:
    """
    Create authentication router with configured handlers
    ENTERPRISE MODE: Requires properly configured SSO
    
    Args:
        auth_config: Authentication configuration
        oidc_handler: OIDC authentication handler
        session_manager: Session manager
        
    Returns:
        Configured FastAPI router
        
    Raises:
        ValueError: If SSO is not properly configured
    """
    if not auth_config.enabled:
        raise ValueError("Enterprise mode requires enabled SSO authentication")
    
    router = APIRouter(tags=["authentication"])
    
    @router.post("/auth/login", response_model=LoginResponse)
    async def initiate_login(request: Request):
        """
        Initiate SSO login flow
        
        Returns:
            Login response with authorization URL
        """
        logger.info("🔐 AUTH ENDPOINT: /auth/login - Initiating SSO login")
        
        try:
            # Generate authorization URL
            auth_url, state, code_verifier = oidc_handler.generate_authorization_url()
            
            logger.info(f"Generated authorization URL for state: {state[:8]}...")
            
            return LoginResponse(
                authorization_url=auth_url,
                state=state,
                message="Redirect to authorization URL to complete login"
            )
            
        except Exception as e:
            logger.error(f"Login initiation failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to initiate login: {str(e)}"
            )
    
    @router.get("/auth/callback")
    async def handle_callback(
        request: Request, 
        response: Response, 
        code: Optional[str] = None, 
        state: Optional[str] = None,
        error: Optional[str] = None,
        error_description: Optional[str] = None
    ):
        """
        Handle OIDC callback from identity provider
        
        Args:
            request: HTTP request
            response: HTTP response
            code: Authorization code from IdP
            state: State parameter for CSRF protection
            
        Returns:
            Redirect to web application with session cookie
        """
        logger.info(f"🔐 AUTH ENDPOINT: /auth/callback - Handling OIDC callback")
        logger.info(f"Callback parameters: code={'***' if code else None}, state={state[:8] + '...' if state else None}, error={error}")
        
        # Handle OAuth error responses
        if error:
            logger.error(f"OAuth error in callback: {error} - {error_description}")
            # Redirect to frontend with error
            return RedirectResponse(
                url=f"http://localhost:8080/?auth_error={error}&error_description={error_description or 'Authentication failed'}",
                status_code=status.HTTP_302_FOUND
            )
        
        # Validate required parameters for success case
        if not code or not state:
            logger.error(f"Missing required callback parameters: code={bool(code)}, state={bool(state)}")
            return RedirectResponse(
                url="http://localhost:8080/?auth_error=invalid_request&error_description=Missing authorization code or state",
                status_code=status.HTTP_302_FOUND
            )
        
        try:
            # Process OIDC callback
            session_id = await oidc_handler.handle_callback(code, state)
            
            # Set secure session cookie
            response = RedirectResponse(
                url=f"http://localhost:8080/",  # Redirect to web frontend
                status_code=status.HTTP_302_FOUND
            )
            
            # Set httpOnly cookie for maximum security
            response.set_cookie(
                key="ceneca_session",
                value=session_id,
                max_age=auth_config.session_timeout,
                httponly=True,  # Prevents JavaScript access
                secure=False,   # Set to True in production with HTTPS
                samesite="lax",  # CSRF protection
                path="/"
            )
            
            logger.info(f"Successfully authenticated user, redirecting to frontend")
            return response
            
        except ValueError as e:
            logger.error(f"Invalid callback parameters: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid callback: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Callback processing failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Authentication failed: {str(e)}"
            )
    
    @router.get("/auth/user", response_model=UserInfoResponse)
    async def get_current_user_info(current_user: SessionData = Depends(get_current_user_strict)):
        """
        Get current authenticated user information
        
        Args:
            current_user: Current authenticated user session
            
        Returns:
            User information
        """
        logger.info(f"🔐 AUTH ENDPOINT: /auth/user - Getting info for user: {current_user.email}")
        
        return UserInfoResponse(
            user_id=current_user.user_id,
            email=current_user.email,
            name=current_user.name,
            groups=current_user.groups,
            roles=current_user.roles,
            provider=current_user.provider,
            session_created=current_user.created_at,
            session_expires=current_user.expires_at
        )
    
    @router.post("/auth/logout", response_model=LogoutResponse)
    async def logout(request: Request, response: Response):
        """
        Logout current user and clear session
        
        Args:
            request: HTTP request
            response: HTTP response
            
        Returns:
            Logout confirmation
        """
        logger.info("🔐 AUTH ENDPOINT: /auth/logout - Logging out user")
        
        try:
            # Get session ID from cookie
            session_id = request.cookies.get('ceneca_session')
            
            if session_id:
                # Delete session
                success = await oidc_handler.logout_user(session_id)
                
                if success:
                    logger.info(f"User session logged out: {session_id[:8]}...")
                
                # Clear session cookie
                response.delete_cookie(
                    key="ceneca_session",
                    path="/",
                    httponly=True,
                    samesite="lax"
                )
                
                return LogoutResponse(
                    success=True,
                    message="Successfully logged out"
                )
            else:
                return LogoutResponse(
                    success=True,
                    message="No active session found"
                )
                
        except Exception as e:
            logger.error(f"Logout failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Logout failed: {str(e)}"
            )
    
    @router.get("/auth/health", response_model=AuthHealthResponse)
    async def auth_health_check():
        """
        Authentication system health check
        
        Returns:
            Health status of authentication components
        """
        logger.info("🔐 AUTH ENDPOINT: /auth/health - Checking authentication system health")
        
        try:
            # Check session manager
            session_health = await session_manager.health_check()
            
            # Check OIDC handler
            oidc_health = await oidc_handler.health_check()
            
            # Determine overall status
            overall_status = "healthy"
            message = None
            
            if oidc_health.get("status") != "healthy":
                overall_status = "degraded"
                message = f"OIDC handler issue: {oidc_health.get('error', 'Unknown error')}"
            
            return AuthHealthResponse(
                status=overall_status,
                sso_enabled=True,  # Always true in enterprise mode
                provider=auth_config.oidc.provider,
                session_manager=session_health,
                oidc_handler=oidc_health,
                message=message,
                mode="enterprise"
            )
            
        except Exception as e:
            logger.error(f"Auth health check failed: {e}")
            return AuthHealthResponse(
                status="error",
                sso_enabled=True,
                provider=auth_config.oidc.provider,
                session_manager={"error": str(e)},
                oidc_handler={"error": str(e)},
                message=f"Health check failed: {str(e)}",
                mode="enterprise"
            )
    
    # Admin-only endpoints
    @router.get("/auth/sessions")
    async def list_sessions(admin_user: SessionData = Depends(require_admin)):
        """
        List active sessions (admin only)
        
        Args:
            admin_user: Admin user session
            
        Returns:
            List of active sessions
        """
        logger.info(f"🔐 AUTH ENDPOINT: /auth/sessions - Admin {admin_user.email} listing sessions")
        
        try:
            active_sessions = await session_manager.get_active_sessions_count()
            
            return {
                "active_sessions_count": active_sessions,
                "session_timeout": session_manager.session_timeout,
                "storage_type": "redis" if session_manager.use_redis else "memory",
                "mode": "enterprise"
            }
            
        except Exception as e:
            logger.error(f"Failed to list sessions: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to list sessions: {str(e)}"
            )
    
    @router.post("/auth/sessions/cleanup")
    async def cleanup_sessions(admin_user: SessionData = Depends(require_admin)):
        """
        Clean up expired sessions (admin only)
        
        Args:
            admin_user: Admin user session
            
        Returns:
            Cleanup results
        """
        logger.info(f"🔐 AUTH ENDPOINT: /auth/sessions/cleanup - Admin {admin_user.email} cleaning up sessions")
        
        try:
            cleaned_count = await session_manager.cleanup_expired_sessions()
            
            return {
                "cleaned_sessions": cleaned_count,
                "message": f"Cleaned up {cleaned_count} expired sessions",
                "mode": "enterprise"
            }
            
        except Exception as e:
            logger.error(f"Session cleanup failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Session cleanup failed: {str(e)}"
            )
    
    return router 
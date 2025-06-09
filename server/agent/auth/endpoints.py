"""
Authentication endpoints for Ceneca Agent Server

Provides SSO login, callback, logout, and user info endpoints.
All authentication logic is kept server-side for maximum security.
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
from .request_auth import get_current_user, require_admin

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

def create_auth_router(auth_config: AuthConfig, oidc_handler: OIDCHandler, session_manager: SessionManager) -> APIRouter:
    """
    Create authentication router with configured handlers
    
    Args:
        auth_config: Authentication configuration
        oidc_handler: OIDC authentication handler
        session_manager: Session manager
        
    Returns:
        Configured FastAPI router
    """
    router = APIRouter(prefix="/auth", tags=["authentication"])
    
    @router.post("/login", response_model=LoginResponse)
    async def initiate_login(request: Request):
        """
        Initiate SSO login flow
        
        Returns:
            Login response with authorization URL
        """
        logger.info("🔐 AUTH ENDPOINT: /auth/login - Initiating SSO login")
        
        if not auth_config.enabled:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="SSO authentication is disabled"
            )
        
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
    
    @router.get("/callback")
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
        
        if not auth_config.enabled:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="SSO authentication is disabled"
            )
        
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
    
    @router.get("/user", response_model=UserInfoResponse)
    async def get_current_user_info(current_user: SessionData = Depends(get_current_user)):
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
    
    @router.post("/logout", response_model=LogoutResponse)
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
    
    @router.get("/health", response_model=AuthHealthResponse)
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
            
            # Check OIDC handler (only if SSO is enabled)
            oidc_health = {}
            if auth_config.enabled:
                oidc_health = await oidc_handler.health_check()
            
            # Determine overall status
            overall_status = "healthy"
            message = None
            
            if auth_config.enabled:
                if oidc_health.get("status") != "healthy":
                    overall_status = "degraded"
                    message = f"OIDC handler issue: {oidc_health.get('error', 'Unknown error')}"
            
            return AuthHealthResponse(
                status=overall_status,
                sso_enabled=auth_config.enabled,
                provider=auth_config.oidc.provider if auth_config.enabled else "none",
                session_manager=session_health,
                oidc_handler=oidc_health,
                message=message
            )
            
        except Exception as e:
            logger.error(f"Auth health check failed: {e}")
            return AuthHealthResponse(
                status="error",
                sso_enabled=auth_config.enabled,
                provider=auth_config.oidc.provider if auth_config.enabled else "none",
                session_manager={"error": str(e)},
                oidc_handler={"error": str(e)},
                message=f"Health check failed: {str(e)}"
            )
    
    # Admin-only endpoints
    @router.get("/sessions")
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
                "storage_type": "redis" if session_manager.use_redis else "memory"
            }
            
        except Exception as e:
            logger.error(f"Failed to list sessions: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to list sessions: {str(e)}"
            )
    
    @router.post("/sessions/cleanup")
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
                "message": f"Cleaned up {cleaned_count} expired sessions"
            }
            
        except Exception as e:
            logger.error(f"Session cleanup failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Session cleanup failed: {str(e)}"
            )
    
    return router

def create_basic_auth_router() -> APIRouter:
    """
    Create basic authentication router that works for both SSO enabled and disabled
    
    Dynamically checks SSO status and responds appropriately
    
    Returns:
        FastAPI router with auth endpoints
    """
    router = APIRouter(prefix="/auth", tags=["authentication"])
    
    @router.get("/health", response_model=AuthHealthResponse)
    async def auth_health_check():
        """
        Get authentication system health status
        
        Returns:
            Authentication health status
        """
        logger.info("🔐 AUTH ENDPOINT: /auth/health - Checking auth system health")
        
        try:
            from .auth_manager import auth_manager
            
            if auth_manager.is_initialized and auth_manager.is_enabled:
                # SSO is enabled - get real health status
                health = await auth_manager.health_check()
                return AuthHealthResponse(
                    status=health.get("status", "unknown"),
                    sso_enabled=True,
                    provider=health.get("provider", "unknown"),
                    session_manager=health.get("session_manager", {}),
                    oidc_handler=health.get("oidc_handler", {}),
                    message=health.get("message")
                )
            else:
                # SSO is disabled
                return AuthHealthResponse(
                    status="disabled",
                    sso_enabled=False,
                    provider="none",
                    session_manager={"status": "disabled"},
                    oidc_handler={"status": "disabled"},
                    message="SSO authentication is disabled"
                )
        except Exception as e:
            logger.error(f"Auth health check failed: {e}")
            return AuthHealthResponse(
                status="error",
                sso_enabled=False,
                provider="unknown",
                session_manager={"status": "error"},
                oidc_handler={"status": "error"},
                message=f"Health check failed: {str(e)}"
            )
    
    @router.post("/login")
    async def login_dynamic(request: Request):
        """Login endpoint that works for both SSO enabled and disabled"""
        try:
            from .auth_manager import auth_manager
            
            if auth_manager.is_initialized and auth_manager.is_enabled:
                # SSO is enabled - proceed with real login
                if not auth_manager.auth_config.enabled:
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="SSO authentication is disabled"
                    )
                
                # Generate authorization URL
                auth_url, state, code_verifier = auth_manager.oidc_handler.generate_authorization_url()
                
                logger.info(f"Generated authorization URL for state: {state[:8]}...")
                
                return LoginResponse(
                    authorization_url=auth_url,
                    state=state,
                    message="Redirect to authorization URL to complete login"
                )
            else:
                # SSO is disabled
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="SSO authentication is disabled. Enable SSO in auth-config.yaml to use this endpoint."
                )
        except Exception as e:
            logger.error(f"Login failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Login failed: {str(e)}"
            )
    
    @router.get("/callback")
    async def callback_dynamic(request: Request, response: Response, code: str, state: str):
        """Callback endpoint that works for both SSO enabled and disabled"""
        try:
            from .auth_manager import auth_manager
            
            if auth_manager.is_initialized and auth_manager.is_enabled:
                # SSO is enabled - process callback
                session_id = await auth_manager.oidc_handler.handle_callback(code, state)
                
                # Set secure session cookie
                response = RedirectResponse(
                    url=f"http://localhost:8080/",  # Redirect to web frontend
                    status_code=status.HTTP_302_FOUND
                )
                
                # Set httpOnly cookie for maximum security
                response.set_cookie(
                    key="ceneca_session",
                    value=session_id,
                    max_age=auth_manager.auth_config.session_timeout,
                    httponly=True,  # Prevents JavaScript access
                    secure=False,   # Set to True in production with HTTPS
                    samesite="lax",  # CSRF protection
                    path="/"
                )
                
                logger.info(f"Successfully authenticated user, redirecting to frontend")
                return response
            else:
                # SSO is disabled
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="SSO authentication is disabled"
                )
        except Exception as e:
            logger.error(f"Callback failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Callback failed: {str(e)}"
            )
    
    @router.get("/user", response_model=UserInfoResponse)
    async def user_info_dynamic(request: Request):
        """User info endpoint that works for both SSO enabled and disabled"""
        try:
            from .auth_manager import auth_manager
            from .request_auth import get_current_user_optional
            
            if auth_manager.is_initialized and auth_manager.is_enabled:
                # SSO is enabled - get real user info
                user = await get_current_user_optional(request)
                if not user:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Not authenticated"
                    )
                
                return UserInfoResponse(
                    user_id=user.user_id,
                    email=user.email,
                    name=user.name,
                    groups=user.groups,
                    roles=user.roles,
                    provider=user.provider,
                    session_created=user.created_at,
                    session_expires=user.expires_at,
                    authenticated=True
                )
            else:
                # SSO is disabled - return dev user
                return UserInfoResponse(
                    user_id="dev-user",
                    email="dev@example.com",
                    name="Development User",
                    groups=["dev"],
                    roles=["admin"],
                    provider="development",
                    session_created=0,
                    session_expires=0,
                    authenticated=False
                )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"User info failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get user info: {str(e)}"
            )
    
    @router.post("/logout", response_model=LogoutResponse)
    async def logout_dynamic(request: Request, response: Response):
        """Logout endpoint that works for both SSO enabled and disabled"""
        try:
            from .auth_manager import auth_manager
            
            if auth_manager.is_initialized and auth_manager.is_enabled:
                # SSO is enabled - real logout
                session_id = request.cookies.get('ceneca_session')
                
                if session_id and auth_manager.session_manager:
                    await auth_manager.session_manager.delete_session(session_id)
                    logger.info(f"Deleted session: {session_id[:8]}...")
                
                # Clear session cookie
                response.delete_cookie("ceneca_session", path="/")
                
                return LogoutResponse(
                    success=True,
                    message="Successfully logged out"
                )
            else:
                # SSO is disabled
                return LogoutResponse(
                    success=True,
                    message="SSO authentication is disabled - no session to logout"
                )
        except Exception as e:
            logger.error(f"Logout failed: {e}")
            return LogoutResponse(
                success=False,
                message=f"Logout failed: {str(e)}"
            )
    
    return router 
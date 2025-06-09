"""
Authentication module for Ceneca Agent Server

Provides enterprise-grade SSO authentication using OIDC/OAuth2 with backend-mediated security.
All sensitive authentication logic is kept server-side for maximum security.
"""

from .oidc_handler import OIDCHandler
from .session_manager import SessionManager
from .middleware import AuthMiddleware
from .config import AuthConfig
from .auth_manager import AuthManager, auth_manager
from .request_auth import (
    get_current_user,
    get_current_user_optional,
    require_role,
    require_admin,
    is_public_route,
    is_auth_enabled
)

__all__ = [
    'OIDCHandler',
    'SessionManager', 
    'AuthMiddleware',
    'AuthConfig',
    'AuthManager',
    'auth_manager',
    'get_current_user',
    'get_current_user_optional',
    'require_role',
    'require_admin',
    'is_public_route',
    'is_auth_enabled'
] 
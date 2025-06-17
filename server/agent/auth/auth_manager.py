"""
Authentication manager for Ceneca Agent Server

Centralizes initialization and management of all authentication components.
ENTERPRISE MODE ONLY - No development fallbacks allowed.
"""

import logging
import asyncio
from typing import Optional

from .config import AuthConfig
from .session_manager import SessionManager
from .oidc_handler import OIDCHandler
from .middleware import AuthMiddleware
from .endpoints import create_auth_router

logger = logging.getLogger(__name__)

class AuthManager:
    """
    Manages all authentication components for the Ceneca agent server
    ENTERPRISE MODE: Requires proper SSO configuration
    """
    
    def __init__(self):
        """Initialize authentication manager"""
        self.auth_config: Optional[AuthConfig] = None
        self.session_manager: Optional[SessionManager] = None
        self.oidc_handler: Optional[OIDCHandler] = None
        self.auth_middleware: Optional[AuthMiddleware] = None
        self._initialized = False
        
        logger.info("Created AuthManager instance (Enterprise Mode)")
    
    async def initialize(self, config_path: Optional[str] = None) -> bool:
        """
        Initialize authentication system in ENTERPRISE MODE
        
        Args:
            config_path: Optional path to auth config file
            
        Returns:
            True if authentication is enabled and initialized successfully
            
        Raises:
            RuntimeError: If SSO is not properly configured for enterprise deployment
        """
        try:
            logger.info("🔐 Initializing authentication system (Enterprise Mode)...")
            
            # Load authentication configuration
            self.auth_config = AuthConfig.load_from_file(config_path)
            self.auth_config.validate()
            
            logger.info(f"Authentication config loaded: SSO {'enabled' if self.auth_config.enabled else 'disabled'}")
            
            if not self.auth_config.enabled:
                logger.error("🚨 ENTERPRISE MODE VIOLATION: SSO authentication is disabled")
                raise RuntimeError(
                    "Enterprise deployment requires SSO authentication. "
                    "Enable SSO in auth-config.yaml or use development deployment."
                )
            
            # Initialize session manager
            # Check if Redis should be used (in production)
            use_redis = self.auth_config.session_timeout > 3600  # Use Redis for longer sessions
            
            self.session_manager = SessionManager(
                session_timeout=self.auth_config.session_timeout,
                use_redis=use_redis
            )
            
            logger.info(f"Session manager initialized with {self.session_manager.session_timeout}s timeout")
            
            # Initialize OIDC handler
            self.oidc_handler = OIDCHandler(
                auth_config=self.auth_config,
                session_manager=self.session_manager
            )
            
            logger.info(f"OIDC handler initialized for provider: {self.auth_config.oidc.provider}")
            
            # Test OIDC connectivity - REQUIRED in enterprise mode
            try:
                await self.oidc_handler.get_provider_config()
                logger.info("✅ OIDC provider connectivity test successful")
            except Exception as e:
                logger.error(f"❌ OIDC provider connectivity test failed: {e}")
                raise RuntimeError(
                    f"Enterprise mode requires working OIDC connectivity. "
                    f"Provider {self.auth_config.oidc.provider} is not reachable: {e}"
                )
            
            self._initialized = True
            logger.info("🔐 Authentication system initialized successfully (Enterprise Mode)")
            return True
            
        except FileNotFoundError as e:
            logger.error(f"Auth config not found: {e}")
            raise RuntimeError(
                f"Enterprise deployment requires auth-config.yaml. File not found: {e}"
            )
        except Exception as e:
            logger.error(f"Failed to initialize authentication: {e}")
            raise RuntimeError(
                f"Enterprise authentication initialization failed: {e}"
            )
    
    def create_middleware(self, app):
        """
        Create and return authentication middleware
        
        Args:
            app: FastAPI application instance
            
        Returns:
            AuthMiddleware instance
            
        Raises:
            RuntimeError: If not properly initialized
        """
        if not self._initialized:
            raise RuntimeError("AuthManager not initialized. Call initialize() first.")
        
        if not self.auth_config or not self.auth_config.enabled:
            raise RuntimeError("Enterprise mode requires enabled authentication")
        
        if not self.session_manager or not self.oidc_handler:
            raise RuntimeError("Cannot create middleware - auth components not initialized")
        
        self.auth_middleware = AuthMiddleware(
            app=app,
            auth_config=self.auth_config,
            session_manager=self.session_manager
        )
        
        logger.info("Authentication middleware created")
        return self.auth_middleware
    
    def create_auth_router(self):
        """
        Create and return authentication router
        
        Returns:
            FastAPI router with authentication endpoints
            
        Raises:
            RuntimeError: If not properly initialized
        """
        if not self._initialized:
            raise RuntimeError("AuthManager not initialized. Call initialize() first.")
        
        if not self.auth_config or not self.auth_config.enabled:
            raise RuntimeError("Enterprise mode requires enabled authentication")
        
        if not self.session_manager or not self.oidc_handler:
            raise RuntimeError("Cannot create auth router - auth components not initialized")
        
        auth_router = create_auth_router(
            auth_config=self.auth_config,
            oidc_handler=self.oidc_handler,
            session_manager=self.session_manager
        )
        
        logger.info("Authentication router created")
        return auth_router
    
    async def health_check(self) -> dict:
        """
        Get health status of authentication system
        
        Returns:
            Health status dictionary
        """
        if not self._initialized:
            return {
                "status": "not_initialized",
                "message": "AuthManager not initialized",
                "mode": "enterprise"
            }
        
        if not self.auth_config or not self.auth_config.enabled:
            return {
                "status": "disabled",
                "message": "SSO authentication is disabled - ENTERPRISE MODE VIOLATION",
                "mode": "enterprise",
                "error": "Enterprise deployment requires SSO"
            }
        
        health_data = {
            "status": "enabled",
            "provider": self.auth_config.oidc.provider,
            "session_timeout": self.auth_config.session_timeout,
            "mode": "enterprise"
        }
        
        try:
            if self.session_manager:
                session_health = await self.session_manager.health_check()
                health_data["session_manager"] = session_health
            
            if self.oidc_handler:
                oidc_health = await self.oidc_handler.health_check()
                health_data["oidc_handler"] = oidc_health
                
        except Exception as e:
            health_data["status"] = "error"
            health_data["error"] = str(e)
        
        return health_data
    
    async def cleanup(self):
        """Clean up authentication resources"""
        if self.oidc_handler:
            await self.oidc_handler.cleanup()
        
        logger.info("Authentication system cleaned up")
    
    @property
    def is_enabled(self) -> bool:
        """Check if authentication is enabled (ALWAYS required in enterprise mode)"""
        return (
            self._initialized and 
            self.auth_config is not None and 
            self.auth_config.enabled
        )
    
    @property
    def is_initialized(self) -> bool:
        """Check if authentication manager is initialized"""
        return self._initialized


# Global auth manager instance
auth_manager = AuthManager() 
"""
Authentication manager for Ceneca Agent Server

Centralizes initialization and management of all authentication components.
Provides a single interface for setting up SSO authentication.
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
    """
    
    def __init__(self):
        """Initialize authentication manager"""
        self.auth_config: Optional[AuthConfig] = None
        self.session_manager: Optional[SessionManager] = None
        self.oidc_handler: Optional[OIDCHandler] = None
        self.auth_middleware: Optional[AuthMiddleware] = None
        self._initialized = False
        
        logger.info("Created AuthManager instance")
    
    async def initialize(self, config_path: Optional[str] = None) -> bool:
        """
        Initialize authentication system
        
        Args:
            config_path: Optional path to auth config file
            
        Returns:
            True if authentication is enabled and initialized successfully
        """
        try:
            logger.info("🔐 Initializing authentication system...")
            
            # Load authentication configuration
            self.auth_config = AuthConfig.load_from_file(config_path)
            self.auth_config.validate()
            
            logger.info(f"Authentication config loaded: SSO {'enabled' if self.auth_config.enabled else 'disabled'}")
            
            if not self.auth_config.enabled:
                logger.info("SSO authentication is disabled - running in open mode")
                self._initialized = True
                return False
            
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
            
            # Test OIDC connectivity
            try:
                await self.oidc_handler.get_provider_config()
                logger.info("✅ OIDC provider connectivity test successful")
            except Exception as e:
                logger.warning(f"⚠️  OIDC provider connectivity test failed: {e}")
                logger.warning("Authentication will still work, but there might be connectivity issues")
            
            self._initialized = True
            logger.info("🔐 Authentication system initialized successfully")
            return True
            
        except FileNotFoundError as e:
            logger.warning(f"Auth config not found: {e}")
            logger.info("Running without authentication (development mode)")
            self._initialized = True
            return False
        except Exception as e:
            logger.error(f"Failed to initialize authentication: {e}")
            logger.info("Running without authentication due to initialization failure")
            self._initialized = True
            return False
    
    def create_middleware(self, app):
        """
        Create and return authentication middleware
        
        Args:
            app: FastAPI application instance
            
        Returns:
            AuthMiddleware instance if SSO is enabled, None otherwise
        """
        if not self._initialized:
            raise RuntimeError("AuthManager not initialized. Call initialize() first.")
        
        if not self.auth_config or not self.auth_config.enabled:
            logger.info("Authentication middleware not created - SSO disabled")
            return None
        
        if not self.session_manager or not self.oidc_handler:
            logger.error("Cannot create middleware - auth components not initialized")
            return None
        
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
        """
        if not self._initialized:
            raise RuntimeError("AuthManager not initialized. Call initialize() first.")
        
        if not self.auth_config or not self.auth_config.enabled:
            logger.info("Authentication router not created - SSO disabled")
            return None
        
        if not self.session_manager or not self.oidc_handler:
            logger.error("Cannot create auth router - auth components not initialized")
            return None
        
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
                "message": "AuthManager not initialized"
            }
        
        if not self.auth_config or not self.auth_config.enabled:
            return {
                "status": "disabled",
                "message": "SSO authentication is disabled"
            }
        
        health_data = {
            "status": "enabled",
            "provider": self.auth_config.oidc.provider,
            "session_timeout": self.auth_config.session_timeout
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
        """Check if authentication is enabled"""
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
import asyncio
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routes import main_router, storage_router, canvas_router
from .config import get_settings
from .middleware import CIDRMiddleware

logger = logging.getLogger(__name__)

def create_app():
    app = FastAPI(
        title="Data Connector API",
        description="API for connecting to various data sources",
        version="0.1.0"
    )
    
    # Add CORS middleware for development
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",  # Web client
            "http://localhost:8080",  # Vite dev server  
            "http://localhost:8787",  # API self-reference
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Store auth state for later initialization
    app.state.auth_enabled = False
    app.state.auth_config = None
    
    # Initialize authentication system on startup
    @app.on_event("startup")
    async def initialize_auth():
        """Initialize authentication system"""
        try:
            from agent.auth import auth_manager
            
            logger.info("🚀 Initializing authentication system...")
            auth_enabled = await auth_manager.initialize()
            
            if auth_enabled:
                logger.info("🔐 SSO authentication enabled")
                app.state.auth_enabled = True
                app.state.auth_config = auth_manager.auth_config
                logger.info("🔐 Authentication system fully initialized")
            else:
                logger.info("🔓 Running without authentication (development mode)")
                app.state.auth_enabled = False
                
        except Exception as e:
            logger.error(f"❌ Failed to initialize authentication: {e}")
            logger.info("🔓 Continuing without authentication")
            app.state.auth_enabled = False
    
    @app.on_event("shutdown")
    async def cleanup_auth():
        """Clean up authentication resources"""
        try:
            from agent.auth import auth_manager
            await auth_manager.cleanup()
            logger.info("🔐 Authentication system cleaned up")
        except Exception as e:
            logger.error(f"Error cleaning up authentication: {e}")
    
    # Add IP filtering middleware for VPN restriction
    settings = get_settings()
    if settings.ALLOWED_CIDR_BLOCKS:
        app.add_middleware(CIDRMiddleware)
    
    # Include routers
    app.include_router(main_router)
    app.include_router(storage_router)
    app.include_router(canvas_router)
    
    return app

import asyncio
import logging
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from .routes import main_router, storage_router, canvas_router
from .config import get_settings
from .middleware import CIDRMiddleware

logger = logging.getLogger(__name__)

def add_cors_headers(response: JSONResponse, origin: str = "*") -> JSONResponse:
    """Add CORS headers to any response"""
    # Allow specific origins in development
    allowed_origins = [
        "http://localhost:3000",
        "http://localhost:8080", 
        "http://localhost:8787"
    ]
    
    # Use the requesting origin if it's in our allowed list, otherwise use the first one
    if origin in allowed_origins:
        response.headers["Access-Control-Allow-Origin"] = origin
    else:
        response.headers["Access-Control-Allow-Origin"] = "http://localhost:8080"
    
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS, PATCH"
    response.headers["Access-Control-Allow-Headers"] = "*"
    response.headers["Vary"] = "Origin"
    return response

def create_app():
    app = FastAPI(
        title="Data Connector API",
        description="API for connecting to various data sources",
        version="0.1.0"
    )
    
    # Global exception handlers to ensure CORS headers are always present
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        """Handle HTTP exceptions with CORS headers"""
        origin = request.headers.get("origin", "http://localhost:8080")
        response = JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail}
        )
        return add_cors_headers(response, origin)
    
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        """Handle validation errors with CORS headers"""
        origin = request.headers.get("origin", "http://localhost:8080")
        response = JSONResponse(
            status_code=422,
            content={"detail": exc.errors()}
        )
        return add_cors_headers(response, origin)
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Handle any other exceptions with CORS headers"""
        origin = request.headers.get("origin", "http://localhost:8080")
        logger.error(f"Unhandled exception: {exc}", exc_info=True)
        response = JSONResponse(
            status_code=500,
            content={"detail": f"Internal server error: {str(exc)}"}
        )
        return add_cors_headers(response, origin)
    
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
        """Initialize authentication system in ENTERPRISE MODE"""
        try:
            from agent.auth import auth_manager
            
            logger.info("🚀 Initializing authentication system (Enterprise Mode)...")
            
            # Enterprise mode requires successful initialization
            auth_enabled = await auth_manager.initialize()
            
            logger.info("🔐 SSO authentication enabled")
            app.state.auth_enabled = True
            app.state.auth_config = auth_manager.auth_config
            
            # Create and include auth router
            auth_router = auth_manager.create_auth_router()
            app.include_router(auth_router, prefix="/api/agent")
            
            logger.info("🔐 Authentication system fully initialized (Enterprise Mode)")
                
        except Exception as e:
            logger.error(f"❌ ENTERPRISE MODE VIOLATION: Failed to initialize authentication: {e}")
            logger.error("🚨 Enterprise deployment requires working SSO authentication")
            # Don't continue without auth in enterprise mode
            raise RuntimeError(f"Enterprise mode requires authentication: {e}")
            
        # Initialize database availability monitoring
        try:
            from agent.services.database_availability import initialize_availability_service
            
            logger.info("🔍 Initializing database availability monitoring...")
            await initialize_availability_service()
            logger.info("✅ Database availability monitoring started")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize database availability monitoring: {e}")
            logger.info("⚠️ Continuing without database availability monitoring")
    
    @app.on_event("shutdown")
    async def cleanup_auth():
        """Clean up authentication resources"""
        try:
            from agent.auth import auth_manager
            await auth_manager.cleanup()
            logger.info("🔐 Authentication system cleaned up")
        except Exception as e:
            logger.error(f"Error cleaning up authentication: {e}")
            
        # Clean up database availability monitoring
        try:
            from agent.services.database_availability import get_availability_service
            
            service = get_availability_service()
            await service.stop_monitoring()
            logger.info("🔍 Database availability monitoring stopped")
            
        except Exception as e:
            logger.error(f"Error cleaning up database availability monitoring: {e}")
    
    # Add IP filtering middleware for VPN restriction
    settings = get_settings()
    if settings.ALLOWED_CIDR_BLOCKS:
        app.add_middleware(CIDRMiddleware)
    
    # Include routers
    app.include_router(main_router)
    app.include_router(storage_router)
    app.include_router(canvas_router)
    
    return app

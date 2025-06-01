from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routes import main_router, storage_router, canvas_router
from .config import get_settings
from .middleware import CIDRMiddleware

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
    
    # Authentication middleware can be added here later
    # This makes it easy to plug in VPN validation and SSO authentication
    # without changing the core application structure
    
    # Add IP filtering middleware for VPN restriction
    settings = get_settings()
    if settings.ALLOWED_CIDR_BLOCKS:
        app.add_middleware(CIDRMiddleware)
    
    # Include routers
    app.include_router(main_router)
    app.include_router(storage_router)
    app.include_router(canvas_router)
    
    return app

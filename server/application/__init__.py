from fastapi import FastAPI
from .routes import main_router
from .config import get_settings
from .middleware import CIDRMiddleware

def create_app():
    app = FastAPI(
        title="Data Connector API",
        description="API for connecting to various data sources",
        version="0.1.0"
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
    
    return app

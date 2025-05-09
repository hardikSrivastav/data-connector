from fastapi import FastAPI
from .routes import main_router

def create_app():
    app = FastAPI(
        title="Data Connector API",
        description="API for connecting to various data sources",
        version="0.1.0"
    )
    
    # Include routers
    app.include_router(main_router)
    
    return app

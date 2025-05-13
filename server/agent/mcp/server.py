from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import uvicorn
import logging
from typing import List
import os
import sys

# Add current directory to path if needed
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

# Try different import styles based on context
try:
    # Direct imports when running as a module
    from config import settings
    from db.database import init_db, get_db
    from api import auth, tools
except ImportError:
    # Package imports when imported from another module
    from .config import settings
    from .db.database import init_db, get_db
    from .api import auth, tools

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Slack MCP Server",
    description="MCP Server for Slack integration with agents",
    version="1.0.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(tools.router, prefix="/api/tools", tags=["tools"])

@app.on_event("startup")
async def startup():
    """Initialize the database on startup"""
    logger.info("Starting MCP server")
    init_db()
    logger.info("Database initialized")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok"}

@app.get("/")
async def root():
    """Root endpoint with basic information"""
    return {
        "server": "Slack MCP Server",
        "version": "1.0.0",
        "docs": "/docs",
    }

def start():
    """Start the MCP server"""
    host = settings.HOST
    port = settings.PORT
    
    logger.info(f"Starting MCP server on {host}:{port}")
    uvicorn.run(
        "agent.mcp.server:app",
        host=host,
        port=port,
        reload=settings.DEV_MODE,
        log_level="info",
    )

if __name__ == "__main__":
    start()

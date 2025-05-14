from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import uvicorn
import logging
from typing import List
import os
import sys
import asyncio
from contextlib import asynccontextmanager

# Add current directory to path if needed
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)
    
# Add parent directory to path to allow absolute imports
parent_dir = os.path.dirname(os.path.dirname(current_dir))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

# Robust import handling
try:
    # First try direct imports
    from config import settings
    from db.database import init_db, get_db
    from api import auth, tools, indexing
    from indexer import run_scheduled_indexing
except ImportError:
    try:
        # Then try package-style imports
        from .config import settings
        from .db.database import init_db, get_db
        from .api import auth, tools, indexing
        from .indexer import run_scheduled_indexing
    except ImportError:
        # Finally try absolute imports
        from agent.mcp.config import settings
        from agent.mcp.db.database import init_db, get_db
        from agent.mcp.api import auth, tools, indexing
        from agent.mcp.indexer import run_scheduled_indexing

# Set up logging
logging.basicConfig(
    level=logging.INFO if settings.DEBUG else logging.WARNING,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Scheduler task
scheduler_task = None

async def schedule_indexing():
    """Background task for scheduled indexing"""
    while True:
        try:
            await run_scheduled_indexing()
        except Exception as e:
            logger.error(f"Error in scheduled indexing: {str(e)}")
        
        # Run every hour
        await asyncio.sleep(3600)  # 1 hour

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Start scheduler at startup
    global scheduler_task
    scheduler_task = asyncio.create_task(schedule_indexing())
    logger.info("Started indexing scheduler")
    
    yield
    
    # Cancel scheduler at shutdown
    if scheduler_task:
        scheduler_task.cancel()
        try:
            await scheduler_task
        except asyncio.CancelledError:
            pass
        logger.info("Cancelled indexing scheduler")

# Create FastAPI app
app = FastAPI(
    title="Slack MCP Server",
    description="Microservice Control Panel for Slack integration",
    version="1.0.0",
    lifespan=lifespan
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
app.include_router(indexing.router, prefix="/api/indexing", tags=["indexing"])

@app.on_event("startup")
async def startup():
    """Initialize the database on startup"""
    logger.info("Starting MCP server")
    init_db()
    logger.info("Database initialized")
    
    # Also run migrations to ensure all columns exist
    try:
        # Try with both import styles
        try:
            from db.migrate import run_migration
        except ImportError:
            try:
                from .db.migrate import run_migration
            except ImportError:
                from agent.mcp.db.migrate import run_migration
                
        logger.info("Running database migrations to ensure schema is up to date...")
        run_migration()
        logger.info("Database migrations applied successfully")
    except Exception as e:
        logger.error(f"Error applying migrations: {str(e)}")
        logger.error("Server might not function correctly without required database columns!")
        # Don't crash the server, but warn loudly about the issue

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

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
        "agent.mcp.server:app",  # Use proper module reference
        host=host,
        port=port,
        reload=settings.DEV_MODE,
        log_level="info",
    )

if __name__ == "__main__":
    start()

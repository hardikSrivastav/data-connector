from fastapi import APIRouter, HTTPException
import asyncio
import logging
from agent.api.endpoints import router as agent_router

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["main"])

@router.get("/")
async def root():
    return {"message": "Welcome to the Data Connector API"}

@router.get("/health")
async def health_check():
    return {"status": "healthy"}

@router.get("/auth/status")
async def auth_status():
    """Get authentication system status"""
    try:
        from agent.auth import auth_manager
        health = await auth_manager.health_check()
        return health
    except Exception as e:
        logger.error(f"Auth status check failed: {e}")
        return {
            "status": "error",
            "message": f"Failed to get auth status: {str(e)}"
        }

# Include agent router
router.include_router(agent_router, prefix="/agent", tags=["agent"])

def setup_auth_router(app):
    """Setup auth router from app state after startup"""
    try:
        # Get the auth router from app state (set during startup)
        auth_router = getattr(app.state, 'auth_router', None)
        
        if auth_router:
            # Include auth router at /api/agent/auth to match frontend expectations
            router.include_router(auth_router, prefix="/agent", tags=["authentication"])
            logger.info("🔐 Auth router included at /api/agent/auth")
            return True
        else:
            logger.warning("🔐 No auth router found in app state")
            return False
            
    except Exception as e:
        logger.error(f"Failed to setup auth router: {e}")
        return False

def add_auth_router_if_enabled():
    """Legacy function - auth router is now handled by setup_auth_router"""
    logger.info("🔐 Auth router setup is now handled by setup_auth_router function")
    return True

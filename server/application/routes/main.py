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

# Always include basic auth router - this will be populated during startup
try:
    from agent.auth.endpoints import create_basic_auth_router
    
    # Create a basic auth router that will work whether SSO is enabled or not
    basic_auth_router = create_basic_auth_router()
    router.include_router(basic_auth_router, prefix="/agent", tags=["authentication"])
    logger.info("📱 Basic authentication router included")
    
except Exception as e:
    logger.warning(f"Failed to include auth router: {e}")

def add_auth_router_if_enabled():
    """Legacy function - auth router is now always included"""
    logger.info("🔐 Auth router already included during setup")
    return True

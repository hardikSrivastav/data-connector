from fastapi import APIRouter, HTTPException
import asyncio
from agent.api.endpoints import router as agent_router

router = APIRouter(prefix="/api", tags=["main"])

@router.get("/")
async def root():
    return {"message": "Welcome to the Data Connector API"}

@router.get("/health")
async def health_check():
    return {"status": "healthy"}

# Include agent router
router.include_router(agent_router, prefix="/agent", tags=["agent"])

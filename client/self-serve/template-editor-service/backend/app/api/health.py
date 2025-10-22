from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database.database import get_db
import os

router = APIRouter()

@router.get("/")
async def health_check():
    """Basic health check endpoint"""
    return {
        "status": "healthy",
        "service": "template-editor-service",
        "version": "1.0.0"
    }

@router.get("/detailed")
async def detailed_health_check(db: Session = Depends(get_db)):
    """Detailed health check including database connectivity"""
    try:
        # Test database connection
        db.execute("SELECT 1")
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
    
    # Check required environment variables
    env_status = "healthy"
    required_env = ["ANTHROPIC_API_KEY"]
    missing_env = [var for var in required_env if not os.getenv(var)]
    if missing_env:
        env_status = f"missing variables: {', '.join(missing_env)}"
    
    return {
        "status": "healthy" if db_status == "healthy" and env_status == "healthy" else "unhealthy",
        "service": "template-editor-service",
        "version": "1.0.0",
        "database": db_status,
        "environment": env_status,
        "anthropic_api": "configured" if os.getenv("ANTHROPIC_API_KEY") else "not configured"
    }
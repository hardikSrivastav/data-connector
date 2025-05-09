from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api", tags=["main"])

@router.get("/")
async def root():
    return {"message": "Welcome to the Data Connector API"}

@router.get("/health")
async def health_check():
    return {"status": "healthy"}

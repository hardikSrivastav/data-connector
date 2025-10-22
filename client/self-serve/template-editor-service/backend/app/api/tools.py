from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

router = APIRouter()

class TokenRequest(BaseModel):
    """Request model for tool token requests"""
    tool_name: Optional[str] = None
    purpose: Optional[str] = None

class TokenResponse(BaseModel):
    """Response model for tool token requests"""
    status: str
    message: str
    token: Optional[str] = None

@router.post("/token")
async def get_tool_token(request: TokenRequest):
    """
    Handle tool token requests
    
    This endpoint is commonly requested by Claude Code extensions or other tools
    for authentication purposes. For this template editor service, we don't need
    actual authentication tokens, so we return a helpful message.
    """
    return TokenResponse(
        status="not_required",
        message="This template editor service does not require authentication tokens. Access is open for development purposes.",
        token=None
    )

@router.get("/token")
async def get_tool_token_get():
    """
    Handle GET requests for tool tokens
    """
    return TokenResponse(
        status="not_required",
        message="This template editor service does not require authentication tokens. Access is open for development purposes.",
        token=None
    )

@router.post("/invoke")
async def invoke_tool(request: dict):
    """
    Handle tool invocation requests
    
    This endpoint is commonly requested by Claude Code extensions for tool execution.
    Since this is a template editor service, we return a helpful message indicating
    that direct tool invocation is not supported.
    """
    return {
        "status": "not_supported",
        "message": "Direct tool invocation is not supported. Please use the template editor interface at the frontend.",
        "suggestion": "Access the template editor at http://localhost:8500 to interact with the service."
    }

@router.get("/status")
async def get_tools_status():
    """
    Return the status of available tools
    """
    return {
        "status": "available",
        "tools": [
            {
                "name": "template-editor",
                "version": "1.0.0",
                "status": "active",
                "description": "AI-powered template editing service"
            }
        ]
    }
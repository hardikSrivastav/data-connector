from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class OAuthState(BaseModel):
    """OAuth state for CSRF protection"""
    state: str
    user_id: int
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None


class OAuthToken(BaseModel):
    """OAuth token response from Slack"""
    access_token: str
    token_type: str
    scope: str
    bot_user_id: str
    app_id: str
    team: Dict[str, Any]
    enterprise: Optional[Dict[str, Any]] = None
    authed_user: Optional[Dict[str, Any]] = None


class TokenResponse(BaseModel):
    """Response model for token generation"""
    token: str
    expires_at: int


class TokenRequest(BaseModel):
    """Request model for token generation"""
    user_id: int
    workspace_id: int

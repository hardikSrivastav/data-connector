from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class SlackWorkspaceInfo(BaseModel):
    """Information about a Slack workspace"""
    id: int
    team_id: str
    team_name: str
    added_at: str
    is_admin: bool = False


class SlackToolRequest(BaseModel):
    """Request model for Slack tool invocation"""
    tool: str
    parameters: Optional[Dict[str, Any]] = {}


class SlackChannel(BaseModel):
    """Slack channel information"""
    id: str
    name: str


class SlackMessage(BaseModel):
    """Slack message information"""
    type: str
    user: Optional[str] = None
    text: str
    ts: str
    thread_ts: Optional[str] = None
    reply_count: Optional[int] = None
    reactions: Optional[List[Dict[str, Any]]] = None


class SlackToolResponse(BaseModel):
    """Response model for Slack tool invocation"""
    result: Dict[str, Any]

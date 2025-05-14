from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime


class IndexingStatus(BaseModel):
    """Status of the indexing process for a workspace"""
    workspace_id: int
    collection_name: str
    last_indexed_at: Optional[datetime] = None
    total_messages: int = 0
    indexed_messages: int = 0
    oldest_message_date: Optional[datetime] = None
    newest_message_date: Optional[datetime] = None
    is_indexing: bool = False


class SearchQuery(BaseModel):
    """Semantic search query for Slack messages"""
    workspace_id: int
    query: str
    channels: Optional[List[str]] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    users: Optional[List[str]] = None
    limit: int = 20
    # Optional user_id for direct credential authentication
    user_id: Optional[int] = None


class SearchResult(BaseModel):
    """Result of a semantic search"""
    messages: List[Dict[str, Any]]
    total: int
    query_time_ms: float


class IndexingRequest(BaseModel):
    """Request to start an indexing process"""
    workspace_id: int
    force_full: bool = False
    # Optional user_id for direct credential authentication
    user_id: Optional[int] = None 
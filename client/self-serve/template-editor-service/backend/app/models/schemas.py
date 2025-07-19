from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum

class SessionStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"

class SessionCreate(BaseModel):
    user_id: str
    template_version: str = "auth-v1.0.0"
    project_context: Optional[Dict[str, Any]] = None

class SessionResponse(BaseModel):
    id: str
    user_id: str
    template_version: str
    template_hash: str
    status: SessionStatus
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

class EditHistoryResponse(BaseModel):
    id: str
    session_id: str
    file_path: str
    placeholder: Optional[str] = None
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    timestamp: datetime

class TemplateVersionResponse(BaseModel):
    version: str
    name: str
    description: Optional[str] = None
    hash: str
    schema: Optional[Dict[str, Any]] = None
    created_at: datetime

class FileContent(BaseModel):
    path: str
    content: str
    hash: str

class WorkspaceResponse(BaseModel):
    session_id: str
    files: List[FileContent]
    metadata: Dict[str, Any]

class ChatMessage(BaseModel):
    message: str
    context: Optional[Dict[str, Any]] = None

class ChatResponse(BaseModel):
    response: str
    action: Optional[str] = None  # question, edit, complete
    data: Optional[Dict[str, Any]] = None

class ValidationResult(BaseModel):
    valid: bool
    errors: List[str] = []
    warnings: List[str] = []
    similarity_score: Optional[float] = None
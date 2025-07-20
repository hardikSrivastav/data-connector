from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum

class SessionStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"

class TemplateCategory(str, Enum):
    AUTHENTICATION = "authentication"
    DEPLOYMENT = "deployment"
    INFRASTRUCTURE = "infrastructure"
    CONFIGURATION = "configuration"
    LEGACY = "legacy"  # For backwards compatibility with existing templates

class TemplateFormat(str, Enum):
    YAML = "yaml"
    DOCKER_COMPOSE = "docker-compose"
    NGINX = "nginx"
    JAVASCRIPT = "javascript"
    ENV = "env"

class SessionCreate(BaseModel):
    user_id: str
    scenario_id: Optional[str] = None
    template_version: Optional[str] = None  # For backwards compatibility
    project_context: Optional[Dict[str, Any]] = None
    variables: Optional[Dict[str, str]] = None  # Initial variable values

class SessionResponse(BaseModel):
    id: str
    user_id: str
    scenario_id: Optional[str] = None
    template_version: Optional[str] = None  # For backwards compatibility
    template_hash: Optional[str] = None     # For backwards compatibility
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
    category: Optional[str] = None
    format: Optional[str] = None

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

class TemplateValidationRequest(BaseModel):
    content: str
    format_type: str

class TemplateValidationResponse(BaseModel):
    valid: bool
    error: Optional[str] = None

class TemplateCategoriesResponse(BaseModel):
    categories: List[str]

class TemplateSchemaResponse(BaseModel):
    version: str
    schema: Dict[str, Any]

class DeploymentScenario(BaseModel):
    id: str
    name: str
    description: str
    category: str
    template_versions: List[str]
    dependencies: Dict[str, Any]
    variable_mappings: Dict[str, Any]
    created_at: datetime

class ScenarioValidationRequest(BaseModel):
    scenario_id: str
    variables: Dict[str, str]

class ScenarioValidationResponse(BaseModel):
    valid: bool
    errors: List[str] = []
    warnings: List[str] = []

class SessionTemplateResponse(BaseModel):
    id: int
    session_id: str
    template_version: str
    template_hash: str
    status: str
    variables: Optional[Dict[str, str]] = None
    created_at: datetime
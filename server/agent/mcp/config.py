from pydantic import BaseSettings, Field, validator
import os
from typing import List, Optional, Dict, Any, Union
import json
import secrets


class Settings(BaseSettings):
    """Settings for the MCP server"""
    
    # Server settings
    HOST: str = Field("0.0.0.0", description="Host to bind the server to")
    PORT: int = Field(8500, description="Port to bind the server to")
    DEBUG: bool = Field(False, description="Enable debug mode")
    DEV_MODE: bool = Field(False, description="Enable development mode with auto-reload")
    
    # Auth database settings
    DB_HOST: str = Field("localhost", description="Database host")
    DB_PORT: int = Field(6500, description="Database port")
    DB_NAME: str = Field("slackoauth", description="Database name")
    DB_USER: str = Field("slackoauth", description="Database user")
    DB_PASSWORD: str = Field("slackoauth", description="Database password")
    
    # URL settings
    API_BASE_URL: str = Field("https://7454-2405-201-4011-b202-e1cf-31d2-65e2-f4e5.ngrok-free.app", description="Base URL for API endpoints")
    WEB_APP_URL: str = Field("http://localhost:3000", description="URL of the web application")
    CORS_ORIGINS: List[str] = Field(["*"], description="CORS allowed origins")
    
    # Slack settings
    SLACK_CLIENT_ID: str = Field("", description="Slack client ID")
    SLACK_CLIENT_SECRET: str = Field("", description="Slack client secret")
    SLACK_SIGNING_SECRET: str = Field("", description="Slack signing secret")
    
    # Bot scopes - used for application/bot level permissions
    SLACK_BOT_SCOPES: List[str] = Field(
        [
            "channels:read",
            "groups:read", 
            "im:read",
            "mpim:read",
            "chat:write",
            "chat:write.public"  # Add ability to post to channels without joining
        ], 
        description="Slack bot token scopes to request"
    )
    
    # User scopes - used for user level permissions (accessing channels the user can access)
    SLACK_USER_SCOPES: List[str] = Field(
        [
            "channels:history",
            "groups:history",
            "im:history", 
            "mpim:history",
            "users:read"
        ],
        description="Slack user token scopes to request"
    )
    
    # Legacy SLACK_SCOPES field for backward compatibility
    @property
    def SLACK_SCOPES(self) -> List[str]:
        """Legacy getter for combined scopes - maintained for compatibility"""
        return self.SLACK_BOT_SCOPES
    
    # Security settings
    TOKEN_EXPIRY_HOURS: int = 1
    SECRET_KEY: str = Field("", description="Secret key for JWT token generation")
    
    # Token encryption
    ENCRYPTION_KEY: Optional[str] = None
    
    # Qdrant settings
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 7750  # Special port for our Slack-dedicated Qdrant
    QDRANT_GRPC_PORT: int = 7751  # gRPC port
    QDRANT_PREFER_GRPC: bool = False
    QDRANT_TIMEOUT: float = 5.0  # Timeout in seconds
    
    # Indexing settings
    DEFAULT_HISTORY_DAYS: int = 30
    DEFAULT_UPDATE_FREQUENCY: int = 6  # Hours
    DEFAULT_EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"  # Sentence transformers model
    EMBEDDING_BATCH_SIZE: int = 50
    
    @validator("SECRET_KEY", pre=True)
    def validate_secret_key(cls, v):
        """Generate a random secret key if none is provided"""
        if not v:
            return secrets.token_hex(32)
        return v
    
    @validator("CORS_ORIGINS", pre=True)
    def parse_cors_origins(cls, v):
        """Parse CORS_ORIGINS from string if needed"""
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return [origin.strip() for origin in v.split(",")]
        return v
    
    @validator("SLACK_BOT_SCOPES", "SLACK_USER_SCOPES", pre=True)
    def parse_slack_scopes(cls, v):
        """Parse SLACK_SCOPES from string if needed"""
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return [scope.strip() for scope in v.split(",")]
        return v
    
    class Config:
        env_prefix = "MCP_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# Create global settings instance
settings = Settings()

def get_settings():
    """Get settings for dependency injection"""
    return settings

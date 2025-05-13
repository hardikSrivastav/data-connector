from pydantic import BaseSettings, Field, validator
import os
from typing import List, Optional


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
    API_BASE_URL: str = Field("https://4f5a-49-36-187-13.ngrok-free.app", description="Base URL for API endpoints")
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
    SECRET_KEY: str = Field("", description="Secret key for JWT token generation")
    TOKEN_EXPIRY_HOURS: int = Field(1, description="JWT token expiry in hours")
    
    @validator("SECRET_KEY", pre=True)
    def validate_secret_key(cls, v):
        """Generate a random secret key if none is provided"""
        if not v:
            import secrets
            return secrets.token_hex(32)
        return v
    
    class Config:
        env_prefix = "MCP_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# Create a global settings instance
settings = Settings()

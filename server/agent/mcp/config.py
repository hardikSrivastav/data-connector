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
    API_BASE_URL: str = Field("https://6aec-2405-201-4011-b202-3089-406f-2549-df4f.ngrok-free.app", description="Base URL for API endpoints")
    WEB_APP_URL: str = Field("http://localhost:3000", description="URL of the web application")
    CORS_ORIGINS: List[str] = Field(["*"], description="CORS allowed origins")
    
    # Slack settings
    SLACK_CLIENT_ID: str = Field("", description="Slack client ID")
    SLACK_CLIENT_SECRET: str = Field("", description="Slack client secret")
    SLACK_SIGNING_SECRET: str = Field("", description="Slack signing secret")
    SLACK_SCOPES: List[str] = Field(
        [
            "channels:read",
            "groups:read",
            "im:read",
            "mpim:read",
            "channels:history",
            "groups:history",
            "im:history",
            "mpim:history",
            "users:read",
            "chat:write"
        ], 
        description="Slack scopes to request"
    )
    
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

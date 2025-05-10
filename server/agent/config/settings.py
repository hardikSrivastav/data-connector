from pydantic import BaseSettings, validator
from typing import Optional
import os
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from .env file if present
load_dotenv()

class Settings(BaseSettings):
    # Database Settings
    DB_HOST: str
    DB_PORT: int = 5432
    DB_NAME: str
    DB_USER: str
    DB_PASS: str
    SSL_MODE: Optional[str] = None
    
    # Debug/Override Settings
    DB_DSN_OVERRIDE: Optional[str] = None
    
    # Authentication Settings (for future SSO integration)
    AUTH_ENABLED: bool = False
    AUTH_PROVIDER: Optional[str] = None  # "azure", "okta", "keycloak", etc.
    AUTH_CLIENT_ID: Optional[str] = None
    AUTH_CLIENT_SECRET: Optional[str] = None
    AUTH_ISSUER_URL: Optional[str] = None
    AUTH_AUDIENCE: Optional[str] = None
    
    # Network Security (for future VPN integration)
    ALLOWED_CIDR_BLOCKS: Optional[str] = None  # Comma-separated list of allowed IP ranges
    
    # LLM Configuration - Local
    MODEL_PATH: Optional[str] = None
    MODEL_TYPE: Optional[str] = None  # "llama2" or "gpt4all"
    DEVICE: Optional[str] = "cpu"  # "cpu" or "gpu"
    
    # LLM Configuration - Cloud
    LLM_API_URL: Optional[str] = None
    LLM_API_KEY: Optional[str] = None
    LLM_MODEL_NAME: Optional[str] = None
    
    # Anthropic Configuration
    ANTHROPIC_API_URL: Optional[str] = "https://api.anthropic.com"
    ANTHROPIC_API_KEY: Optional[str] = None
    ANTHROPIC_MODEL_NAME: Optional[str] = "claude-3-opus-20240229"
    
    # Agent Settings
    AGENT_PORT: int = 8080
    LOG_LEVEL: str = "info"  # "info", "debug", or "error"
    CACHE_PATH: Optional[str] = None
    WIPE_ON_EXIT: bool = False
    
    # Redis Cache Settings
    REDIS_HOST: Optional[str] = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: Optional[str] = None
    REDIS_DB: int = 0
    REDIS_ENABLED: bool = True  # Set to False to disable Redis and use file-based caching
    REDIS_TTL: int = 3600  # Default cache TTL in seconds (1 hour)
    
    # Analysis Settings
    MAX_ANALYSIS_STEPS: int = 10
    MAX_ROWS_DIRECT: int = 100000  # Max rows for direct query without sampling
    DEFAULT_SAMPLE_SIZE: int = 1000  # Default sample size for large datasets
    MAX_QUERY_TIMEOUT: int = 60  # Maximum query timeout in seconds
    
    # Application data directory
    APP_DATA_DIR: Optional[str] = None
    
    def get_app_dir(self) -> str:
        """
        Returns the directory where application data should be stored.
        
        If APP_DATA_DIR is set, uses that directory.
        Otherwise, creates a directory in the user's home directory.
        """
        if self.APP_DATA_DIR:
            app_dir = Path(self.APP_DATA_DIR)
        else:
            # Use a directory in the user's home folder
            app_dir = Path.home() / ".data-connector"
            
        # Ensure the directory exists
        app_dir.mkdir(parents=True, exist_ok=True)
        
        return str(app_dir)
    
    @property
    def db_dsn(self) -> str:
        """
        Constructs the PostgreSQL connection string from settings
        """ 
        base_dsn = f"postgresql://{self.DB_USER}:{self.DB_PASS}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        
        if self.SSL_MODE:
            return f"{base_dsn}?sslmode={self.SSL_MODE}"
        
        return base_dsn
    
    @validator("LLM_API_KEY")
    def validate_api_key_if_url_provided(cls, v, values):
        """Validate that API key is provided if API URL is set"""
        if values.get("LLM_API_URL") and not v:
            # Check if OPENAI_API_KEY is set in environment
            openai_key = os.environ.get("OPENAI_API_KEY")
            if openai_key:
                return openai_key
            raise ValueError("LLM_API_KEY must be provided when LLM_API_URL is set")
        return v
    
    @validator("MODEL_TYPE")
    def validate_model_type_if_path_provided(cls, v, values):
        """Validate that model type is provided if model path is set"""
        if values.get("MODEL_PATH") and not v:
            raise ValueError("MODEL_TYPE must be provided when MODEL_PATH is set")
        return v
    
    class Config:
        env_file = ".env"
        case_sensitive = True

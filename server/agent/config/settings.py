from pydantic import BaseSettings, validator
from typing import Optional
import os
from dotenv import load_dotenv

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
    
    # LLM Configuration - Local
    MODEL_PATH: Optional[str] = None
    MODEL_TYPE: Optional[str] = None  # "llama2" or "gpt4all"
    DEVICE: Optional[str] = "cpu"  # "cpu" or "gpu"
    
    # LLM Configuration - Cloud
    LLM_API_URL: Optional[str] = None
    LLM_API_KEY: Optional[str] = None
    LLM_MODEL_NAME: Optional[str] = None
    
    # Agent Settings
    AGENT_PORT: int = 8080
    LOG_LEVEL: str = "info"  # "info", "debug", or "error"
    CACHE_PATH: Optional[str] = None
    WIPE_ON_EXIT: bool = False
    
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

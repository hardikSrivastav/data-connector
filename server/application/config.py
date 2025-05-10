"""
Configuration utilities for the application.
"""
from functools import lru_cache
from pydantic import BaseSettings
import os
import sys

# Add the parent directory to sys.path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.config.settings import Settings

@lru_cache
def get_settings() -> Settings:
    """
    Get application settings, cached for efficiency.
    """
    return Settings() 
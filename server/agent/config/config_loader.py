"""
Configuration Loader

This module handles loading configuration from YAML files.
"""

import os
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import json

# Configure logging
logger = logging.getLogger(__name__)

# Default locations to look for config file
DEFAULT_CONFIG_LOCATIONS = [
    # User home directory
    os.path.expanduser("~/.data-connector/config.yaml"),
    # Current directory
    "./config.yaml",
    # Config directory
    "./config/config.yaml",
]

# Default locations to look for auth config file
DEFAULT_AUTH_CONFIG_LOCATIONS = [
    # User home directory
    os.path.expanduser("~/.data-connector/auth-config.yaml"),
    # Current directory
    "./auth-config.yaml",
    # Config directory
    "./config/auth-config.yaml",
]

# Default configuration
DEFAULT_CONFIG = {
    "db": {
        "type": "postgres",
        "uri": "postgresql://postgres:postgres@localhost:5432/postgres",
        "cache_dir": None
    },
    "llm": {
        "provider": "openai",
        "model": "gpt-4-turbo",
        "temperature": 0.1,
        "max_tokens": 2000,
        "api_key": None,
        "api_base": None
    },
    "logging": {
        "level": "info",
        "file": None
    },
    "output": {
        "format": "markdown",
        "max_rows": 50
    },
    "slack": {
        "mcp_url": "http://localhost:8500",
        "history_days": 30,
        "update_frequency": 6
    }
}

# Default auth configuration
DEFAULT_AUTH_CONFIG = {
    "sso": {
        "enabled": False,
        "default_protocol": "oidc",
        "oidc": {
            "provider": None,
            "client_id": None,
            "client_secret": None,
            "issuer": None,
            "discovery_url": None,
            "redirect_uri": None,
            "scopes": ["openid", "email", "profile"]
        }
    },
    "role_mappings": {}
}

def get_config_path() -> str:
    """Get the path to the configuration file"""
    # First check for environment variable
    if os.environ.get("DATA_CONNECTOR_CONFIG"):
        return os.environ["DATA_CONNECTOR_CONFIG"]
    
    # Next check in current directory
    if os.path.exists("config.yaml"):
        return "config.yaml"
    
    # Finally check in user home directory
    home_config = os.path.join(str(Path.home()), ".data-connector", "config.yaml")
    if os.path.exists(home_config):
        return home_config
    
    # Return the default path for writing the config
    config_dir = os.path.join(str(Path.home()), ".data-connector")
    os.makedirs(config_dir, exist_ok=True)
    return os.path.join(config_dir, "config.yaml")

def get_auth_config_path() -> str:
    """Get the path to the auth configuration file"""
    # First check for environment variable
    if os.environ.get("DATA_CONNECTOR_AUTH_CONFIG"):
        return os.environ["DATA_CONNECTOR_AUTH_CONFIG"]
    
    # Next check in current directory
    if os.path.exists("auth-config.yaml"):
        return "auth-config.yaml"
    
    # Finally check in user home directory
    home_config = os.path.join(str(Path.home()), ".data-connector", "auth-config.yaml")
    if os.path.exists(home_config):
        return home_config
    
    # Return the default path for writing the config
    config_dir = os.path.join(str(Path.home()), ".data-connector")
    os.makedirs(config_dir, exist_ok=True)
    return os.path.join(config_dir, "auth-config.yaml")

def load_config() -> Dict[str, Any]:
    """Load configuration from file"""
    config_path = get_config_path()
    
    if not os.path.exists(config_path):
        logger.warning(f"Config file not found at {config_path}, using defaults")
        return {}
    
    try:
        with open(config_path, 'r') as f:
            if config_path.endswith('.yaml'):
                config = yaml.safe_load(f) or {}
            elif config_path.endswith('.json'):
                config = json.load(f)
            else:
                logger.warning(f"Unknown config file format: {config_path}")
                config = {}
                
        return config
    except Exception as e:
        logger.error(f"Error loading config: {str(e)}")
        return {}

def load_auth_config() -> Dict[str, Any]:
    """Load authentication configuration from file"""
    auth_config_path = get_auth_config_path()
    
    if not os.path.exists(auth_config_path):
        logger.warning(f"Auth config file not found at {auth_config_path}, using defaults")
        return {}
    
    try:
        with open(auth_config_path, 'r') as f:
            if auth_config_path.endswith('.yaml'):
                auth_config = yaml.safe_load(f) or {}
            elif auth_config_path.endswith('.json'):
                auth_config = json.load(f)
            else:
                logger.warning(f"Unknown auth config file format: {auth_config_path}")
                auth_config = {}
                
        return auth_config
    except Exception as e:
        logger.error(f"Error loading auth config: {str(e)}")
        return {}

async def load_config_with_defaults() -> Dict[str, Any]:
    """Load configuration with default values"""
    user_config = load_config()
    
    # Deep merge with defaults
    merged_config = DEFAULT_CONFIG.copy()
    
    for key, value in user_config.items():
        if key in merged_config and isinstance(merged_config[key], dict) and isinstance(value, dict):
            # Merge this section
            merged_config[key].update(value)
        else:
            # Override this key
            merged_config[key] = value
    
    return merged_config

async def load_auth_config_with_defaults() -> Dict[str, Any]:
    """Load authentication configuration with default values"""
    user_auth_config = load_auth_config()
    
    # Deep merge with defaults
    merged_auth_config = DEFAULT_AUTH_CONFIG.copy()
    
    for key, value in user_auth_config.items():
        if key in merged_auth_config and isinstance(merged_auth_config[key], dict) and isinstance(value, dict):
            # Merge this section
            merged_auth_config[key].update(value)
        else:
            # Override this key
            merged_auth_config[key] = value
    
    return merged_auth_config

def get_database_uri(db_type: str) -> Optional[str]:
    """
    Get database URI for specified database type.
    
    Args:
        db_type: Database type (e.g., 'postgres', 'mongodb')
        
    Returns:
        URI string or None if not found
    """
    config = load_config()
    if db_type in config and 'uri' in config[db_type]:
        return config[db_type]['uri']
    return None

def get_default_database_type() -> str:
    """
    Get default database type from config.
    
    Returns:
        Default database type (falls back to 'postgres' if not specified)
    """
    config = load_config()
    return config.get('default_database', 'postgres')

def save_config(config: Dict[str, Any]) -> bool:
    """Save configuration to file"""
    config_path = get_config_path()
    
    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        
        with open(config_path, 'w') as f:
            if config_path.endswith('.yaml'):
                yaml.dump(config, f, default_flow_style=False)
            elif config_path.endswith('.json'):
                json.dump(config, f, indent=2)
            else:
                # Default to YAML
                yaml.dump(config, f, default_flow_style=False)
                
        logger.info(f"Config saved to {config_path}")
        return True
    except Exception as e:
        logger.error(f"Error saving config: {str(e)}")
        return False

def save_auth_config(auth_config: Dict[str, Any]) -> bool:
    """Save authentication configuration to file"""
    auth_config_path = get_auth_config_path()
    
    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(auth_config_path), exist_ok=True)
        
        with open(auth_config_path, 'w') as f:
            if auth_config_path.endswith('.yaml'):
                yaml.dump(auth_config, f, default_flow_style=False)
            elif auth_config_path.endswith('.json'):
                json.dump(auth_config, f, indent=2)
            else:
                # Default to YAML
                yaml.dump(auth_config, f, default_flow_style=False)
                
        logger.info(f"Auth config saved to {auth_config_path}")
        return True
    except Exception as e:
        logger.error(f"Error saving auth config: {str(e)}")
        return False 
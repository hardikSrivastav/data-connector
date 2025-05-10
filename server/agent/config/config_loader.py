"""
Configuration Loader

This module handles loading configuration from YAML files.
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional

# Default locations to look for config file
DEFAULT_CONFIG_LOCATIONS = [
    # User home directory
    os.path.expanduser("~/.data-connector/config.yaml"),
    # Current directory
    "./config.yaml",
    # Config directory
    "./config/config.yaml",
]

def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load configuration from YAML file.
    
    Args:
        config_path: Optional path to config file. If None, searches default locations.
        
    Returns:
        Dict containing configuration
    """
    # If config path specified, use it
    if config_path:
        return _load_from_path(config_path)
    
    # Otherwise try default locations
    for location in DEFAULT_CONFIG_LOCATIONS:
        if os.path.exists(location):
            return _load_from_path(location)
    
    # If no config file found, return empty dict
    return {}

def _load_from_path(path: str) -> Dict[str, Any]:
    """
    Load YAML config from specified path.
    
    Args:
        path: Path to YAML config file
        
    Returns:
        Dict containing configuration
    """
    try:
        with open(path, 'r') as f:
            config = yaml.safe_load(f)
            return config if config else {}
    except Exception as e:
        print(f"Error loading config from {path}: {e}")
        return {}

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

def save_config(config: Dict[str, Any], config_path: Optional[str] = None) -> bool:
    """
    Save configuration to YAML file.
    
    Args:
        config: Configuration dict to save
        config_path: Optional path to save to. If None, uses first default location.
        
    Returns:
        True if successful, False otherwise
    """
    # Determine where to save
    path = config_path or DEFAULT_CONFIG_LOCATIONS[0]
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(path), exist_ok=True)
    
    try:
        with open(path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
        
        # Set appropriate permissions (owner read/write only)
        os.chmod(path, 0o600)
        return True
    except Exception as e:
        print(f"Error saving config to {path}: {e}")
        return False 
"""
Query Plan Module

Implements structured classes for cross-database query plans with DAG support.
This module dynamically discovers database types from config.yaml.
"""

import os
import yaml
import logging
from pathlib import Path
from typing import Dict, List, Set

# Configure logging
logger = logging.getLogger(__name__)

# Dictionary to store operation types
OPERATION_REGISTRY: Dict[str, type] = {}

def register_operation(db_type: str):
    """Decorator to register operation types by database type"""
    def decorator(cls):
        OPERATION_REGISTRY[db_type] = cls
        logger.info(f"Registered operation class for database type: {db_type}")
        return cls
    return decorator

def load_config() -> Dict:
    """
    Load configuration from config.yaml
    
    Returns:
        Dictionary with configuration values
    """
    config_path = os.environ.get("DATA_CONNECTOR_CONFIG", 
                                str(Path.home() / ".data-connector" / "config.yaml"))
    
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        logger.info(f"Loaded configuration from {config_path}")
        return config
    except Exception as e:
        logger.warning(f"Failed to load config.yaml: {e}")
        # Return default minimal config
        return {
            "default_database": "postgres",
            "postgres": {"uri": "postgresql://localhost:5432/postgres"}
        }

def get_supported_db_types() -> List[str]:
    """
    Get list of supported database types from config
    
    Returns:
        List of database type strings
    """
    config = load_config()
    
    # Get all database types from config.yaml
    db_types = [k for k in config.keys() if k not in 
               ['default_database', 'vector_db', 'additional_settings']]
    
    logger.info(f"Discovered database types from config: {db_types}")
    return db_types

# Import base module first to avoid circular references
from .base import Operation, QueryPlan

# Import other modules
from .operations import initialize_operations

# Get supported database types
SUPPORTED_DB_TYPES = get_supported_db_types()
initialize_operations(SUPPORTED_DB_TYPES)

# Now we can import the rest of the modules
from .dag import OperationDAG
from .factory import create_operation, create_empty_plan
from .serialization import serialize_plan, deserialize_plan, serialize_plan_to_json, deserialize_plan_from_json

__all__ = [
    'Operation', 
    'QueryPlan',
    'OperationDAG',
    'create_operation',
    'create_empty_plan',
    'serialize_plan',
    'deserialize_plan',
    'serialize_plan_to_json',
    'deserialize_plan_from_json',
    'OPERATION_REGISTRY',
    'SUPPORTED_DB_TYPES',
] 
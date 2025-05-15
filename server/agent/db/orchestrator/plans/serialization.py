"""
Serialization and deserialization for query plans.

This module provides functions for:
1. Converting plans to/from JSON
2. Saving plans to disk
3. Loading plans from disk
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
import datetime

# Configure logging
logger = logging.getLogger(__name__)

class DateTimeEncoder(json.JSONEncoder):
    """JSON encoder that handles datetime objects"""
    
    def default(self, obj):
        if isinstance(obj, (datetime.datetime, datetime.date)):
            return obj.isoformat()
        return super().default(obj)

def serialize_plan(plan) -> Dict[str, Any]:
    """
    Serialize a query plan to a dictionary
    
    Args:
        plan: QueryPlan instance
        
    Returns:
        Dictionary representation of the plan
    """
    return plan.to_dict()

def serialize_plan_to_json(plan, pretty: bool = True) -> str:
    """
    Serialize a query plan to a JSON string
    
    Args:
        plan: QueryPlan instance
        pretty: Whether to format the JSON with indentation
        
    Returns:
        JSON string representation of the plan
    """
    plan_dict = serialize_plan(plan)
    
    if pretty:
        return json.dumps(plan_dict, indent=2, cls=DateTimeEncoder)
    else:
        return json.dumps(plan_dict, cls=DateTimeEncoder)

def deserialize_plan(plan_dict: Dict[str, Any]):
    """
    Deserialize a dictionary to a query plan
    
    Args:
        plan_dict: Dictionary representation of a plan
        
    Returns:
        QueryPlan instance
    """
    from .factory import create_plan_from_dict
    return create_plan_from_dict(plan_dict)

def deserialize_plan_from_json(json_str: str):
    """
    Deserialize a JSON string to a query plan
    
    Args:
        json_str: JSON string representation of a plan
        
    Returns:
        QueryPlan instance
    """
    try:
        plan_dict = json.loads(json_str)
        return deserialize_plan(plan_dict)
    except json.JSONDecodeError as e:
        logger.error(f"Error deserializing plan from JSON: {e}")
        return None

def save_plan_to_file(plan, file_path: str) -> bool:
    """
    Save a query plan to a file
    
    Args:
        plan: QueryPlan instance
        file_path: Path to save the plan to
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        
        # Serialize plan to JSON
        json_str = serialize_plan_to_json(plan)
        
        # Write to file
        with open(file_path, 'w') as f:
            f.write(json_str)
            
        logger.info(f"Saved plan to {file_path}")
        return True
    except Exception as e:
        logger.error(f"Error saving plan to {file_path}: {e}")
        return False

def load_plan_from_file(file_path: str):
    """
    Load a query plan from a file
    
    Args:
        file_path: Path to load the plan from
        
    Returns:
        QueryPlan instance or None if loading failed
    """
    try:
        # Read from file
        with open(file_path, 'r') as f:
            json_str = f.read()
            
        # Deserialize plan from JSON
        plan = deserialize_plan_from_json(json_str)
        
        logger.info(f"Loaded plan from {file_path}")
        return plan
    except Exception as e:
        logger.error(f"Error loading plan from {file_path}: {e}")
        return None 
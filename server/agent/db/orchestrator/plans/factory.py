"""
Factory functions for creating operations and query plans.

This module provides functions for:
1. Creating operations based on database type
2. Creating empty query plans
3. Building complete plans from JSON or dict representations
"""

import logging
from typing import Dict, List, Any, Optional, Union
import uuid

# Configure logging
logger = logging.getLogger(__name__)

# Import registry and classes
from . import OPERATION_REGISTRY
from .base import Operation, QueryPlan
from .operations import GenericOperation

def create_operation(
    db_type: str,
    source_id: str,
    params: Dict[str, Any] = None,
    id: str = None,
    depends_on: List[str] = None,
    metadata: Dict[str, Any] = None
) -> Operation:
    """
    Create an operation for a specific database type
    
    Args:
        db_type: Database type (postgres, mongodb, etc.)
        source_id: Data source ID
        params: Operation parameters
        id: Optional operation ID (generated if not provided)
        depends_on: Optional list of dependencies
        metadata: Optional metadata
        
    Returns:
        Operation instance
    """
    params = params or {}
    id = id or str(uuid.uuid4())
    depends_on = depends_on or []
    metadata = metadata or {}
    
    # Get the operation class for this database type
    if db_type in OPERATION_REGISTRY:
        operation_class = OPERATION_REGISTRY[db_type]
        
        try:
            # Create the operation
            # Handle specific parameter names based on db_type
            if db_type == "postgres":
                # SQL operation parameters
                if "query" in params:
                    return operation_class(
                        id=id,
                        source_id=source_id,
                        sql_query=params["query"],
                        params=params.get("params", []),
                        depends_on=depends_on,
                        metadata=metadata
                    )
            elif db_type == "mongodb":
                # MongoDB operation parameters
                return operation_class(
                    id=id,
                    source_id=source_id,
                    collection=params.get("collection"),
                    pipeline=params.get("pipeline", []),
                    query=params.get("query", {}),
                    projection=params.get("projection", {}),
                    depends_on=depends_on,
                    metadata=metadata
                )
            elif db_type == "qdrant":
                # Qdrant operation parameters
                return operation_class(
                    id=id,
                    source_id=source_id,
                    collection=params.get("collection"),
                    vector_query=params.get("vector", []),
                    filter=params.get("filter", {}),
                    top_k=params.get("limit", 10),
                    depends_on=depends_on,
                    metadata=metadata
                )
            elif db_type == "slack":
                # Slack operation parameters
                return operation_class(
                    id=id,
                    source_id=source_id,
                    channel=params.get("channel"),
                    query=params.get("query"),
                    time_range=params.get("time_range", {}),
                    limit=params.get("limit", 100),
                    depends_on=depends_on,
                    metadata=metadata
                )
            elif db_type == "shopify":
                # Shopify operation parameters
                return operation_class(
                    id=id,
                    source_id=source_id,
                    endpoint=params.get("endpoint", "orders"),
                    query_params=params.get("query_params", {}),
                    api_method=params.get("method", "GET"),
                    limit=params.get("limit", 100),
                    depends_on=depends_on,
                    metadata=metadata
                )
            
            # For other registered database types, use default approach
            return operation_class(
                id=id,
                source_id=source_id,
                depends_on=depends_on,
                metadata=metadata,
                **params
            )
            
        except Exception as e:
            logger.error(f"Error creating operation for {db_type}: {e}")
    
    # Default to generic operation if no specific class found
    logger.warning(f"No operation class found for {db_type}, using GenericOperation")
    return GenericOperation(
        id=id,
        source_id=source_id,
        params=params,
        depends_on=depends_on,
        metadata=metadata
    )

def create_empty_plan(metadata: Dict[str, Any] = None) -> QueryPlan:
    """
    Create an empty query plan
    
    Args:
        metadata: Optional metadata
        
    Returns:
        Empty QueryPlan instance
    """
    return QueryPlan(operations=[], metadata=metadata)

def create_plan_from_dict(plan_dict: Dict[str, Any]) -> QueryPlan:
    """
    Create a query plan from a dictionary representation
    
    Args:
        plan_dict: Dictionary representation of a query plan
        
    Returns:
        QueryPlan instance
    """
    # Import registry_client with proper path
    from ...registry.integrations import registry_client
    
    # Create an empty plan
    plan = create_empty_plan(metadata=plan_dict.get("metadata", {}))
    
    # Set the plan ID if provided
    if "id" in plan_dict:
        plan.id = plan_dict["id"]
    
    # Add operations
    for op_dict in plan_dict.get("operations", []):
        # Get operation details
        op_id = op_dict.get("id")
        source_id = op_dict.get("source_id")
        depends_on = op_dict.get("depends_on", [])
        metadata = op_dict.get("metadata", {})
        
        # Get database type from source_id using registry client
        try:
            source_info = registry_client.get_data_source(source_id)
            db_type = source_info.get("type")
        except Exception as e:
            logger.warning(f"Error getting source info for {source_id}: {e}")
            db_type = None
        
        # If db_type wasn't available from registry, try to get it from the operation type
        if not db_type and "type" in op_dict:
            # Try to infer db_type from operation type
            op_type = op_dict.get("type", "")
            if "Sql" in op_type:
                db_type = "postgres"
            elif "Mongo" in op_type:
                db_type = "mongodb"
            elif "Qdrant" in op_type:
                db_type = "qdrant"
            elif "Slack" in op_type:
                db_type = "slack"
            elif "Shopify" in op_type:
                db_type = "shopify"
        
        # Get params based on the operation type
        params = {}
        if db_type == "postgres":
            params = {
                "query": op_dict.get("sql_query", ""),
                "params": op_dict.get("params", [])
            }
        elif db_type == "mongodb":
            params = {
                "collection": op_dict.get("collection", ""),
                "pipeline": op_dict.get("pipeline", []),
                "query": op_dict.get("query", {}),
                "projection": op_dict.get("projection", {})
            }
        elif db_type == "qdrant":
            params = {
                "collection": op_dict.get("collection", ""),
                "vector": op_dict.get("vector_query", []),
                "filter": op_dict.get("filter", {}),
                "limit": op_dict.get("top_k", 10)
            }
        elif db_type == "slack":
            params = {
                "channel": op_dict.get("channel", ""),
                "query": op_dict.get("query", ""),
                "time_range": op_dict.get("time_range", {}),
                "limit": op_dict.get("limit", 100)
            }
        elif db_type == "shopify":
            params = {
                "endpoint": op_dict.get("endpoint", "orders"),
                "query_params": op_dict.get("query_params", {}),
                "method": op_dict.get("api_method", "GET"),
                "limit": op_dict.get("limit", 100)
            }
        else:
            # For other types, use all available parameters
            params = {k: v for k, v in op_dict.items() 
                     if k not in ["id", "source_id", "depends_on", "metadata", "type"]}
        
        # Create the operation
        if db_type and source_id:
            operation = create_operation(
                db_type=db_type,
                source_id=source_id,
                params=params,
                id=op_id,
                depends_on=depends_on,
                metadata=metadata
            )
            
            # Add result and status if available
            if "result" in op_dict:
                operation.result = op_dict["result"]
            if "error" in op_dict:
                operation.error = op_dict["error"]
            if "execution_time" in op_dict:
                operation.execution_time = op_dict["execution_time"]
            if "status" in op_dict:
                operation.status = op_dict["status"]
            
            # Add the operation to the plan
            plan.add_operation(operation)
    
    return plan 
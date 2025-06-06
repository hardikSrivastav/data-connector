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

# Set up dedicated logging for cross-database execution
def setup_cross_db_logger():
    """Set up a dedicated logger for cross-database execution with file output"""
    cross_db_logger = logging.getLogger('cross_db_execution')
    cross_db_logger.setLevel(logging.INFO)
    
    # Remove any existing handlers to avoid duplicates
    cross_db_logger.handlers.clear()
    
    # Create file handler for cross-database logs
    file_handler = logging.FileHandler('cross_db_execution.log', mode='a')  # Append mode
    file_handler.setLevel(logging.INFO)
    
    # Create console handler as well
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # Add handlers to logger
    cross_db_logger.addHandler(file_handler)
    cross_db_logger.addHandler(console_handler)
    
    # Prevent propagation to root logger to avoid SQLAlchemy noise
    cross_db_logger.propagate = False
    
    return cross_db_logger

# Get or create the dedicated logger
cross_db_logger = setup_cross_db_logger()

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
    
    cross_db_logger.info(f"🔨 Creating operation: db_type={db_type}, source_id={source_id}, id={id}")
    cross_db_logger.info(f"🔨 Operation params: {params}")
    cross_db_logger.info(f"🔨 Available operation types in registry: {list(OPERATION_REGISTRY.keys())}")
    
    # Get the operation class for this database type
    if db_type in OPERATION_REGISTRY:
        operation_class = OPERATION_REGISTRY[db_type]
        cross_db_logger.info(f"🔨 Found operation class for {db_type}: {operation_class}")
        
        try:
            # Create the operation
            # Handle specific parameter names based on db_type
            if db_type == "postgres":
                # SQL operation parameters
                if "query" in params:
                    cross_db_logger.info(f"🔨 Creating PostgreSQL operation with query: {params['query'][:100]}...")
                    return operation_class(
                        id=id,
                        source_id=source_id,
                        sql_query=params["query"],
                        params=params.get("params", []),
                        depends_on=depends_on,
                        metadata=metadata
                    )
                else:
                    cross_db_logger.warning(f"🔨 PostgreSQL operation missing 'query' parameter. Available: {list(params.keys())}")
            elif db_type == "mongodb":
                # MongoDB operation parameters
                cross_db_logger.info(f"🔨 Creating MongoDB operation with collection: {params.get('collection')}")
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
                cross_db_logger.info(f"🔨 Creating Qdrant operation with collection: {params.get('collection')}, vector: {params.get('vector', [])[:3]}...")
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
                cross_db_logger.info(f"🔨 Creating Slack operation with channel: {params.get('channels')}")
                return operation_class(
                    id=id,
                    source_id=source_id,
                    channel=params.get("channel") or (params.get("channels", [None])[0] if params.get("channels") else None),
                    query=params.get("query", ""),
                    time_range=params.get("time_range", {}),
                    limit=params.get("limit", 100),
                    depends_on=depends_on,
                    metadata=metadata
                )
            elif db_type == "shopify":
                # Shopify operation parameters
                cross_db_logger.info(f"🔨 Creating Shopify operation with endpoint: {params.get('endpoint')}")
                return operation_class(
                    id=id,
                    source_id=source_id,
                    endpoint=params.get("endpoint", "products"),
                    query_params=params.get("query_params", {}),
                    api_method=params.get("api_method", "GET"),
                    limit=params.get("limit", 100),
                    depends_on=depends_on,
                    metadata=metadata
                )
        except Exception as e:
            cross_db_logger.error(f"🔨 Error creating {db_type} operation: {str(e)}")
            cross_db_logger.error(f"🔨 Exception type: {type(e)}")
            import traceback
            cross_db_logger.error(f"🔨 Traceback: {traceback.format_exc()}")
    else:
        cross_db_logger.warning(f"🔨 Database type {db_type} not found in registry")
    
    # Fallback to generic operation
    cross_db_logger.warning(f"🔨 Falling back to GenericOperation for {db_type}")
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
        
        # Get database type in order of preference:
        # 1. From the operation dict directly (LLM should include this)
        # 2. From source_id using registry client  
        # 3. From the operation type field as fallback
        db_type = op_dict.get("db_type")
        
        if not db_type:
            # Try to get database type from source_id using registry client
            try:
                source_info = registry_client.get_data_source(source_id)
                db_type = source_info.get("type") if source_info else None
            except Exception as e:
                logger.warning(f"Error getting source info for {source_id}: {e}")
                db_type = None
        
        # If db_type still not available, try to infer from the operation type
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
            # Look for params inside the "params" object, not at top level
            operation_params = op_dict.get("params", {})
            params = {
                "query": operation_params.get("query", op_dict.get("sql_query", "")),
                "params": operation_params.get("params", op_dict.get("params", []))
            }
        elif db_type == "mongodb":
            # Look for params inside the "params" object first, then fall back to top level
            operation_params = op_dict.get("params", {})
            params = {
                "collection": operation_params.get("collection", op_dict.get("collection", "")),
                "pipeline": operation_params.get("pipeline", op_dict.get("pipeline", [])),
                "query": operation_params.get("query", op_dict.get("query", {})),
                "projection": operation_params.get("projection", op_dict.get("projection", {}))
            }
        elif db_type == "qdrant":
            # Look for params inside the "params" object first, then fall back to top level
            operation_params = op_dict.get("params", {})
            params = {
                "collection": operation_params.get("collection", op_dict.get("collection", "")),
                "vector": operation_params.get("vector", op_dict.get("vector_query", [])),
                "filter": operation_params.get("filter", op_dict.get("filter", {})),
                "limit": operation_params.get("limit", op_dict.get("top_k", 10))
            }
        elif db_type == "slack":
            # Look for params inside the "params" object first, then fall back to top level
            operation_params = op_dict.get("params", {})
            params = {
                "channel": operation_params.get("channel", op_dict.get("channel", "")),
                "query": operation_params.get("query", op_dict.get("query", "")),
                "time_range": operation_params.get("time_range", op_dict.get("time_range", {})),
                "limit": operation_params.get("limit", op_dict.get("limit", 100))
            }
        elif db_type == "shopify":
            # Look for params inside the "params" object first, then fall back to top level
            operation_params = op_dict.get("params", {})
            params = {
                "endpoint": operation_params.get("endpoint", op_dict.get("endpoint", "orders")),
                "query_params": operation_params.get("query_params", op_dict.get("query_params", {})),
                "method": operation_params.get("method", op_dict.get("api_method", "GET")),
                "limit": operation_params.get("limit", op_dict.get("limit", 100))
            }
        else:
            # For other types, use params object if available, otherwise use all top-level parameters
            operation_params = op_dict.get("params", {})
            if operation_params:
                params = operation_params
            else:
                params = {k: v for k, v in op_dict.items() 
                         if k not in ["id", "source_id", "depends_on", "metadata", "type", "db_type"]}
        
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
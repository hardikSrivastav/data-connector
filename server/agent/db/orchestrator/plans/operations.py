"""
Specific operation classes for different database types.

This module defines the concrete operation classes for each database type
and handles dynamic registration based on config.yaml.
"""

import logging
from typing import Dict, List, Any, Optional, Set
from .base import Operation

# Configure logging
logger = logging.getLogger(__name__)

# Import the register_operation decorator
from . import register_operation, OPERATION_REGISTRY

class GenericOperation(Operation):
    """
    Generic operation for any database type
    
    This is a fallback for database types that don't have a specific implementation.
    """
    
    def __init__(
        self, 
        id: str = None, 
        source_id: str = None, 
        params: Dict[str, Any] = None,
        depends_on: List[str] = None,
        metadata: Dict[str, Any] = None
    ):
        """
        Initialize a generic operation
        
        Args:
            id: Unique identifier for this operation
            source_id: ID of the data source this operation targets
            params: Parameters for the database adapter
            depends_on: List of operation IDs this operation depends on
            metadata: Additional metadata for this operation
        """
        super().__init__(id, source_id, depends_on, metadata)
        self.params = params or {}
    
    def get_adapter_params(self) -> Dict[str, Any]:
        """Get parameters for the database adapter"""
        return self.params

    @property
    def operation_id(self):
        """Alias for id to match the implementation agent"""
        return self.id
    
    @property
    def operation_type(self):
        """Return operation type from metadata"""
        return self.metadata.get("operation_type", "unknown")
    
    @property
    def parameters(self):
        """Return params as parameters for the implementation agent"""
        return self.params


@register_operation("postgres")
class SqlOperation(Operation):
    """Operation for SQL databases (PostgreSQL)"""
    
    def __init__(
        self, 
        id: str = None, 
        source_id: str = None, 
        sql_query: str = None,
        params: List[Any] = None,
        depends_on: List[str] = None,
        metadata: Dict[str, Any] = None
    ):
        """
        Initialize an SQL operation
        
        Args:
            id: Unique identifier for this operation
            source_id: ID of the data source this operation targets
            sql_query: SQL query string
            params: Query parameters for prepared statements
            depends_on: List of operation IDs this operation depends on
            metadata: Additional metadata for this operation
        """
        super().__init__(id, source_id, depends_on, metadata)
        self.sql_query = sql_query or ""
        self.params = params or []
    
    def get_adapter_params(self) -> Dict[str, Any]:
        """Get parameters for the database adapter"""
        return {
            "query": self.sql_query,
            "params": self.params
        }
    
    def validate(self, schema_registry=None) -> bool:
        """
        Validate this SQL operation
        
        Args:
            schema_registry: Schema registry client
            
        Returns:
            True if valid, False otherwise
        """
        # Call parent validation first
        if not super().validate(schema_registry):
            return False
        
        # Check if we have an SQL query
        if not self.sql_query:
            logger.error(f"SQL operation {self.id} missing sql_query")
            return False
        
        # Additional validation with schema registry if available
        if schema_registry:
            try:
                # Check if tables in query exist in schema
                return schema_registry.validate_sql_query(self.source_id, self.sql_query)
            except Exception as e:
                logger.warning(f"Error validating SQL query: {e}")
        
        return True


@register_operation("mongodb")
class MongoOperation(Operation):
    """Operation for MongoDB databases"""
    
    def __init__(
        self, 
        id: str = None, 
        source_id: str = None, 
        collection: str = None,
        pipeline: List[Dict[str, Any]] = None,
        query: Dict[str, Any] = None,
        projection: Dict[str, Any] = None,
        depends_on: List[str] = None,
        metadata: Dict[str, Any] = None
    ):
        """
        Initialize a MongoDB operation
        
        Args:
            id: Unique identifier for this operation
            source_id: ID of the data source this operation targets
            collection: MongoDB collection name
            pipeline: Aggregation pipeline
            query: Query filter
            projection: Field projection
            depends_on: List of operation IDs this operation depends on
            metadata: Additional metadata for this operation
        """
        super().__init__(id, source_id, depends_on, metadata)
        self.collection = collection
        self.pipeline = pipeline or []
        self.query = query or {}
        self.projection = projection or {}
    
    def get_adapter_params(self) -> Dict[str, Any]:
        """Get parameters for the database adapter"""
        return {
            "collection": self.collection,
            "pipeline": self.pipeline,
            "query": self.query,
            "projection": self.projection
        }
    
    def validate(self, schema_registry=None) -> bool:
        """
        Validate this MongoDB operation
        
        Args:
            schema_registry: Schema registry client
            
        Returns:
            True if valid, False otherwise
        """
        # Call parent validation first
        if not super().validate(schema_registry):
            return False
        
        # Check if we have a collection
        if not self.collection:
            logger.error(f"MongoDB operation {self.id} missing collection")
            return False
        
        # Additional validation with schema registry if available
        if schema_registry:
            try:
                # Check if collection exists in schema
                return schema_registry.validate_mongo_collection(self.source_id, self.collection)
            except Exception as e:
                logger.warning(f"Error validating MongoDB collection: {e}")
        
        return True


@register_operation("qdrant")
class QdrantOperation(Operation):
    """Operation for Qdrant vector database"""
    
    def __init__(
        self, 
        id: str = None, 
        source_id: str = None, 
        collection: str = None,
        vector_query: List[float] = None,
        filter: Dict[str, Any] = None,
        top_k: int = 10,
        depends_on: List[str] = None,
        metadata: Dict[str, Any] = None
    ):
        """
        Initialize a Qdrant operation
        
        Args:
            id: Unique identifier for this operation
            source_id: ID of the data source this operation targets
            collection: Qdrant collection name
            vector_query: Vector embedding for similarity search
            filter: Filter conditions
            top_k: Number of results to return
            depends_on: List of operation IDs this operation depends on
            metadata: Additional metadata for this operation
        """
        super().__init__(id, source_id, depends_on, metadata)
        self.collection = collection
        self.vector_query = vector_query or []
        self.filter = filter or {}
        self.top_k = top_k
    
    def get_adapter_params(self) -> Dict[str, Any]:
        """Get parameters for the database adapter"""
        return {
            "collection": self.collection,
            "vector": self.vector_query,
            "filter": self.filter,
            "limit": self.top_k
        }
    
    def validate(self, schema_registry=None) -> bool:
        """
        Validate this Qdrant operation
        
        Args:
            schema_registry: Schema registry client
            
        Returns:
            True if valid, False otherwise
        """
        # Call parent validation first
        if not super().validate(schema_registry):
            return False
        
        # Check if we have a collection
        if not self.collection:
            logger.error(f"Qdrant operation {self.id} missing collection")
            return False
        
        # Check if we have a vector query
        if not self.vector_query:
            logger.error(f"Qdrant operation {self.id} missing vector_query. Found: {self.vector_query}")
            # Print params for debugging
            logger.error(f"Qdrant operation params: collection={self.collection}, filter={self.filter}, top_k={self.top_k}")
            return False
        
        # Validate vector query format
        if not isinstance(self.vector_query, list):
            logger.error(f"Qdrant operation {self.id} vector_query must be a list, got {type(self.vector_query)}")
            return False
        
        # Additional validation with schema registry if available
        if schema_registry:
            try:
                # Check if collection exists in schema
                valid = schema_registry.validate_qdrant_collection(self.source_id, self.collection)
                if not valid:
                    logger.error(f"Collection {self.collection} not found in schema for source {self.source_id}")
                    return False
                return valid
            except Exception as e:
                logger.warning(f"Error validating Qdrant collection: {e}")
        
        return True


@register_operation("slack")
class SlackOperation(Operation):
    """Operation for Slack data source"""
    
    def __init__(
        self, 
        id: str = None, 
        source_id: str = None, 
        channel: str = None,
        query: str = None,
        time_range: Dict[str, Any] = None,
        limit: int = 100,
        depends_on: List[str] = None,
        metadata: Dict[str, Any] = None
    ):
        """
        Initialize a Slack operation
        
        Args:
            id: Unique identifier for this operation
            source_id: ID of the data source this operation targets
            channel: Slack channel ID or name
            query: Search query
            time_range: Time range filter (start/end timestamps)
            limit: Maximum number of messages to return
            depends_on: List of operation IDs this operation depends on
            metadata: Additional metadata for this operation
        """
        super().__init__(id, source_id, depends_on, metadata)
        self.channel = channel
        self.query = query or ""
        self.time_range = time_range or {}
        self.limit = limit
    
    def get_adapter_params(self) -> Dict[str, Any]:
        """Get parameters for the database adapter"""
        return {
            "channel": self.channel,
            "query": self.query,
            "time_range": self.time_range,
            "limit": self.limit
        }
    
    def validate(self, schema_registry=None) -> bool:
        """
        Validate this Slack operation
        
        Args:
            schema_registry: Schema registry client
            
        Returns:
            True if valid, False otherwise
        """
        # Call parent validation first
        if not super().validate(schema_registry):
            return False
        
        # Simple validation - we need either a channel or a query
        if not self.channel and not self.query:
            logger.error(f"Slack operation {self.id} missing both channel and query")
            return False
        
        return True


@register_operation("shopify")
class ShopifyOperation(Operation):
    """Operation for Shopify e-commerce data source"""
    
    def __init__(
        self, 
        id: str = None, 
        source_id: str = None, 
        endpoint: str = None,
        query_params: Dict[str, Any] = None,
        api_method: str = "GET",
        limit: int = 100,
        depends_on: List[str] = None,
        metadata: Dict[str, Any] = None
    ):
        """
        Initialize a Shopify operation
        
        Args:
            id: Unique identifier for this operation
            source_id: ID of the data source this operation targets
            endpoint: Shopify API endpoint (e.g., 'orders', 'products', 'customers')
            query_params: Query parameters for the API request
            api_method: HTTP method (GET, POST, etc.)
            limit: Maximum number of records to return
            depends_on: List of operation IDs this operation depends on
            metadata: Additional metadata for this operation
        """
        super().__init__(id, source_id, depends_on, metadata)
        self.endpoint = endpoint or "orders"
        self.query_params = query_params or {}
        self.api_method = api_method
        self.limit = limit
    
    def get_adapter_params(self) -> Dict[str, Any]:
        """Get parameters for the database adapter"""
        return {
            "endpoint": self.endpoint,
            "params": self.query_params,
            "method": self.api_method,
            "limit": self.limit
        }
    
    def validate(self, schema_registry=None) -> bool:
        """
        Validate this Shopify operation
        
        Args:
            schema_registry: Schema registry client
            
        Returns:
            True if valid, False otherwise
        """
        # Call parent validation first
        if not super().validate(schema_registry):
            return False
        
        # Check if we have a valid endpoint
        valid_endpoints = [
            "orders", "products", "customers", "inventory_levels", 
            "checkouts", "variants", "collections", "locations",
            "fulfillments", "transactions", "discounts", "price_rules"
        ]
        
        if self.endpoint not in valid_endpoints:
            logger.warning(f"Shopify operation {self.id} has potentially invalid endpoint: {self.endpoint}")
            # Don't fail validation for unknown endpoints as Shopify API may have new ones
        
        return True


def initialize_operations(db_types: List[str]) -> None:
    """
    Initialize operation classes for all database types
    
    This function ensures that we have an operation class for each database type
    in the configuration, creating dynamic classes if needed.
    
    Args:
        db_types: List of database types from configuration
    """
    for db_type in db_types:
        # Skip if we already have a registered operation for this db_type
        if db_type in OPERATION_REGISTRY:
            continue
        
        # Create dynamic operation class for this database type
        logger.info(f"Creating dynamic operation class for database type: {db_type}")
        
        # Use class factory pattern to create a new class
        cls_name = f"{db_type.capitalize()}Operation"
        
        # Define the new class dynamically
        @register_operation(db_type)
        class DynamicOperation(Operation):
            def __init__(
                self, 
                id: str = None, 
                source_id: str = None, 
                query: Any = None,
                params: Dict[str, Any] = None,
                depends_on: List[str] = None,
                metadata: Dict[str, Any] = None
            ):
                super().__init__(id, source_id, depends_on, metadata)
                self.query = query
                self.params = params or {}
            
            def get_adapter_params(self) -> Dict[str, Any]:
                return {
                    "query": self.query,
                    **self.params
                }
        
        # Rename the class for better debugging
        DynamicOperation.__name__ = cls_name
        
        logger.info(f"Registered dynamic operation class: {cls_name}")
    
    logger.info(f"Initialized operations for all database types: {list(OPERATION_REGISTRY.keys())}") 
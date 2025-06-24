"""
Database adapters module.
Provides a common interface for different types of databases.
"""

import logging
from typing import Dict, Type, Any

from .base import DBAdapter
from .postgres import PostgresAdapter
from .mongo import MongoAdapter
from .qdrant import QdrantAdapter, EmbeddingProvider
from .slack import SlackAdapter
from .shopify import ShopifyAdapter
from .ga4 import GA4Adapter

# Configure logging
logger = logging.getLogger(__name__)

# Registry of database adapters
ADAPTER_REGISTRY: Dict[str, Type[DBAdapter]] = {
    "postgres": PostgresAdapter,
    "postgresql": PostgresAdapter,
    "mongodb": MongoAdapter,
    "mongo": MongoAdapter,
    "qdrant": QdrantAdapter,
    "slack": SlackAdapter,
    "shopify": ShopifyAdapter,
    "ga4": GA4Adapter,
}

def get_adapter(source_type: str, connection_info: Any) -> DBAdapter:
    """
    Get the appropriate adapter based on the source type.
    
    Args:
        source_type: Type of data source (postgres, mongodb, qdrant, slack, etc.)
        connection_info: Connection information for the data source
        
    Returns:
        Instance of the appropriate adapter
        
    Raises:
        ValueError: If the source type is not supported
    """
    source_type_lower = source_type.lower()
    
    if source_type_lower not in ADAPTER_REGISTRY:
        raise ValueError(f"Unsupported data source type: {source_type}. Supported types: {list(ADAPTER_REGISTRY.keys())}")
    
    adapter_class = ADAPTER_REGISTRY[source_type_lower]
    
    # Handle special cases for different connection info formats
    if source_type_lower in ("mongodb", "mongo"):
        # MongoDB adapter expects URI as string, not dict
        if isinstance(connection_info, dict):
            uri = connection_info.get("uri", "")
            if not uri:
                raise ValueError("MongoDB connection info missing URI")
            return adapter_class(uri)
        else:
            # connection_info is already a URI string
            return adapter_class(connection_info)
    else:
        # For other adapters, pass connection_info directly
        return adapter_class(connection_info)

__all__ = ['DBAdapter', 'PostgresAdapter', 'MongoAdapter', 'QdrantAdapter', 'EmbeddingProvider', 'SlackAdapter', 'ShopifyAdapter', 'GA4Adapter', 'get_adapter', 'ADAPTER_REGISTRY'] 
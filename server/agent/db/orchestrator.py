"""
Database Orchestrator

Routes natural language queries to the appropriate database adapter
based on the connection URI scheme, and provides a unified interface
for all database operations.
"""

import logging
from typing import Any, Dict, List, Optional, Type
from urllib.parse import urlparse

from .adapters.base import DBAdapter
from .adapters.postgres import PostgresAdapter
from .adapters.mongo import MongoAdapter
from .adapters.qdrant import QdrantAdapter

# Configure logging
logger = logging.getLogger(__name__)

# Registry of adapters by URI scheme
ADAPTERS = {
    "postgresql": PostgresAdapter,
    "postgres": PostgresAdapter,
    "mongodb": MongoAdapter,
    "qdrant": QdrantAdapter,
    # Additional adapters will be registered here
    # "mysql": MySQLAdapter,
    # "sqlserver": SQLServerAdapter,
    # etc.
}

class Orchestrator:
    """
    Database Orchestrator
    
    Provides a unified interface for interacting with different databases
    by routing queries to the appropriate adapter based on the connection URI.
    """
    
    def __init__(self, conn_uri: str, **kwargs):
        """
        Initialize the orchestrator with a connection URI.
        
        Args:
            conn_uri: Database connection URI
            **kwargs: Additional adapter-specific parameters
                - db_type: Optional explicit database type override (useful for HTTP-based URIs)
        
        Raises:
            ValueError: If no adapter is available for the URI scheme
        """
        # Parse the URI to get the scheme
        parsed_uri = urlparse(conn_uri)
        scheme = parsed_uri.scheme
        
        # Check if db_type is explicitly provided
        explicit_db_type = kwargs.pop('db_type', None)
        
        # Special handling for HTTP-based URIs (like Qdrant)
        if scheme in ['http', 'https'] and not explicit_db_type:
            # Try to determine from settings
            from ..config.settings import Settings
            settings = Settings()
            if settings.DB_TYPE.lower() == 'qdrant':
                logger.info(f"Detected HTTP URI for Qdrant database")
                scheme = 'qdrant'
            else:
                # Use DB_TYPE from settings as fallback
                scheme = settings.DB_TYPE.lower()
        
        # Use explicit db_type if provided
        if explicit_db_type:
            scheme = explicit_db_type.lower()
            logger.info(f"Using explicitly provided database type: {scheme}")
        
        # Get the appropriate adapter class
        AdapterCls = ADAPTERS.get(scheme)
        if not AdapterCls:
            raise ValueError(f"No adapter available for database scheme: '{scheme}'")
        
        logger.info(f"Using {AdapterCls.__name__} for connection URI scheme: {scheme}")
        
        # Initialize the adapter
        self.adapter = AdapterCls(conn_uri, **kwargs)
    
    async def llm_to_query(self, nl_prompt: str, **kwargs) -> Any:
        """
        Convert natural language to a database-specific query.
        
        Args:
            nl_prompt: Natural language question or instruction
            **kwargs: Additional adapter-specific parameters
            
        Returns:
            Database-specific query representation
        """
        return await self.adapter.llm_to_query(nl_prompt, **kwargs)
    
    async def execute(self, query: Any) -> List[Dict]:
        """
        Execute a query on the database.
        
        Args:
            query: Database-specific query
            
        Returns:
            List of dictionaries with query results
        """
        return await self.adapter.execute(query)
    
    async def run(self, nl_prompt: str, **kwargs) -> List[Dict]:
        """
        Complete pipeline: Convert natural language to query and execute.
        
        Args:
            nl_prompt: Natural language question or instruction
            **kwargs: Additional adapter-specific parameters
            
        Returns:
            List of dictionaries with query results
        """
        query = await self.llm_to_query(nl_prompt, **kwargs)
        return await self.execute(query)
    
    async def introspect_schema(self) -> List[Dict[str, str]]:
        """
        Introspect the database schema.
        
        Returns:
            List of document dictionaries with schema metadata
        """
        return await self.adapter.introspect_schema()
    
    async def test_connection(self) -> bool:
        """
        Test the database connection.
        
        Returns:
            True if connection successful, False otherwise
        """
        return await self.adapter.test_connection() 
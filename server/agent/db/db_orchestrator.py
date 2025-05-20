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
from .adapters import ADAPTER_REGISTRY

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
    
    def __init__(self, uri: str, **kwargs):
        """
        Initialize the orchestrator with a URI and create the appropriate adapter
        
        Args:
            uri: Connection URI for the database
            **kwargs: Additional arguments to pass to the adapter
        """
        # Parse the URI to determine the database type
        parsed_uri = urlparse(uri)
        
        # Get explicit db_type if provided, otherwise infer from URI
        db_type = kwargs.pop('db_type', None)
        
        # Use explicit db_type if provided, otherwise infer from URI
        if not db_type:
            # For HTTP and HTTPS URLs, we can't infer the DB type
            if parsed_uri.scheme in ['http', 'https']:
                # Try to get from kwargs or fall back to default
                db_type = kwargs.get('db_type', 'postgres')
                logger.warning(f"HTTP(S) URI provided without explicit db_type, assuming {db_type}")
            else:
                # Use the scheme as the database type
                db_type = parsed_uri.scheme
        
        # Normalize the database type
        db_type = db_type.lower()
        
        # Log the database type and URI (with password redacted for security)
        redacted_uri = self._redact_password(uri)
        logger.info(f"Initializing orchestrator for {db_type} with URI: {redacted_uri}")
        
        # Create the appropriate adapter based on the database type
        if db_type in ADAPTER_REGISTRY:
            adapter_class = ADAPTER_REGISTRY[db_type]
            self.adapter = adapter_class(uri, **kwargs)
        else:
            # Fall back to legacy handling for backward compatibility
            if db_type in ['postgres', 'postgresql']:
                self.adapter = PostgresAdapter(uri, **kwargs)
            elif db_type in ['mongodb', 'mongo']:
                self.adapter = MongoAdapter(uri, **kwargs)
            elif db_type == 'qdrant':
                self.adapter = QdrantAdapter(uri, **kwargs)
            else:
                raise ValueError(f"Unsupported database type: {db_type}")
        
        self.db_type = db_type
    
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

    def _redact_password(self, uri: str) -> str:
        """
        Redact the password from a URI for safer logging
        
        Args:
            uri: Database connection URI
            
        Returns:
            URI with password replaced by '***'
        """
        try:
            parsed = urlparse(uri)
            
            # If there's no netloc, just return the URI
            if not parsed.netloc:
                return uri
                
            # Check if there's a username:password format
            netloc_parts = parsed.netloc.split('@')
            if len(netloc_parts) == 1:
                # No username:password
                return uri
                
            auth_parts = netloc_parts[0].split(':')
            if len(auth_parts) < 2:
                # No password
                return uri
                
            # Replace password with ***
            auth_parts[1] = '***'
            netloc_parts[0] = ':'.join(auth_parts)
            
            # Reconstruct netloc
            new_netloc = '@'.join(netloc_parts)
            
            # Reconstruct URI
            redacted = parsed._replace(netloc=new_netloc)
            return redacted.geturl()
        except:
            # If anything goes wrong, return the original URI
            return uri 
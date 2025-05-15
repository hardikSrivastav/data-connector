"""
Base adapter interface for database connections.
All database adapters must implement this interface.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

class DBAdapter(ABC):
    """
    Abstract base class for database adapters.
    
    This interface defines the common operations that all database
    adapters must implement, regardless of the underlying database technology.
    """
    
    def __init__(self, conn_uri: str):
        """
        Initialize the adapter with a connection URI.
        
        Args:
            conn_uri: Connection URI for the database
        """
        self.conn_uri = conn_uri
    
    @abstractmethod
    async def llm_to_query(self, nl_prompt: str, **kwargs) -> Any:
        """
        Convert natural language prompt into a database-specific query format.
        
        Args:
            nl_prompt: Natural language question or instruction
            **kwargs: Additional parameters (schema_chunks, etc.)
            
        Returns:
            A query representation appropriate for the specific database
            (e.g., SQL string, MongoDB aggregation pipeline, etc.)
        """
        pass
    
    @abstractmethod
    async def execute(self, query: Any) -> List[Dict]:
        """
        Execute the database query and return results.
        
        Args:
            query: Database-specific query (as returned by llm_to_query)
            
        Returns:
            List of dictionaries representing the query results
        """
        pass
    
    async def execute_query(self, query: Any) -> List[Dict]:
        """
        Execute the database query and return results (alias for execute).
        
        This method provides compatibility with the implementation agent.
        By default, it delegates to execute(), but adapters can override
        this if they need different behavior.
        
        Args:
            query: Database-specific query (as returned by llm_to_query)
            
        Returns:
            List of dictionaries representing the query results
        """
        return await self.execute(query)
    
    @abstractmethod
    async def introspect_schema(self) -> List[Dict[str, str]]:
        """
        Introspect the database schema and return metadata.
        
        Returns:
            List of document dictionaries with 'id' and 'content' keys,
            suitable for embedding and semantic search
        """
        pass
    
    @abstractmethod
    async def test_connection(self) -> bool:
        """
        Test the database connection.
        
        Returns:
            True if connection successful, False otherwise
        """
        pass 
"""
PostgreSQL adapter implementation.
Wraps existing PostgreSQL functionality in the DBAdapter interface.
"""

import logging
import sys
import os
from typing import Any, Dict, List, Optional

from .base import DBAdapter
from ..execute import execute_query, test_conn, create_connection_pool
from ..introspect import get_schema_metadata

# Configure logging
logger = logging.getLogger(__name__)

class PostgresAdapter(DBAdapter):
    """
    PostgreSQL adapter implementation.
    
    This adapter wraps the existing PostgreSQL functionality
    to conform to the DBAdapter interface without modifying
    the original implementation.
    """
    
    def __init__(self, conn_uri: str):
        """
        Initialize the PostgreSQL adapter.
        
        Args:
            conn_uri: PostgreSQL connection URI
        """
        super().__init__(conn_uri)
    
    async def llm_to_query(self, nl_prompt: str, **kwargs) -> str:
        """
        Convert natural language to SQL using the LLM.
        
        This method delegates to the existing LLM client for SQL generation.
        
        Args:
            nl_prompt: Natural language query
            **kwargs: Additional parameters like schema_chunks
            
        Returns:
            SQL query string
        """
        from ...llm.client import get_llm_client
        from ...meta.ingest import SchemaSearcher
        
        # Get schema metadata if not provided
        schema_chunks = kwargs.get('schema_chunks')
        if not schema_chunks:
            # Search schema metadata
            searcher = SchemaSearcher()
            schema_chunks = await searcher.search(nl_prompt, top_k=5)
        
        # Get LLM client
        llm = get_llm_client()
        
        # Render prompt template and generate SQL
        prompt = llm.render_template("nl2sql.tpl", schema_chunks=schema_chunks, user_question=nl_prompt)
        sql = await llm.generate_sql(prompt)
        
        # Sanitize SQL (optional, could also be done by caller)
        from ...api.endpoints import sanitize_sql
        return sanitize_sql(sql)
    
    async def execute(self, query: str) -> List[Dict]:
        """
        Execute a SQL query using the existing execute_query function.
        
        Args:
            query: SQL query string
            
        Returns:
            List of dictionaries with query results
        """
        return await execute_query(query)
    
    async def introspect_schema(self) -> List[Dict[str, str]]:
        """
        Introspect the database schema using the existing functionality.
        
        Returns:
            List of document dictionaries with schema metadata
        """
        return await get_schema_metadata()
    
    async def test_connection(self) -> bool:
        """
        Test the database connection using the existing test_conn function.
        
        Returns:
            True if connection successful, False otherwise
        """
        return await test_conn() 
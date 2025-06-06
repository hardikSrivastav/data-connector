"""
Database connection utilities

This module contains shared database connection functionality
to avoid circular imports between modules.
"""

import asyncpg
import logging
from typing import Optional, List, Dict, Any
from ..config.settings import Settings

# Set up logging
logger = logging.getLogger(__name__)

async def create_connection_pool() -> asyncpg.Pool:
    """
    Create and return an asyncpg connection pool
    
    Returns:
        asyncpg.Pool: Configured connection pool
    """
    settings = Settings()
    
    try:
        pool = await asyncpg.create_pool(
            dsn=settings.db_dsn,
            min_size=5,
            max_size=20
        )
        logger.info("PostgreSQL connection pool created successfully")
        return pool
    except Exception as e:
        logger.error(f"Failed to create connection pool: {str(e)}")
        raise

async def execute_query_with_pool(query: str) -> list:
    """
    Execute a SQL query using a connection pool and return the results
    
    Args:
        query: SQL query to execute
        
    Returns:
        List of dictionaries with query results
    """
    pool = await create_connection_pool()
    try:
        async with pool.acquire() as conn:
            results = await conn.fetch(query)
            # Convert to dict list for easier serialization
            return [dict(row) for row in results]
    finally:
        await pool.close()

async def execute_query(query: str) -> List[Dict[str, Any]]:
    """
    Execute a SQL query and return the results (alias for execute_query_with_pool)
    
    Args:
        query: SQL query to execute
        
    Returns:
        List of dictionaries with query results
    """
    return await execute_query_with_pool(query)

async def test_postgresql_connection() -> bool:
    """
    Test PostgreSQL database connection by connecting and executing a simple query
    
    Returns:
        bool: True if connection successful, False otherwise
    """
    settings = Settings()
    logger.info(f"Testing connection to database: {settings.DB_HOST}/{settings.DB_NAME}")
    
    try:
        conn = await asyncpg.connect(settings.db_dsn)
        result = await conn.fetchval("SELECT 1")
        logger.info(f"Connection test successful! Test query result: {result}")
        await conn.close()
        return True
    except Exception as e:
        logger.error(f"Connection test failed: {str(e)}")
        return False

async def test_conn() -> bool:
    """
    Test database connection (alias for test_postgresql_connection)
    
    Returns:
        bool: True if connection successful, False otherwise
    """
    return await test_postgresql_connection() 
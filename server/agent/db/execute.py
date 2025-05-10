import asyncpg
import asyncio
from ..config.settings import Settings

async def test_conn():
    """
    Test database connection by connecting and executing a simple query
    """
    s = Settings()
    print(f"Connecting to database: {s.DB_HOST}/{s.DB_NAME}")
    print(f"Connection string: {s.db_dsn}")
    
    try:
        conn = await asyncpg.connect(s.db_dsn)
        result = await conn.fetchval("SELECT 1")
        print(f"Connection successful! Test query result: {result}")
        await conn.close()
        return True
    except Exception as e:
        print(f"Connection failed: {str(e)}")
        return False

async def create_connection_pool() -> asyncpg.Pool:
    """
    Create and return an asyncpg connection pool
    """
    settings = Settings()
    return await asyncpg.create_pool(
        dsn=settings.db_dsn,
        min_size=5,
        max_size=20
    )

async def execute_query(query: str) -> list:
    """
    Execute a SQL query and return the results
    
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

if __name__ == "__main__":
    asyncio.run(test_conn())

import asyncpg
import asyncio
from ..config.settings import Settings

async def test_conn():
    """
    Test database connection by connecting and executing a simple query
    """
    s = Settings()
    print(f"Connecting to database: {s.DB_HOST}/{s.DB_NAME}")
    
    try:
        conn = await asyncpg.connect(s.db_dsn)
        result = await conn.fetchval("SELECT 1")
        print(f"Connection successful! Test query result: {result}")
        await conn.close()
        return True
    except Exception as e:
        print(f"Connection failed: {str(e)}")
        return False

if __name__ == "__main__":
    asyncio.run(test_conn())

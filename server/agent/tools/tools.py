import logging
import asyncio
import json
from typing import List, Dict, Any, Optional, Tuple
import asyncpg
import statistics
import random
from decimal import Decimal
from ..db.execute import create_connection_pool
from ..meta.ingest import SchemaSearcher
from ..config.settings import Settings
import redis
from redis.asyncio import Redis
import pickle
import hashlib

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def _make_json_serializable(obj: Any) -> Any:
    """
    Convert non-JSON-serializable objects to serializable types
    
    Args:
        obj: The object to convert
        
    Returns:
        A JSON-serializable version of the object
    """
    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, (set, frozenset)):
        return list(obj)
    elif hasattr(obj, '__dict__'):
        return obj.__dict__
    elif hasattr(obj, 'isoformat'):  # datetime objects
        return obj.isoformat()
    else:
        return str(obj)

def _convert_to_serializable(data: Any) -> Any:
    """
    Recursively convert a complex data structure to a JSON-serializable form
    
    Args:
        data: The data structure to convert
        
    Returns:
        A JSON-serializable version of the data structure
    """
    if isinstance(data, dict):
        return {k: _convert_to_serializable(v) for k, v in data.items()}
    elif isinstance(data, (list, tuple)):
        return [_convert_to_serializable(item) for item in data]
    else:
        return _make_json_serializable(data)

class DataTools:
    """Collection of tools for data analysis and query execution"""
    
    def __init__(self):
        """Initialize the data tools"""
        self.settings = Settings()
        self.schema_searcher = SchemaSearcher()
        self.session_id = None
        self.redis_client = None
        
    async def initialize(self, session_id: str):
        """Initialize connections and resources"""
        self.session_id = session_id
        
        # Initialize Redis connection if cache path is set
        if self.settings.CACHE_PATH:
            try:
                redis_host = self.settings.REDIS_HOST or "localhost"
                redis_port = self.settings.REDIS_PORT or 6379
                self.redis_client = Redis(host=redis_host, port=redis_port, decode_responses=False)
                logger.info(f"Initialized Redis cache connection to {redis_host}:{redis_port}")
            except Exception as e:
                logger.warning(f"Failed to connect to Redis: {str(e)}. Caching will be disabled.")
                self.redis_client = None
    
    async def get_cached_result(self, key: str) -> Optional[Any]:
        """Get a cached result from Redis"""
        if not self.redis_client:
            return None
            
        cache_key = f"{self.session_id}:{key}"
        try:
            cached_data = await self.redis_client.get(cache_key)
            if cached_data:
                return pickle.loads(cached_data)
            return None
        except Exception as e:
            logger.warning(f"Error retrieving from cache: {str(e)}")
            return None
    
    async def set_cached_result(self, key: str, data: Any, ttl: int = 3600) -> bool:
        """Store a result in Redis cache"""
        if not self.redis_client:
            return False
            
        cache_key = f"{self.session_id}:{key}"
        try:
            # Make data serializable before storing
            serializable_data = _convert_to_serializable(data)
            serialized_data = pickle.dumps(serializable_data)
            await self.redis_client.setex(cache_key, ttl, serialized_data)
            return True
        except Exception as e:
            logger.warning(f"Error caching result: {str(e)}")
            return False
    
    async def get_metadata(self, table_names: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Get metadata about the database schema and tables
        
        Args:
            table_names: Optional list of table names to get metadata for
                        If None, gets metadata for all tables
                        
        Returns:
            Dictionary with schema metadata
        """
        logger.info(f"Getting schema metadata for tables: {table_names or 'all'}")
        
        # Generate cache key
        key = f"metadata:{','.join(sorted(table_names)) if table_names else 'all'}"
        cached_result = await self.get_cached_result(key)
        if cached_result:
            logger.info("Using cached metadata")
            return cached_result
            
        pool = await create_connection_pool()
        try:
            async with pool.acquire() as conn:
                # Get table info
                tables_query = """
                SELECT table_name, 
                       (SELECT COUNT(*) FROM information_schema.columns WHERE table_name = t.table_name) as column_count,
                       pg_total_relation_size(quote_ident(t.table_name)) as table_size_bytes
                FROM information_schema.tables t
                WHERE table_schema = 'public'
                """
                if table_names:
                    tables_query += " AND table_name = ANY($1)"
                    tables = await conn.fetch(tables_query, table_names)
                else:
                    tables = await conn.fetch(tables_query)
                
                # For each table, get row count estimate
                table_stats = []
                for table in tables:
                    table_name = table['table_name']
                    row_count = await conn.fetchval(f"SELECT reltuples::bigint AS estimate FROM pg_class WHERE relname = $1", table_name)
                    
                    # Get detailed column info
                    columns = await conn.fetch("""
                    SELECT column_name, data_type, 
                           column_default, is_nullable
                    FROM information_schema.columns
                    WHERE table_name = $1
                    ORDER BY ordinal_position
                    """, table_name)
                    
                    # Get primary key info
                    pk_query = """
                    SELECT a.attname
                    FROM pg_index i
                    JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
                    WHERE i.indrelid = $1::regclass
                    AND i.indisprimary
                    """
                    primary_keys = await conn.fetch(pk_query, table_name)
                    pk_columns = [pk['attname'] for pk in primary_keys]
                    
                    # Add to table stats
                    table_stats.append({
                        'table_name': table_name,
                        'row_count': row_count or 0,
                        'column_count': table['column_count'],
                        'size_bytes': table['table_size_bytes'],
                        'columns': [dict(col) for col in columns],
                        'primary_keys': pk_columns
                    })
                
                result = {
                    'tables': table_stats,
                    'total_tables': len(table_stats),
                    'database_name': self.settings.DB_NAME
                }
                
                # Convert to serializable format and cache the result
                result = _convert_to_serializable(result)
                await self.set_cached_result(key, result)
                
                return result
        finally:
            await pool.close()
    
    async def run_summary_query(self, table_name: str, columns: List[str] = None) -> Dict[str, Any]:
        """
        Run statistical summary queries on specified columns
        
        Args:
            table_name: Name of the table to analyze
            columns: List of columns to generate statistics for
                    If None, uses all numeric columns
                    
        Returns:
            Dictionary with summary statistics
        """
        logger.info(f"Generating summary statistics for {table_name}, columns: {columns}")
        
        # Generate cache key
        key = f"summary:{table_name}:{','.join(sorted(columns)) if columns else 'all'}"
        cached_result = await self.get_cached_result(key)
        if cached_result:
            logger.info("Using cached summary statistics")
            return cached_result
        
        pool = await create_connection_pool()
        try:
            async with pool.acquire() as conn:
                # If columns not specified, get all numeric columns
                if not columns:
                    numeric_cols = await conn.fetch("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = $1
                    AND data_type IN ('integer', 'bigint', 'numeric', 'decimal', 'real', 'double precision')
                    """, table_name)
                    columns = [col['column_name'] for col in numeric_cols]
                
                if not columns:
                    return {"error": "No numeric columns found for summary statistics"}
                
                # Get table row count
                row_count = await conn.fetchval(f"SELECT COUNT(*) FROM {table_name}")
                
                # For each column, get summary statistics
                column_stats = {}
                for column in columns:
                    # Build a single query for all statistics to minimize round trips
                    stats_query = f"""
                    SELECT
                        COUNT("{column}") as count,
                        COUNT(DISTINCT "{column}") as distinct_count,
                        MIN("{column}") as min_value,
                        MAX("{column}") as max_value,
                        AVG("{column}") as avg_value,
                        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY "{column}") as median,
                        PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY "{column}") as q1,
                        PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY "{column}") as q3
                    FROM {table_name}
                    WHERE "{column}" IS NOT NULL
                    """
                    
                    try:
                        stats = await conn.fetchrow(stats_query)
                        column_stats[column] = dict(stats)
                        
                        # Calculate null percentage
                        null_count = row_count - stats['count']
                        column_stats[column]['null_count'] = null_count
                        column_stats[column]['null_percentage'] = (null_count / row_count * 100) if row_count > 0 else 0
                    except Exception as e:
                        logger.warning(f"Error getting statistics for column {column}: {str(e)}")
                        column_stats[column] = {"error": str(e)}
                
                result = {
                    "table_name": table_name,
                    "row_count": row_count,
                    "column_stats": column_stats
                }
                
                # Convert to serializable format and cache the result
                result = _convert_to_serializable(result)
                await self.set_cached_result(key, result)
                
                return result
        finally:
            await pool.close()
    
    async def sample_data(self, query: str, sample_size: int = 100, 
                          sampling_method: str = "random") -> Dict[str, Any]:
        """
        Get a representative sample of data from a query
        
        Args:
            query: SQL query to sample from
            sample_size: Number of rows to sample
            sampling_method: Method to use for sampling
                            "random": Random sample
                            "first": First N rows
                            "stratified": Attempt to get representative data
            
        Returns:
            Dictionary with sample data and metadata
        """
        logger.info(f"Sampling data using method: {sampling_method}, sample_size: {sample_size}")
        
        # Generate a hash of the query for caching
        query_hash = hashlib.md5(query.encode()).hexdigest()
        key = f"sample:{query_hash}:{sampling_method}:{sample_size}"
        cached_result = await self.get_cached_result(key)
        if cached_result:
            logger.info("Using cached sample data")
            return cached_result
        
        pool = await create_connection_pool()
        try:
            async with pool.acquire() as conn:
                # Get total row count for the query
                count_query = f"SELECT COUNT(*) FROM ({query}) AS subquery"
                total_rows = await conn.fetchval(count_query)
                
                if sampling_method == "random":
                    # Random sampling using TABLESAMPLE if supported, otherwise ORDER BY RANDOM()
                    if total_rows <= 10000:  # For smaller datasets, ORDER BY RANDOM() is fine
                        sampled_query = f"""
                        SELECT * FROM ({query}) AS subquery
                        ORDER BY RANDOM()
                        LIMIT {sample_size}
                        """
                    else:  # For larger datasets, use system sampling
                        # Calculate approximate percentage to get desired sample size
                        percent = min(100, (sample_size / total_rows * 100) * 3)  # Get 3x more rows than needed
                        sampled_query = f"""
                        SELECT * FROM ({query}) AS subquery
                        TABLESAMPLE SYSTEM({percent})
                        LIMIT {sample_size}
                        """
                elif sampling_method == "first":
                    # Simply get the first N rows
                    sampled_query = f"""
                    SELECT * FROM ({query}) AS subquery
                    LIMIT {sample_size}
                    """
                elif sampling_method == "stratified":
                    # Attempt a simple form of stratified sampling
                    # This gets more complex with multiple dimensions, so we'll do a basic version
                    # First, identify a column that might be good for stratification (e.g., date/category)
                    # Here we assume the first column as a simple default:
                    column_info = await conn.fetch(f"SELECT * FROM ({query}) AS subquery LIMIT 1")
                    if column_info and len(column_info[0].keys()) > 0:
                        strat_column = list(column_info[0].keys())[0]
                        sampled_query = f"""
                        WITH strata AS (
                            SELECT *, ntile({min(10, sample_size)}) OVER (ORDER BY "{strat_column}") AS strata_id
                            FROM ({query}) AS subquery
                        ),
                        sampled AS (
                            SELECT *, ROW_NUMBER() OVER (PARTITION BY strata_id ORDER BY RANDOM()) AS rn
                            FROM strata
                        )
                        SELECT * FROM sampled 
                        WHERE rn <= {max(1, sample_size // 10)}
                        ORDER BY strata_id, rn
                        LIMIT {sample_size}
                        """
                    else:
                        # Fall back to random if column detection fails
                        sampled_query = f"""
                        SELECT * FROM ({query}) AS subquery
                        ORDER BY RANDOM()
                        LIMIT {sample_size}
                        """
                else:
                    raise ValueError(f"Unsupported sampling method: {sampling_method}")
                
                # Execute the sampling query
                sample = await conn.fetch(sampled_query)
                
                # Convert to list of dicts for easier serialization
                rows = [dict(row) for row in sample]
                
                # Calculate basic statistics about the rows for debugging
                columns = []
                if rows:
                    columns = list(rows[0].keys())
                
                result = {
                    "total_rows": total_rows,
                    "sampled_rows": len(rows),
                    "sampling_method": sampling_method,
                    "sample_size_requested": sample_size,
                    "columns": columns,
                    "rows": rows
                }
                
                # Convert to serializable format and cache the result
                result = _convert_to_serializable(result)
                await self.set_cached_result(key, result)
                
                return result
        except Exception as e:
            logger.error(f"Error sampling data: {str(e)}")
            return {"error": str(e)}
        finally:
            await pool.close()
    
    async def run_targeted_query(self, query: str, timeout: int = 30) -> Dict[str, Any]:
        """
        Run a targeted SQL query with timeout protection
        
        Args:
            query: SQL query to execute
            timeout: Query timeout in seconds
            
        Returns:
            Dictionary with query results and metadata
        """
        logger.info(f"Running targeted query with timeout {timeout}s")
        
        # Generate a hash of the query for caching
        query_hash = hashlib.md5(query.encode()).hexdigest()
        key = f"query:{query_hash}"
        cached_result = await self.get_cached_result(key)
        if cached_result:
            logger.info("Using cached query result")
            return cached_result
        
        pool = await create_connection_pool()
        try:
            async with pool.acquire() as conn:
                # Set statement timeout
                await conn.execute(f"SET statement_timeout = {timeout * 1000}")
                
                # Execute the query
                start_time = asyncio.get_event_loop().time()
                rows = await conn.fetch(query)
                execution_time = asyncio.get_event_loop().time() - start_time
                
                # Convert to list of dicts for easier serialization
                results = [dict(row) for row in rows]
                
                # Collect basic metadata about the results
                row_count = len(results)
                columns = []
                if row_count > 0:
                    columns = list(results[0].keys())
                
                # Make all results JSON serializable
                results = _convert_to_serializable(results)
                
                result = {
                    "query": query,
                    "row_count": row_count,
                    "columns": columns,
                    "execution_time_seconds": execution_time,
                    "rows": results
                }
                
                # Cache the result if it's not too large
                if row_count <= 1000:  # Don't cache extremely large results
                    await self.set_cached_result(key, result)
                
                return result
        except asyncio.TimeoutError:
            return {"error": f"Query timed out after {timeout} seconds"}
        except Exception as e:
            logger.error(f"Error executing targeted query: {str(e)}")
            return {"error": str(e)}
        finally:
            await pool.close()
    
    async def generate_insights(self, data: Dict[str, Any], insight_type: str) -> Dict[str, Any]:
        """
        Generate specific insights from data
        This is a placeholder for various statistical or ML-based insights
        
        Args:
            data: Dictionary containing data to analyze
            insight_type: Type of insight to generate
                        "outliers": Detect outliers
                        "trends": Detect trends over time
                        "clusters": Basic clustering
                        "correlations": Find correlations between columns
            
        Returns:
            Dictionary with generated insights
        """
        logger.info(f"Generating {insight_type} insights")
        
        # Convert input data to serializable form
        data = _convert_to_serializable(data)
        
        # This would typically call specific analytical functions
        # For now, we return a placeholder
        result = {
            "insight_type": insight_type,
            "message": f"Insight generation for {insight_type} would be implemented here",
            "data": data
        }
        
        return result 
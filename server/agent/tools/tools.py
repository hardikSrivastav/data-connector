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
# Use lazy import for Orchestrator
# from ..db.orchestrator import Orchestrator
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
    
    def __init__(self, db_type: str = None):
        """
        Initialize the data tools
        
        Args:
            db_type: The database type to use (postgres, mongodb, qdrant, slack, etc.)
        """
        self.settings = Settings()
        if db_type:
            self.settings.DB_TYPE = db_type  # Add this line to update settings
        self.schema_searcher = SchemaSearcher()
        self.session_id = None
        self.redis_client = None
        self.db_type = db_type or self.settings.DB_TYPE
        self.orchestrator = None
        logger.info(f"Initializing DataTools with database type: {self.db_type}")
        
    async def initialize(self, session_id: str):
        """Initialize connections and resources"""
        self.session_id = session_id
        
        # Initialize the orchestrator with the appropriate connection
        try:
            # Lazy import to avoid circular dependency
            from ..db.orchestrator import Orchestrator
            
            conn_uri = self.settings.connection_uri
            logger.info(f"Initializing orchestrator for {self.db_type} with URI: {conn_uri.replace(self.settings.DB_PASS, '***') if self.settings.DB_PASS else conn_uri}")
            self.orchestrator = Orchestrator(conn_uri, db_type=self.db_type)
        except Exception as e:
            logger.error(f"Failed to initialize orchestrator: {str(e)}")
            raise
        
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
        key = f"metadata:{self.db_type}:{','.join(sorted(table_names)) if table_names else 'all'}"
        cached_result = await self.get_cached_result(key)
        if cached_result:
            logger.info("Using cached metadata")
            return cached_result
        
        # Use the orchestrator to get metadata based on the database type
        if not self.orchestrator:
            raise ValueError("Orchestrator not initialized. Call initialize() first.")
        
        try:
            # Get metadata through the appropriate adapter
            metadata = await self.orchestrator.introspect_schema()
            
            # Filter to specific tables if requested
            if table_names:
                if self.db_type in ["postgres", "postgresql"]:
                    metadata = [table for table in metadata if table.get('table_name') in table_names]
                elif self.db_type == "mongodb":
                    metadata = [coll for coll in metadata if coll.get('collection') in table_names]
                # Add filters for other database types as needed
            
            # Format the results based on database type
            if self.db_type in ["postgres", "postgresql"]:
                result = {
                    'tables': metadata,
                    'total_tables': len(metadata),
                    'database_name': self.settings.DB_NAME
                }
            else:
                # For other database types, we'll use the adapter's response format
                result = {
                    'tables': metadata,
                    'total_tables': len(metadata),
                    'database_name': self.settings.DB_NAME,
                    'db_type': self.db_type
                }
            
            # Convert to serializable format and cache the result
            result = _convert_to_serializable(result)
            await self.set_cached_result(key, result)
            
            return result
        except Exception as e:
            logger.error(f"Error getting metadata: {str(e)}")
            return {"error": str(e), "db_type": self.db_type}
    
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
        key = f"summary:{self.db_type}:{table_name}:{','.join(sorted(columns)) if columns else 'all'}"
        cached_result = await self.get_cached_result(key)
        if cached_result:
            logger.info("Using cached summary statistics")
            return cached_result
        
        if not self.orchestrator:
            raise ValueError("Orchestrator not initialized. Call initialize() first.")
        
        try:
            if self.db_type in ["postgres", "postgresql"]:
                # For PostgreSQL, use a SQL query
                cols_clause = ', '.join([f'"{col}"' for col in columns]) if columns else '*'
                query = f"""
                SELECT
                    '{table_name}' as table_name,
                    COUNT(*) as row_count,
                    {cols_clause}
                FROM {table_name}
                """
                result = await self.run_targeted_query(query)
                
                # Process results to calculate statistics if needed
                # This would depend on the specific requirements
                
                return result
            elif self.db_type == "mongodb":
                # For MongoDB, use aggregation pipeline
                pipeline = [
                    {"$match": {}},
                    {"$limit": 1000},
                    {"$project": {col: 1 for col in columns} if columns else {}}
                ]
                
                # Format as a MongoDB query
                query = {
                    "collection": table_name,
                    "pipeline": pipeline
                }
                
                # Execute through the orchestrator
                results = await self.orchestrator.execute(query)
                
                # Calculate statistics from results
                stats = {
                    "table_name": table_name,
                    "row_count": len(results),
                    "sample_size": min(len(results), 1000),
                    "db_type": self.db_type
                }
                
                # Process results to provide column-level statistics
                if results and len(results) > 0:
                    column_stats = {}
                    for col in (columns or results[0].keys()):
                        if col in results[0]:
                            values = [r.get(col) for r in results if col in r and r.get(col) is not None]
                            if values:
                                try:
                                    numeric_values = [float(v) for v in values if isinstance(v, (int, float))]
                                    if numeric_values:
                                        column_stats[col] = {
                                            "count": len(numeric_values),
                                            "min_value": min(numeric_values),
                                            "max_value": max(numeric_values),
                                            "avg_value": sum(numeric_values) / len(numeric_values),
                                        }
                                except (ValueError, TypeError):
                                    # For non-numeric columns, just count distinct values
                                    column_stats[col] = {
                                        "count": len(values),
                                        "distinct_count": len(set(str(v) for v in values)),
                                    }
                    
                    stats["column_stats"] = column_stats
                
                return stats
            elif self.db_type in ["qdrant", "slack"]:
                # These databases may have different approaches for statistics
                # For now, return a basic response indicating the limitation
                return {
                    "message": f"Summary statistics for {self.db_type} are limited.",
                    "table_name": table_name,
                    "db_type": self.db_type,
                }
            else:
                return {
                    "error": f"Summary statistics not implemented for database type: {self.db_type}",
                    "db_type": self.db_type
                }
        except Exception as e:
            logger.error(f"Error generating summary for {self.db_type}: {str(e)}")
            return {"error": str(e), "db_type": self.db_type}
    
    async def sample_data(self, query: str, sample_size: int = 100, 
                          sampling_method: str = "random") -> Dict[str, Any]:
        """
        Get a representative sample of data from a query
        
        Args:
            query: Query to sample from (SQL for postgres, aggregation for MongoDB, etc.)
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
        query_hash = hashlib.md5(str(query).encode()).hexdigest()
        key = f"sample:{self.db_type}:{query_hash}:{sampling_method}:{sample_size}"
        cached_result = await self.get_cached_result(key)
        if cached_result:
            logger.info("Using cached sample data")
            return cached_result
        
        if not self.orchestrator:
            raise ValueError("Orchestrator not initialized. Call initialize() first.")
        
        try:
            # Adjust the query based on database type and sampling method
            if self.db_type in ["postgres", "postgresql"]:
                # For PostgreSQL, modify the SQL query for sampling
                if isinstance(query, str):
                    if sampling_method == "random":
                        if "ORDER BY" not in query.upper():
                            sampled_query = f"""
                            SELECT * FROM ({query}) AS subquery
                            ORDER BY RANDOM()
                            LIMIT {sample_size}
                            """
                        else:
                            # Be careful not to break existing ORDER BY clauses
                            sampled_query = f"""
                            SELECT * FROM ({query}) AS subquery
                            LIMIT {sample_size}
                            """
                    elif sampling_method == "first":
                        sampled_query = f"""
                        SELECT * FROM ({query}) AS subquery
                        LIMIT {sample_size}
                        """
                    else:  # Default to basic limit
                        sampled_query = f"""
                        SELECT * FROM ({query}) AS subquery
                        LIMIT {sample_size}
                        """
                    
                    # Execute the query
                    results = await self.run_targeted_query(sampled_query)
                    return results
                else:
                    return {"error": "Query must be a string for PostgreSQL", "db_type": self.db_type}
            
            elif self.db_type == "mongodb":
                # For MongoDB, add sampling to the aggregation pipeline
                if isinstance(query, dict) and "pipeline" in query:
                    # Add $sample stage for random sampling if requested
                    pipeline = query["pipeline"]
                    collection = query.get("collection", "")
                    
                    if sampling_method == "random":
                        pipeline.append({"$sample": {"size": sample_size}})
                    elif sampling_method == "first":
                        pipeline.append({"$limit": sample_size})
                    else:
                        pipeline.append({"$limit": sample_size})
                    
                    # Execute the modified query
                    results = await self.orchestrator.execute(query)
                    
                    return {
                        "rows": results,
                        "row_count": len(results),
                        "sampled_rows": len(results),
                        "sampling_method": sampling_method,
                        "sample_size_requested": sample_size,
                        "db_type": self.db_type
                    }
                else:
                    return {"error": "Query must be a dictionary with 'pipeline' key for MongoDB", "db_type": self.db_type}
            
            elif self.db_type in ["qdrant", "slack"]:
                # For vector and other specialized databases
                # Just pass through to the adapter and limit results
                modified_query = query
                
                # Adjust for size limits if possible
                if isinstance(query, dict) and "limit" in query:
                    modified_query["limit"] = min(query.get("limit", 100), sample_size)
                
                results = await self.orchestrator.execute(modified_query)
                
                return {
                    "rows": results[:sample_size],
                    "row_count": len(results),
                    "sampled_rows": min(len(results), sample_size),
                    "sampling_method": sampling_method,
                    "sample_size_requested": sample_size,
                    "db_type": self.db_type
                }
            
            else:
                return {"error": f"Sampling not implemented for database type: {self.db_type}", "db_type": self.db_type}
                
        except Exception as e:
            logger.error(f"Error sampling data for {self.db_type}: {str(e)}")
            return {"error": str(e), "db_type": self.db_type}
    
    async def run_targeted_query(self, query: str, timeout: int = 30) -> Dict[str, Any]:
        """
        Run a targeted query with timeout protection
        
        Args:
            query: Query to execute (SQL for postgres, aggregation for MongoDB, etc.)
            timeout: Query timeout in seconds
            
        Returns:
            Dictionary with query results and metadata
        """
        logger.info(f"Running targeted query for {self.db_type} with timeout {timeout}s")
        
        # Generate a hash of the query for caching
        query_hash = hashlib.md5(str(query).encode()).hexdigest()
        key = f"query:{self.db_type}:{query_hash}"
        cached_result = await self.get_cached_result(key)
        if cached_result:
            logger.info("Using cached query result")
            return cached_result
        
        if not self.orchestrator:
            raise ValueError("Orchestrator not initialized. Call initialize() first.")
        
        try:
            # Execute the query through the orchestrator
            # The orchestrator will route to the appropriate adapter
            start_time = asyncio.get_event_loop().time()
            
            # Set timeout for the query execution
            results = await asyncio.wait_for(
                self.orchestrator.execute(query), 
                timeout=timeout
            )
            
            execution_time = asyncio.get_event_loop().time() - start_time
            
            # Ensure results are in a standardized format
            if not isinstance(results, list):
                if hasattr(results, 'to_dict'):
                    results = [results.to_dict()]
                else:
                    results = [{"result": results}]
            
            # Collect basic metadata about the results
            row_count = len(results)
            columns = []
            if row_count > 0:
                columns = list(results[0].keys()) if isinstance(results[0], dict) else []
            
            # Make all results JSON serializable
            results = _convert_to_serializable(results)
            
            result = {
                "query": query,
                "row_count": row_count,
                "columns": columns,
                "execution_time_seconds": execution_time,
                "rows": results,
                "db_type": self.db_type
            }
            
            # Cache the result if it's not too large
            if row_count <= 1000:  # Don't cache extremely large results
                await self.set_cached_result(key, result)
            
            return result
        except asyncio.TimeoutError:
            return {"error": f"Query timed out after {timeout} seconds", "db_type": self.db_type}
        except Exception as e:
            logger.error(f"Error executing targeted query for {self.db_type}: {str(e)}")
            return {"error": str(e), "db_type": self.db_type}
    
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
        logger.info(f"Generating {insight_type} insights for {self.db_type}")
        
        # Convert input data to serializable form
        data = _convert_to_serializable(data)
        
        # This would typically call specific analytical functions
        # For now, we return a placeholder
        result = {
            "insight_type": insight_type,
            "message": f"Insight generation for {insight_type} would be implemented here",
            "data": data,
            "db_type": self.db_type
        }
        
        return result 
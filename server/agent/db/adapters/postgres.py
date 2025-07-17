"""
PostgreSQL adapter implementation.
Wraps existing PostgreSQL functionality in the DBAdapter interface.
"""

import logging
import sys
import os
import json
import re
from typing import Any, Dict, List, Optional
from decimal import Decimal

from .base import DBAdapter
from ..connection_utils import execute_query, test_conn, create_connection_pool
from ..introspect import get_schema_metadata
from ...langgraph.graphs.bedrock_client import get_bedrock_langgraph_client

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
        logger.info(f"Initializing PostgresAdapter with URI: {self._sanitize_uri(conn_uri)}")
    
    def _sanitize_uri(self, uri: str) -> str:
        """Sanitize URI for logging by hiding password."""
        return re.sub(r'://([^:]+):([^@]+)@', r'://\1:***@', uri)
    
    async def llm_to_query(self, nl_prompt: str, **kwargs) -> str:
        """
        Convert natural language to SQL using Bedrock LLM.
        
        Args:
            nl_prompt: Natural language query
            **kwargs: Additional parameters like schema_chunks
            
        Returns:
            SQL query string
        """
        logger.info(f"Converting natural language to SQL: {nl_prompt[:100]}...")
        logger.debug(f"LLM conversion kwargs: {list(kwargs.keys())}")
        
        try:
            # Use singleton factory instead of direct instantiation
            bedrock_client = get_bedrock_langgraph_client()
            
            # Get schema metadata if not provided
            schema_chunks = kwargs.get('schema_chunks')
            if not schema_chunks:
                logger.debug("No schema chunks provided, searching for relevant schema")
                # Import SchemaSearcher only when needed to avoid circular imports
                from ...meta.ingest import SchemaSearcher
                # Search schema metadata
                searcher = SchemaSearcher()
                schema_chunks = await searcher.search(nl_prompt, top_k=5)
                logger.debug(f"Found {len(schema_chunks)} relevant schema chunks")
            
            # Format schema information for prompt
            schema_info = ""
            if schema_chunks:
                schema_info = "\n".join([
                    f"Table: {chunk.get('table_name', 'unknown')}\n"
                    f"Schema: {chunk.get('schema_info', 'no schema')}\n"
                    for chunk in schema_chunks[:3]  # Limit to top 3 for token efficiency
                ])
            
            # Create SQL generation prompt
            prompt = f"""Convert the following natural language query to PostgreSQL SQL.

Database Schema Information:
{schema_info}

Natural Language Query: {nl_prompt}

Instructions:
1. Generate valid PostgreSQL SQL syntax
2. Use appropriate table and column names from the schema
3. Return ONLY the SQL query, no explanations
4. Ensure the query is safe and follows best practices

SQL Query:"""
            
            # Generate SQL using Bedrock
            sql = await bedrock_client.generate_completion(
                prompt=prompt,
                max_tokens=500,
                temperature=0.1
            )
            
            # Clean up SQL response
            sql = sql.strip()
            if sql.startswith("```sql"):
                sql = sql[6:]
            if sql.endswith("```"):
                sql = sql[:-3]
            sql = sql.strip()
            
            logger.info(f"Generated SQL query: {sql[:200]}...")
            
            # Basic SQL sanitization
            if not sql or sql.lower().strip() in ['no sql', 'none', 'n/a']:
                raise ValueError("No valid SQL generated")
            
            return sql
            
        except Exception as e:
            logger.error(f"Failed to convert natural language to SQL: {e}")
            raise
    
    async def execute(self, query: str) -> List[Dict]:
        """
        Execute a SQL query, handling multiple commands properly.
        
        Args:
            query: SQL query string (can contain multiple statements)
            
        Returns:
            List of dictionaries with query results
        """
        logger.info(f"Executing PostgreSQL query: {query[:200]}...")
        
        try:
            # Check if query contains multiple statements
            statements = self._split_sql_statements(query)
            
            if len(statements) == 1:
                # Single statement - use existing method
                result = await execute_query(query)
                logger.info(f"Query executed successfully, returned {len(result)} rows")
                logger.debug(f"Sample result: {result[:2] if result else 'No results'}")
                return result
            else:
                # Multiple statements - execute them separately
                logger.info(f"Executing {len(statements)} separate SQL statements")
                final_result = []
                
                for i, statement in enumerate(statements):
                    statement = statement.strip()
                    if not statement:
                        continue
                        
                    logger.debug(f"Executing statement {i+1}/{len(statements)}: {statement[:100]}...")
                    
                    try:
                        result = await execute_query(statement)
                        
                        # For SELECT/EXPLAIN queries, keep the results
                        if statement.upper().startswith(('SELECT', 'WITH', 'EXPLAIN')):
                            final_result.extend(result)
                            logger.info(f"Statement {i+1} returned {len(result)} rows")
                        else:
                            # For non-SELECT queries (ANALYZE, etc.), just log success
                            logger.info(f"Statement {i+1} executed successfully")
                    
                    except Exception as e:
                        logger.warning(f"Statement {i+1} failed: {e}")
                        # Continue with other statements
                        continue
                
                logger.info(f"Multi-statement query completed, final result: {len(final_result)} rows")
                return final_result
            
        except Exception as e:
            logger.error(f"Failed to execute PostgreSQL query: {e}")
            raise
    
    def _split_sql_statements(self, query: str) -> List[str]:
        """
        Split a multi-statement SQL query into individual statements.
        
        Args:
            query: Multi-statement SQL query
            
        Returns:
            List of individual SQL statements
        """
        # Simple splitting by semicolon - this could be enhanced with proper SQL parsing
        statements = []
        current_statement = ""
        in_string = False
        escape_next = False
        
        for char in query:
            if escape_next:
                current_statement += char
                escape_next = False
                continue
                
            if char == '\\':
                escape_next = True
                current_statement += char
                continue
                
            if char in ("'", '"'):
                in_string = not in_string
                current_statement += char
                continue
                
            if char == ';' and not in_string:
                # End of statement
                if current_statement.strip():
                    statements.append(current_statement.strip())
                current_statement = ""
                continue
                
            current_statement += char
        
        # Add the last statement if it doesn't end with semicolon
        if current_statement.strip():
            statements.append(current_statement.strip())
            
        return statements
    
    async def execute_query(self, query: str, params: Optional[List] = None) -> List[Dict]:
        """
        Execute a SQL query (alias for execute).
        
        This method exists for compatibility with the implementation agent.
        
        Args:
            query: SQL query string
            params: Optional query parameters (currently not used but accepted for compatibility)
            
        Returns:
            List of dictionaries with query results
        """
        # Note: params are currently ignored as the existing execute_query function doesn't support them
        # Future enhancement could add parameter support
        if params:
            logger.warning(f"Parameters provided but not supported: {params}")
        
        return await self.execute(query)
    
    async def introspect_schema(self) -> List[Dict[str, str]]:
        """
        Introspect the database schema using the existing functionality.
        
        Returns:
            List of document dictionaries with schema metadata
        """
        logger.info("Starting PostgreSQL schema introspection")
        
        try:
            result = await get_schema_metadata()
            logger.info(f"Schema introspection completed, found {len(result)} schema elements")
            return result
            
        except Exception as e:
            logger.error(f"Failed to introspect PostgreSQL schema: {e}")
            raise
    
    async def test_connection(self) -> bool:
        """
        Test the database connection using the existing test_conn function.
        
        Returns:
            True if connection successful, False otherwise
        """
        logger.info("Testing PostgreSQL connection")
        
        try:
            result = await test_conn()
            logger.info(f"PostgreSQL connection test result: {result}")
            return result
            
        except Exception as e:
            logger.error(f"PostgreSQL connection test failed: {e}")
            return False
    
    # Additional PostgreSQL-specific tools for the registry
    
    async def analyze_query_performance(self, query: str) -> Dict[str, Any]:
        """
        Analyze SQL query performance using EXPLAIN ANALYZE.
        
        Args:
            query: SQL query to analyze
            
        Returns:
            Performance analysis results
        """
        logger.info(f"Analyzing query performance: {query[:100]}...")
        
        try:
            # Add EXPLAIN ANALYZE to the query
            explain_query = f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {query}"
            
            result = await execute_query(explain_query)
            
            if result and len(result) > 0:
                explain_result = result[0].get('QUERY PLAN', [])
                
                analysis = {
                    "execution_time_ms": self._extract_execution_time(explain_result),
                    "total_cost": self._extract_total_cost(explain_result),
                    "rows_returned": self._extract_rows_returned(explain_result),
                    "buffers_hit": self._extract_buffer_stats(explain_result),
                    "plan_details": explain_result,
                    "performance_recommendations": self._generate_performance_recommendations(explain_result)
                }
                
                logger.info(f"Query performance analysis completed: {analysis['execution_time_ms']}ms")
                return analysis
            else:
                logger.warning("No EXPLAIN results returned")
                return {"error": "No explain results available"}
                
        except Exception as e:
            logger.error(f"Failed to analyze query performance: {e}")
            raise
    
    def _extract_execution_time(self, explain_result: List[Dict]) -> float:
        """Extract execution time from EXPLAIN ANALYZE result."""
        try:
            if explain_result and len(explain_result) > 0:
                return explain_result[0].get("Execution Time", 0.0)
            return 0.0
        except Exception:
            return 0.0
    
    def _extract_total_cost(self, explain_result: List[Dict]) -> float:
        """Extract total cost from EXPLAIN result."""
        try:
            if explain_result and len(explain_result) > 0:
                plan = explain_result[0].get("Plan", {})
                return plan.get("Total Cost", 0.0)
            return 0.0
        except Exception:
            return 0.0
    
    def _extract_rows_returned(self, explain_result: List[Dict]) -> int:
        """Extract rows returned from EXPLAIN result."""
        try:
            if explain_result and len(explain_result) > 0:
                plan = explain_result[0].get("Plan", {})
                return plan.get("Actual Rows", 0)
            return 0
        except Exception:
            return 0
    
    def _extract_buffer_stats(self, explain_result: List[Dict]) -> Dict[str, int]:
        """Extract buffer statistics from EXPLAIN result."""
        try:
            if explain_result and len(explain_result) > 0:
                plan = explain_result[0].get("Plan", {})
                return {
                    "shared_hit": plan.get("Shared Hit Blocks", 0),
                    "shared_read": plan.get("Shared Read Blocks", 0),
                    "shared_dirtied": plan.get("Shared Dirtied Blocks", 0),
                    "shared_written": plan.get("Shared Written Blocks", 0)
                }
            return {}
        except Exception:
            return {}
    
    def _generate_performance_recommendations(self, explain_result: List[Dict]) -> List[str]:
        """Generate performance recommendations based on EXPLAIN result."""
        recommendations = []
        
        try:
            if explain_result and len(explain_result) > 0:
                plan = explain_result[0].get("Plan", {})
                
                # Check for sequential scans
                if plan.get("Node Type") == "Seq Scan":
                    recommendations.append("Consider adding an index to avoid sequential scan")
                
                # Check for high cost operations
                total_cost = plan.get("Total Cost", 0)
                if total_cost > 1000:
                    recommendations.append("Query has high cost, consider optimization")
                
                # Check for buffer misses
                shared_read = plan.get("Shared Read Blocks", 0)
                shared_hit = plan.get("Shared Hit Blocks", 0)
                if shared_read > 0 and shared_hit > 0:
                    hit_ratio = shared_hit / (shared_hit + shared_read)
                    if hit_ratio < 0.9:
                        recommendations.append("Low buffer cache hit ratio, consider increasing shared_buffers")
                
                # Check execution time
                execution_time = explain_result[0].get("Execution Time", 0)
                if execution_time > 1000:
                    recommendations.append("Query execution time is high, consider optimization")
        
        except Exception as e:
            logger.warning(f"Failed to generate recommendations: {e}")
        
        return recommendations
    
    async def get_table_statistics(self, table_name: str) -> Dict[str, Any]:
        """
        Get comprehensive statistics for a PostgreSQL table.
        
        Args:
            table_name: Name of the table
            
        Returns:
            Table statistics and metadata
        """
        logger.info(f"Getting statistics for table: {table_name}")
        
        try:
            # Get basic table info
            table_info_query = """
                SELECT 
                    schemaname,
                    tablename,
                    tableowner,
                    hasindexes,
                    hasrules,
                    hastriggers,
                    rowsecurity
                FROM pg_tables 
                WHERE tablename = %s
            """
            
            # Get table size
            size_query = """
                SELECT 
                    pg_size_pretty(pg_total_relation_size(%s)) as total_size,
                    pg_size_pretty(pg_relation_size(%s)) as table_size,
                    pg_size_pretty(pg_total_relation_size(%s) - pg_relation_size(%s)) as index_size
            """
            
            # Get row count estimate
            count_query = """
                SELECT reltuples::bigint as estimated_rows
                FROM pg_class 
                WHERE relname = %s
            """
            
            # Get column information
            columns_query = """
                SELECT 
                    column_name,
                    data_type,
                    is_nullable,
                    column_default,
                    character_maximum_length
                FROM information_schema.columns 
                WHERE table_name = %s
                ORDER BY ordinal_position
            """
            
            # Execute queries
            table_info = await execute_query(table_info_query.replace('%s', f"'{table_name}'"))
            size_info = await execute_query(size_query.replace('%s', f"'{table_name}'"))
            count_info = await execute_query(count_query.replace('%s', f"'{table_name}'"))
            columns_info = await execute_query(columns_query.replace('%s', f"'{table_name}'"))
            
            # Compile results
            statistics = {
                "table_name": table_name,
                "table_info": table_info[0] if table_info else {},
                "size_info": size_info[0] if size_info else {},
                "estimated_rows": count_info[0].get("estimated_rows", 0) if count_info else 0,
                "columns": columns_info,
                "column_count": len(columns_info),
                "has_primary_key": await self._check_primary_key(table_name),
                "indexes": await self._get_table_indexes(table_name)
            }
            
            logger.info(f"Table statistics collected for {table_name}: {statistics['estimated_rows']} rows, {statistics['column_count']} columns")
            return statistics
            
        except Exception as e:
            logger.error(f"Failed to get table statistics for {table_name}: {e}")
            raise
    
    async def _check_primary_key(self, table_name: str) -> bool:
        """Check if table has a primary key."""
        try:
            pk_query = """
                SELECT COUNT(*) as pk_count
                FROM information_schema.table_constraints 
                WHERE table_name = %s AND constraint_type = 'PRIMARY KEY'
            """
            result = await execute_query(pk_query.replace('%s', f"'{table_name}'"))
            return result[0].get("pk_count", 0) > 0 if result else False
        except Exception:
            return False
    
    async def _get_table_indexes(self, table_name: str) -> List[Dict[str, Any]]:
        """Get indexes for a table."""
        try:
            indexes_query = """
                SELECT 
                    indexname,
                    indexdef,
                    pg_size_pretty(pg_relation_size(indexname::regclass)) as index_size
                FROM pg_indexes 
                WHERE tablename = %s
            """
            result = await execute_query(indexes_query.replace('%s', f"'{table_name}'"))
            return result
        except Exception:
            return []
    
    async def optimize_table(self, table_name: str) -> Dict[str, Any]:
        """
        Perform table optimization operations.
        
        Args:
            table_name: Name of the table to optimize
            
        Returns:
            Optimization results
        """
        logger.info(f"Optimizing table: {table_name}")
        
        try:
            optimization_results = {
                "table_name": table_name,
                "operations_performed": [],
                "before_stats": {},
                "after_stats": {},
                "recommendations": []
            }
            
            # Get before statistics
            optimization_results["before_stats"] = await self.get_table_statistics(table_name)
            
            # Run ANALYZE to update statistics
            analyze_query = f"ANALYZE {table_name}"
            await execute_query(analyze_query)
            optimization_results["operations_performed"].append("ANALYZE")
            logger.info(f"ANALYZE completed for {table_name}")
            
            # Run VACUUM to reclaim space (in a real implementation, you might want to be more careful about this)
            vacuum_query = f"VACUUM ANALYZE {table_name}"
            await execute_query(vacuum_query)
            optimization_results["operations_performed"].append("VACUUM ANALYZE")
            logger.info(f"VACUUM ANALYZE completed for {table_name}")
            
            # Get after statistics
            optimization_results["after_stats"] = await self.get_table_statistics(table_name)
            
            # Generate recommendations
            optimization_results["recommendations"] = await self._generate_table_recommendations(table_name)
            
            logger.info(f"Table optimization completed for {table_name}")
            return optimization_results
            
        except Exception as e:
            logger.error(f"Failed to optimize table {table_name}: {e}")
            raise
    
    async def _generate_table_recommendations(self, table_name: str) -> List[str]:
        """Generate optimization recommendations for a table."""
        recommendations = []
        
        try:
            stats = await self.get_table_statistics(table_name)
            
            # Check for missing primary key
            if not stats.get("has_primary_key", False):
                recommendations.append("Consider adding a primary key to improve performance")
            
            # Check for large tables without indexes
            estimated_rows = stats.get("estimated_rows", 0)
            indexes = stats.get("indexes", [])
            if estimated_rows > 10000 and len(indexes) <= 1:  # Only primary key index
                recommendations.append("Large table with few indexes, consider adding indexes on frequently queried columns")
            
            # Check column types
            columns = stats.get("columns", [])
            for col in columns:
                if col.get("data_type") == "text" and not col.get("character_maximum_length"):
                    recommendations.append(f"Column '{col['column_name']}' uses TEXT type, consider VARCHAR with appropriate length")
            
        except Exception as e:
            logger.warning(f"Failed to generate recommendations for {table_name}: {e}")
        
        return recommendations
    
    async def validate_sql_syntax(self, sql: str) -> Dict[str, Any]:
        """
        Validate SQL syntax without executing the query.
        
        Args:
            sql: SQL query to validate
            
        Returns:
            Validation results
        """
        logger.info(f"Validating SQL syntax: {sql[:100]}...")
        
        try:
            # Use EXPLAIN to validate syntax without execution
            explain_query = f"EXPLAIN {sql}"
            
            try:
                await execute_query(explain_query)
                logger.info("SQL syntax validation passed")
                return {
                    "valid": True,
                    "error": None,
                    "warnings": []
                }
            except Exception as e:
                error_msg = str(e)
                logger.warning(f"SQL syntax validation failed: {error_msg}")
                return {
                    "valid": False,
                    "error": error_msg,
                    "warnings": self._extract_sql_warnings(error_msg)
                }
                
        except Exception as e:
            logger.error(f"Failed to validate SQL syntax: {e}")
            raise
    
    def _extract_sql_warnings(self, error_msg: str) -> List[str]:
        """Extract warnings from SQL error message."""
        warnings = []
        
        if "syntax error" in error_msg.lower():
            warnings.append("Syntax error detected")
        if "relation does not exist" in error_msg.lower():
            warnings.append("Referenced table or view does not exist")
        if "column does not exist" in error_msg.lower():
            warnings.append("Referenced column does not exist")
        if "permission denied" in error_msg.lower():
            warnings.append("Insufficient permissions")
            
        return warnings 
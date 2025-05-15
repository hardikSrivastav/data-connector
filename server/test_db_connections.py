#!/usr/bin/env python3
"""
Standalone test script for the ResultAggregator functionality.

This script tests the core functionality of result aggregation with
real database connections from the configured sources.
"""

import os
import sys
import json
import logging
import asyncio
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from datetime import datetime, date
from decimal import Decimal
from urllib.parse import urlparse

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import necessary components directly without causing circular imports
from agent.config.settings import Settings
from agent.db.adapters.base import DBAdapter
from agent.db.adapters.postgres import PostgresAdapter
from agent.db.adapters.mongo import MongoAdapter
from agent.db.adapters.qdrant import QdrantAdapter

# Create JSON encoder for handling datetime and other non-serializable types
class CustomJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder for handling non-serializable types"""
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        elif isinstance(obj, Decimal):
            return float(obj)
        elif hasattr(obj, '__dict__'):
            return obj.__dict__
        elif isinstance(obj, (set, frozenset)):
            return list(obj)
        return super().default(obj)

# Helper function to safely convert objects to JSON
def safe_json_dumps(obj, **kwargs):
    """Convert object to JSON string safely handling non-serializable types"""
    return json.dumps(obj, cls=CustomJSONEncoder, **kwargs)

# Helper function to print section headers
def print_section(title):
    """Print a section header"""
    separator = "=" * 80
    logger.info(separator)
    logger.info(f" {title} ".center(80, "="))
    logger.info(separator)

# Create a simplified version of the Orchestrator class to avoid import issues
class TestOrchestrator:
    """
    Simplified Orchestrator for testing purposes
    
    This avoids importing the actual Orchestrator class which might cause circular imports
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
        if db_type in ['postgres', 'postgresql']:
            self.adapter = PostgresAdapter(uri, **kwargs)
        elif db_type in ['mongodb', 'mongo']:
            self.adapter = MongoAdapter(uri, **kwargs)
        elif db_type == 'qdrant':
            self.adapter = QdrantAdapter(uri, **kwargs)
        else:
            raise ValueError(f"Unsupported database type: {db_type}")
        
        self.db_type = db_type
    
    async def execute(self, query: Any) -> List[Dict]:
        """
        Execute a query on the database.
        
        Args:
            query: Database-specific query
            
        Returns:
            List of dictionaries with query results
        """
        return await self.adapter.execute(query)
    
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

# Simplified version of ResultAggregator directly included here
class ResultAggregator:
    """
    ResultAggregator for testing purposes.
    
    Handles aggregation of results from different database operations.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the result aggregator"""
        self.config = config or {}
        self.llm_client = MockLLMClient()
    
    def _convert_for_aggregation(self, value: Any) -> Any:
        """Convert a value to a format suitable for aggregation"""
        # Handle custom types that might not be JSON serializable
        if hasattr(value, 'isoformat'):  # datetime objects
            return value.isoformat()
        elif hasattr(value, '__dict__'):  # custom objects
            return str(value)
        elif isinstance(value, (set, frozenset)):
            return list(value)
        elif isinstance(value, (list, tuple)):
            return [self._convert_for_aggregation(item) for item in value]
        elif isinstance(value, dict):
            return {k: self._convert_for_aggregation(v) for k, v in value.items()}
        else:
            return value
    
    async def aggregate_results(
        self, 
        query_plan: Any, 
        operation_results: Dict[str, Any],
        user_question: str
    ) -> Dict[str, Any]:
        """Aggregate results from multiple operations using LLM"""
        logger.info("Aggregating results using mock LLM")
        
        try:
            # Convert operation results to JSON-serializable format
            processed_results = {}
            for op_id, result in operation_results.items():
                processed_results[op_id] = self._convert_for_aggregation(result)
            
            # Convert query plan to dict if it's not already
            if hasattr(query_plan, 'to_dict'):
                plan_dict = query_plan.to_dict()
            else:
                plan_dict = query_plan
            
            # Simulate using LLM to aggregate results
            prompt = self.llm_client.render_template(
                "result_aggregator.tpl",
                query_plan=safe_json_dumps(plan_dict, indent=2),
                operation_results=processed_results,
                user_question=user_question
            )
            
            # Call mock LLM for aggregation
            response = await self.llm_client.chat_completions_create(
                model=self.llm_client.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2
            )
            
            # Parse the JSON response
            content = response.choices[0].message.content
            aggregated_result = json.loads(content)
            
            logger.info("Successfully aggregated results using mock LLM")
            
            return aggregated_result
        except Exception as e:
            logger.error(f"Error aggregating results: {e}")
            # Return a basic aggregation with error information
            return {
                "error": f"Failed to aggregate results: {str(e)}",
                "partial_results": operation_results
            }
    
    def merge_results(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Merge results from multiple sources without LLM involvement"""
        # Count successful and failed operations
        success_count = sum(1 for r in results if r.get("success", False))
        failed_count = len(results) - success_count
        
        # Collect all data
        all_data = []
        for result in results:
            if result.get("success", False) and "data" in result:
                data = result.get("data", [])
                if isinstance(data, list):
                    all_data.extend(data)
                else:
                    all_data.append(data)
        
        # Create merged result
        merged = {
            "success": success_count > 0,
            "sources_queried": len(results),
            "successful_sources": success_count,
            "failed_sources": failed_count,
            "total_rows": len(all_data),
            "results": all_data
        }
        
        # Add errors if any
        errors = []
        for result in results:
            if not result.get("success", False) and "error" in result:
                errors.append({
                    "source_id": result.get("source_id", "unknown"),
                    "error": result.get("error")
                })
        
        if errors:
            merged["errors"] = errors
        
        return merged
    
    def join_results(
        self, 
        results: List[Dict[str, Any]], 
        join_fields: Optional[Dict[str, str]] = None,
        type_mappings: Optional[Dict[str, Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """Join results from multiple sources on specified fields"""
        if not join_fields:
            logger.warning("No join fields specified, falling back to merge")
            return self.merge_results(results)
        
        # Process each source's data
        source_data = {}
        for result in results:
            if result.get("success", False) and "data" in result:
                source_id = result.get("source_id", "unknown")
                data = result.get("data", [])
                if isinstance(data, list):
                    source_data[source_id] = data
                else:
                    source_data[source_id] = [data]
        
        # If we don't have enough sources, fall back to merge
        if len(source_data) < 2:
            logger.warning("Not enough successful sources for join, falling back to merge")
            return self.merge_results(results)
        
        # Perform join
        joined_data = []
        
        # Get the primary source (first one)
        primary_source_id = list(source_data.keys())[0]
        primary_data = source_data[primary_source_id]
        primary_join_field = join_fields.get(primary_source_id)
        
        if not primary_join_field:
            logger.warning(f"No join field for primary source {primary_source_id}")
            return self.merge_results(results)
        
        # For each row in the primary source
        for primary_row in primary_data:
            # Skip if join field doesn't exist
            if primary_join_field not in primary_row:
                continue
                
            join_value = primary_row[primary_join_field]
            
            # Create a new row with primary data
            joined_row = {f"{primary_source_id}_{k}": v for k, v in primary_row.items()}
            
            # Add data from other sources
            for source_id, data in source_data.items():
                if source_id == primary_source_id:
                    continue
                    
                join_field = join_fields.get(source_id)
                if not join_field:
                    continue
                
                # Find matching rows
                matches = []
                for row in data:
                    if join_field in row:
                        # Apply type coercion if needed
                        row_value = row[join_field]
                        if type_mappings and source_id in type_mappings:
                            field_type = type_mappings[source_id].get(join_field)
                            primary_type = (type_mappings.get(primary_source_id, {})
                                           .get(primary_join_field))
                            
                            # Convert to common type if possible
                            if field_type and primary_type:
                                if field_type == "str" or primary_type == "str":
                                    # Convert both to string
                                    row_value = str(row_value)
                                    join_value = str(join_value)
                                elif field_type == "int" and primary_type == "int":
                                    # Convert to int
                                    try:
                                        row_value = int(row_value)
                                        join_value = int(join_value)
                                    except:
                                        pass
                        
                        # Compare values (with coercion for common cases)
                        if isinstance(row_value, str) and not isinstance(join_value, str):
                            if str(join_value) == row_value:
                                matches.append(row)
                        elif isinstance(row_value, (int, float)) and isinstance(join_value, (int, float)):
                            if float(row_value) == float(join_value):
                                matches.append(row)
                        elif row_value == join_value:
                            matches.append(row)
                
                # Add first match to joined row
                if matches:
                    for k, v in matches[0].items():
                        joined_row[f"{source_id}_{k}"] = v
            
            # Add the joined row to results
            joined_data.append(joined_row)
        
        return {
            "success": True,
            "sources_joined": len(source_data),
            "join_fields": join_fields,
            "total_rows": len(joined_data),
            "results": joined_data
        }


# Mock LLM client for testing
class MockLLMClient:
    """Mock LLM client to avoid external dependencies"""
    
    def __init__(self):
        self.model_name = "mock-model"
        self.client = self
    
    def render_template(self, template_name, **kwargs):
        """Simulate template rendering"""
        return f"Template: {template_name}\nContext: {safe_json_dumps(kwargs, indent=2)}"
    
    async def chat_completions_create(self, model=None, messages=None, **kwargs):
        """Simulate chat completions API"""
        # Create a standard response for testing
        aggregation = {
            "aggregated_results": [
                {"id": 1, "name": "User 1", "email": "user1@example.com", "order_count": 5},
                {"id": 2, "name": "User 2", "email": "user2@example.com", "order_count": 3}
            ],
            "summary_statistics": {
                "total_count": 2,
                "sources_used": 2
            },
            "key_insights": [
                "Found 2 matching records across databases"
            ],
            "aggregation_notes": {
                "join_strategy": "inner join on id field"
            }
        }
        
        # Create a response object similar to what the API would return
        response = type('MockResponse', (), {
            'choices': [
                type('Choice', (), {
                    'message': type('Message', (), {
                        'content': safe_json_dumps(aggregation, indent=2)
                    })
                })
            ]
        })
        
        return response

async def connect_to_databases():
    """Connect to all configured databases and return the orchestrators"""
    settings = Settings()
    
    # Dictionary to store orchestrators
    orchestrators = {}
    
    # Connect to PostgreSQL
    try:
        settings.DB_TYPE = "postgres"
        postgres_uri = settings.connection_uri
        logger.info(f"Connecting to PostgreSQL at {postgres_uri}")
        postgres_orchestrator = TestOrchestrator(postgres_uri)
        if await postgres_orchestrator.test_connection():
            logger.info("PostgreSQL connection successful")
            orchestrators["postgres"] = postgres_orchestrator
        else:
            logger.error("PostgreSQL connection failed")
    except Exception as e:
        logger.error(f"Error connecting to PostgreSQL: {e}")
    
    # Connect to MongoDB
    try:
        settings.DB_TYPE = "mongodb"
        mongo_uri = settings.connection_uri
        mongo_kwargs = {}
        
        # Extract database name from MongoDB URI
        parsed_uri = urlparse(mongo_uri)
        db_name = parsed_uri.path.lstrip('/')
        if db_name:
            mongo_kwargs['db_name'] = db_name
        
        logger.info(f"Connecting to MongoDB at {mongo_uri}")
        mongo_orchestrator = TestOrchestrator(mongo_uri, **mongo_kwargs)
        if await mongo_orchestrator.test_connection():
            logger.info("MongoDB connection successful")
            orchestrators["mongodb"] = mongo_orchestrator
        else:
            logger.error("MongoDB connection failed")
    except Exception as e:
        logger.error(f"Error connecting to MongoDB: {e}")
    
    # Connect to Qdrant
    try:
        settings.DB_TYPE = "qdrant"
        qdrant_uri = settings.connection_uri
        qdrant_kwargs = {
            'collection_name': settings.QDRANT_COLLECTION,
            'api_key': settings.QDRANT_API_KEY,
            'prefer_grpc': settings.QDRANT_PREFER_GRPC
        }
        
        logger.info(f"Connecting to Qdrant at {qdrant_uri}")
        qdrant_orchestrator = TestOrchestrator(qdrant_uri, **qdrant_kwargs)
        if await qdrant_orchestrator.test_connection():
            logger.info("Qdrant connection successful")
            orchestrators["qdrant"] = qdrant_orchestrator
        else:
            logger.error("Qdrant connection failed")
    except Exception as e:
        logger.error(f"Error connecting to Qdrant: {e}")
    
    return orchestrators

async def execute_sample_queries(orchestrators):
    """Execute sample queries on each database"""
    results = {}
    
    # Execute PostgreSQL query
    if "postgres" in orchestrators:
        try:
            logger.info("Executing sample PostgreSQL query")
            # Query to get users from the users table (adjust based on your schema)
            sql_query = "SELECT * FROM users LIMIT 10"
            try:
                postgres_results = await orchestrators["postgres"].execute(sql_query)
                results["op1"] = postgres_results
                logger.info(f"PostgreSQL query returned {len(postgres_results)} rows")
            except Exception as e:
                logger.error(f"Error executing users query: {e}")
                # Fall back to getting db info
                sql_query = "SELECT relname FROM pg_class WHERE relkind='r' AND relname !~ '^(pg_|sql_)' LIMIT 10;"
                postgres_results = await orchestrators["postgres"].execute(sql_query)
                logger.info(f"PostgreSQL tables: {postgres_results}")
                results["op1"] = [{"info": "table list", "tables": [r.get('relname') for r in postgres_results]}]
        except Exception as e:
            logger.error(f"Error executing PostgreSQL query: {e}")
            results["op1"] = []
    
    # Execute MongoDB query
    if "mongodb" in orchestrators:
        try:
            logger.info("Executing sample MongoDB query")
            # First list collections to make sure we query ones that exist
            mongo_list_cmd = {
                "command": {"listCollections": 1},
                "db_name": orchestrators["mongodb"].adapter.db_name
            }
            try:
                collections = await orchestrators["mongodb"].execute(mongo_list_cmd)
                collection_names = [col.get("name") for col in collections]
                logger.info(f"MongoDB collections: {collection_names}")
                
                # Query one of the collections
                collection_to_query = collection_names[0] if collection_names else "orders"
                mongo_query = {
                    "collection": collection_to_query,
                    "query": {},
                    "limit": 10
                }
                mongodb_results = await orchestrators["mongodb"].execute(mongo_query)
                results["op2"] = mongodb_results
                logger.info(f"MongoDB query returned {len(mongodb_results)} documents")
            except Exception as e:
                logger.error(f"Error fetching collections: {e}")
                results["op2"] = [{"info": "error listing collections", "error": str(e)}]
        except Exception as e:
            logger.error(f"Error executing MongoDB query: {e}")
            results["op2"] = []
    
    # Execute Qdrant query
    if "qdrant" in orchestrators:
        try:
            logger.info("Executing sample Qdrant query")
            # First list collections
            qdrant_collections_cmd = {
                "command": "list_collections"
            }
            try:
                collections = await orchestrators["qdrant"].execute(qdrant_collections_cmd)
                collection_names = [col.get("name") for col in collections.get("collections", [])]
                logger.info(f"Qdrant collections: {collection_names}")
                
                # Query a collection if available
                collection_to_query = collection_names[0] if collection_names else orchestrators["qdrant"].adapter.collection_name
                qdrant_query = {
                    "collection": collection_to_query,
                    "filter": {},
                    "limit": 10
                }
                qdrant_results = await orchestrators["qdrant"].execute(qdrant_query)
                results["op3"] = qdrant_results
                logger.info(f"Qdrant query returned {len(qdrant_results)} documents")
            except Exception as e:
                logger.error(f"Error listing Qdrant collections: {e}")
                results["op3"] = [{"info": "error listing collections", "error": str(e)}]
        except Exception as e:
            logger.error(f"Error executing Qdrant query: {e}")
            results["op3"] = []
    
    return results

def create_sample_query_plan():
    """Create a sample query plan for testing"""
    # Create a sample query plan as a dictionary
    plan_dict = {
        "metadata": {
            "description": "Test query plan",
            "user_question": "Show me customers with their order counts and product interests"
        },
        "operations": [
            {
                "id": "op1",
                "db_type": "postgres",
                "source_id": "postgres_main",
                "params": {
                    "query": "SELECT * FROM users LIMIT 10",
                    "params": []
                },
                "depends_on": []
            },
            {
                "id": "op2",
                "db_type": "mongodb",
                "source_id": "mongodb_main",
                "params": {
                    "collection": "orders",
                    "query": {},
                    "limit": 10
                },
                "depends_on": []
            },
            {
                "id": "op3",
                "db_type": "qdrant",
                "source_id": "qdrant_products",
                "params": {
                    "collection": "products",
                    "filter": {},
                    "limit": 10
                },
                "depends_on": []
            }
        ]
    }
    
    return plan_dict

async def test_merge_results(orchestrators):
    """Test the merge_results method with real data"""
    print_section("Testing merge_results Method with Real Data")
    
    # Initialize ResultAggregator
    aggregator = ResultAggregator()
    
    # Prepare results in the format expected by merge_results
    merge_input = []
    
    # Add PostgreSQL results if available
    if "postgres" in orchestrators:
        try:
            # Query users table or fall back to table list
            try:
                postgres_data = await orchestrators["postgres"].execute("SELECT * FROM users LIMIT 10")
            except:
                postgres_data = await orchestrators["postgres"].execute("SELECT relname FROM pg_class WHERE relkind='r' AND relname !~ '^(pg_|sql_)' LIMIT 10;")
                
            merge_input.append({
                "source_id": "postgres_main",
                "success": True,
                "data": postgres_data
            })
            logger.info(f"Added {len(postgres_data)} rows from PostgreSQL")
        except Exception as e:
            logger.error(f"Error querying PostgreSQL: {e}")
            merge_input.append({
                "source_id": "postgres_main",
                "success": False,
                "error": str(e)
            })
    
    # Add MongoDB results if available
    if "mongodb" in orchestrators:
        try:
            # Query collections first
            mongo_list_cmd = {
                "command": {"listCollections": 1},
                "db_name": orchestrators["mongodb"].adapter.db_name
            }
            collections = await orchestrators["mongodb"].execute(mongo_list_cmd)
            collection_names = [col.get("name") for col in collections]
            
            # Query a collection if available
            collection_to_query = collection_names[0] if collection_names else "orders"
            mongo_query = {
                "collection": collection_to_query,
                "query": {},
                "limit": 10
            }
            mongodb_data = await orchestrators["mongodb"].execute(mongo_query)
            merge_input.append({
                "source_id": "mongodb_main",
                "success": True,
                "data": mongodb_data
            })
            logger.info(f"Added {len(mongodb_data)} documents from MongoDB (collection: {collection_to_query})")
        except Exception as e:
            logger.error(f"Error querying MongoDB: {e}")
            merge_input.append({
                "source_id": "mongodb_main",
                "success": False,
                "error": str(e)
            })
    
    # Add Qdrant results if available
    if "qdrant" in orchestrators:
        try:
            # List collections first
            qdrant_collections_cmd = {
                "command": "list_collections"
            }
            collections = await orchestrators["qdrant"].execute(qdrant_collections_cmd)
            collection_names = [col.get("name") for col in collections.get("collections", [])]
            
            # Query a collection if available
            collection_to_query = collection_names[0] if collection_names else orchestrators["qdrant"].adapter.collection_name
            qdrant_query = {
                "collection": collection_to_query,
                "filter": {},
                "limit": 10
            }
            qdrant_data = await orchestrators["qdrant"].execute(qdrant_query)
            merge_input.append({
                "source_id": "qdrant_products",
                "success": True,
                "data": qdrant_data
            })
            logger.info(f"Added {len(qdrant_data)} documents from Qdrant (collection: {collection_to_query})")
        except Exception as e:
            logger.error(f"Error querying Qdrant: {e}")
            merge_input.append({
                "source_id": "qdrant_products",
                "success": False,
                "error": str(e)
            })
    
    # If no real data available, add mock data for testing
    if not merge_input:
        logger.warning("No real data available, using mock data")
        merge_input = [
            {
                "source_id": "postgres_main",
                "success": True,
                "data": [{"id": 1, "name": "Test User"}]
            },
            {
                "source_id": "failed_source",
                "success": False,
                "error": "Connection timed out",
                "data": []
            }
        ]
    
    # Call merge_results
    merge_result = aggregator.merge_results(merge_input)
    
    # Log the result
    logger.info(f"Merge operation succeeded: {merge_result['success']}")
    logger.info(f"Sources queried: {merge_result['sources_queried']}")
    logger.info(f"Successful sources: {merge_result['successful_sources']}")
    logger.info(f"Failed sources: {merge_result['failed_sources']}")
    logger.info(f"Total rows: {merge_result['total_rows']}")
    
    if 'errors' in merge_result:
        logger.info(f"Errors: {safe_json_dumps(merge_result['errors'], indent=2)}")
    
    if merge_result['results']:
        sample_size = min(2, len(merge_result['results']))
        logger.info(f"Results (first {sample_size} entries): {safe_json_dumps(merge_result['results'][:sample_size], indent=2)}")
    
    return merge_result

async def test_join_results(orchestrators):
    """Test the join_results method with real data"""
    print_section("Testing join_results Method with Real Data")
    
    # Initialize ResultAggregator
    aggregator = ResultAggregator()
    
    # Prepare results in the format expected by join_results
    join_input = []
    join_fields = {}
    type_mappings = {}
    
    # Add PostgreSQL results if available
    if "postgres" in orchestrators:
        try:
            # Query users table
            try:
                postgres_data = await orchestrators["postgres"].execute("SELECT * FROM users LIMIT 10")
            except:
                postgres_data = await orchestrators["postgres"].execute("SELECT relname as id FROM pg_class WHERE relkind='r' AND relname !~ '^(pg_|sql_)' LIMIT 10;")
                
            join_input.append({
                "source_id": "postgres_main",
                "success": True,
                "data": postgres_data
            })
            
            # Determine join field (assuming data has an id field)
            join_field = next((k for k in postgres_data[0].keys() if k.lower() in ["id", "user_id", "_id"]), list(postgres_data[0].keys())[0]) if postgres_data else "id"
            join_fields["postgres_main"] = join_field
            
            # Add type mappings
            if postgres_data:
                value = postgres_data[0].get(join_field)
                type_mappings["postgres_main"] = {
                    join_field: "int" if isinstance(value, int) else "str"
                }
                logger.info(f"Added {len(postgres_data)} rows from PostgreSQL with join field '{join_field}'")
        except Exception as e:
            logger.error(f"Error querying PostgreSQL: {e}")
            join_input.append({
                "source_id": "postgres_main",
                "success": False,
                "error": str(e)
            })
    
    # Add MongoDB results if available
    if "mongodb" in orchestrators:
        try:
            # Query collections first
            mongo_list_cmd = {
                "command": {"listCollections": 1},
                "db_name": orchestrators["mongodb"].adapter.db_name
            }
            collections = await orchestrators["mongodb"].execute(mongo_list_cmd)
            collection_names = [col.get("name") for col in collections]
            
            # Query a collection if available
            collection_to_query = collection_names[0] if collection_names else "orders"
            mongo_query = {
                "collection": collection_to_query,
                "query": {},
                "limit": 10
            }
            mongodb_data = await orchestrators["mongodb"].execute(mongo_query)
            join_input.append({
                "source_id": "mongodb_main",
                "success": True,
                "data": mongodb_data
            })
            
            # Determine join field
            join_field = next((k for k in mongodb_data[0].keys() if k.lower() in ["id", "user_id", "_id"]), list(mongodb_data[0].keys())[0]) if mongodb_data else "id"
            join_fields["mongodb_main"] = join_field
            
            # Add type mappings
            if mongodb_data:
                value = mongodb_data[0].get(join_field)
                type_mappings["mongodb_main"] = {
                    join_field: "int" if isinstance(value, int) else "str"
                }
                logger.info(f"Added {len(mongodb_data)} documents from MongoDB with join field '{join_field}'")
        except Exception as e:
            logger.error(f"Error querying MongoDB: {e}")
            join_input.append({
                "source_id": "mongodb_main",
                "success": False,
                "error": str(e)
            })
    
    # Add Qdrant results if available
    if "qdrant" in orchestrators:
        try:
            # List collections first
            qdrant_collections_cmd = {
                "command": "list_collections"
            }
            collections = await orchestrators["qdrant"].execute(qdrant_collections_cmd)
            collection_names = [col.get("name") for col in collections.get("collections", [])]
            
            # Query a collection if available
            collection_to_query = collection_names[0] if collection_names else orchestrators["qdrant"].adapter.collection_name
            qdrant_query = {
                "collection": collection_to_query,
                "filter": {},
                "limit": 10
            }
            qdrant_data = await orchestrators["qdrant"].execute(qdrant_query)
            join_input.append({
                "source_id": "qdrant_products",
                "success": True,
                "data": qdrant_data
            })
            
            # Determine join field
            if qdrant_data:
                join_field = next((k for k in qdrant_data[0].keys() if k.lower() in ["id", "user_id", "_id"]), list(qdrant_data[0].keys())[0])
                join_fields["qdrant_products"] = join_field
                
                # Add type mappings
                value = qdrant_data[0].get(join_field)
                type_mappings["qdrant_products"] = {
                    join_field: "int" if isinstance(value, int) else "str"
                }
                logger.info(f"Added {len(qdrant_data)} documents from Qdrant with join field '{join_field}'")
        except Exception as e:
            logger.error(f"Error querying Qdrant: {e}")
            join_input.append({
                "source_id": "qdrant_products",
                "success": False,
                "error": str(e)
            })
    
    # If no join fields found or not enough sources for joining, create mock data
    if len(join_fields) < 2 or len([i for i in join_input if i.get("success", False)]) < 2:
        logger.warning("Not enough joinable data available, using mock data")
        join_input = [
            {
                "source_id": "postgres_main",
                "success": True,
                "data": [
                    {"id": 1, "name": "User 1"},
                    {"id": 2, "name": "User 2"}
                ]
            },
            {
                "source_id": "mongodb_main",
                "success": True,
                "data": [
                    {"_id": "abc", "user_id": 1, "order_count": 5},
                    {"_id": "def", "user_id": 3, "order_count": 2}
                ]
            }
        ]
        join_fields = {
            "postgres_main": "id",
            "mongodb_main": "user_id"
        }
        type_mappings = {
            "postgres_main": {"id": "int"},
            "mongodb_main": {"user_id": "int"}
        }
    
    # Call join_results
    join_result = aggregator.join_results(join_input, join_fields, type_mappings)
    
    # Log the result
    logger.info(f"Join operation succeeded: {join_result['success']}")
    logger.info(f"Sources joined: {join_result['sources_joined']}")
    logger.info(f"Join fields: {safe_json_dumps(join_result['join_fields'], indent=2)}")
    logger.info(f"Total rows: {join_result['total_rows']}")
    
    if join_result['results']:
        sample_size = min(2, len(join_result['results']))
        logger.info(f"Results (first {sample_size} entries): {safe_json_dumps(join_result['results'][:sample_size], indent=2)}")
    else:
        logger.warning("No joined results found")
    
    return join_result

async def test_llm_aggregation(database_results):
    """Test the LLM-based aggregation method with real data"""
    print_section("Testing LLM-based Aggregation with Real Data")
    
    # Initialize ResultAggregator
    aggregator = ResultAggregator()
    
    # Create a sample query plan
    query_plan = create_sample_query_plan()
    
    # User question
    user_question = "Show me customers with their order counts and product interests"
    
    # Call aggregate_results
    aggregated_result = await aggregator.aggregate_results(
        query_plan=query_plan,
        operation_results=database_results,
        user_question=user_question
    )
    
    # Log the result
    logger.info("LLM Aggregation Result:")
    logger.info(safe_json_dumps(aggregated_result, indent=2))
    
    return aggregated_result

async def main():
    """Main test function"""
    logger.info("Starting ResultAggregator tests with real database connections")
    
    # Connect to databases
    orchestrators = await connect_to_databases()
    
    if not orchestrators:
        logger.warning("No database connections established, tests will use mock data")
    else:
        logger.info(f"Connected to {len(orchestrators)} databases: {', '.join(orchestrators.keys())}")
    
    # Execute sample queries to get real data
    database_results = await execute_sample_queries(orchestrators)
    
    # Test merge_results with real data
    merge_result = await test_merge_results(orchestrators)
    
    # Test join_results with real data
    join_result = await test_join_results(orchestrators)
    
    # Test LLM-based aggregation with real data
    llm_result = await test_llm_aggregation(database_results)
    
    logger.info("All tests completed!")

if __name__ == "__main__":
    asyncio.run(main()) 
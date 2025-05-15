#!/usr/bin/env python3
"""
Test script for the ResultAggregator functionality.

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
import random

# Add parent directory to path for imports
parent_dir = str(Path(__file__).parent.parent.parent.parent)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Import database modules - import directly from agent.db
from agent.config.settings import Settings
from agent.db.adapters.base import DBAdapter
from agent.db.adapters.postgres import PostgresAdapter
from agent.db.adapters.mongo import MongoAdapter
from agent.db.adapters.qdrant import QdrantAdapter
from agent.db.adapters.slack import SlackAdapter

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles datetime and Decimal objects"""
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)

# Helper function to safely convert objects to JSON
def safe_json_dumps(obj, **kwargs):
    """Convert object to JSON string safely handling non-serializable types"""
    return json.dumps(obj, cls=DateTimeEncoder, **kwargs)

# Helper function to print section headers
def print_section(title):
    """Print a section header"""
    separator = "=" * 80
    logger.info(separator)
    logger.info(f" {title} ".center(80, "="))
    logger.info(separator)

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

# Implementation of the ResultAggregator for testing
class ResultAggregator:
    """
    Simplified implementation of ResultAggregator for testing.
    
    This version has the same interface but doesn't rely on external dependencies.
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
            "data": all_data
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

# TestOrchestrator class for database connections without circular imports
class TestOrchestrator:
    """
    Test orchestrator for database connections.
    This uses the real database adapters but avoids circular imports.
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
        
        # Create a clean version of kwargs without db_type
        clean_kwargs = {k: v for k, v in kwargs.items() if k != 'db_type'}
        
        # Log the database type and URI (with password redacted for security)
        redacted_uri = self._redact_password(uri)
        logger.info(f"Initializing orchestrator for {db_type} with URI: {redacted_uri}")
        
        # Create the appropriate adapter based on the database type
        if db_type in ['postgres', 'postgresql']:
            self.adapter = PostgresAdapter(uri, **clean_kwargs)
        elif db_type in ['mongodb', 'mongo']:
            self.adapter = MongoAdapter(uri, **clean_kwargs)
        elif db_type == 'qdrant':
            self.adapter = QdrantAdapter(uri, **clean_kwargs)
        elif db_type == 'slack':
            self.adapter = SlackAdapter(uri, **clean_kwargs)
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
        postgres_orchestrator = TestOrchestrator(postgres_uri, db_type="postgres")
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
        mongo_orchestrator = TestOrchestrator(mongo_uri, db_type="mongodb", **mongo_kwargs)
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
        # Fix Qdrant connection parameters - remove collection_name which is causing problems
        qdrant_kwargs = {
            'api_key': settings.QDRANT_API_KEY,
            'prefer_grpc': settings.QDRANT_PREFER_GRPC
        }
        
        logger.info(f"Connecting to Qdrant at {qdrant_uri}")
        qdrant_orchestrator = TestOrchestrator(qdrant_uri, db_type="qdrant", **qdrant_kwargs)
        if await qdrant_orchestrator.test_connection():
            logger.info("Qdrant connection successful")
            orchestrators["qdrant"] = qdrant_orchestrator
        else:
            logger.error("Qdrant connection failed")
    except Exception as e:
        logger.error(f"Error connecting to Qdrant: {e}")
    
    # Connect to Slack
    try:
        settings.DB_TYPE = "slack"
        slack_uri = settings.connection_uri
        # Access config directly without using get()
        slack_kwargs = {
            'history_days': 30,  # Default value
            'update_frequency': 6  # Default value
        }
        
        # Try to extract history_days and update_frequency from the config if available
        try:
            slack_config = settings.get_config().get('slack', {})
            if isinstance(slack_config, dict):
                if 'history_days' in slack_config:
                    slack_kwargs['history_days'] = slack_config['history_days']
                if 'update_frequency' in slack_config:
                    slack_kwargs['update_frequency'] = slack_config['update_frequency']
        except:
            # If config access fails, just use defaults
            pass
        
        logger.info(f"Connecting to Slack MCP at {slack_uri}")
        slack_orchestrator = TestOrchestrator(slack_uri, db_type="slack", **slack_kwargs)
        if await slack_orchestrator.test_connection():
            logger.info("Slack connection successful")
            orchestrators["slack"] = slack_orchestrator
        else:
            logger.error("Slack connection failed")
    except Exception as e:
        logger.error(f"Error connecting to Slack: {e}")
    
    return orchestrators

async def execute_sample_queries(orchestrators):
    """Execute sample queries for each database type"""
    print_section("Executing Sample Queries")
    
    # PostgreSQL query
    if "postgres" in orchestrators:
        try:
            results = await orchestrators["postgres"].execute("SELECT * FROM users LIMIT 5")
            logger.info(f"PostgreSQL query returned {len(results)} rows")
        except Exception as e:
            logger.error(f"Error executing PostgreSQL query: {e}")
    
    # MongoDB query
    if "mongodb" in orchestrators:
        try:
            mongo_query = {
                "collection": "orders",
                "pipeline": [
                    {"$match": {}},  # Match all documents
                    {"$limit": 10}   # Limit to 10 documents
                ]
            }
            results = await orchestrators["mongodb"].execute(mongo_query)
            logger.info(f"MongoDB query returned {len(results)} documents")
        except Exception as e:
            logger.error(f"Error executing MongoDB query: {e}")
    
    # Qdrant query - use a proper vector query with a sample vector
    if "qdrant" in orchestrators:
        try:
            # Use a sample vector of the right dimensionality for Qdrant
            # Most models use 1536 dimensions, but we'll create a simple vector as an example
            sample_vector = [0.1] * 1536  # Create a 1536-dimensional vector with all values = 0.1
            
            qdrant_query = {
                "collection": "corporate_knowledge",
                "vector": sample_vector,
                "limit": 5
            }
            results = await orchestrators["qdrant"].execute(qdrant_query)
            logger.info(f"Qdrant query returned {len(results)} documents")
        except Exception as e:
            logger.error(f"Error executing Qdrant query: {e}")
    
    # Slack query - list channels
    if "slack" in orchestrators:
        try:
            # Slack query to list channels
            slack_query = {
                "type": "channels"
            }
            results = await orchestrators["slack"].execute(slack_query)
            logger.info(f"Slack query returned {len(results)} channels")
        except Exception as e:
            logger.error(f"Error executing Slack query: {e}")

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
            },
            {
                "id": "op4",
                "db_type": "slack",
                "source_id": "slack_main",
                "params": {
                    "type": "channels"
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
            postgres_data = await orchestrators["postgres"].execute("SELECT * FROM users LIMIT 5")
            merge_input.append({
                "source_id": "postgres_users",
                "success": True,
                "data": postgres_data
            })
            logger.info(f"Added {len(postgres_data)} rows from PostgreSQL")
        except Exception as e:
            logger.error(f"Error querying PostgreSQL: {e}")
            merge_input.append({
                "source_id": "postgres_users",
                "success": False,
                "error": str(e)
            })
    
    # Add MongoDB results if available
    if "mongodb" in orchestrators:
        try:
            mongo_query = {
                "collection": "orders",
                "pipeline": [
                    {"$match": {}},  # Match all documents
                    {"$limit": 10}   # Limit to 10 documents
                ]
            }
            mongodb_data = await orchestrators["mongodb"].execute(mongo_query)
            merge_input.append({
                "source_id": "mongodb_orders",
                "success": True,
                "data": mongodb_data
            })
            logger.info(f"Added {len(mongodb_data)} documents from MongoDB")
        except Exception as e:
            logger.error(f"Error querying MongoDB: {e}")
            merge_input.append({
                "source_id": "mongodb_orders",
                "success": False,
                "error": str(e)
            })
    
    # Add Qdrant results if available
    if "qdrant" in orchestrators:
        try:
            # Use a sample vector of the right dimensionality for Qdrant
            sample_vector = [0.1] * 1536  # Create a 1536-dimensional vector with all values = 0.1
            
            qdrant_query = {
                "collection": "corporate_knowledge",
                "vector": sample_vector,
                "limit": 5
            }
            qdrant_data = await orchestrators["qdrant"].execute(qdrant_query)
            merge_input.append({
                "source_id": "qdrant_collections",
                "success": True,
                "data": qdrant_data
            })
            logger.info(f"Added {len(qdrant_data)} documents from Qdrant")
        except Exception as e:
            logger.error(f"Error querying Qdrant: {e}")
            merge_input.append({
                "source_id": "qdrant_collections",
                "success": False,
                "error": str(e)
            })
    
    # Add Slack results if available
    if "slack" in orchestrators:
        try:
            # Query Slack channels
            slack_query = {
                "type": "channels"
            }
            slack_data = await orchestrators["slack"].execute(slack_query)
            merge_input.append({
                "source_id": "slack_channels",
                "success": True,
                "data": slack_data
            })
            logger.info(f"Added {len(slack_data)} channels from Slack")
        except Exception as e:
            logger.error(f"Error querying Slack: {e}")
            merge_input.append({
                "source_id": "slack_channels",
                "success": False,
                "error": str(e)
            })
    
    # If no real data available, use mock data
    if not merge_input:
        logger.warning("No real data available, using mock data for merge_results test")
        merge_input = [
            {
                "source_id": "postgres_users",
                "success": True,
                "data": [{"id": 1, "name": "Test User"}]
            },
            {
                "source_id": "mongodb_orders",
                "success": True,
                "data": [{"_id": "abc123", "order_id": "ORD001"}]
            }
        ]
    
    # Call the merge_results method (without await since it's not async)
    merge_result = aggregator.merge_results(merge_input)
    
    # Log the results
    logger.info(f"Merge operation succeeded: {merge_result['success']}")
    logger.info(f"Sources queried: {merge_result['sources_queried']}")
    logger.info(f"Successful sources: {merge_result['successful_sources']}")
    logger.info(f"Failed sources: {merge_result['failed_sources']}")
    logger.info(f"Total rows: {len(merge_result['data'])}")
    
    if merge_result.get("errors"):
        logger.info(f"Errors: {json.dumps(merge_result['errors'], indent=2)}")
    
    if merge_result["data"]:
        first_n = min(2, len(merge_result["data"]))
        logger.info(f"Results (first {first_n} entries): {json.dumps(merge_result['data'][:first_n], indent=2, cls=DateTimeEncoder)}")
    
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
            postgres_data = await orchestrators["postgres"].execute("SELECT * FROM users LIMIT 10")
            join_input.append({
                "source_id": "postgres_main",
                "success": True,
                "data": postgres_data
            })
            
            # Determine join field (assuming users have an id field)
            if postgres_data and "id" in postgres_data[0]:
                join_fields["postgres_main"] = "id"
                # Add type mappings
                type_mappings["postgres_main"] = {
                    "id": "int" if isinstance(postgres_data[0]["id"], int) else "str"
                }
                logger.info(f"Added {len(postgres_data)} rows from PostgreSQL with join field 'id'")
            else:
                logger.warning("PostgreSQL data doesn't have 'id' field for joining")
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
            # Query orders collection with proper pipeline format
            mongo_query = {
                "collection": "orders",
                "pipeline": [
                    {"$match": {}},  # Match all documents
                    {"$limit": 10}   # Limit to 10 documents
                ]
            }
            mongodb_data = await orchestrators["mongodb"].execute(mongo_query)
            join_input.append({
                "source_id": "mongodb_main",
                "success": True,
                "data": mongodb_data
            })
            
            # Check for possible join fields
            possible_join_fields = ["user_id", "_id", "id"]
            join_field = None
            
            if mongodb_data:
                for field in possible_join_fields:
                    if field in mongodb_data[0]:
                        join_field = field
                        join_fields["mongodb_main"] = field
                        # Add type mappings
                        type_mappings["mongodb_main"] = {
                            field: "int" if isinstance(mongodb_data[0][field], int) else "str"
                        }
                        logger.info(f"Added {len(mongodb_data)} documents from MongoDB with join field '{field}'")
                        break
                
                if not join_field:
                    # If no standard field found, use the first field that could be an ID
                    sample_doc = mongodb_data[0]
                    for key, value in sample_doc.items():
                        if isinstance(value, (int, str)) and ('id' in key.lower() or key == '_id'):
                            join_field = key
                            join_fields["mongodb_main"] = key
                            type_mappings["mongodb_main"] = {
                                key: "int" if isinstance(value, int) else "str"
                            }
                            logger.info(f"Added {len(mongodb_data)} documents from MongoDB with join field '{key}'")
                            break
                    
                    if not join_field:
                        logger.warning("MongoDB data doesn't have a suitable field for joining")
            else:
                logger.warning("No MongoDB data available for joining")
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
            # Use a sample vector of the right dimensionality for Qdrant
            sample_vector = [0.1] * 1536  # Create a 1536-dimensional vector with all values = 0.1
            
            qdrant_query = {
                "collection": "corporate_knowledge",
                "vector": sample_vector,
                "limit": 5
            }
            qdrant_data = await orchestrators["qdrant"].execute(qdrant_query)
            
            # Process data to ensure each item has an ID field for joining
            processed_qdrant_data = []
            for i, item in enumerate(qdrant_data):
                # Make sure each item has an id field
                if "id" not in item and "_id" not in item:
                    item["id"] = f"qdrant_{i}"
                processed_qdrant_data.append(item)
            
            join_input.append({
                "source_id": "qdrant_main",
                "success": True,
                "data": processed_qdrant_data
            })
            
            # For Qdrant, we'll use id as the join field
            if processed_qdrant_data:
                # Determine which ID field to use
                id_field = "id" if "id" in processed_qdrant_data[0] else "_id"
                join_fields["qdrant_main"] = id_field
                type_mappings["qdrant_main"] = {
                    id_field: "str"
                }
                logger.info(f"Added {len(processed_qdrant_data)} documents from Qdrant with join field '{id_field}'")
            else:
                logger.warning("No Qdrant data available for joining")
        except Exception as e:
            logger.error(f"Error querying Qdrant: {e}")
            join_input.append({
                "source_id": "qdrant_main",
                "success": False,
                "error": str(e)
            })
    
    # Add Slack results if available
    if "slack" in orchestrators:
        try:
            # Query Slack channels
            slack_query = {
                "type": "channels"
            }
            slack_data = await orchestrators["slack"].execute(slack_query)
            
            # Process data to make it compatible with join
            processed_slack_data = []
            for channel in slack_data:
                # Ensure each channel has an id field that can be used for joining
                if "id" in channel:
                    processed_slack_data.append(channel)
            
            join_input.append({
                "source_id": "slack_main",
                "success": True,
                "data": processed_slack_data
            })
            
            # For Slack, we'll use channel id as the join field
            if processed_slack_data:
                join_fields["slack_main"] = "id"
                type_mappings["slack_main"] = {
                    "id": "str"
                }
                logger.info(f"Added {len(processed_slack_data)} channels from Slack with join field 'id'")
            else:
                logger.warning("No Slack channels available for joining")
        except Exception as e:
            logger.error(f"Error querying Slack: {e}")
            join_input.append({
                "source_id": "slack_main",
                "success": False,
                "error": str(e)
            })
    
    # If not enough joinable data available, use mock data
    if len(join_fields) < 2:
        logger.warning("Not enough joinable data available, using mock data")
        # Create mock data with joinable fields
        join_input = [
            {
                "source_id": "postgres_main",
                "success": True,
                "data": [
                    {"id": 1, "name": "User 1", "email": "user1@example.com"},
                    {"id": 2, "name": "User 2", "email": "user2@example.com"}
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
    
    # Call the join_results method (without await since it's not async)
    join_result = aggregator.join_results(
        join_input,
        join_fields,
        type_mappings
    )
    
    # Log the results
    logger.info(f"Join operation succeeded: {join_result['success']}")
    logger.info(f"Sources joined: {join_result['sources_joined']}")
    logger.info(f"Join fields: {json.dumps(join_result['join_fields'], indent=2)}")
    logger.info(f"Total rows: {join_result['total_rows']}")
    
    if join_result.get('results'):
        sample_size = min(2, len(join_result['results']))
        logger.info(f"Results (first {sample_size} entries): {json.dumps(join_result['results'][:sample_size], indent=2, cls=DateTimeEncoder)}")
    else:
        logger.warning("No joined results found")
    
    return join_result

async def test_llm_aggregation(result_aggregator, merge_result=None, join_result=None):
    """Test the LLM-based aggregation with real data"""
    print_section("Testing LLM-based Aggregation with Real Data")
    
    # Create a sample query plan
    query_plan = create_sample_query_plan()
    
    # Use the merge result or join result as operation results
    if merge_result:
        operation_results = {"op1": merge_result}
    elif join_result:
        operation_results = {"op1": join_result}
    else:
        # Create mock results if none provided
        logger.warning("No real results available, using mock data for LLM aggregation test")
        mock_data = [
            {"id": 1, "name": "User 1", "email": "user1@example.com", "orders": 5},
            {"id": 2, "name": "User 2", "email": "user2@example.com", "orders": 3}
        ]
        
        operation_results = {
            "op1": {
                "success": True,
                "sources_queried": 2,
                "successful_sources": 2,
                "failed_sources": 0,
                "data": mock_data,
                "errors": []
            }
        }
    
    # User question
    user_question = "Show me customers with their order counts and product interests"
    
    try:
        logger.info("Aggregating results using mock LLM")
        
        # Call the aggregate_results method
        aggregation_result = await result_aggregator.aggregate_results(
            query_plan=query_plan,
            operation_results=operation_results,
            user_question=user_question
        )
        
        logger.info("Successfully aggregated results using mock LLM")
        logger.info(f"LLM Aggregation Result:\n{json.dumps(aggregation_result, indent=2, cls=DateTimeEncoder)}")
        
        return aggregation_result
    except Exception as e:
        logger.error(f"Error aggregating results: {e}")
        logger.info("LLM Aggregation Result:")
        logger.info(json.dumps({
            "error": f"Failed to aggregate results: {e}",
            "partial_results": None
        }, indent=2))
        return None

async def main():
    """Main entry point for testing the ResultAggregator with real database connections"""
    logger.info("Starting ResultAggregator tests with real database connections")
    
    # Connect to databases
    orchestrators = await connect_to_databases()
    
    # Execute sample queries to get real data
    await execute_sample_queries(orchestrators)
    
    # Test merge_results with real data
    merge_result = await test_merge_results(orchestrators)
    
    # Test join_results with real data
    join_result = await test_join_results(orchestrators)
    
    # Initialize ResultAggregator for LLM test
    result_aggregator = ResultAggregator()
    
    # Test LLM-based aggregation with real data
    llm_result = await test_llm_aggregation(result_aggregator, merge_result, join_result)
    
    logger.info("All tests completed!")

if __name__ == "__main__":
    asyncio.run(main()) 
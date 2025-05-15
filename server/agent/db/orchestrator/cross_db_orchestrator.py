"""
Cross-Database Orchestrator

This module implements the orchestrator for querying multiple databases
with a single natural language query. It uses the database classifier
to determine which databases to query and coordinates the execution of
multiple queries in parallel.
"""

import logging
import asyncio
import time
from typing import Dict, List, Any, Optional, Set, Tuple
import os
import yaml
from pathlib import Path

from ..classifier import classifier as db_classifier
from ..registry.integrations import registry_client
# Fix import to avoid circular reference
import server.agent.db.orchestrator as base_orchestrator 
from .result_aggregator import ResultAggregator

# Configure logging
logger = logging.getLogger(__name__)

class CrossDatabaseOrchestrator:
    """
    Orchestrator for cross-database queries.
    
    This class enables querying multiple databases with a single natural language query.
    It uses the database classifier to determine which databases to query and coordinates
    the execution of multiple queries in parallel.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the cross-database orchestrator.
        
        Args:
            config: Optional configuration dictionary. If not provided, will be loaded from config.yaml.
        """
        # Load config if not provided
        self.config = config or self._load_config()
        
        # Get max parallel queries from config (default to 3)
        self.max_parallel_queries = self.config.get("max_parallel_queries", 3)
        
        # Initialize classifier and registry client
        self.classifier = db_classifier
        self.registry_client = registry_client
        
        # Initialize result aggregator
        self.result_aggregator = ResultAggregator()
        
        # Dictionary to cache orchestrators by source_id
        self.orchestrators = {}
        
        # Semaphore for controlling parallel queries
        self.semaphore = asyncio.Semaphore(self.max_parallel_queries)
        
        # Import here to avoid circular reference
        from .. import orchestrator as db_orchestrator
        self.Orchestrator = db_orchestrator.Orchestrator
    
    def _load_config(self) -> Dict[str, Any]:
        """
        Load configuration from config.yaml.
        
        Returns:
            Dictionary with configuration values
        """
        config_path = os.environ.get("DATA_CONNECTOR_CONFIG", 
                                    str(Path.home() / ".data-connector" / "config.yaml"))
        
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            return config
        except Exception as e:
            logger.warning(f"Failed to load config.yaml: {e}")
            # Return default config
            return {
                "default_database": "postgres",
                "max_parallel_queries": 3
            }
    
    async def _classify_databases(self, question: str) -> Set[str]:
        """
        Determine which databases are relevant for this question.
        
        Args:
            question: Natural language question
            
        Returns:
            Set of source_ids that should be queried
        """
        # Use the classifier to determine which databases to query
        classification = self.classifier.classify(question)
        relevant_sources = set(classification["sources"])
        
        logger.info(f"Classified databases for query: {relevant_sources}")
        logger.info(f"Classification reasoning: {classification['reasoning']}")
        
        return relevant_sources
    
    async def _get_or_create_orchestrator(self, source_id: str) -> Optional[Any]:
        """
        Get or create an orchestrator for a specific data source.
        
        Args:
            source_id: The data source ID
            
        Returns:
            Orchestrator instance or None if the source does not exist
        """
        # Return cached orchestrator if available
        if source_id in self.orchestrators:
            return self.orchestrators[source_id]
        
        # Get source info from registry
        source = self.registry_client.get_all_sources()
        source_info = next((s for s in source if s["id"] == source_id), None)
        
        if not source_info:
            logger.warning(f"Source {source_id} not found in registry")
            return None
        
        # Create orchestrator
        try:
            uri = source_info.get("uri")
            db_type = source_info.get("type")
            
            if not uri:
                logger.warning(f"No URI found for source {source_id}")
                return None
            
            # Create orchestrator
            db_orchestrator = self.Orchestrator(uri, db_type=db_type)
            
            # Cache orchestrator
            self.orchestrators[source_id] = db_orchestrator
            
            return db_orchestrator
        except Exception as e:
            logger.error(f"Failed to create orchestrator for source {source_id}: {e}")
            return None
    
    async def _execute_query_on_source(self, source_id: str, question: str) -> Dict[str, Any]:
        """
        Execute a query on a specific data source.
        
        Args:
            source_id: The data source ID
            question: Natural language question
            
        Returns:
            Dictionary with query results and metadata
        """
        async with self.semaphore:
            start_time = time.time()
            
            try:
                # Get orchestrator for this source
                db_orchestrator = await self._get_or_create_orchestrator(source_id)
                
                if not db_orchestrator:
                    return {
                        "source_id": source_id,
                        "success": False,
                        "error": f"Failed to initialize orchestrator for source {source_id}",
                        "data": [],
                        "query": None,
                        "execution_time": 0
                    }
                
                # Execute query
                logger.info(f"Executing query on {source_id}: {question}")
                result = await db_orchestrator.run(question)
                
                execution_time = time.time() - start_time
                
                return {
                    "source_id": source_id,
                    "success": True,
                    "data": result,
                    "query": None,  # We don't have the raw query here, would need adapter change
                    "execution_time": execution_time
                }
            except Exception as e:
                execution_time = time.time() - start_time
                
                logger.error(f"Error executing query on {source_id}: {e}")
                return {
                    "source_id": source_id,
                    "success": False,
                    "error": str(e),
                    "data": [],
                    "query": None,
                    "execution_time": execution_time
                }
    
    async def execute(self, question: str, operation: str = "merge") -> Dict[str, Any]:
        """
        Execute a natural language query across multiple databases.
        
        Args:
            question: Natural language query
            operation: Aggregation operation: "merge" (default), "join", or "union"
            
        Returns:
            Dictionary with results from all relevant databases
        """
        # Step 1: Classify databases
        relevant_sources = await self._classify_databases(question)
        
        if not relevant_sources:
            logger.warning("No relevant sources found for query")
            return {
                "success": False,
                "error": "No relevant data sources found for this query",
                "results": [],
                "sources_queried": []
            }
        
        # Step 2: Execute queries in parallel
        tasks = [self._execute_query_on_source(source_id, question) for source_id in relevant_sources]
        results = await asyncio.gather(*tasks)
        
        # Step 3: Aggregate results
        # Determine if we need type mappings (for joins)
        type_mappings = None
        join_fields = None
        
        if operation == "join":
            # Try to automatically determine join fields based on schema
            join_fields = self._determine_join_fields(relevant_sources)
            
            # Auto-generate type mappings from schema
            type_mappings = self._determine_type_mappings(relevant_sources)
            
            logger.info(f"Using join fields: {join_fields}")
            logger.info(f"Using type mappings: {type_mappings}")
        
        # Aggregate results
        return self.result_aggregator.aggregate_results(
            results, 
            operation=operation,
            join_fields=join_fields,
            type_mappings=type_mappings
        )
    
    def _determine_join_fields(self, source_ids: Set[str]) -> Dict[str, str]:
        """
        Automatically determine join fields based on schema information.
        
        Args:
            source_ids: Set of source IDs to consider
            
        Returns:
            Mapping of source_id to join field
        """
        join_fields = {}
        
        # Get ontology mapping to find related tables
        ontology = self.registry_client.get_ontology_to_tables_mapping()
        
        # Find common fields across sources
        common_fields = set()
        field_candidates = {
            "id", "uuid", "key", "code", "name", "reference", "external_id", 
            "customer_id", "user_id", "order_id", "product_id"
        }
        
        # Find potential join fields for each source
        for source_id in source_ids:
            tables = self.registry_client.list_tables(source_id)
            for table in tables:
                schema = self.registry_client.get_table_schema(source_id, table)
                if not schema:
                    continue
                
                fields = schema.get("schema", {}).get("fields", {})
                field_names = set(fields.keys())
                
                # Intersect with candidates
                matching_fields = field_names.intersection(field_candidates)
                if matching_fields:
                    # Prioritize primary keys and common ID fields
                    for field in matching_fields:
                        field_info = fields[field]
                        if field_info.get("primary_key", False):
                            join_fields[source_id] = field
                            break
                    
                    # If no primary key found, use the first matching field
                    if source_id not in join_fields and matching_fields:
                        join_fields[source_id] = next(iter(matching_fields))
        
        return join_fields
    
    def _determine_type_mappings(self, source_ids: Set[str]) -> Dict[str, Dict[str, str]]:
        """
        Automatically determine type mappings based on schema information.
        
        Args:
            source_ids: Set of source IDs to consider
            
        Returns:
            Mapping of source_id to field type mappings
        """
        type_mappings = {}
        
        # Type mapping for common database types
        db_type_to_python = {
            # SQL types
            "int": "int", "integer": "int", "smallint": "int", "bigint": "int",
            "float": "float", "double": "float", "real": "float", "numeric": "float",
            "varchar": "str", "text": "str", "char": "str", "string": "str",
            "boolean": "bool", "bool": "bool",
            "date": "date", "timestamp": "date", "datetime": "date",
            "json": "object", "jsonb": "object",
            "array": "array",
            
            # MongoDB/BSON types
            "objectId": "str",
            "string": "str",
            "number": "float",
            "object": "object",
            "array": "array",
            "boolean": "bool",
            "date": "date",
            
            # Qdrant types
            "keyword": "str",
            "integer": "int",
            "float": "float",
            "vector": "array"
        }
        
        # Generate type mappings for each source
        for source_id in source_ids:
            field_types = {}
            
            tables = self.registry_client.list_tables(source_id)
            for table in tables:
                schema = self.registry_client.get_table_schema(source_id, table)
                if not schema:
                    continue
                
                fields = schema.get("schema", {}).get("fields", {})
                for field_name, field_info in fields.items():
                    data_type = field_info.get("data_type", "unknown").lower()
                    
                    # Map to python type
                    python_type = db_type_to_python.get(data_type, "str")
                    
                    # Add to field types
                    field_types[field_name] = python_type
            
            if field_types:
                type_mappings[source_id] = field_types
        
        return type_mappings
    
    async def plan_execution(self, question: str) -> Dict[str, Any]:
        """
        Generate an execution plan for a cross-database query.
        This is a simplified version that doesn't use an LLM for planning yet.
        
        Args:
            question: Natural language query
            
        Returns:
            Dictionary with execution plan
        """
        # Step 1: Classify databases
        relevant_sources = await self._classify_databases(question)
        
        # Step 2: Get schema summary for relevant sources
        schema_summary = self.registry_client.get_schema_summary_for_sources(list(relevant_sources))
        
        # Step 3: Determine join fields if possible
        join_fields = self._determine_join_fields(relevant_sources)
        
        # Step 4: Generate plan
        operation = "merge"
        if len(relevant_sources) > 1 and len(join_fields) > 1:
            # We can do a join
            operation = "join"
        
        plan = {
            "question": question,
            "sources": list(relevant_sources),
            "operation": operation,
            "join_fields": join_fields if operation == "join" else None,
            "operations": [
                {
                    "source_id": source_id,
                    "operation": "query",
                    "question": question
                }
                for source_id in relevant_sources
            ],
            "schema_summary": schema_summary
        }
        
        return plan 
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
# Fix circular import by using lazy/delayed import
# import server.agent.db.orchestrator as base_orchestrator 
from .result_aggregator import ResultAggregator
from .planning_agent import PlanningAgent

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
        
        # Initialize the planning agent
        self.planning_agent = PlanningAgent(config=self.config)
        
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
    
    async def plan_execution(self, question: str) -> Dict[str, Any]:
        """
        Plan the execution of a cross-database query without executing it.
        
        This implements a "dry run" capability for validation before execution.
        
        Args:
            question: Natural language question
            
        Returns:
            Dictionary with plan and validation results
        """
        try:
            # Use the planning agent to create and validate a plan
            query_plan, validation_result = await self.planning_agent.create_plan(
                question=question, 
                optimize=True
            )
            
            # Return the plan and validation result
            return {
                "plan": query_plan.to_dict(),
                "validation": validation_result,
                "valid": validation_result.get("valid", False)
            }
        except Exception as e:
            logger.error(f"Error in plan execution: {e}")
            return {
                "error": str(e),
                "valid": False
            }
    
    async def execute_plan(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a pre-generated query plan.
        
        Args:
            plan: Query plan dictionary or QueryPlan instance
            
        Returns:
            Dictionary with execution results
        """
        # Import the OperationDAG class for execution
        from .plans.dag import OperationDAG
        
        try:
            # Convert plan dict to QueryPlan if needed
            if isinstance(plan, dict):
                from .plans.factory import create_plan_from_dict
                query_plan = create_plan_from_dict(plan)
            else:
                query_plan = plan
            
            # Validate the plan one more time before execution
            validation = query_plan.validate(self.registry_client)
            if not validation["valid"]:
                logger.error(f"Plan validation failed before execution: {validation['errors']}")
                return {
                    "success": False,
                    "errors": validation["errors"],
                    "results": []
                }
            
            # Create a DAG for parallel execution
            dag = OperationDAG(query_plan)
            
            # Check for cycles
            if dag.has_cycles():
                return {
                    "success": False,
                    "errors": ["Plan has cyclic dependencies"],
                    "results": []
                }
            
            # Get the parallel execution plan
            parallel_plan = dag.get_parallel_execution_plan()
            
            # Dictionary to track operation results by ID
            operation_results = {}
            
            # Execute operations layer by layer
            for layer_idx, layer in enumerate(parallel_plan):
                logger.info(f"Executing layer {layer_idx+1}/{len(parallel_plan)} with {len(layer)} operations")
                
                # Execute operations in this layer in parallel
                layer_operations = []
                for op_id in layer:
                    operation = query_plan.get_operation(op_id)
                    if operation:
                        layer_operations.append(operation)
                
                # Execute operations in parallel with semaphore control
                async def execute_operation(operation):
                    async with self.semaphore:
                        source_id = operation.source_id
                        db_orchestrator = await self._get_or_create_orchestrator(source_id)
                        
                        if not db_orchestrator:
                            operation.status = "failed"
                            operation.error = f"Failed to initialize orchestrator for source {source_id}"
                            return operation
                        
                        # Get adapter params
                        params = operation.get_adapter_params()
                        
                        # Record start time
                        start_time = time.time()
                        
                        try:
                            # Execute operation
                            operation.status = "running"
                            result = await db_orchestrator.execute(params)
                            operation.result = result
                            operation.status = "completed"
                        except Exception as e:
                            operation.status = "failed"
                            operation.error = str(e)
                        
                        # Record execution time
                        operation.execution_time = time.time() - start_time
                        
                        return operation
                
                # Execute all operations in this layer
                tasks = [execute_operation(op) for op in layer_operations]
                completed_ops = await asyncio.gather(*tasks)
                
                # Process results
                for op in completed_ops:
                    operation_results[op.id] = op.result if op.status == "completed" else {"error": op.error}
            
            # Aggregate results if needed
            final_results = []
            for op in query_plan.operations:
                if op.status == "completed" and not op.depends_on:
                    # This is a "terminal" operation with no dependents
                    final_results.append({
                        "operation_id": op.id,
                        "result": op.result
                    })
            
            # If we have a final operation that depends on others, it's likely a join/aggregation
            join_operations = [op for op in query_plan.operations 
                               if op.depends_on and op.status == "completed"]
            
            if join_operations:
                # Use the result aggregator to combine results
                try:
                    # Use LLM-based result aggregation for the final results
                    aggregated_result = await self.result_aggregator.aggregate_results(
                        query_plan=query_plan,
                        operation_results=operation_results,
                        user_question=query_plan.metadata.get("original_question", "")
                    )
                    return {
                        "success": True,
                        "aggregated_result": aggregated_result,
                        "raw_results": operation_results
                    }
                except Exception as e:
                    logger.error(f"Error in result aggregation: {e}")
                    return {
                        "success": True,
                        "error_in_aggregation": str(e),
                        "raw_results": operation_results
                    }
            
            return {
                "success": True,
                "results": final_results,
                "all_results": operation_results
            }
            
        except Exception as e:
            logger.error(f"Error in plan execution: {e}")
            return {
                "success": False,
                "errors": [str(e)],
                "results": []
            }
    
    async def execute(self, question: str, operation: str = "merge") -> Dict[str, Any]:
        """
        Execute a cross-database query.
        
        This is the main entry point for querying multiple databases.
        
        Args:
            question: Natural language question
            operation: How to combine results from multiple sources
                      "merge": Merge results from all sources
                      "join": Join results based on common fields
                      "union": Union results from all sources
                      
        Returns:
            Dictionary with query results
        """
        try:
            # Use the planning agent to create a plan
            query_plan, validation_result = await self.planning_agent.create_plan(
                question=question, 
                optimize=True
            )
            
            # Check if plan is valid
            if not validation_result.get("valid", False):
                return {
                    "success": False,
                    "errors": validation_result.get("errors", ["Plan validation failed"]),
                    "plan": query_plan.to_dict()
                }
            
            # Execute the plan
            execution_result = await self.execute_plan(query_plan)
            
            # Add plan to the result
            execution_result["plan"] = query_plan.to_dict()
            
            return execution_result
        except Exception as e:
            logger.error(f"Error in query execution: {e}")
            return {
                "success": False,
                "errors": [str(e)]
            }
    
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
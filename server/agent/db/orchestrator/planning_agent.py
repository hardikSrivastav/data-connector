"""
Planning Agent for Cross-Database Orchestration

This module implements the planning agent that:
1. Uses FAISS schema metadata during planning for fast schema retrieval
2. Validates generated plans against the schema registry for correctness
3. Coordinates the generation, validation, and optimization of query plans
"""

import logging
import json
import asyncio
from typing import Dict, List, Any, Optional, Set, Tuple
import uuid

from ...llm.client import get_llm_client
from ...meta.ingest import SchemaSearcher
from ..classifier import classifier as db_classifier
from ..registry.integrations import registry_client
from .plans.factory import create_plan_from_dict, create_empty_plan
from .plans.base import QueryPlan, Operation

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PlanningAgent:
    """
    Agent responsible for planning cross-database queries.
    
    This agent handles:
    1. Database classification to identify relevant sources
    2. Schema retrieval from FAISS indices for plan generation
    3. LLM-based query plan generation
    4. Validation against the schema registry
    5. Plan optimization if requested
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the planning agent.
        
        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
        self.llm_client = get_llm_client()
        self.schema_searcher = SchemaSearcher()
        self.classifier = db_classifier
        self.registry_client = registry_client
        
        # Maximum tokens for schema context
        self.max_schema_tokens = self.config.get("max_schema_tokens", 4000)
        
        # Number of schema items to retrieve per database type
        self.schema_items_per_db = self.config.get("schema_items_per_db", 5)
    
    async def _classify_databases(self, question: str) -> List[str]:
        """
        Determine which database types are relevant for the question.
        
        Args:
            question: User's natural language question
            
        Returns:
            List of database types in order of relevance
        """
        try:
            # Use the LLM-based classifier with the schema_classifier template
            prompt = self.llm_client.render_template(
                "schema_classifier.tpl",
                user_question=question
            )
            
            # Call LLM to classify database types
            response = await self.llm_client.client.chat.completions.create(
                model=self.llm_client.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2
            )
            
            # Parse the JSON response
            content = response.choices[0].message.content
            # Extract JSON string from content (might be wrapped in ```json blocks)
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0].strip()
            else:
                json_str = content.strip()
                
            result = json.loads(json_str)
            
            # Get the selected databases
            selected_dbs = result.get("selected_databases", [])
            
            # Log classification rationale
            rationale = result.get("rationale", {})
            logger.info(f"Database classification rationale: {rationale}")
            
            return selected_dbs
        except Exception as e:
            logger.error(f"Error in database classification: {e}")
            # Return empty list on error
            return []
    
    async def _get_schema_info(self, db_types: List[str]) -> List[Dict[str, Any]]:
        """
        Retrieve schema information from FAISS indices for the specified database types.
        
        Args:
            db_types: List of database types to retrieve schema for
            
        Returns:
            List of schema metadata objects
        """
        all_schema_info = []
        
        # For each database type, retrieve schema information
        for db_type in db_types:
            try:
                # Search for relevant schema in FAISS index
                schema_results = await self.schema_searcher.search(
                    query="",  # Empty query to get general schema information
                    top_k=self.schema_items_per_db,
                    db_type=db_type
                )
                
                # Add to combined results
                all_schema_info.extend(schema_results)
                
                logger.info(f"Retrieved {len(schema_results)} schema items for {db_type}")
            except Exception as e:
                logger.error(f"Error retrieving schema for {db_type}: {e}")
        
        return all_schema_info
    
    async def _generate_plan(self, question: str, db_types: List[str], 
                             schema_info: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate a query plan using the LLM.
        
        Args:
            question: User's natural language question
            db_types: List of database types to consider
            schema_info: Schema information retrieved from FAISS
            
        Returns:
            Dictionary representation of the query plan
        """
        try:
            # Render the orchestration plan template
            prompt = self.llm_client.render_template(
                "orchestration_plan.tpl",
                user_question=question,
                db_candidates=db_types,
                schema_info=schema_info
            )
            
            # Call LLM to generate plan
            response = await self.llm_client.client.chat.completions.create(
                model=self.llm_client.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2
            )
            
            # Parse the JSON response
            content = response.choices[0].message.content
            # Extract JSON string from content (might be wrapped in ```json blocks)
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0].strip()
            else:
                json_str = content.strip()
                
            plan_dict = json.loads(json_str)
            
            logger.info(f"Generated plan with {len(plan_dict.get('operations', []))} operations")
            
            return plan_dict
        except Exception as e:
            logger.error(f"Error generating plan: {e}")
            # Return empty plan on error
            return {"metadata": {}, "operations": []}
    
    async def _validate_plan(self, query_plan: QueryPlan, 
                             user_question: str) -> Dict[str, Any]:
        """
        Validate a query plan against the schema registry.
        
        Args:
            query_plan: The query plan to validate
            user_question: Original user question for context
            
        Returns:
            Dictionary with validation results
        """
        try:
            # Get registry schemas for validation
            registry_schemas = {}
            
            # Get unique source_ids from plan
            source_ids = set()
            for op in query_plan.operations:
                if op.source_id:
                    source_ids.add(op.source_id)
            
            # Get schema information for each source
            for source_id in source_ids:
                source_info = registry_client.get_source_by_id(source_id)
                if not source_info:
                    logger.warning(f"Source {source_id} not found in registry")
                    continue
                
                source_type = source_info.get("type")
                tables = registry_client.list_tables(source_id)
                
                table_schemas = {}
                for table in tables:
                    schema = registry_client.get_table_schema(source_id, table)
                    if schema:
                        table_schemas[table] = json.dumps(schema["schema"], indent=2)
                
                registry_schemas[source_id] = {
                    "type": source_type,
                    "tables": table_schemas
                }
            
            # First, perform basic validation using QueryPlan.validate()
            basic_validation = query_plan.validate(registry_client)
            
            # If basic validation fails, return immediately
            if not basic_validation["valid"]:
                logger.warning(f"Basic plan validation failed: {basic_validation['errors']}")
                return basic_validation
            
            # For more detailed validation, use the LLM with the validation_check template
            plan_dict = query_plan.to_dict()
            
            prompt = self.llm_client.render_template(
                "validation_check.tpl",
                query_plan=json.dumps(plan_dict, indent=2),
                registry_schemas=registry_schemas,
                user_question=user_question
            )
            
            # Call LLM for detailed validation
            response = await self.llm_client.client.chat.completions.create(
                model=self.llm_client.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2
            )
            
            # Parse the JSON response
            content = response.choices[0].message.content
            # Extract JSON string from content
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0].strip()
            else:
                json_str = content.strip()
                
            validation_result = json.loads(json_str)
            
            logger.info(f"Plan validation result: valid={validation_result.get('valid')}")
            logger.info(f"Validation result content: {validation_result}")
            
            return validation_result
        except Exception as e:
            logger.error(f"Error validating plan: {e}")
            # Return validation error
            return {
                "valid": False,
                "errors": [{"error_type": "validation_error", "description": str(e)}]
            }
    
    async def _optimize_plan(self, plan_dict: Dict[str, Any], 
                             registry_schemas: Dict[str, Any]) -> Dict[str, Any]:
        """
        Optimize a query plan for better performance.
        
        Args:
            plan_dict: Dictionary representation of the plan
            registry_schemas: Schema information from registry
            
        Returns:
            Optimized plan dictionary
        """
        try:
            prompt = self.llm_client.render_template(
                "plan_optimization.tpl",
                original_plan=json.dumps(plan_dict, indent=2),
                schemas=registry_schemas
            )
            
            # Call LLM for plan optimization
            response = await self.llm_client.client.chat.completions.create(
                model=self.llm_client.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2
            )
            
            # Parse the JSON response
            content = response.choices[0].message.content
            # Extract JSON string from content
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0].strip()
            else:
                json_str = content.strip()
                
            optimized_plan = json.loads(json_str)
            
            # Log optimization notes
            opt_notes = optimized_plan.get("metadata", {}).get("optimization_notes", "")
            logger.info(f"Plan optimization notes: {opt_notes}")
            
            return optimized_plan
        except Exception as e:
            logger.error(f"Error optimizing plan: {e}")
            # Return original plan on error
            return plan_dict
    
    async def create_plan(self, question: str, optimize: bool = False) -> Tuple[QueryPlan, Dict[str, Any]]:
        """
        Create a validated query plan for the given question.
        
        Args:
            question: User's natural language question
            optimize: Whether to optimize the plan after validation
            
        Returns:
            Tuple of (QueryPlan, validation_result)
        """
        # Track timing for performance analysis
        start_time = asyncio.get_event_loop().time()
        
        # Step 1: Identify relevant database types
        logger.info(f"Classifying databases for question: {question}")
        db_types = await self._classify_databases(question)
        
        if not db_types:
            logger.warning("No relevant database types identified")
            # Return empty plan
            empty_plan = create_empty_plan({"error": "No relevant database types identified"})
            return empty_plan, {"valid": False, "errors": ["No relevant database types identified"]}
        
        logger.info(f"Identified relevant database types: {db_types}")
        
        # Step 2: Retrieve schema information from FAISS for plan generation
        logger.info("Retrieving schema information from FAISS indices")
        schema_info = await self._get_schema_info(db_types)
        
        # Step 3: Generate initial query plan
        logger.info("Generating query plan")
        plan_dict = await self._generate_plan(question, db_types, schema_info)
        
        # Step 4: Create QueryPlan instance from dictionary
        query_plan = create_plan_from_dict(plan_dict)
        
        # Step 5: Validate plan against schema registry
        logger.info("Validating plan against schema registry")
        validation_result = await self._validate_plan(query_plan, question)
        
        # If optimization requested and validation succeeded, optimize plan
        if optimize and validation_result.get("valid", False):
            logger.info("Optimizing plan")
            
            # Get registry schemas for optimization
            registry_schemas = {}
            for op in query_plan.operations:
                if op.source_id and op.source_id not in registry_schemas:
                    source_info = registry_client.get_source_by_id(op.source_id)
                    if source_info:
                        source_type = source_info.get("type")
                        tables = registry_client.list_tables(op.source_id)
                        
                        table_schemas = {}
                        for table in tables:
                            schema = registry_client.get_table_schema(op.source_id, table)
                            if schema:
                                table_schemas[table] = json.dumps(schema["schema"], indent=2)
                        
                        registry_schemas[op.source_id] = {
                            "type": source_type,
                            "tables": table_schemas
                        }
            
            # Optimize plan
            optimized_plan_dict = await self._optimize_plan(query_plan.to_dict(), registry_schemas)
            
            # Create new QueryPlan from optimized dictionary
            query_plan = create_plan_from_dict(optimized_plan_dict)
            
            # Re-validate the optimized plan
            validation_result = await self._validate_plan(query_plan, question)
        
        # Calculate total planning time
        planning_time = asyncio.get_event_loop().time() - start_time
        logger.info(f"Plan creation completed in {planning_time:.2f} seconds")
        
        # Add planning metadata to query plan
        query_plan.metadata["planning_time_seconds"] = planning_time
        query_plan.metadata["original_question"] = question
        query_plan.metadata["classified_db_types"] = db_types
        
        return query_plan, validation_result 
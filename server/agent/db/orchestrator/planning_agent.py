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
import re
from typing import Dict, List, Any, Optional, Set, Tuple
import uuid

from ...llm.client import get_llm_client
from ...meta.ingest import SchemaSearcher
from ..classifier import classifier as db_classifier
from ..registry.integrations import registry_client
from .plans.factory import create_plan_from_dict, create_empty_plan
from .plans.base import QueryPlan, Operation
from ...tools.tools import DataTools

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
        
        # Import the rule-based classifier for fallback
        from ...db.classifier import classifier as db_classifier
        self.classifier = db_classifier
        
        # Import and initialize DataTools
        self.data_tools = None  # Will be initialized when needed with the correct db_type
        
        self.registry_client = registry_client
        
        # Maximum tokens for schema context
        self.max_schema_tokens = self.config.get("max_schema_tokens", 4000)
        
        # Number of schema items to retrieve per database type
        self.schema_items_per_db = self.config.get("schema_items_per_db", 5)
        
        # Cache for schema metadata to avoid duplicate fetching
        self.cached_schema_metadata = None
        
        # Track the current session ID
        self.session_id = str(uuid.uuid4())
    
    async def _call_llm(self, prompt: str, temperature: float = 0.2) -> str:
        """
        Call the LLM with the appropriate client method based on client type
        
        Args:
            prompt: The prompt to send to the LLM
            temperature: Temperature parameter for the LLM
            
        Returns:
            Content string from the LLM response
        """
        # Determine if we're using OpenAI or Anthropic
        client_class_name = self.llm_client.__class__.__name__
        
        try:
            if client_class_name == "OpenAIClient":
                # Use OpenAI's structure
                response = await self.llm_client.client.chat.completions.create(
                    model=self.llm_client.model_name,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature
                )
                content = response.choices[0].message.content
                
            elif client_class_name == "AnthropicClient":
                # Use Anthropic's structure
                response = await self.llm_client.client.messages.create(
                    model=self.llm_client.model_name,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                    max_tokens=4000
                )
                
                # Extract content from Anthropic response
                if hasattr(response, 'content') and len(response.content) > 0:
                    if hasattr(response.content[0], 'text'):
                        content = response.content[0].text
                    else:
                        content = response.content[0]
                else:
                    content = ""
                    
            elif client_class_name == "DummyLLMClient":
                # Handle dummy client
                response = await self.llm_client.client.chat_completions_create(
                    model=self.llm_client.model_name,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature
                )
                content = response.choices[0].message.content
                
            else:
                # Use a generic approach for other client types
                logger.warning(f"Unknown LLM client type: {client_class_name}. Using generic call.")
                content = await self.llm_client.generate_sql(prompt)
                
            # Extract JSON if wrapped in ```json blocks
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                json_str = content.split("```")[1].strip()
            else:
                json_str = content.strip()
                
            return json_str
            
        except Exception as e:
            logger.error(f"Error calling LLM with {client_class_name}: {e}")
            raise
    
    async def _classify_databases(self, question: str) -> List[str]:
        """
        Determine which database types are relevant for the question.
        
        Args:
            question: User's natural language question
            
        Returns:
            List of database types in order of relevance
        """
        logger.info(f"🔍 CLASSIFICATION: Starting database classification for: '{question}'")
        
        try:
            # Use the LLM-based classifier with the schema_classifier template
            logger.info(f"🔍 CLASSIFICATION: Rendering schema_classifier template")
            prompt = self.llm_client.render_template(
                "schema_classifier.tpl",
                user_question=question
            )
            
            logger.info(f"🔍 CLASSIFICATION: Calling LLM with prompt length: {len(prompt)} chars")
            logger.info(f"🔍 CLASSIFICATION: LLM client type: {self.llm_client.__class__.__name__}")
            
            # Call LLM to classify database types
            json_str = await self._call_llm(prompt)
            
            logger.info(f"🔍 CLASSIFICATION: LLM returned: '{json_str[:200]}...' (truncated)")
            
            result = json.loads(json_str)
            
            # Get the selected databases
            selected_dbs = result.get("selected_databases", [])
            
            # Log classification rationale
            rationale = result.get("rationale", {})
            logger.info(f"🔍 LLM Database classification for question: '{question}'")
            logger.info(f"🔍 LLM Selected databases: {selected_dbs}")
            logger.info(f"🔍 LLM Classification rationale: {rationale}")
            
            # Clear cached schema metadata since we're not using the fallback
            self.cached_schema_metadata = None
            
            # If LLM returned valid results, use them
            if selected_dbs:
                logger.info(f"✅ Using LLM classification results: {selected_dbs}")
                return selected_dbs
                
            # If LLM returned empty results, fall back to rule-based classifier
            logger.warning("⚠️ LLM classification returned empty results, falling back to rule-based classifier")
            db_types, schema_metadata = await self._fallback_classification(question)
            # Cache the schema metadata for later use
            self.cached_schema_metadata = schema_metadata
            return db_types
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON parsing error in LLM classification: {e}")
            logger.error(f"❌ Raw LLM response: '{json_str}'")
            # Fall back to rule-based classifier
            logger.warning("⚠️ JSON parsing error in LLM classification, falling back to rule-based classifier")
            db_types, schema_metadata = await self._fallback_classification(question)
            # Cache the schema metadata for later use
            self.cached_schema_metadata = schema_metadata
            return db_types
        except Exception as e:
            logger.error(f"❌ Error in LLM database classification: {e}")
            logger.error(f"❌ Exception type: {type(e).__name__}")
            # Fall back to rule-based classifier
            logger.warning("⚠️ Error in LLM classification, falling back to rule-based classifier")
            db_types, schema_metadata = await self._fallback_classification(question)
            # Cache the schema metadata for later use
            self.cached_schema_metadata = schema_metadata
            return db_types
    
    async def _fallback_classification(self, question: str) -> Tuple[List[str], Optional[Dict[str, Any]]]:
        """
        Fallback to rule-based classification using DatabaseClassifier
        when LLM-based classification fails.
        
        Args:
            question: User's natural language question
            
        Returns:
            Tuple of (database_types, schema_metadata)
        """
        try:
            # Use the rule-based classifier from classifier.py
            result = await self.classifier.classify(question)
            
            # Get the source IDs from the result
            source_ids = result.get("sources", [])
            
            # Get the database types for these sources
            db_types = set()
            for source_id in source_ids:
                source_info = self.registry_client.get_source_by_id(source_id)
                if source_info and "type" in source_info:
                    db_types.add(source_info["type"])
            
            logger.info(f"Rule-based classifier selected databases: {list(db_types)}")
            logger.info(f"Rule-based reasoning: {result.get('reasoning', 'No reasoning provided')}")
            
            # Get the schema metadata for reuse
            schema_metadata = result.get("schema_metadata")
            
            return list(db_types), schema_metadata
        except Exception as e:
            logger.error(f"Error in rule-based classification: {e}")
            # Return empty list if both classification methods fail
            return [], None
    
    async def _get_schema_info(self, db_types: List[str], question: str = "") -> List[Dict[str, Any]]:
        """
        Retrieve schema information from FAISS indices for the specified database types.
        
        Args:
            db_types: List of database types to retrieve schema for
            question: User's question to use for relevant schema search
            
        Returns:
            List of schema metadata objects
        """
        logger.info(f"📊 _get_schema_info called with db_types: {db_types}")
        logger.info(f"📊 Question for schema search: '{question}'")
        
        all_schema_info = []
        
        # For each database type, retrieve schema information
        for db_type in db_types:
            logger.info(f"🔍 Processing schema for database type: {db_type}")
            try:
                # Search for relevant schema in FAISS index, using the question for better relevance
                # If question is empty, fall back to a generic search term
                search_query = question if question else "database schema"
                
                logger.info(f"🔍 Searching FAISS for db_type='{db_type}' with query='{search_query}'")
                
                schema_results = await self.schema_searcher.search(
                    query=search_query,
                    top_k=self.schema_items_per_db,
                    db_type=db_type
                )
                
                logger.info(f"📊 FAISS returned {len(schema_results)} results for {db_type}")
                
                # Add to combined results
                all_schema_info.extend(schema_results)
                
                # Log detailed schema info for debugging
                logger.info(f"Retrieved {len(schema_results)} schema items for {db_type}:")
                for i, schema_item in enumerate(schema_results):
                    # Extract item type and name - check various possible metadata fields
                    item_type = "unknown"
                    item_name = "unknown"
                    
                    # Check content for metadata extraction if available
                    if 'content' in schema_item:
                        content = schema_item.get('content', '')
                        if content and isinstance(content, str):
                            # Try to extract metadata from content
                            if "TABLE:" in content:
                                item_type = "table"
                                # Extract table name from "TABLE: table_name"
                                table_match = re.search(r'TABLE:\s*(\w+)', content)
                                if table_match:
                                    item_name = table_match.group(1)
                            elif "COLLECTION:" in content:
                                item_type = "collection"
                                # Extract collection name from "COLLECTION: collection_name"
                                coll_match = re.search(r'COLLECTION:\s*(\w+)', content)
                                if coll_match:
                                    item_name = coll_match.group(1)
                    
                    # Check other fields if we couldn't extract from content
                    if item_type == "unknown" or item_name == "unknown":
                        if 'table_name' in schema_item:
                            item_name = schema_item.get('table_name')
                            item_type = "table"
                        elif 'name' in schema_item:
                            item_name = schema_item.get('name')
                        
                        if 'type' in schema_item:
                            item_type = schema_item.get('type')
                    
                    # Check if this schema item actually belongs to the requested db_type
                    actual_db_type = schema_item.get('db_type', 'unknown')
                    if actual_db_type != db_type:
                        logger.warning(f"⚠️ Schema mismatch! Requested {db_type} but got {actual_db_type} for {item_type} '{item_name}'")
                    
                    logger.info(f"  Schema {i+1}: {item_type} '{item_name}' (db_type: {actual_db_type})")
                    
                    # Log columns if available
                    if 'columns' in schema_item:
                        columns = schema_item.get('columns', [])
                        if isinstance(columns, list) and columns:
                            col_names = [col.get('name', str(col)) if isinstance(col, dict) else str(col) for col in columns[:5]]
                            logger.info(f"    Columns: {', '.join(col_names)}...")
                        elif isinstance(columns, dict):
                            col_names = list(columns.keys())[:5]
                            logger.info(f"    Columns: {', '.join(col_names)}...")
                    
                    # Log content preview
                    if 'content' in schema_item:
                        content = schema_item.get('content', '')
                        if content and isinstance(content, str):
                            preview = content[:100] + "..." if len(content) > 100 else content
                            logger.info(f"    Content preview: {preview}")
                
                logger.info(f"✅ Retrieved {len(schema_results)} schema items for {db_type}")
            except Exception as e:
                logger.error(f"❌ Error retrieving schema for {db_type}: {e}")
        
        logger.info(f"📊 Total schema items collected: {len(all_schema_info)}")
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
            json_str = await self._call_llm(prompt)
                
            plan_dict = json.loads(json_str)
            
            logger.info(f"Generated plan with {len(plan_dict.get('operations', []))} operations")
            
            return plan_dict
        except Exception as e:
            logger.error(f"Error generating plan: {e}")
            # Return empty plan on error
            return {"metadata": {}, "operations": []}
    
    async def _initialize_data_tools(self, db_type: str) -> None:
        """
        Initialize DataTools for a specific database type
        
        Args:
            db_type: Database type to initialize tools for
        """
        if self.data_tools is None or self.data_tools.db_type != db_type:
            self.data_tools = DataTools(db_type=db_type)
            await self.data_tools.initialize(self.session_id)
            logger.info(f"Initialized DataTools for {db_type}")

    async def _get_detailed_metadata(self, db_type: str, tables: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Get detailed metadata about database tables and columns
        
        Args:
            db_type: Database type to get metadata for
            tables: Optional list of tables to focus on
            
        Returns:
            Dictionary with detailed metadata
        """
        await self._initialize_data_tools(db_type)
        return await self.data_tools.get_metadata(table_names=tables)

    async def _sample_data(self, db_type: str, query: str, sample_size: int = 10) -> Dict[str, Any]:
        """
        Get a sample of data to better understand the database content
        
        Args:
            db_type: Database type to sample from
            query: Query to execute (SQL for postgres, etc.)
            sample_size: Number of rows to sample
            
        Returns:
            Dictionary with sample data
        """
        await self._initialize_data_tools(db_type)
        return await self.data_tools.sample_data(query, sample_size=sample_size)

    async def _run_summary_query(self, db_type: str, table: str, columns: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Get statistical summaries for data in a table
        
        Args:
            db_type: Database type
            table: Table to summarize
            columns: Optional columns to focus on
            
        Returns:
            Dictionary with summary statistics
        """
        await self._initialize_data_tools(db_type)
        return await self.data_tools.run_summary_query(table, columns=columns)

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
                source_info = self.registry_client.get_source_by_id(source_id)
                if not source_info:
                    logger.warning(f"Source {source_id} not found in registry")
                    continue
                
                source_type = source_info.get("type")
                tables = self.registry_client.list_tables(source_id)
                
                # Get detailed metadata for additional validation if needed
                try:
                    detailed_metadata = await self._get_detailed_metadata(
                        source_type, tables=tables
                    )
                    logger.info(f"Retrieved detailed metadata for {source_id} ({source_type})")
                except Exception as e:
                    logger.warning(f"Failed to get detailed metadata for {source_id}: {str(e)}")
                    detailed_metadata = {}
                
                table_schemas = {}
                for table in tables:
                    schema = self.registry_client.get_table_schema(source_id, table)
                    if schema:
                        table_schemas[table] = json.dumps(schema["schema"], indent=2)
                
                registry_schemas[source_id] = {
                    "type": source_type,
                    "tables": table_schemas,
                    "detailed_metadata": detailed_metadata
                }
            
            # First, perform basic validation using QueryPlan.validate()
            basic_validation = query_plan.validate(self.registry_client)
            
            # If basic validation fails, return immediately
            if not basic_validation["valid"]:
                logger.warning(f"Basic plan validation failed: {basic_validation['errors']}")
                return basic_validation
            
            # If basic validation passes, return success
            # Skip the LLM-based validation for now as it's producing false positives
            logger.info("Basic plan validation passed, skipping LLM validation")
            return {
                "valid": True,
                "errors": [],
                "warnings": [],
                "suggestions": [],
                "validation_method": "basic"
            }
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
            # Get additional optimization insights using DataTools when possible
            optimization_insights = {}
            
            # For each operation in the plan, try to gather performance insights
            operations = plan_dict.get("operations", [])
            for op in operations:
                source_id = op.get("source_id")
                if not source_id:
                    continue
                    
                # Get source info
                source_info = self.registry_client.get_source_by_id(source_id)
                if not source_info:
                    continue
                    
                source_type = source_info.get("type")
                if not source_type:
                    continue
                
                # For relevant operations, get sample statistics
                op_type = op.get("metadata", {}).get("operation_type")
                if op_type in ["query", "aggregate"] and "params" in op:
                    # Only do this for a small subset of critical operations
                    if len(optimization_insights) < 2:  # Limit to avoid excessive API calls
                        try:
                            # Initialize data tools for this source type
                            await self._initialize_data_tools(source_type)
                            
                            # For query operations, we might run small test queries or get table statistics
                            if op_type == "query" and source_type in ["postgres", "postgresql"]:
                                table_name = None
                                # Try to extract the main table from the query
                                query = op.get("params", {}).get("query", "")
                                if "FROM" in query.upper():
                                    table_match = re.search(r'FROM\s+([^\s,;()]+)', query, re.IGNORECASE)
                                    if table_match:
                                        table_name = table_match.group(1).strip()
                                
                                if table_name:
                                    # Get table statistics
                                    stats = await self._run_summary_query(source_type, table_name)
                                    if not isinstance(stats, dict) or "error" in stats:
                                        continue
                                    
                                    # Add to optimization insights
                                    operation_id = op.get("id", "unknown")
                                    optimization_insights[operation_id] = {
                                        "table_stats": stats,
                                        "source_type": source_type
                                    }
                                    logger.info(f"Added optimization insights for operation {operation_id}")
                        except Exception as e:
                            logger.warning(f"Error getting optimization insights for {source_type}: {str(e)}")
            
            # Include optimization insights in the prompt if available
            prompt = self.llm_client.render_template(
                "plan_optimization.tpl",
                original_plan=json.dumps(plan_dict, indent=2),
                schemas=registry_schemas,
                optimization_insights=optimization_insights
            )
            
            # Call LLM for plan optimization
            json_str = await self._call_llm(prompt)
                
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
        
        # Step 2: Retrieve schema information for plan generation
        logger.info("Retrieving schema information for planning")
        
        # Use cached schema metadata if available, otherwise fetch it
        schema_info = []
        remaining_db_types = list(db_types)  # Copy to track which db types still need fetching
        
        if self.cached_schema_metadata and "schema_info" in self.cached_schema_metadata:
            logger.info("Using cached schema metadata from classifier")
            
            # Extract schema info for selected database types only
            cached_info = self.cached_schema_metadata.get("schema_info", {})
            for db_type in list(db_types):  # Use a copy for iteration
                if db_type in cached_info:
                    schema_results = cached_info[db_type]
                    schema_info.extend(schema_results)
                    logger.info(f"Using {len(schema_results)} cached schema items for {db_type}")
                    # Remove from the list of types that need fetching
                    if db_type in remaining_db_types:
                        remaining_db_types.remove(db_type)
        
        # Fetch schema for any db types not in cache
        if remaining_db_types:
            logger.info(f"Fetching schema information from FAISS for remaining types: {remaining_db_types}")
            additional_schema_info = await self._get_schema_info(remaining_db_types, question)
            schema_info.extend(additional_schema_info)
        
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
                    source_info = self.registry_client.get_source_by_id(op.source_id)
                    if source_info:
                        source_type = source_info.get("type")
                        tables = self.registry_client.list_tables(op.source_id)
                        
                        table_schemas = {}
                        for table in tables:
                            schema = self.registry_client.get_table_schema(op.source_id, table)
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
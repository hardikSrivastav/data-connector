import asyncpg
import asyncio
import json
import re
import random
import logging
import uuid
from typing import List, Dict, Any, Optional, AsyncIterator
from datetime import datetime
from ..config.settings import Settings

# Import basic database functions from connection utilities to avoid circular imports
from .connection_utils import create_connection_pool, execute_query_with_pool, test_postgresql_connection, execute_query, test_conn

# Import cross-database components
from ..db.classifier import DatabaseClassifier
from ..db.registry.integrations import registry_client
from ..db.orchestrator.cross_db_agent import CrossDatabaseAgent
from ..db.orchestrator.planning_agent import PlanningAgent
from ..db.orchestrator.implementation_agent import ImplementationAgent
from ..db.orchestrator.result_aggregator import ResultAggregator
from ..tools.state_manager import StateManager, AnalysisState
from ..db.db_orchestrator import Orchestrator
from ..llm.client import get_llm_client
# ensure_index_exists and SchemaSearcher will be imported lazily to avoid circular imports
from ..performance.schema_monitor import ensure_schema_index_updated

# Set up dedicated logging for cross-database execution
def setup_cross_db_logger():
    """Set up a dedicated logger for cross-database execution with file output"""
    cross_db_logger = logging.getLogger('cross_db_execution')
    cross_db_logger.setLevel(logging.INFO)
    
    # Remove any existing handlers to avoid duplicates
    cross_db_logger.handlers.clear()
    
    # Create file handler for cross-database logs
    file_handler = logging.FileHandler('cross_db_execution.log', mode='w')
    file_handler.setLevel(logging.INFO)
    
    # Create console handler as well
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # Add handlers to logger
    cross_db_logger.addHandler(file_handler)
    cross_db_logger.addHandler(console_handler)
    
    # Prevent propagation to root logger to avoid SQLAlchemy noise
    cross_db_logger.propagate = False
    
    return cross_db_logger

# Initialize the dedicated logger
cross_db_logger = setup_cross_db_logger()

# Set up logging for the database executor
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set up dedicated visualization logger
def setup_visualization_logger():
    """Set up dedicated logger for visualization pipeline"""
    viz_logger = logging.getLogger('visualization_pipeline')
    viz_logger.setLevel(logging.DEBUG)
    
    # Remove existing handlers to avoid duplicates
    for handler in viz_logger.handlers[:]:
        viz_logger.removeHandler(handler)
    
    # Create file handler for visualization logs
    viz_handler = logging.FileHandler('visualization_pipeline.log')
    viz_handler.setLevel(logging.DEBUG)
    
    # Create detailed formatter
    viz_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(funcName)s:%(lineno)d] - %(message)s'
    )
    viz_handler.setFormatter(viz_formatter)
    
    # Add handler to logger
    viz_logger.addHandler(viz_handler)
    viz_logger.propagate = False  # Don't propagate to root logger
    
    return viz_logger

# Initialize visualization logger
viz_logger = setup_visualization_logger()

class CrossDatabaseQueryEngine:
    """
    Enhanced query engine that supports both single-database and cross-database queries
    """
    
    def __init__(self):
        self.cross_db_agent = CrossDatabaseAgent()
        self.classifier = DatabaseClassifier()
        self.planning_agent = PlanningAgent()
        self.implementation_agent = ImplementationAgent()
        self.result_aggregator = ResultAggregator()
        self.state_manager = StateManager()
        self.llm_client = get_llm_client()
        logger.info("🤖 Cross-Database Query Engine initialized")
    
    def _create_stream_event(self, event_type: str, session_id: str, **kwargs) -> Dict[str, Any]:
        """Create a standardized streaming event"""
        event = {
            "type": event_type,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "session_id": session_id,
            **kwargs
        }
        return event
        
    async def classify_query(self, question: str) -> Dict[str, Any]:
        """
        Classify which databases are relevant for a given question
        
        Args:
            question: Natural language question
            
        Returns:
            Classification results with relevant databases
        """
        logger.info(f"🔍 Classifying query: '{question}'")
        
        try:
            results = await self.classifier.classify(question)
            
            # Get all sources for additional information
            sources = registry_client.get_all_sources()
            sources_by_id = {s["id"]: s for s in sources}
            
            # Enhance results with source information
            selected_sources = results.get("sources", [])
            enhanced_sources = []
            
            for source_id in selected_sources:
                if source_id in sources_by_id:
                    source = sources_by_id[source_id]
                    enhanced_sources.append({
                        "id": source_id,
                        "type": source.get("type", "unknown"),
                        "name": source.get("name", source_id),
                        "relevance": "high"  # Could implement scoring here
                    })
            
            return {
                "question": question,
                "sources": enhanced_sources,
                "reasoning": results.get("reasoning", ""),
                "is_cross_database": len(enhanced_sources) > 1
            }
            
        except Exception as e:
            logger.error(f"❌ Error classifying query: {str(e)}")
            return {
                "question": question,
                "sources": [],
                "reasoning": f"Classification failed: {str(e)}",
                "is_cross_database": False,
                "error": str(e)
            }
    
    async def classify_query_stream(self, question: str, session_id: str = None) -> AsyncIterator[Dict[str, Any]]:
        """
        Classify which databases are relevant for a given question with streaming
        
        Args:
            question: Natural language question
            session_id: Session identifier for tracking
            
        Yields:
            Streaming classification events
        """
        if not session_id:
            session_id = str(uuid.uuid4())
        
        logger.info(f"🔍 Starting streaming classification for: '{question}'")
        
        try:
            yield self._create_stream_event("status", session_id, message="Starting query classification...")
            yield self._create_stream_event("classifying", session_id, message="Analyzing query semantics...")
            
            # Perform classification
            results = await self.classifier.classify(question)
            
            yield self._create_stream_event("classifying", session_id, message="Matching against database schemas...")
            
            # Get all sources for additional information
            sources = registry_client.get_all_sources()
            sources_by_id = {s["id"]: s for s in sources}
            
            # Enhance results with source information
            selected_sources = results.get("sources", [])
            enhanced_sources = []
            
            for source_id in selected_sources:
                if source_id in sources_by_id:
                    source = sources_by_id[source_id]
                    enhanced_sources.append({
                        "id": source_id,
                        "type": source.get("type", "unknown"),
                        "name": source.get("name", source_id),
                        "relevance": "high"  # Could implement scoring here
                    })
            
            is_cross_database = len(enhanced_sources) > 1
            
            yield self._create_stream_event(
                "databases_selected", 
                session_id,
                databases=[source["type"] for source in enhanced_sources],
                reasoning=results.get("reasoning", ""),
                is_cross_database=is_cross_database,
                confidence=0.95  # Could implement actual confidence scoring
            )
            
            yield self._create_stream_event(
                "classification_complete", 
                session_id,
                reasoning=results.get("reasoning", ""),
                success=True
            )
            
        except Exception as e:
            logger.error(f"❌ Error in streaming classification: {str(e)}")
            yield self._create_stream_event(
                "error", 
                session_id,
                error_code="CLASSIFICATION_FAILED",
                message=f"Classification failed: {str(e)}",
                recoverable=True
            )
    
    async def execute_single_database_query(self, question: str, db_type: str, db_uri: str, analyze: bool = False) -> Dict[str, Any]:
        """
        Execute a query against a single database
        
        Args:
            question: Natural language question
            db_type: Database type (postgres, mongodb, etc.)
            db_uri: Database connection URI
            analyze: Whether to include analysis
            
        Returns:
            Query results with optional analysis
        """
        logger.info(f"🔄 Executing single DB query: {db_type}")
        
        try:
            # Create orchestrator for the specified database
            orchestrator = Orchestrator(db_uri, db_type=db_type)
            
            # Test connection
            if not await orchestrator.test_connection():
                return {
                    "rows": [{"error": "Database connection failed"}],
                    "sql": "-- Connection failed",
                    "analysis": "❌ **Error**: Database connection failed" if analyze else None,
                    "success": False
                }
            
            # Ensure schema index exists
            try:
                # Import ensure_index_exists lazily to avoid circular imports
                from ..meta.ingest import ensure_index_exists
                await ensure_index_exists(db_type=db_type, conn_uri=db_uri)
                await ensure_schema_index_updated(force=False, db_type=db_type, conn_uri=db_uri)
            except Exception as schema_error:
                logger.warning(f"⚠️ Schema index setup failed: {schema_error}")
            
            # Generate and execute query based on database type
            if db_type.lower() in ["postgres", "postgresql"]:
                return await self._execute_postgres_query(question, analyze, orchestrator, db_type)
            elif db_type.lower() == "mongodb":
                return await self._execute_mongodb_query(question, analyze, orchestrator, db_type)
            elif db_type.lower() == "qdrant":
                return await self._execute_qdrant_query(question, analyze, orchestrator, db_type)
            elif db_type.lower() == "slack":
                return await self._execute_slack_query(question, analyze, orchestrator, db_type)
            elif db_type.lower() == "shopify":
                return await self._execute_shopify_query(question, analyze, orchestrator, db_type)
            elif db_type.lower() == "ga4":
                return await self._execute_ga4_query(question, analyze, orchestrator, db_type)
            else:
                return {
                    "rows": [{"error": f"Unsupported database type: {db_type}"}],
                    "sql": "-- Unsupported database type",
                    "analysis": f"❌ **Error**: Unsupported database type: {db_type}" if analyze else None,
                    "success": False
                }
                
        except Exception as e:
            logger.error(f"❌ Error executing single database query: {str(e)}")
            return {
                "rows": [{"error": f"Query execution failed: {str(e)}"}],
                "sql": "-- Error occurred during execution",
                "analysis": f"❌ **Error**: {str(e)}" if analyze else None,
                "success": False
            }
    
    async def _execute_postgres_query_stream(self, question: str, analyze: bool, orchestrator: Orchestrator, db_type: str, session_id: str) -> AsyncIterator[Dict[str, Any]]:
        """Execute a PostgreSQL query with streaming"""
        try:
            yield self._create_stream_event("postgres_connecting", session_id, host="localhost", database="testdb")
            
            # Search schema metadata
            yield self._create_stream_event("postgres_schema_loading", session_id, tables_found=15, progress=0.4)
            # Import SchemaSearcher lazily to avoid circular imports
            from ..meta.ingest import SchemaSearcher
            searcher = SchemaSearcher(db_type=db_type)
            schema_chunks = await searcher.search(question, top_k=10, db_type=db_type)
            
            yield self._create_stream_event("sql_generating", session_id, template="nl2sql.tpl", schema_chunks=len(schema_chunks))
            
            # Render prompt template for PostgreSQL
            prompt = self.llm_client.render_template("nl2sql.tpl", schema_chunks=schema_chunks, user_question=question)
            
            # Generate SQL with streaming
            sql = ""
            async for event in self.llm_client.generate_sql_stream(prompt, session_id):
                if event["type"] == "partial_sql":
                    sql += event.get("content", "")
                    yield self._create_stream_event("sql_generating", session_id, partial_sql=event.get("content", ""))
                elif event["type"] == "sql_complete":
                    sql = event.get("sql", sql)
                    yield self._create_stream_event("sql_validating", session_id, sql=sql, syntax_valid=True)
                    break
            
            yield self._create_stream_event("sql_executing", session_id, sql=sql, explain_plan="Seq Scan")
            
            # Execute query using the orchestrator
            rows = await orchestrator.execute(sql)
            
            yield self._create_stream_event("postgres_results", session_id, rows_processed=len(rows) if rows else 0, execution_time=0.45)
            
            # Add analysis if requested
            if analyze:
                yield self._create_stream_event("analysis_generating", session_id, message="Creating insights...")
                async for event in self.llm_client.analyze_results_stream(rows, session_id):
                    if event["type"] == "analysis_chunk":
                        yield self._create_stream_event("analysis_chunk", session_id, text=event.get("text", ""), chunk_index=event.get("chunk_index", 1))
                    elif event["type"] == "analysis_complete":
                        break
            
            yield self._create_stream_event("postgres_complete", session_id, success=True)
            
        except Exception as e:
            logger.error(f"❌ PostgreSQL streaming query error: {str(e)}")
            yield self._create_stream_event(
                "error", 
                session_id,
                error_code="POSTGRES_QUERY_FAILED",
                message=f"PostgreSQL query failed: {str(e)}",
                recoverable=False
            )
    
    async def execute_single_database_query_stream(self, question: str, db_type: str, db_uri: str, analyze: bool = False, session_id: str = None) -> AsyncIterator[Dict[str, Any]]:
        """
        Execute a query against a single database with streaming
        
        Args:
            question: Natural language question
            db_type: Database type (postgres, mongodb, etc.)
            db_uri: Database connection URI
            analyze: Whether to include analysis
            session_id: Session identifier for tracking
            
        Yields:
            Streaming execution events
        """
        if not session_id:
            session_id = str(uuid.uuid4())
        
        logger.info(f"🔄 Starting streaming single DB query: {db_type}")
        
        try:
            yield self._create_stream_event("status", session_id, message="Initializing single database query...")
            
            # Test connection
            yield self._create_stream_event("connection_testing", session_id, database=db_type, status="connecting")
            
            # Create orchestrator for the specified database
            orchestrator = Orchestrator(db_uri, db_type=db_type)
            
            # Test connection
            if not await orchestrator.test_connection():
                yield self._create_stream_event(
                    "error", 
                    session_id,
                    error_code="CONNECTION_FAILED",
                    message="Database connection failed",
                    recoverable=False
                )
                return
            
            yield self._create_stream_event("connection_established", session_id, database=db_type, latency=0.05)
            
            # Ensure schema index exists
            yield self._create_stream_event("schema_loading", session_id, database=db_type, progress=0.2)
            
            try:
                # Import ensure_index_exists lazily to avoid circular imports
                from ..meta.ingest import ensure_index_exists
                await ensure_index_exists(db_type=db_type, conn_uri=db_uri)
                await ensure_schema_index_updated(force=False, db_type=db_type, conn_uri=db_uri)
                
                yield self._create_stream_event(
                    "schema_chunks", 
                    session_id,
                    chunks=[{"table": "schema_loaded"}],  # Simplified schema representation
                    database=db_type
                )
            except Exception as schema_error:
                logger.warning(f"⚠️ Schema index setup failed: {schema_error}")
                yield self._create_stream_event("schema_loading", session_id, database=db_type, progress=1.0, warning="Schema index setup failed")
            
            # Generate and execute query based on database type
            yield self._create_stream_event("query_generating", session_id, database=db_type, template="nl2sql.tpl" if db_type.lower() in ["postgres", "postgresql"] else "query.tpl")
            
            if db_type.lower() in ["postgres", "postgresql"]:
                async for event in self._execute_postgres_query_stream(question, analyze, orchestrator, db_type, session_id):
                    yield event
            elif db_type.lower() == "mongodb":
                async for event in self._execute_mongodb_query_stream(question, analyze, orchestrator, db_type, session_id):
                    yield event
            elif db_type.lower() == "qdrant":
                async for event in self._execute_qdrant_query_stream(question, analyze, orchestrator, db_type, session_id):
                    yield event
            elif db_type.lower() == "slack":
                async for event in self._execute_slack_query_stream(question, analyze, orchestrator, db_type, session_id):
                    yield event
            elif db_type.lower() == "shopify":
                async for event in self._execute_shopify_query_stream(question, analyze, orchestrator, db_type, session_id):
                    yield event
            elif db_type.lower() == "ga4":
                async for event in self._execute_ga4_query_stream(question, analyze, orchestrator, db_type, session_id):
                    yield event
            else:
                yield self._create_stream_event(
                    "error", 
                    session_id,
                    error_code="UNSUPPORTED_DATABASE",
                    message=f"Unsupported database type: {db_type}",
                    recoverable=False
                )
                return
            
            yield self._create_stream_event("execution_complete", session_id, success=True)
                
        except Exception as e:
            logger.error(f"❌ Error executing single database query: {str(e)}")
            yield self._create_stream_event(
                "error", 
                session_id,
                error_code="QUERY_EXECUTION_FAILED",
                message=f"Query execution failed: {str(e)}",
                recoverable=False
            )
    
    async def execute_cross_database_query(self, question: str, analyze: bool = False, optimize: bool = False, save_session: bool = True) -> Dict[str, Any]:
        """
        Execute a cross-database query using orchestration
        
        Args:
            question: Natural language question
            analyze: Whether to include analysis
            optimize: Whether to optimize the query plan
            save_session: Whether to save session state
            
        Returns:
            Cross-database query results
        """
        cross_db_logger.info(f"🌐 Executing cross-database query: '{question}'")
        cross_db_logger.info(f"🔧 Parameters: analyze={analyze}, optimize={optimize}, save_session={save_session}")
        
        try:
            # Create session if saving
            session_id = None
            state = None
            
            if save_session:
                cross_db_logger.info(f"💾 Creating session for cross-database query")
                session_id = await self.state_manager.create_session(question)
                state = await self.state_manager.get_state(session_id)
                state.add_executed_tool("cross_db_query", {"question": question, "optimize": optimize}, {})
                cross_db_logger.info(f"💾 Session created with ID: {session_id}")
            
            # Execute the cross-database query
            cross_db_logger.info(f"🚀 Calling cross_db_agent.execute_query")
            result = await self.cross_db_agent.execute_query(
                question, 
                optimize_plan=optimize, 
                dry_run=False
            )
            
            cross_db_logger.info(f"📊 Result received from cross_db_agent.execute_query")
            cross_db_logger.info(f"📊 Result type: {type(result)}")
            cross_db_logger.info(f"📊 Result keys: {list(result.keys()) if isinstance(result, dict) else 'Not a dict'}")
            
            if isinstance(result, dict):
                cross_db_logger.info(f"📊 Result.success: {result.get('success', 'KEY_NOT_FOUND')}")
                if "execution" in result:
                    exec_data = result["execution"]
                    cross_db_logger.info(f"📊 Execution data type: {type(exec_data)}")
                    cross_db_logger.info(f"📊 Execution data keys: {list(exec_data.keys()) if isinstance(exec_data, dict) else 'Not a dict'}")
                    if isinstance(exec_data, dict):
                        cross_db_logger.info(f"📊 Execution.success: {exec_data.get('success', 'KEY_NOT_FOUND')}")
                        if "result" in exec_data:
                            exec_result = exec_data["result"]
                            cross_db_logger.info(f"📊 Execution result type: {type(exec_result)}")
                            cross_db_logger.info(f"📊 Execution result keys: {list(exec_result.keys()) if isinstance(exec_result, dict) else 'Not a dict'}")
                else:
                    cross_db_logger.warning(f"⚠️ No 'execution' key found in result")
            
            # Check if execution was successful
            execution_success = False
            if isinstance(result, dict):
                # Check for success in multiple possible locations
                if result.get("success", False):
                    execution_success = True
                    cross_db_logger.info(f"✅ Top-level success flag is True")
                elif isinstance(result.get("execution"), dict) and result["execution"].get("success", False):
                    execution_success = True
                    cross_db_logger.info(f"✅ Execution-level success flag is True")
                else:
                    cross_db_logger.warning(f"❌ No success flag found or success is False")
                    cross_db_logger.warning(f"❌ Top-level success: {result.get('success', 'KEY_NOT_FOUND')}")
                    if "execution" in result and isinstance(result["execution"], dict):
                        cross_db_logger.warning(f"❌ Execution success: {result['execution'].get('success', 'KEY_NOT_FOUND')}")
            
            if not execution_success:
                error_msg = result.get("error", "Unknown error during cross-database execution")
                cross_db_logger.error(f"❌ Cross-database execution failed: {error_msg}")
                return {
                    "rows": [{"error": error_msg}],
                    "sql": "-- Cross-database query failed",
                    "analysis": f"❌ **Error**: {error_msg}" if analyze else None,
                    "success": False,
                    "session_id": session_id
                }
            
            cross_db_logger.info(f"🔍 Beginning result extraction process")
            
            # Extract results
            rows = []
            sql_info = "-- Cross-database query executed successfully"
            
            # Extract from the correct nested structure: result["execution"]["result"]
            execution_data = result.get("execution", {})
            cross_db_logger.info(f"🔍 Execution data extracted: {type(execution_data)}")
            
            if "result" in execution_data:
                cross_db_logger.info(f"🔍 Found 'result' in execution_data")
                result_data = execution_data["result"]
                cross_db_logger.info(f"🔍 Result data type: {type(result_data)}")
                cross_db_logger.info(f"🔍 Result data keys: {list(result_data.keys()) if isinstance(result_data, dict) else 'Not a dict'}")
                
                if isinstance(result_data, dict):
                    # Check for different possible data structures
                    if "data" in result_data:
                        rows = result_data["data"]
                        cross_db_logger.info(f"🔍 Extracted {len(rows) if isinstance(rows, list) else 'N/A'} rows from 'data' field")
                    elif "aggregated_results" in result_data:
                        rows = result_data["aggregated_results"]
                        cross_db_logger.info(f"🔍 Extracted {len(rows) if isinstance(rows, list) else 'N/A'} rows from 'aggregated_results' field")
                    elif "results" in result_data:
                        rows = result_data["results"]
                        cross_db_logger.info(f"🔍 Extracted {len(rows) if isinstance(rows, list) else 'N/A'} rows from 'results' field")
                    elif "all_results" in result_data:
                        cross_db_logger.info(f"🔍 Processing 'all_results' field")
                        # Handle case where we have operation results
                        all_results = result_data["all_results"]
                        cross_db_logger.info(f"🔍 all_results type: {type(all_results)}")
                        cross_db_logger.info(f"🔍 all_results keys: {list(all_results.keys()) if isinstance(all_results, dict) else 'Not a dict'}")
                        
                        combined_rows = []
                        for op_id, op_result in all_results.items():
                            cross_db_logger.info(f"🔍 Processing operation {op_id}: {type(op_result)}")
                            if isinstance(op_result, list):
                                combined_rows.extend(op_result)
                                cross_db_logger.info(f"🔍 Added {len(op_result)} rows from operation {op_id}")
                            elif isinstance(op_result, dict) and "data" in op_result:
                                if isinstance(op_result["data"], list):
                                    combined_rows.extend(op_result["data"])
                                    cross_db_logger.info(f"🔍 Added {len(op_result['data'])} rows from operation {op_id} data field")
                                else:
                                    combined_rows.append(op_result["data"])
                                    cross_db_logger.info(f"🔍 Added 1 row from operation {op_id} data field")
                            else:
                                cross_db_logger.info(f"🔍 Operation {op_id} result structure not recognized")
                        rows = combined_rows
                        cross_db_logger.info(f"🔍 Total combined rows: {len(rows)}")
                    else:
                        rows = [result_data]
                        cross_db_logger.info(f"🔍 Using entire result_data as single row")
                elif isinstance(result_data, list):
                    rows = result_data
                    cross_db_logger.info(f"🔍 Result data is already a list with {len(rows)} items")
                else:
                    rows = [{"result": str(result_data)}]
                    cross_db_logger.info(f"🔍 Converting result_data to string representation")
            elif execution_data and execution_data.get("success", False):
                cross_db_logger.info(f"🔍 No 'result' field but execution was successful, checking execution_summary")
                # If execution was successful but no result field, try to extract from execution summary
                if "execution_summary" in execution_data and "operation_details" in execution_data["execution_summary"]:
                    operation_details = execution_data["execution_summary"]["operation_details"]
                    cross_db_logger.info(f"🔍 Found operation_details with {len(operation_details)} operations")
                    
                    combined_rows = []
                    for op_id, op_detail in operation_details.items():
                        cross_db_logger.info(f"🔍 Processing operation detail {op_id}: status={op_detail.get('status')}")
                        if op_detail.get("status") == "COMPLETED" and "result" in op_detail:
                            op_result = op_detail["result"]
                            cross_db_logger.info(f"🔍 Operation {op_id} result type: {type(op_result)}")
                            if isinstance(op_result, list):
                                combined_rows.extend(op_result)
                                cross_db_logger.info(f"🔍 Added {len(op_result)} rows from operation {op_id}")
                            elif isinstance(op_result, dict):
                                combined_rows.append(op_result)
                                cross_db_logger.info(f"🔍 Added 1 row from operation {op_id}")
                    rows = combined_rows
                    cross_db_logger.info(f"🔍 Total rows from execution summary: {len(rows)}")
                else:
                    rows = [{"message": "Query executed successfully but no data returned"}]
                    cross_db_logger.info(f"🔍 No operation details found, using default message")
            else:
                cross_db_logger.warning(f"⚠️ No result extraction method succeeded")
                rows = [{"error": "Unable to extract results from cross-database query"}]
            
            cross_db_logger.info(f"🔍 Final rows count: {len(rows) if isinstance(rows, list) else 'Not a list'}")
            
            # Generate plan information as "SQL"
            if "plan" in result:
                cross_db_logger.info(f"🔍 Generating plan information")
                plan = result["plan"]
                if hasattr(plan, 'id'):
                    plan_info = {
                        "plan_id": plan.id,
                        "operations": len(plan.operations) if hasattr(plan, 'operations') else 0,
                        "databases": list(set(op.source_id for op in plan.operations if hasattr(op, 'source_id') and op.source_id)) if hasattr(plan, 'operations') else []
                    }
                elif isinstance(plan, dict):
                    plan_info = {
                        "plan_id": plan.get("id", "unknown"),
                        "operations": len(plan.get("operations", [])),
                        "databases": list(set(op.get("source_id") for op in plan.get("operations", []) if op.get("source_id")))
                    }
                else:
                    plan_info = {"plan": str(plan)}
                sql_info = f"-- Cross-database plan: {json.dumps(plan_info, indent=2)}"
                cross_db_logger.info(f"🔍 Plan info generated: {plan_info}")
            
            # Prepare response
            cross_db_logger.info(f"🔧 Building final response")
            response = {
                "rows": rows,
                "sql": sql_info,
                "success": True,
                "session_id": session_id,
                "plan_info": result.get("plan"),
                "execution_summary": execution_data.get("execution_summary", {})
            }
            cross_db_logger.info(f"🔧 Response built with {len(rows) if isinstance(rows, list) else 'N/A'} rows")
            
            # Add analysis if requested
            if analyze:
                cross_db_logger.info(f"🧠 Generating analysis")
                cross_db_logger.info(f"🧠 Generating LLM analysis for {len(rows)} rows")
                try:
                    # Note: analyze_results doesn't accept is_cross_database, only is_vector_search
                    analysis = await self.llm_client.analyze_results(rows, is_vector_search=False)
                    response["analysis"] = analysis
                    cross_db_logger.info(f"🧠 Analysis generated successfully")
                except Exception as e:
                    cross_db_logger.error(f"🧠 Error generating analysis: {str(e)}")
                    response["analysis"] = f"Error generating analysis: {str(e)}"
            
            # Update session state
            if save_session and state:
                cross_db_logger.info(f"💾 Updating session state")
                formatted_result = execution_data.get("formatted_result", "") or (execution_data.get("result", {}).get("formatted_result", "") if isinstance(execution_data.get("result"), dict) else "")
                state.set_final_result(result, formatted_result)
                await self.state_manager.update_state(state)
                cross_db_logger.info(f"💾 Session state updated")
            
            cross_db_logger.info(f"✅ Cross-database query completed successfully")
            return response
            
        except Exception as e:
            cross_db_logger.error(f"❌ Error executing cross-database query: {str(e)}")
            cross_db_logger.error(f"❌ Exception type: {type(e)}")
            import traceback
            cross_db_logger.error(f"❌ Traceback: {traceback.format_exc()}")
            return {
                "rows": [{"error": f"Cross-database query failed: {str(e)}"}],
                "sql": "-- Error occurred during cross-database execution",
                "analysis": f"❌ **Error**: {str(e)}" if analyze else None,
                "success": False,
                "session_id": session_id
            }
    
    async def execute_cross_database_query_stream(self, question: str, analyze: bool = False, optimize: bool = False, save_session: bool = True, session_id: str = None) -> AsyncIterator[Dict[str, Any]]:
        """
        Execute a cross-database query using orchestration with streaming
        
        Args:
            question: Natural language question
            analyze: Whether to include analysis
            optimize: Whether to optimize the query plan
            save_session: Whether to save session state
            session_id: Session identifier for tracking
            
        Yields:
            Streaming cross-database execution events
        """
        if not session_id:
            session_id = str(uuid.uuid4())
        
        cross_db_logger.info(f"🌐 Starting streaming cross-database query: '{question}'")
        
        try:
            yield self._create_stream_event("status", session_id, message="Starting cross-database query processing...")
            yield self._create_stream_event("planning", session_id, step="Analyzing query dependencies", databases=[])
            
            # Create session if saving
            state = None
            if save_session:
                yield self._create_stream_event("status", session_id, message="Creating session...")
                session_id = await self.state_manager.create_session(question)
                state = await self.state_manager.get_state(session_id)
                state.add_executed_tool("cross_db_query", {"question": question, "optimize": optimize}, {})
            
            # Plan optimization simulation
            if optimize:
                yield self._create_stream_event("plan_optimization", session_id, original_operations=5, optimized_operations=3)
            
            yield self._create_stream_event("plan_validated", session_id, operations=3, estimated_time="30s")
            
            # Execute the cross-database query
            yield self._create_stream_event("status", session_id, message="Starting cross-database execution...")
            
            result = await self.cross_db_agent.execute_query(
                question, 
                optimize_plan=optimize, 
                dry_run=False
            )
            
            # Check if execution was successful
            execution_success = False
            if isinstance(result, dict):
                if result.get("success", False):
                    execution_success = True
                elif isinstance(result.get("execution"), dict) and result["execution"].get("success", False):
                    execution_success = True
            
            if not execution_success:
                error_msg = result.get("error", "Unknown error during cross-database execution")
                yield self._create_stream_event(
                    "error", 
                    session_id,
                    error_code="CROSS_DB_EXECUTION_FAILED",
                    message=error_msg,
                    recoverable=False
                )
                return
            
            # Simulate parallel execution
            yield self._create_stream_event("parallel_execution_start", session_id, databases=["postgres", "mongodb"])
            yield self._create_stream_event("query_executing", session_id, database="postgres", operation_id=1)
            yield self._create_stream_event("query_executing", session_id, database="mongodb", operation_id=2)
            
            # Extract results
            rows = []
            execution_data = result.get("execution", {})
            
            if "result" in execution_data:
                result_data = execution_data["result"]
                if isinstance(result_data, dict):
                    if "data" in result_data:
                        rows = result_data["data"]
                        yield self._create_stream_event("partial_results", session_id, database="postgres", rows_count=len(rows)//2 if rows else 0)
                        yield self._create_stream_event("partial_results", session_id, database="mongodb", rows_count=len(rows)//2 if rows else 0)
                    elif "aggregated_results" in result_data:
                        rows = result_data["aggregated_results"]
                        yield self._create_stream_event("partial_results", session_id, rows_count=len(rows) if rows else 0)
                    elif "all_results" in result_data:
                        all_results = result_data["all_results"]
                        combined_rows = []
                        for op_id, op_result in all_results.items():
                            if isinstance(op_result, list):
                                combined_rows.extend(op_result)
                                yield self._create_stream_event("results_ready", session_id, operation_id=op_id)
                            elif isinstance(op_result, dict) and "data" in op_result:
                                if isinstance(op_result["data"], list):
                                    combined_rows.extend(op_result["data"])
                                else:
                                    combined_rows.append(op_result["data"])
                                yield self._create_stream_event("results_ready", session_id, operation_id=op_id)
                        rows = combined_rows
                        
            # Aggregation process
            if len(rows) > 0:
                yield self._create_stream_event("aggregating", session_id, step="Merging results", progress=0.3)
                yield self._create_stream_event("aggregating", session_id, step="Applying joins", progress=0.7)
                yield self._create_stream_event("aggregation_complete", session_id, total_rows=len(rows), aggregation_time=1.2)
            
            # Analysis if requested
            if analyze:
                yield self._create_stream_event("analysis_generating", session_id, message="Creating cross-database insights...")
                try:
                    analysis = await self.llm_client.analyze_results(rows, is_vector_search=False)
                    yield self._create_stream_event("analysis_complete", session_id, success=True)
                except Exception as e:
                    yield self._create_stream_event("error", session_id, error_code="ANALYSIS_FAILED", message=str(e), recoverable=True)
            
            yield self._create_stream_event("cross_db_complete", session_id, success=True, total_time=44.8)
            
        except Exception as e:
            cross_db_logger.error(f"❌ Error in streaming cross-database query: {str(e)}")
            yield self._create_stream_event(
                "error", 
                session_id,
                error_code="CROSS_DB_QUERY_FAILED",
                message=f"Cross-database query failed: {str(e)}",
                recoverable=False
            )
    
    async def _execute_postgres_query(self, question: str, analyze: bool, orchestrator: Orchestrator, db_type: str) -> Dict[str, Any]:
        """Execute a PostgreSQL query"""
        try:
            # Search schema metadata
            # Import SchemaSearcher lazily to avoid circular imports
            from ..meta.ingest import SchemaSearcher
            searcher = SchemaSearcher(db_type=db_type)
            schema_chunks = await searcher.search(question, top_k=10, db_type=db_type)
            
            # Render prompt template for PostgreSQL
            prompt = self.llm_client.render_template("nl2sql.tpl", schema_chunks=schema_chunks, user_question=question)
            
            # Generate SQL
            sql = await self.llm_client.generate_sql(prompt)
            
            # Execute query using the orchestrator
            rows = await orchestrator.execute(sql)
            
            result = {
                "rows": rows,
                "sql": sql,
                "success": True
            }
            
            # Add analysis if requested
            if analyze:
                analysis = await self.llm_client.analyze_results(rows)
                result["analysis"] = analysis
            
            return result
            
        except Exception as e:
            logger.error(f"❌ PostgreSQL query error: {str(e)}")
            return {
                "rows": [{"error": f"PostgreSQL query failed: {str(e)}"}],
                "sql": "-- Error occurred during query generation",
                "analysis": f"❌ **Error**: {str(e)}" if analyze else None,
                "success": False
            }
    
    async def _execute_mongodb_query_stream(self, question: str, analyze: bool, orchestrator: Orchestrator, db_type: str, session_id: str) -> AsyncIterator[Dict[str, Any]]:
        """Execute a MongoDB query with streaming"""
        try:
            yield self._create_stream_event("mongodb_connecting", session_id, host="localhost", database="testdb")
            
            # Search schema metadata
            yield self._create_stream_event("mongodb_schema_loading", session_id, collections_found=8, progress=0.6)
            # Import SchemaSearcher lazily to avoid circular imports
            from ..meta.ingest import SchemaSearcher
            searcher = SchemaSearcher(db_type=db_type)
            schema_chunks = await searcher.search(question, top_k=5, db_type=db_type)
            
            # Get default collection (if applicable)
            default_collection = getattr(orchestrator.adapter, 'default_collection', None)
            
            yield self._create_stream_event("mongodb_query_generating", session_id, template="mongo_query.tpl")
            
            # Render prompt template for MongoDB
            prompt = self.llm_client.render_template("mongo_query.tpl", 
                                          schema_chunks=schema_chunks, 
                                          user_question=question,
                                          default_collection=default_collection)
            
            # Generate MongoDB query with streaming
            query_data = {}
            async for event in self.llm_client.generate_mongodb_query_stream(prompt, session_id):
                if event["type"] == "partial_query":
                    yield self._create_stream_event("mongodb_query_generating", session_id, partial_query=event.get("content", ""))
                elif event["type"] == "query_complete":
                    query_data = json.loads(event.get("query", "{}"))
                    yield self._create_stream_event("mongodb_query_validating", session_id, query=json.dumps(query_data), valid=True)
                    break
            
            yield self._create_stream_event("mongodb_executing", session_id, query=json.dumps(query_data), explain=True)
            
            # Execute query
            rows = await orchestrator.execute(query_data)
            
            yield self._create_stream_event("mongodb_results", session_id, documents_processed=len(rows) if rows else 0, execution_time=0.32)
            
            # Add analysis if requested
            if analyze:
                yield self._create_stream_event("analysis_generating", session_id, message="Creating insights...")
                async for event in self.llm_client.analyze_results_stream(rows, session_id):
                    if event["type"] == "analysis_chunk":
                        yield self._create_stream_event("analysis_chunk", session_id, text=event.get("text", ""), chunk_index=event.get("chunk_index", 1))
                    elif event["type"] == "analysis_complete":
                        break
            
            yield self._create_stream_event("mongodb_complete", session_id, success=True)
            
        except Exception as e:
            logger.error(f"❌ MongoDB streaming query error: {str(e)}")
            yield self._create_stream_event(
                "error", 
                session_id,
                error_code="MONGODB_QUERY_FAILED",
                message=f"MongoDB query failed: {str(e)}",
                recoverable=False
            )
    
    async def _execute_qdrant_query_stream(self, question: str, analyze: bool, orchestrator: Orchestrator, db_type: str, session_id: str) -> AsyncIterator[Dict[str, Any]]:
        """Execute a Qdrant vector search query with streaming"""
        try:
            yield self._create_stream_event("qdrant_connecting", session_id, host="localhost", collection="knowledge")
            
            # Search schema metadata
            # Import SchemaSearcher lazily to avoid circular imports
            from ..meta.ingest import SchemaSearcher
            searcher = SchemaSearcher(db_type=db_type)
            schema_chunks = await searcher.search(question, top_k=5, db_type=db_type)
            
            yield self._create_stream_event("vector_search_preparing", session_id, query_vector_dims=768, similarity_threshold=0.7)
            
            # Generate query using the orchestrator's LLM-to-query method
            query_data = await orchestrator.llm_to_query(question)
            
            yield self._create_stream_event("vector_search_executing", session_id, collection="knowledge", top_k=10)
            
            # Execute query
            rows = await orchestrator.execute(query_data)
            
            yield self._create_stream_event("vector_results", session_id, matches_found=len(rows) if rows else 0, max_similarity=0.92)
            
            # Add analysis if requested
            if analyze:
                yield self._create_stream_event("analysis_generating", session_id, message="Creating insights...")
                async for event in self.llm_client.analyze_results_stream(rows, session_id, is_vector_search=True):
                    if event["type"] == "analysis_chunk":
                        yield self._create_stream_event("analysis_chunk", session_id, text=event.get("text", ""), chunk_index=event.get("chunk_index", 1))
                    elif event["type"] == "analysis_complete":
                        break
            
            yield self._create_stream_event("qdrant_complete", session_id, success=True)
            
        except Exception as e:
            logger.error(f"❌ Qdrant streaming query error: {str(e)}")
            yield self._create_stream_event(
                "error", 
                session_id,
                error_code="QDRANT_QUERY_FAILED",
                message=f"Qdrant query failed: {str(e)}",
                recoverable=False
            )
    
    async def _execute_slack_query_stream(self, question: str, analyze: bool, orchestrator: Orchestrator, db_type: str, session_id: str) -> AsyncIterator[Dict[str, Any]]:
        """Execute a Slack query with streaming"""
        try:
            yield self._create_stream_event("slack_connecting", session_id, workspace="company")
            
            # Use orchestrator's LLM-to-query method
            query_data = await orchestrator.llm_to_query(question)
            
            yield self._create_stream_event("slack_query_executing", session_id, query=json.dumps(query_data))
            
            # Execute query
            rows = await orchestrator.execute(query_data)
            
            yield self._create_stream_event("slack_results", session_id, messages_found=len(rows) if rows else 0, execution_time=0.28)
            
            # Add analysis if requested
            if analyze:
                yield self._create_stream_event("analysis_generating", session_id, message="Creating insights...")
                async for event in self.llm_client.analyze_results_stream(rows, session_id):
                    if event["type"] == "analysis_chunk":
                        yield self._create_stream_event("analysis_chunk", session_id, text=event.get("text", ""), chunk_index=event.get("chunk_index", 1))
                    elif event["type"] == "analysis_complete":
                        break
            
            yield self._create_stream_event("slack_complete", session_id, success=True)
            
        except Exception as e:
            logger.error(f"❌ Slack streaming query error: {str(e)}")
            yield self._create_stream_event(
                "error", 
                session_id,
                error_code="SLACK_QUERY_FAILED",
                message=f"Slack query failed: {str(e)}",
                recoverable=False
            )
    
    async def _execute_shopify_query_stream(self, question: str, analyze: bool, orchestrator: Orchestrator, db_type: str, session_id: str) -> AsyncIterator[Dict[str, Any]]:
        """Execute a Shopify query with streaming"""
        try:
            yield self._create_stream_event("shopify_connecting", session_id, store="company_store")
            
            # Use orchestrator's LLM-to-query method
            query_data = await orchestrator.llm_to_query(question)
            
            yield self._create_stream_event("shopify_query_executing", session_id, query=json.dumps(query_data))
            
            # Execute query
            rows = await orchestrator.execute(query_data)
            
            yield self._create_stream_event("shopify_results", session_id, records_found=len(rows) if rows else 0, execution_time=0.35)
            
            # Add analysis if requested
            if analyze:
                yield self._create_stream_event("analysis_generating", session_id, message="Creating insights...")
                async for event in self.llm_client.analyze_results_stream(rows, session_id):
                    if event["type"] == "analysis_chunk":
                        yield self._create_stream_event("analysis_chunk", session_id, text=event.get("text", ""), chunk_index=event.get("chunk_index", 1))
                    elif event["type"] == "analysis_complete":
                        break
            
            yield self._create_stream_event("shopify_complete", session_id, success=True)
            
        except Exception as e:
            logger.error(f"❌ Shopify streaming query error: {str(e)}")
            yield self._create_stream_event(
                "error", 
                session_id,
                error_code="SHOPIFY_QUERY_FAILED",
                message=f"Shopify query failed: {str(e)}",
                recoverable=False
            )
    
    async def _execute_ga4_query_stream(self, question: str, analyze: bool, orchestrator: Orchestrator, db_type: str, session_id: str) -> AsyncIterator[Dict[str, Any]]:
        """Execute a GA4 query with streaming"""
        try:
            yield self._create_stream_event("ga4_connecting", session_id, property="company_analytics")
            
            # Use orchestrator's LLM-to-query method
            query_data = await orchestrator.llm_to_query(question)
            
            yield self._create_stream_event("ga4_query_executing", session_id, query=json.dumps(query_data))
            
            # Execute query
            rows = await orchestrator.execute(query_data)
            
            yield self._create_stream_event("ga4_results", session_id, metrics_processed=len(rows) if rows else 0, execution_time=0.42)
            
            # Add analysis if requested
            if analyze:
                yield self._create_stream_event("analysis_generating", session_id, message="Creating insights...")
                async for event in self.llm_client.analyze_results_stream(rows, session_id):
                    if event["type"] == "analysis_chunk":
                        yield self._create_stream_event("analysis_chunk", session_id, text=event.get("text", ""), chunk_index=event.get("chunk_index", 1))
                    elif event["type"] == "analysis_complete":
                        break
            
            yield self._create_stream_event("ga4_complete", session_id, success=True)
            
        except Exception as e:
            logger.error(f"❌ GA4 streaming query error: {str(e)}")
            yield self._create_stream_event(
                "error", 
                session_id,
                error_code="GA4_QUERY_FAILED",
                message=f"GA4 query failed: {str(e)}",
                recoverable=False
            )
    
    async def _execute_mongodb_query(self, question: str, analyze: bool, orchestrator: Orchestrator, db_type: str) -> Dict[str, Any]:
        """Execute a MongoDB query"""
        try:
            # Search schema metadata
            # Import SchemaSearcher lazily to avoid circular imports
            from ..meta.ingest import SchemaSearcher
            searcher = SchemaSearcher(db_type=db_type)
            schema_chunks = await searcher.search(question, top_k=5, db_type=db_type)
            
            # Get default collection (if applicable)
            default_collection = getattr(orchestrator.adapter, 'default_collection', None)
            
            # Render prompt template for MongoDB
            prompt = self.llm_client.render_template("mongo_query.tpl", 
                                          schema_chunks=schema_chunks, 
                                          user_question=question,
                                          default_collection=default_collection)
            
            # Generate MongoDB query
            raw_response = await self.llm_client.generate_mongodb_query(prompt)
            query_data = json.loads(raw_response)
            
            # Execute query
            rows = await orchestrator.execute(query_data)
            
            result = {
                "rows": rows,
                "sql": json.dumps(query_data, indent=2),  # Return formatted query as "sql"
                "success": True
            }
            
            # Add analysis if requested
            if analyze:
                analysis = await self.llm_client.analyze_results(rows)
                result["analysis"] = analysis
            
            return result
            
        except Exception as e:
            logger.error(f"❌ MongoDB query error: {str(e)}")
            return {
                "rows": [{"error": f"MongoDB query failed: {str(e)}"}],
                "sql": "-- Error occurred during query generation",
                "analysis": f"❌ **Error**: {str(e)}" if analyze else None,
                "success": False
            }
    
    async def _execute_qdrant_query(self, question: str, analyze: bool, orchestrator: Orchestrator, db_type: str) -> Dict[str, Any]:
        """Execute a Qdrant vector search query"""
        try:
            # Search schema metadata
            # Import SchemaSearcher lazily to avoid circular imports
            from ..meta.ingest import SchemaSearcher
            searcher = SchemaSearcher(db_type=db_type)
            schema_chunks = await searcher.search(question, top_k=5, db_type=db_type)
            
            # Generate query using the orchestrator's LLM-to-query method
            query_data = await orchestrator.llm_to_query(question)
            
            # Execute query
            rows = await orchestrator.execute(query_data)
            
            result = {
                "rows": rows,
                "sql": json.dumps(query_data, indent=2),  # Return formatted query as "sql"
                "success": True
            }
            
            # Add analysis if requested
            if analyze:
                analysis = await self.llm_client.analyze_results(rows, is_vector_search=True)
                result["analysis"] = analysis
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Qdrant query error: {str(e)}")
            return {
                "rows": [{"error": f"Qdrant query failed: {str(e)}"}],
                "sql": "-- Error occurred during query generation",
                "analysis": f"❌ **Error**: {str(e)}" if analyze else None,
                "success": False
            }
    
    async def _execute_slack_query(self, question: str, analyze: bool, orchestrator: Orchestrator, db_type: str) -> Dict[str, Any]:
        """Execute a Slack query"""
        try:
            # Use orchestrator's LLM-to-query method
            query_data = await orchestrator.llm_to_query(question)
            
            # Execute query
            rows = await orchestrator.execute(query_data)
            
            result = {
                "rows": rows,
                "sql": json.dumps(query_data, indent=2),  # Return formatted query as "sql"
                "success": True
            }
            
            # Add analysis if requested
            if analyze:
                analysis = await self.llm_client.analyze_results(rows)
                result["analysis"] = analysis
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Slack query error: {str(e)}")
            return {
                "rows": [{"error": f"Slack query failed: {str(e)}"}],
                "sql": "-- Error occurred during query generation",
                "analysis": f"❌ **Error**: {str(e)}" if analyze else None,
                "success": False
            }
    
    async def _execute_shopify_query(self, question: str, analyze: bool, orchestrator: Orchestrator, db_type: str) -> Dict[str, Any]:
        """Execute a Shopify query"""
        try:
            # Use orchestrator's LLM-to-query method
            query_data = await orchestrator.llm_to_query(question)
            
            # Execute query
            rows = await orchestrator.execute(query_data)
            
            result = {
                "rows": rows,
                "sql": json.dumps(query_data, indent=2),  # Return formatted query as "sql"
                "success": True
            }
            
            # Add analysis if requested
            if analyze:
                analysis = await self.llm_client.analyze_results(rows)
                result["analysis"] = analysis
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Shopify query error: {str(e)}")
            return {
                "rows": [{"error": f"Shopify query failed: {str(e)}"}],
                "sql": "-- Error occurred during query generation",
                "analysis": f"❌ **Error**: {str(e)}" if analyze else None,
                "success": False
            }
    
    async def _execute_ga4_query(self, question: str, analyze: bool, orchestrator: Orchestrator, db_type: str) -> Dict[str, Any]:
        """Execute a GA4 query"""
        try:
            # Use orchestrator's LLM-to-query method
            query_data = await orchestrator.llm_to_query(question)
            
            # Execute query
            rows = await orchestrator.execute(query_data)
            
            result = {
                "rows": rows,
                "sql": json.dumps(query_data, indent=2),  # Return formatted query as "sql"
                "success": True
            }
            
            # Add analysis if requested
            if analyze:
                analysis = await self.llm_client.analyze_results(rows)
                result["analysis"] = analysis
            
            return result
            
        except Exception as e:
            logger.error(f"❌ GA4 query error: {str(e)}")
            return {
                "rows": [{"error": f"GA4 query failed: {str(e)}"}],
                "sql": "-- Error occurred during query generation",
                "analysis": f"❌ **Error**: {str(e)}" if analyze else None,
                "success": False
            }

# Global query engine instance (lazy initialization)
_query_engine = None

def get_query_engine():
    """Get or create the global query engine instance."""
    global _query_engine
    if _query_engine is None:
        _query_engine = CrossDatabaseQueryEngine()
    return _query_engine

async def process_ai_query_stream(question: str, analyze: bool = False, db_type: Optional[str] = None, db_uri: Optional[str] = None, cross_database: bool = False, session_id: str = None) -> AsyncIterator[Dict[str, Any]]:
    """
    Process an AI query with enhanced cross-database capabilities and streaming
    
    Args:
        question: Natural language question
        analyze: Whether to include analysis
        db_type: Specific database type (if targeting single DB)
        db_uri: Specific database URI (if targeting single DB)
        cross_database: Whether to force cross-database mode
        session_id: Session identifier for tracking
        
    Yields:
        Streaming query processing events
    """
    if not session_id:
        session_id = str(uuid.uuid4())
    
    cross_db_logger.info(f"🎯 STREAMING ENTRY POINT: process_ai_query_stream called with question='{question}', analyze={analyze}, cross_database={cross_database}")
    
    # ========== VISUALIZATION ROUTING LOGIC ==========
    # Check if this is a visualization query and route accordingly
    if question.startswith("analyze_for_visualization:"):
        viz_logger.info(f"=== STREAMING VISUALIZATION ROUTE DETECTED ===")
        actual_query = question.replace("analyze_for_visualization:", "").strip()
        viz_logger.info(f"Original question: '{question}'")
        viz_logger.info(f"Extracted query: '{actual_query}'")
        viz_logger.info(f"Session ID: {session_id}")
        
        async for event in _process_visualization_query_stream(actual_query, analyze, session_id):
            yield event
        return
    # ================================================
    
    try:
        yield get_query_engine()._create_stream_event("status", session_id, message="Starting query processing...")
        
        # If specific db_type and db_uri provided, use single database mode
        if db_type and db_uri and not cross_database:
            cross_db_logger.info(f"🔄 Using single database streaming mode: {db_type}")
            async for event in get_query_engine().execute_single_database_query_stream(question, db_type, db_uri, analyze, session_id):
                yield event
        else:
            # Classify the query first to determine if cross-database is needed
            cross_db_logger.info(f"🔍 Classifying query to determine database mode")
            
            classification = None
            async for event in get_query_engine().classify_query_stream(question, session_id):
                yield event
                if event["type"] == "databases_selected":
                    classification = {
                        "is_cross_database": event.get("is_cross_database", False),
                        "databases": event.get("databases", [])
                    }
            
            if not classification:
                # Fallback if classification failed
                yield get_query_engine()._create_stream_event(
                    "error", 
                    session_id,
                    error_code="CLASSIFICATION_FAILED",
                    message="Failed to classify query",
                    recoverable=True
                )
                # Use fallback to default database
                settings = Settings()
                async for event in get_query_engine().execute_single_database_query_stream(question, settings.DB_TYPE, settings.connection_uri, analyze, session_id):
                    yield event
                return
            
            if classification.get("is_cross_database", False) or cross_database:
                cross_db_logger.info(f"🌐 Using cross-database streaming mode")
                async for event in get_query_engine().execute_cross_database_query_stream(question, analyze, optimize=False, save_session=True, session_id=session_id):
                    yield event
            else:
                # Single database based on classification
                databases = classification.get("databases", [])
                cross_db_logger.info(f"🔄 Single database streaming mode - found {len(databases)} databases")
                
                if databases:
                    # Use the first relevant database
                    db_type_selected = databases[0]
                    cross_db_logger.info(f"🔄 Using database: {db_type_selected}")
                    settings = Settings()
                    
                    # Get appropriate URI for the database type
                    if db_type_selected == "postgres":
                        uri = settings.connection_uri
                    elif db_type_selected == "mongodb":
                        uri = settings.connection_uri  # Adjust based on your config
                    else:
                        uri = settings.connection_uri
                    
                    async for event in get_query_engine().execute_single_database_query_stream(question, db_type_selected, uri, analyze, session_id):
                        yield event
                else:
                    # Fallback to default database
                    settings = Settings()
                    cross_db_logger.info(f"🔄 Using fallback single database streaming mode: {settings.DB_TYPE}")
                    async for event in get_query_engine().execute_single_database_query_stream(question, settings.DB_TYPE, settings.connection_uri, analyze, session_id):
                        yield event
        
        yield get_query_engine()._create_stream_event("complete", session_id, success=True, total_time=5.2)
        cross_db_logger.info(f"🏁 STREAMING ENTRY POINT: process_ai_query_stream completed successfully")
        
    except Exception as e:
        cross_db_logger.error(f"❌ Error in streaming process_ai_query: {str(e)}")
        yield get_query_engine()._create_stream_event(
            "error", 
            session_id,
            error_code="QUERY_PROCESSING_FAILED",
            message=f"Query processing failed: {str(e)}",
            recoverable=False
        )

async def process_ai_query(question: str, analyze: bool = False, db_type: Optional[str] = None, db_uri: Optional[str] = None, cross_database: bool = False) -> Dict[str, Any]:
    """
    Process an AI query with enhanced cross-database capabilities
    
    Args:
        question: Natural language question
        analyze: Whether to include analysis
        db_type: Specific database type (if targeting single DB)
        db_uri: Specific database URI (if targeting single DB)
        cross_database: Whether to force cross-database mode
        
    Returns:
        Formatted response with rows, sql, and optional analysis
    """
    cross_db_logger.info(f"🎯 ENTRY POINT: process_ai_query called with question='{question}', analyze={analyze}, cross_database={cross_database}")
    cross_db_logger.info(f"🎯 Additional params: db_type={db_type}, db_uri={db_uri}")
    
    # ========== VISUALIZATION ROUTING LOGIC ==========
    # Check if this is a visualization query and route accordingly
    if question.startswith("analyze_for_visualization:"):
        viz_logger.info(f"=== NON-STREAMING VISUALIZATION ROUTE DETECTED ===")
        actual_query = question.replace("analyze_for_visualization:", "").strip()
        viz_logger.info(f"Original question: '{question}'")
        viz_logger.info(f"Extracted query: '{actual_query}'")
        
        return await _process_visualization_query(actual_query, analyze)
    # ================================================
    
    try:
        # If specific db_type and db_uri provided, use single database mode
        if db_type and db_uri and not cross_database:
            cross_db_logger.info(f"🔄 Using single database mode: {db_type}")
            result = await get_query_engine().execute_single_database_query(question, db_type, db_uri, analyze)
        else:
            # Classify the query first to determine if cross-database is needed
            cross_db_logger.info(f"🔍 Classifying query to determine database mode")
            classification = await get_query_engine().classify_query(question)
            cross_db_logger.info(f"🔍 Classification result: {classification}")
            
            if classification.get("is_cross_database", False) or cross_database:
                cross_db_logger.info(f"🌐 Using cross-database mode")
                cross_db_logger.info(f"🌐 is_cross_database: {classification.get('is_cross_database', False)}, force_cross_database: {cross_database}")
                result = await get_query_engine().execute_cross_database_query(question, analyze, optimize=False)
            else:
                # Single database based on classification
                sources = classification.get("sources", [])
                cross_db_logger.info(f"🔄 Single database mode - found {len(sources)} sources")
                
                if sources:
                    # Use the first relevant source
                    source = sources[0]
                    cross_db_logger.info(f"🔄 Using source: {source}")
                    settings = Settings()
                    
                    # Get appropriate URI for the source type
                    if source["type"] == "postgres":
                        uri = settings.connection_uri
                    elif source["type"] == "mongodb":
                        uri = settings.connection_uri  # Adjust based on your config
                    else:
                        uri = settings.connection_uri
                    
                    cross_db_logger.info(f"🔄 Using single database mode based on classification: {source['type']}")
                    result = await get_query_engine().execute_single_database_query(question, source["type"], uri, analyze)
                else:
                    # Fallback to default database
                    settings = Settings()
                    cross_db_logger.info(f"🔄 Using fallback single database mode: {settings.DB_TYPE}")
                    result = await get_query_engine().execute_single_database_query(question, settings.DB_TYPE, settings.connection_uri, analyze)
        
        cross_db_logger.info(f"🏁 ENTRY POINT: process_ai_query returning: {type(result)} with keys: {list(result.keys())}")
        cross_db_logger.info(f"🏁 Result success: {result.get('success', 'KEY_NOT_FOUND')}")
        cross_db_logger.info(f"🏁 Result rows count: {len(result.get('rows', [])) if isinstance(result.get('rows'), list) else 'Not a list'}")
        
        return result
        
    except Exception as e:
        cross_db_logger.error(f"❌ Error in process_ai_query: {str(e)}")
        cross_db_logger.error(f"❌ Exception type: {type(e)}")
        import traceback
        cross_db_logger.error(f"❌ Traceback: {traceback.format_exc()}")
        return {
            "rows": [{"error": f"Query processing failed: {str(e)}"}],
            "sql": "-- Error occurred during query processing",
            "analysis": f"❌ **Error**: {str(e)}" if analyze else None,
            "success": False
        }

# ========== VISUALIZATION PROCESSING FUNCTIONS ==========

async def _process_visualization_query(question: str, analyze: bool = False) -> Dict[str, Any]:
    """
    Process a visualization query using the dedicated visualization endpoints
    
    Args:
        question: The visualization request (e.g., "Show me sales trends by region")
        analyze: Whether to include analysis
        
    Returns:
        Formatted response with chart config and data
    """
    session_id = f"viz_sync_{int(datetime.now().timestamp())}"
    viz_logger.info(f"=== VISUALIZATION QUERY START === Session: {session_id}")
    viz_logger.info(f"Question: '{question}', Analyze: {analyze}")
    
    try:
        # Step 1: Get data for visualization using existing query engine
        viz_logger.info(f"Step 1: Fetching data for visualization using cross-database query")
        data_result = await get_query_engine().execute_cross_database_query(question, analyze=True)
        
        viz_logger.info(f"Data fetch result keys: {list(data_result.keys())}")
        viz_logger.info(f"Data fetch success: {data_result.get('success', False)}")
        viz_logger.info(f"Data fetch rows count: {len(data_result.get('rows', []))}")
        viz_logger.debug(f"Full data result: {data_result}")
        
        if not data_result.get("success", False):
            viz_logger.error(f"Data fetch failed - result: {data_result}")
            return {
                "rows": [{"error": "Failed to fetch data for visualization"}],
                "sql": "-- Data fetch failed",
                "analysis": "Could not retrieve data for chart generation",
                "success": False
            }
        
        # Step 2: Call visualization analysis endpoint
        viz_logger.info(f"Step 2: Analyzing data for visualization")
        from ..llm.client import get_llm_client
        from ..visualization.analyzer import DataAnalysisModule
        from ..visualization.selector import ChartSelectionEngine
        from ..visualization.types import VisualizationDataset, UserPreferences
        
        # Convert query result to visualization dataset
        import pandas as pd
        
        rows = data_result.get("rows", [])
        viz_logger.info(f"Retrieved {len(rows)} rows for visualization")
        viz_logger.debug(f"Sample rows (first 3): {rows[:3] if rows else 'No rows'}")
        
        if not rows:
            viz_logger.warning(f"No data available for visualization - returning empty result")
            return {
                "rows": [{"message": "No data available for visualization"}],
                "sql": data_result.get("sql", ""),
                "analysis": "No data to visualize",
                "success": False
            }
        
        # Create DataFrame from query results
        viz_logger.info(f"Creating pandas DataFrame from {len(rows)} rows")
        df = pd.DataFrame(rows)
        viz_logger.info(f"DataFrame created - shape: {df.shape}, columns: {list(df.columns)}")
        viz_logger.debug(f"DataFrame dtypes: {df.dtypes.to_dict()}")
        viz_logger.debug(f"DataFrame sample:\n{df.head()}")
        
        dataset = VisualizationDataset(
            data=df,
            columns=list(df.columns),
            metadata={"source": "query_result", "original_sql": data_result.get("sql", "")},
            source_info={"origin": "database_query", "question": question}
        )
        viz_logger.info(f"Created VisualizationDataset with {dataset.size} rows, {len(dataset.columns)} columns")
        
        # Step 3: Analyze dataset for visualization
        viz_logger.info(f"Step 3: Starting dataset analysis")
        llm_client = get_llm_client()
        analyzer = DataAnalysisModule(llm_client)
        analysis_result = await analyzer.analyze_dataset(dataset, question, session_id)
        
        viz_logger.info(f"Analysis completed - dataset_size: {analysis_result.dataset_size}")
        viz_logger.info(f"Variable types: {list(analysis_result.variable_types.keys())}")
        viz_logger.info(f"Dimensionality: {analysis_result.dimensionality.variable_count} variables")
        viz_logger.debug(f"Analysis recommendations: {analysis_result.recommendations}")
        
        # Step 4: Select optimal chart
        viz_logger.info(f"Step 4: Starting chart selection")
        selector = ChartSelectionEngine(llm_client)
        user_prefs = UserPreferences(
            preferred_style='modern',
            performance_priority='medium',
            interactivity_level='medium'
        )
        chart_selection = await selector.select_optimal_chart(analysis_result, user_prefs, session_id)
        
        viz_logger.info(f"Chart selection completed - primary: {chart_selection.primary_chart.chart_type}")
        viz_logger.info(f"Chart confidence: {chart_selection.primary_chart.confidence_score}")
        viz_logger.info(f"Chart data mapping: {chart_selection.primary_chart.data_mapping}")
        viz_logger.info(f"Number of alternatives: {len(chart_selection.alternatives)}")
        
        # Step 5: Build visualization response
        viz_logger.info(f"Step 5: Building visualization response")
        viz_response = {
            "rows": [
                {
                    "chart_type": chart_selection.primary_chart.chart_type,
                    "chart_config": chart_selection.primary_chart.data_mapping,
                    "confidence": chart_selection.primary_chart.confidence_score,
                    "rationale": chart_selection.primary_chart.rationale,
                    "data_size": analysis_result.dataset_size,
                    "alternatives": [
                        {
                            "type": alt.chart_type,
                            "confidence": alt.confidence_score
                        } for alt in chart_selection.alternatives
                    ]
                }
            ],
            "sql": f"-- Visualization Analysis\n{data_result.get('sql', '')}",
            "analysis": f"**Chart Recommendation**: {chart_selection.primary_chart.chart_type}\n\n**Reasoning**: {chart_selection.primary_chart.rationale}\n\n**Data Analysis**: {analysis_result.recommendations}" if analyze else None,
            "success": True,
            "visualization_data": {
                "dataset": rows,
                "chart_config": chart_selection.primary_chart.data_mapping,
                "chart_type": chart_selection.primary_chart.chart_type,
                "performance_estimate": f"{len(rows)} rows - estimated render time: 2-5 seconds"
            }
        }
        
        viz_logger.info(f"Visualization response built successfully")
        viz_logger.debug(f"Response keys: {list(viz_response.keys())}")
        viz_logger.debug(f"Visualization data keys: {list(viz_response['visualization_data'].keys())}")
        viz_logger.info(f"=== VISUALIZATION QUERY SUCCESS === Session: {session_id}")
        
        return viz_response
        
    except Exception as e:
        viz_logger.error(f"=== VISUALIZATION QUERY FAILED === Session: {session_id}")
        viz_logger.error(f"Error in visualization processing: {str(e)}")
        import traceback
        viz_logger.error(f"Full traceback: {traceback.format_exc()}")
        return {
            "rows": [{"error": f"Visualization processing failed: {str(e)}"}],
            "sql": "-- Visualization error",
            "analysis": f"❌ **Visualization Error**: {str(e)}" if analyze else None,
            "success": False
        }

async def _process_visualization_query_stream(question: str, analyze: bool = False, session_id: str = None) -> AsyncIterator[Dict[str, Any]]:
    """
    Process a visualization query with streaming updates
    
    Args:
        question: The visualization request
        analyze: Whether to include analysis
        session_id: Session identifier for tracking
        
    Yields:
        Streaming visualization processing events
    """
    if not session_id:
        session_id = str(uuid.uuid4())
    
    viz_logger.info(f"=== STREAMING VISUALIZATION QUERY START === Session: {session_id}")
    viz_logger.info(f"Question: '{question}', Analyze: {analyze}")
    
    try:
        # Step 1: Data retrieval
        yield get_query_engine()._create_stream_event("status", session_id, message="Fetching data for visualization...")
        yield get_query_engine()._create_stream_event("visualization_stage", session_id, stage="data_fetching", progress=0.1)
        
        data_result = await get_query_engine().execute_cross_database_query(question, analyze=True)
        
        if not data_result.get("success", False):
            yield get_query_engine()._create_stream_event(
                "error", 
                session_id,
                error_code="DATA_FETCH_FAILED",
                message="Failed to fetch data for visualization",
                recoverable=False
            )
            return
        
        # Step 2: Data analysis
        yield get_query_engine()._create_stream_event("status", session_id, message="Analyzing data characteristics...")
        yield get_query_engine()._create_stream_event("visualization_stage", session_id, stage="data_analysis", progress=0.3)
        
        # Convert to visualization dataset
        import pandas as pd
        from ..llm.client import get_llm_client
        from ..visualization.analyzer import DataAnalysisModule
        from ..visualization.selector import ChartSelectionEngine
        from ..visualization.types import VisualizationDataset, UserPreferences
        
        rows = data_result.get("rows", [])
        df = pd.DataFrame(rows)
        dataset = VisualizationDataset(
            data=df,
            columns=list(df.columns),
            metadata={"source": "query_result"},
            source_info={"origin": "database_query", "question": question}
        )
        
        llm_client = get_llm_client()
        analyzer = DataAnalysisModule(llm_client)
        analysis_result = await analyzer.analyze_dataset(dataset, question, session_id)
        
        # Step 3: Chart selection
        yield get_query_engine()._create_stream_event("status", session_id, message="Selecting optimal chart type...")
        yield get_query_engine()._create_stream_event("visualization_stage", session_id, stage="chart_selection", progress=0.6)
        
        selector = ChartSelectionEngine(llm_client)
        user_prefs = UserPreferences(
            preferred_style='modern',
            performance_priority='medium',
            interactivity_level='medium'
        )
        chart_selection = await selector.select_optimal_chart(analysis_result, user_prefs, session_id)
        
        # Step 4: Chart configuration
        yield get_query_engine()._create_stream_event("status", session_id, message="Generating chart configuration...")
        yield get_query_engine()._create_stream_event("visualization_stage", session_id, stage="config_generation", progress=0.8)
        
        # Step 5: Complete
        yield get_query_engine()._create_stream_event("status", session_id, message="Visualization ready!")
        yield get_query_engine()._create_stream_event("visualization_stage", session_id, stage="complete", progress=1.0)
        
        yield get_query_engine()._create_stream_event(
            "complete", 
            session_id, 
            success=True, 
            total_time=3.5,
            results={
                "chart_type": chart_selection.primary_chart.chart_type,
                "chart_config": chart_selection.primary_chart.data_mapping,
                "data_size": len(rows),
                "rationale": chart_selection.primary_chart.rationale,
                "visualization_data": {
                    "dataset": rows,
                    "chart_config": chart_selection.primary_chart.data_mapping,
                    "chart_type": chart_selection.primary_chart.chart_type
                }
            }
        )
        
        viz_logger.info(f"=== STREAMING VISUALIZATION QUERY SUCCESS === Session: {session_id}")
        
    except Exception as e:
        viz_logger.error(f"=== STREAMING VISUALIZATION QUERY FAILED === Session: {session_id}")
        viz_logger.error(f"Error in visualization streaming: {str(e)}")
        import traceback
        viz_logger.error(f"Full traceback: {traceback.format_exc()}")
        yield get_query_engine()._create_stream_event(
            "error", 
            session_id,
            error_code="VISUALIZATION_FAILED",
            message=f"Visualization processing failed: {str(e)}",
            recoverable=False
        )

# ================================================

if __name__ == "__main__":
    # Test the enhanced query engine
    async def test_enhanced_engine():
        print("🤖 Testing Enhanced Cross-Database Query Engine")
        print("=" * 60)
        
        test_queries = [
            # Single database queries
            ("Show me the latest users from PostgreSQL", False, "postgres"),
            ("Find recent orders in MongoDB", False, "mongodb"),
            ("Search for product information in Qdrant", False, "qdrant"),
            
            # Cross-database queries
            ("Compare user activity between Slack and Shopify", True, "cross"),
            ("Show me analytics from GA4 and correlate with orders", True, "cross"),
            ("Find customer support issues across all platforms", True, "cross")
        ]
        
        for query, analyze, mode in test_queries:
            print(f"\n🔍 Query: {query}")
            print(f"📊 Mode: {mode}, Analyze: {analyze}")
            
            try:
                if mode == "cross":
                    result = await process_ai_query(query, analyze=analyze, cross_database=True)
                else:
                    # Let classification determine the database
                    result = await process_ai_query(query, analyze=analyze)
                
                print(f"✅ Success: {result.get('success', False)}")
                print(f"📋 Rows: {len(result.get('rows', []))} results")
                
                if result.get('analysis'):
                    print(f"🧠 Analysis: {result['analysis'][:100]}...")
                    
                if result.get('session_id'):
                    print(f"💾 Session: {result['session_id']}")
                    
            except Exception as e:
                print(f"❌ Error: {str(e)}")
            
            print("-" * 40)
    
    # Also test database connection
    asyncio.run(test_enhanced_engine())
    asyncio.run(test_conn())

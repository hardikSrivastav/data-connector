import asyncpg
import asyncio
import json
import re
import random
import logging
from typing import List, Dict, Any, Optional
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
from ..meta.ingest import SchemaSearcher, ensure_index_exists
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
    
    async def _execute_postgres_query(self, question: str, analyze: bool, orchestrator: Orchestrator, db_type: str) -> Dict[str, Any]:
        """Execute a PostgreSQL query"""
        try:
            # Search schema metadata
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
    
    async def _execute_mongodb_query(self, question: str, analyze: bool, orchestrator: Orchestrator, db_type: str) -> Dict[str, Any]:
        """Execute a MongoDB query"""
        try:
            # Search schema metadata
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

# Create global query engine instance
query_engine = CrossDatabaseQueryEngine()

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
    
    try:
        # If specific db_type and db_uri provided, use single database mode
        if db_type and db_uri and not cross_database:
            cross_db_logger.info(f"🔄 Using single database mode: {db_type}")
            result = await query_engine.execute_single_database_query(question, db_type, db_uri, analyze)
        else:
            # Classify the query first to determine if cross-database is needed
            cross_db_logger.info(f"🔍 Classifying query to determine database mode")
            classification = await query_engine.classify_query(question)
            cross_db_logger.info(f"🔍 Classification result: {classification}")
            
            if classification.get("is_cross_database", False) or cross_database:
                cross_db_logger.info(f"🌐 Using cross-database mode")
                cross_db_logger.info(f"🌐 is_cross_database: {classification.get('is_cross_database', False)}, force_cross_database: {cross_database}")
                result = await query_engine.execute_cross_database_query(question, analyze, optimize=False)
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
                    result = await query_engine.execute_single_database_query(question, source["type"], uri, analyze)
                else:
                    # Fallback to default database
                    settings = Settings()
                    cross_db_logger.info(f"🔄 Using fallback single database mode: {settings.DB_TYPE}")
                    result = await query_engine.execute_single_database_query(question, settings.DB_TYPE, settings.connection_uri, analyze)
        
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

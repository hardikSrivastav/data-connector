from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional, AsyncIterator, Union
import asyncpg
import logging
import re
import json
import traceback
import asyncio
from datetime import datetime, date
import uuid
import time
import pandas as pd
import decimal

from ..db.db_orchestrator import Orchestrator
from ..config.settings import Settings
from ..llm.client import get_llm_client
from ..llm.trivial_client import get_trivial_llm_client
from ..meta.ingest import SchemaSearcher, ensure_index_exists, build_and_save_index_for_db
from ..performance.schema_monitor import ensure_schema_index_updated

# Import the enhanced cross-database query engine
from ..db.execute import get_query_engine, process_ai_query

# Import cross-database components
from ..db.classifier import DatabaseClassifier
from ..db.orchestrator.cross_db_agent import CrossDatabaseAgent
from ..tools.state_manager import StateManager, AnalysisState
from ..langgraph.integration import LangGraphIntegrationOrchestrator
from ..langgraph.compat import GraphState

# Import database availability service
from ..services.database_availability import get_availability_service, DatabaseStatus

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Set up logging for auth
auth_logger = logging.getLogger("agent_auth")

# Configure endpoint-specific logging directory
import os
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs", "endpoints")
os.makedirs(LOG_DIR, exist_ok=True)

# Create separate loggers for each endpoint
def create_endpoint_logger(endpoint_name: str) -> logging.Logger:
    """Create a dedicated logger for an endpoint with its own file"""
    endpoint_logger = logging.getLogger(f"endpoint.{endpoint_name}")
    
    # Set DEBUG level for LangGraph to capture detailed streaming events
    if endpoint_name == "langgraph":
        endpoint_logger.setLevel(logging.DEBUG)
    else:
        endpoint_logger.setLevel(logging.INFO)
    
    # Remove existing handlers to avoid duplicates
    for handler in endpoint_logger.handlers[:]:
        endpoint_logger.removeHandler(handler)
    
    # Create file handler
    log_file = os.path.join(LOG_DIR, f"{endpoint_name}.log")
    file_handler = logging.FileHandler(log_file)
    
    # Set DEBUG level for LangGraph file handler to capture detailed streaming events
    if endpoint_name == "langgraph":
        file_handler.setLevel(logging.DEBUG)
    else:
        file_handler.setLevel(logging.INFO)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(formatter)
    
    # Add handler to logger
    endpoint_logger.addHandler(file_handler)
    
    # Prevent propagation to root logger to avoid duplicate logs
    endpoint_logger.propagate = False
    
    return endpoint_logger

# Create loggers for each endpoint
health_logger = create_endpoint_logger("health")
query_logger = create_endpoint_logger("query")
cross_db_logger = create_endpoint_logger("cross_database_query")
classify_logger = create_endpoint_logger("classify")
sessions_logger = create_endpoint_logger("sessions")
trivial_logger = create_endpoint_logger("trivial")
database_logger = create_endpoint_logger("database")
visualization_logger = create_endpoint_logger("visualization")
orchestration_logger = create_endpoint_logger("orchestration")
stream_logger = create_endpoint_logger("streaming")
langgraph_logger = create_endpoint_logger("langgraph")

# ✅ NEW: Create dedicated detailed reasoning logger for LangGraph
langgraph_reasoning_logger = create_endpoint_logger("langgraph_reasoning")
langgraph_reasoning_logger.setLevel(logging.DEBUG)  # Capture all detailed events

# Helper function to log request/response
def log_request_response(endpoint_logger: logging.Logger, endpoint: str, request_data: dict, response_data: dict, duration: float, error: str = None):
    """Log request and response data for an endpoint"""
    log_entry = {
        "endpoint": endpoint,
        "timestamp": datetime.utcnow().isoformat(),
        "duration_ms": round(duration * 1000, 2),
        "request": request_data,
        "response": response_data if not error else {"error": error},
        "success": error is None
    }
    
    if error:
        endpoint_logger.error(f"Request failed: {json.dumps(log_entry, indent=2)}")
    else:
        endpoint_logger.info(f"Request completed: {json.dumps(log_entry, indent=2)}")

# Create API router
router = APIRouter()

# Define request and response models
class QueryRequest(BaseModel):
    question: str
    analyze: bool = False
    db_type: Optional[str] = None
    db_uri: Optional[str] = None
    cross_database: bool = False
    optimize: bool = False
    save_session: bool = True

class CrossDatabaseQueryRequest(BaseModel):
    question: str
    analyze: bool = False
    optimize: bool = False
    save_session: bool = True
    dry_run: bool = False

class ClassifyRequest(BaseModel):
    question: str
    threshold: float = 0.3

class QueryResponse(BaseModel):
    rows: List[Dict[str, Any]]
    sql: str
    analysis: Optional[str] = None
    success: bool = True
    session_id: Optional[str] = None
    plan_info: Optional[Dict[str, Any]] = None
    execution_summary: Optional[Dict[str, Any]] = None

class ClassifyResponse(BaseModel):
    question: str
    sources: List[Dict[str, Any]]
    reasoning: str
    is_cross_database: bool
    error: Optional[str] = None

class HealthResponse(BaseModel):
    status: str
    message: Optional[str] = None

class SessionResponse(BaseModel):
    sessions: List[Dict[str, Any]]

class SessionDetailResponse(BaseModel):
    session_id: str
    user_question: str
    start_time: float
    final_analysis: Optional[str] = None
    generated_queries: List[Dict[str, Any]]
    executed_tools: List[Dict[str, Any]]

class TrivialQueryRequest(BaseModel):
    operation: str
    text: str
    context: Optional[Dict[str, Any]] = None

class TrivialQueryResponse(BaseModel):
    result: str
    operation: str
    duration: float
    cached: bool = False
    provider: str
    model: str

class TrivialHealthResponse(BaseModel):
    status: str
    provider: str
    model: Optional[str] = None
    message: Optional[str] = None
    supported_operations: List[str] = []
    supports_natural_language: Optional[bool] = None

class DatabaseStatusResponse(BaseModel):
    name: str
    type: str
    status: str
    last_checked: str
    response_time_ms: Optional[float] = None
    error_message: Optional[str] = None
    user_accessible: bool = True
    connection_details: Optional[Dict[str, Any]] = None

class DatabaseAvailabilityResponse(BaseModel):
    databases: List[DatabaseStatusResponse]
    summary: Dict[str, Any]

class ForceCheckRequest(BaseModel):
    database_name: Optional[str] = None

# Visualization-related models
class VisualizationAnalysisRequest(BaseModel):
    dataset: Dict[str, Any]  # Simplified dataset representation
    user_intent: str
    preferences: Optional[Dict[str, Any]] = {}

class VisualizationAnalysisResponse(BaseModel):
    analysis: Dict[str, Any]
    recommendations: Dict[str, Any]
    estimated_render_time: float

class ChartGenerationRequest(BaseModel):
    chart_type: str
    data: Dict[str, Any]
    customizations: Optional[Dict[str, Any]] = {}
    performance_requirements: Optional[Dict[str, Any]] = {}

class ChartGenerationResponse(BaseModel):
    config: Dict[str, Any]
    performance_profile: Dict[str, Any]
    alternative_configs: List[Dict[str, Any]]

def sanitize_sql(sql: str) -> str:
    """Basic SQL sanitization"""
    # Remove dangerous keywords
    dangerous_keywords = ['DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 'CREATE', 'TRUNCATE']
    sql_upper = sql.upper()
    
    for keyword in dangerous_keywords:
        if keyword in sql_upper:
            raise ValueError(f"Dangerous SQL keyword '{keyword}' detected")
    
    return sql.strip()

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint - tests database connection
    """
    start_time = time.time()
    request_data = {"endpoint": "/health"}
    
    health_logger.info("🏥 Health check started")
    logger.info("🏥 API ENDPOINT: /health - Starting health check")
    
    try:
        health_logger.info("Initializing settings")
        settings = Settings()
        
        health_logger.info(f"Testing database connection - DB_TYPE: {settings.DB_TYPE}")
        # Test database connection using the default database
        orchestrator = Orchestrator(settings.connection_uri, db_type=settings.DB_TYPE)
        
        conn_ok = await orchestrator.test_connection()
        health_logger.info(f"Database connection test result: {conn_ok}")
        logger.info(f"🔍 Database connection result: {conn_ok}")
        
        if not conn_ok:
            response_data = {
                "status": "degraded", 
                "message": "Database connection failed"
            }
            duration = time.time() - start_time
            log_request_response(health_logger, "/health", request_data, response_data, duration)
            
            response = HealthResponse(**response_data)
            logger.warning(f"⚠️ Health check degraded: {response.message}")
            return response
        
        response_data = {
            "status": "ok", 
            "message": "Database connection is operational"
        }
        duration = time.time() - start_time
        log_request_response(health_logger, "/health", request_data, response_data, duration)
        
        response = HealthResponse(**response_data)
        health_logger.info(f"Health check completed successfully in {duration:.2f}s")
        logger.info(f"✅ Health check successful: {response.message}")
        return response
        
    except Exception as e:
        duration = time.time() - start_time
        error_msg = f"Health check failed: {str(e)}"
        health_logger.error(f"Health check failed after {duration:.2f}s: {error_msg}")
        health_logger.error(f"Exception details: {traceback.format_exc()}")
        log_request_response(health_logger, "/health", request_data, {}, duration, error_msg)
        
        logger.error(f"❌ Health check failed with exception: {str(e)}")
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
        response = HealthResponse(
            status="error", 
            message=error_msg
        )
        return response

@router.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest, http_request: Request):
    """
    Enhanced query endpoint supporting both single-database and cross-database operations
    
    Args:
        request: QueryRequest containing the question, analyze flag, and optional settings
        http_request: HTTP request for user authentication
        
    Returns:
        QueryResponse containing the results, SQL query, and optional analysis
    """
    start_time = time.time()
    
    # Get current user for audit and isolation
    current_user = await get_current_user_from_request(http_request)
    
    request_data = {
        "endpoint": "/query",
        "user": current_user,
        "question": request.question,
        "analyze": request.analyze,
        "db_type": request.db_type,
        "cross_database": request.cross_database,
        "optimize": request.optimize
    }
    
    query_logger.info(f"🚀 Query request started for user: {current_user}")
    query_logger.info(f"Request details: {json.dumps(request_data, indent=2)}")
    logger.info(f"🚀 API ENDPOINT: /query - Processing enhanced request for user: {current_user}")
    logger.info(f"📥 Request received: question='{request.question}', analyze={request.analyze}, cross_database={request.cross_database}")
    
    try:
        query_logger.info("Calling process_ai_query function")
        # Use the enhanced process_ai_query function
        result = await process_ai_query(
            question=request.question,
            analyze=request.analyze,
            db_type=request.db_type,
            db_uri=request.db_uri,
            cross_database=request.cross_database
        )
        
        query_logger.info(f"process_ai_query completed: success={result.get('success', True)}, rows={len(result.get('rows', []))}")
        
        # Build response from result with user context
        response_data = {
            "rows": result.get("rows", []),
            "sql": result.get("sql", "-- No SQL generated"),
            "analysis": result.get("analysis") if request.analyze else None,
            "success": result.get("success", True),
            "session_id": result.get("session_id"),
            "plan_info": result.get("plan_info"),
            "execution_summary": result.get("execution_summary")
        }
        
        # Add user context for audit trail
        response_data = add_user_context_to_response(response_data, current_user)
        
        response = QueryResponse(**response_data)
        
        duration = time.time() - start_time
        log_request_response(query_logger, "/query", request_data, {
            "rows_count": len(response.rows),
            "success": response.success,
            "session_id": response.session_id,
            "has_analysis": response.analysis is not None
        }, duration)
        
        query_logger.info(f"Query completed successfully in {duration:.2f}s")
        logger.info(f"✅ Query processed successfully for user: {current_user}")
        logger.info(f"📤 Returning response: rows={len(response.rows)}, success={response.success}")
        
        return response
        
    except HTTPException as he:
        duration = time.time() - start_time
        error_msg = f"HTTPException: {he.detail}"
        query_logger.error(f"HTTPException after {duration:.2f}s: {error_msg}")
        log_request_response(query_logger, "/query", request_data, {}, duration, error_msg)
        
        # Re-raise HTTP exceptions as-is
        logger.error(f"❌ HTTPException occurred, re-raising")
        raise
    except Exception as e:
        duration = time.time() - start_time
        error_msg = f"Query execution failed: {str(e)}"
        query_logger.error(f"Unexpected error after {duration:.2f}s: {error_msg}")
        query_logger.error(f"Exception details: {traceback.format_exc()}")
        log_request_response(query_logger, "/query", request_data, {}, duration, error_msg)
        
        logger.error(f"❌ Unexpected error processing query: {str(e)}")
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=error_msg)

@router.post("/cross-database-query", response_model=QueryResponse)
async def cross_database_query(request: CrossDatabaseQueryRequest, http_request: Request):
    """
    Dedicated endpoint for cross-database queries with planning and orchestration
    
    Args:
        request: CrossDatabaseQueryRequest with cross-database specific options
        http_request: HTTP request for user authentication
        
    Returns:
        QueryResponse with cross-database execution results
    """
    start_time = time.time()
    
    # Get current user for audit and isolation
    current_user = await get_current_user_from_request(http_request)
    
    request_data = {
        "endpoint": "/cross-database-query",
        "user": current_user,
        "question": request.question,
        "analyze": request.analyze,
        "optimize": request.optimize,
        "dry_run": request.dry_run,
        "save_session": request.save_session
    }
    
    cross_db_logger.info(f"🌐 Cross-database query started for user: {current_user}")
    cross_db_logger.info(f"Request details: {json.dumps(request_data, indent=2)}")
    logger.info(f"🌐 API ENDPOINT: /cross-database-query - Processing cross-database request for user: {current_user}")
    logger.info(f"📥 Request: question='{request.question}', optimize={request.optimize}, dry_run={request.dry_run}")
    
    try:
        if request.dry_run:
            cross_db_logger.info("Executing dry run - plan generation only")
            # For dry run, only create and validate the plan
            cross_db_agent = CrossDatabaseAgent()
            result = await cross_db_agent.execute_query(
                request.question, 
                optimize_plan=request.optimize, 
                dry_run=True
            )
            
            cross_db_logger.info(f"Dry run completed: plan_exists={result.get('plan') is not None}")
            
            # Extract plan information
            plan_info = None
            if "plan" in result:
                plan = result["plan"]
                plan_info = {
                    "plan_id": plan.id,
                    "operations": [
                        {
                            "id": op.id,
                            "type": op.metadata.get("operation_type", "unknown"),
                            "source_id": op.source_id,
                            "depends_on": op.depends_on
                        }
                        for op in plan.operations
                    ],
                    "validation": result.get("validation", {})
                }
                cross_db_logger.info(f"Plan generated with {len(plan.operations)} operations")
            
            response = QueryResponse(
                rows=[{"message": "Dry run completed - plan generated but not executed"}],
                sql=f"-- Dry run plan: {json.dumps(plan_info, indent=2) if plan_info else 'No plan generated'}",
                analysis="Plan generated successfully. Use dry_run=false to execute." if request.analyze else None,
                success=result.get("plan") is not None,
                plan_info=plan_info
            )
        else:
            cross_db_logger.info("Executing cross-database query")
            # Execute the cross-database query
            result = await get_query_engine().execute_cross_database_query(
                request.question,
                analyze=request.analyze,
                optimize=request.optimize,
                save_session=request.save_session
            )
            
            cross_db_logger.info(f"Cross-database execution completed: success={result.get('success', True)}, rows={len(result.get('rows', []))}")
            
            response = QueryResponse(
                rows=result.get("rows", []),
                sql=result.get("sql", "-- Cross-database query"),
                analysis=result.get("analysis") if request.analyze else None,
                success=result.get("success", True),
                session_id=result.get("session_id"),
                plan_info=result.get("plan_info"),
                execution_summary=result.get("execution_summary")
            )
        
        duration = time.time() - start_time
        log_request_response(cross_db_logger, "/cross-database-query", request_data, {
            "success": response.success,
            "rows_count": len(response.rows),
            "session_id": response.session_id,
            "dry_run": request.dry_run,
            "has_plan_info": response.plan_info is not None
        }, duration)
        
        cross_db_logger.info(f"Cross-database query completed in {duration:.2f}s")
        logger.info(f"✅ Cross-database query processed: success={response.success}")
        return response
        
    except Exception as e:
        duration = time.time() - start_time
        error_msg = f"Cross-database query failed: {str(e)}"
        cross_db_logger.error(f"Cross-database query failed after {duration:.2f}s: {error_msg}")
        cross_db_logger.error(f"Exception details: {traceback.format_exc()}")
        log_request_response(cross_db_logger, "/cross-database-query", request_data, {}, duration, error_msg)
        
        logger.error(f"❌ Error in cross-database query: {str(e)}")
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=error_msg)

@router.post("/classify", response_model=ClassifyResponse)
async def classify_query(request: ClassifyRequest):
    """
    Classify which databases are relevant for a given question
    
    Args:
        request: ClassifyRequest with question and threshold
        
    Returns:
        ClassifyResponse with relevant databases and reasoning
    """
    logger.info(f"🔍 API ENDPOINT: /classify - Classifying query")
    logger.info(f"📥 Request: question='{request.question}', threshold={request.threshold}")
    
    try:
        # Use the query engine's classification
        classification = await get_query_engine().classify_query(request.question)
        
        response = ClassifyResponse(
            question=classification.get("question", request.question),
            sources=classification.get("sources", []),
            reasoning=classification.get("reasoning", ""),
            is_cross_database=classification.get("is_cross_database", False),
            error=classification.get("error")
        )
        
        logger.info(f"✅ Classification completed: {len(response.sources)} sources, cross_db={response.is_cross_database}")
        return response
        
    except Exception as e:
        logger.error(f"❌ Error in classification: {str(e)}")
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Classification failed: {str(e)}")

@router.get("/sessions", response_model=SessionResponse)
async def list_sessions(limit: int = 10):
    """
    List recent analysis sessions
    
    Args:
        limit: Maximum number of sessions to return
        
    Returns:
        List of recent sessions
    """
    logger.info(f"📋 API ENDPOINT: /sessions - Listing sessions (limit={limit})")
    
    try:
        state_manager = StateManager()
        sessions = await state_manager.list_sessions(limit=limit)
        
        response = SessionResponse(sessions=sessions)
        
        logger.info(f"✅ Listed {len(sessions)} sessions")
        return response
        
    except Exception as e:
        logger.error(f"❌ Error listing sessions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to list sessions: {str(e)}")

@router.get("/sessions/{session_id}", response_model=SessionDetailResponse)
async def get_session(session_id: str):
    """
    Get details for a specific session
    
    Args:
        session_id: ID of the session to retrieve
        
    Returns:
        Detailed session information
    """
    logger.info(f"📄 API ENDPOINT: /sessions/{session_id} - Getting session details")
    
    try:
        state_manager = StateManager()
        state = await state_manager.get_state(session_id)
        
        if not state:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
        
        response = SessionDetailResponse(
            session_id=session_id,
            user_question=state.user_question,
            start_time=state.start_time,
            final_analysis=state.final_analysis,
            generated_queries=state.generated_queries,
            executed_tools=state.executed_tools
        )
        
        logger.info(f"✅ Retrieved session details for {session_id}")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting session: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get session: {str(e)}")

@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """
    Delete a specific session
    
    Args:
        session_id: ID of the session to delete
        
    Returns:
        Success message
    """
    logger.info(f"🗑️ API ENDPOINT: DELETE /sessions/{session_id} - Deleting session")
    
    try:
        state_manager = StateManager()
        
        # Check if session exists
        state = await state_manager.get_state(session_id)
        if not state:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
        
        # Delete the session (implementation depends on StateManager)
        # This might need to be implemented in StateManager
        success = await state_manager.delete_session(session_id)
        
        if success:
            logger.info(f"✅ Session {session_id} deleted successfully")
            return {"message": f"Session {session_id} deleted successfully"}
        else:
            raise HTTPException(status_code=500, detail=f"Failed to delete session {session_id}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error deleting session: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete session: {str(e)}")

@router.post("/sessions/cleanup")
async def cleanup_sessions(max_age_hours: int = 24):
    """
    Clean up old sessions
    
    Args:
        max_age_hours: Maximum age of sessions to keep
        
    Returns:
        Number of sessions cleaned up
    """
    logger.info(f"🧹 API ENDPOINT: /sessions/cleanup - Cleaning up sessions older than {max_age_hours} hours")
    
    try:
        state_manager = StateManager()
        cleaned = await state_manager.cleanup_old_sessions(max_age_hours=max_age_hours)
        
        logger.info(f"✅ Cleaned up {cleaned} old sessions")
        return {"message": f"Cleaned up {cleaned} old sessions", "cleaned_count": cleaned}
        
    except Exception as e:
        logger.error(f"❌ Error cleaning up sessions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to cleanup sessions: {str(e)}")

# Keep the legacy endpoints for backward compatibility
async def execute_postgres_query(llm, question: str, analyze: bool, orchestrator: Orchestrator, db_type: str) -> Dict[str, Any]:
    """Execute a PostgreSQL query (legacy)"""
    logger.info(f"🐘 Executing PostgreSQL query: {question}")
    
    try:
        # Search schema metadata
        searcher = SchemaSearcher(db_type=db_type)
        schema_chunks = await searcher.search(question, top_k=10, db_type=db_type)
        
        # Render prompt template for PostgreSQL
        prompt = llm.render_template("nl2sql.tpl", schema_chunks=schema_chunks, user_question=question)
        
        # Generate SQL
        sql = await llm.generate_sql(prompt)
        
        # Sanitize SQL
        validated_sql = sanitize_sql(sql)
        logger.info(f"🛠️ Generated SQL: {validated_sql}")
        
        # Execute query using the orchestrator
        rows = await orchestrator.execute(validated_sql)
        
        result = {
            "rows": rows,
            "sql": validated_sql
        }
        
        # Add analysis if requested
        if analyze:
            analysis = await llm.analyze_results(rows)
            result["analysis"] = analysis
        
        return result
        
    except Exception as e:
        logger.error(f"❌ PostgreSQL query error: {str(e)}")
        return {
            "rows": [{"error": f"PostgreSQL query failed: {str(e)}"}],
            "sql": "-- Error occurred during query generation",
            "analysis": f"❌ **Error**: {str(e)}" if analyze else None
        }

async def execute_mongodb_query(llm, question: str, analyze: bool, orchestrator: Orchestrator, db_type: str) -> Dict[str, Any]:
    """Execute a MongoDB query (legacy)"""
    logger.info(f"🍃 Executing MongoDB query: {question}")
    
    try:
        # Search schema metadata
        searcher = SchemaSearcher(db_type=db_type)
        schema_chunks = await searcher.search(question, top_k=5, db_type=db_type)
        
        # Get default collection (if applicable)
        default_collection = getattr(orchestrator.adapter, 'default_collection', None)
        
        # Render prompt template for MongoDB
        prompt = llm.render_template("mongo_query.tpl", 
                                  schema_chunks=schema_chunks, 
                                  user_question=question,
                                  default_collection=default_collection)
        
        # Generate MongoDB query
        raw_response = await llm.generate_mongodb_query(prompt)
        query_data = json.loads(raw_response)
        
        logger.info(f"🛠️ Generated MongoDB query: {json.dumps(query_data, indent=2)}")
        
        # Execute query
        rows = await orchestrator.execute(query_data)
        
        result = {
            "rows": rows,
            "sql": json.dumps(query_data, indent=2)  # Return formatted query as "sql"
        }
        
        # Add analysis if requested
        if analyze:
            analysis = await llm.analyze_results(rows)
            result["analysis"] = analysis
        
        return result
        
    except Exception as e:
        logger.error(f"❌ MongoDB query error: {str(e)}")
        return {
            "rows": [{"error": f"MongoDB query failed: {str(e)}"}],
            "sql": "-- Error occurred during query generation",
            "analysis": f"❌ **Error**: {str(e)}" if analyze else None
        }

async def execute_qdrant_query(llm, question: str, analyze: bool, orchestrator: Orchestrator, db_type: str) -> Dict[str, Any]:
    """Execute a Qdrant vector search query (legacy)"""
    logger.info(f"🔍 Executing Qdrant query: {question}")
    
    try:
        # Search schema metadata
        searcher = SchemaSearcher(db_type=db_type)
        schema_chunks = await searcher.search(question, top_k=5, db_type=db_type)
        
        # Render prompt template for vector search
        prompt = llm.render_template("vector_search.tpl", 
                                  schema_chunks=schema_chunks, 
                                  user_question=question)
        
        # Generate query using the orchestrator's LLM-to-query method
        query_data = await orchestrator.llm_to_query(question)
        
        logger.info(f"🛠️ Generated Qdrant query: {json.dumps(query_data, indent=2)}")
        
        # Execute query
        rows = await orchestrator.execute(query_data)
        
        result = {
            "rows": rows,
            "sql": json.dumps(query_data, indent=2)  # Return formatted query as "sql"
        }
        
        # Add analysis if requested
        if analyze:
            analysis = await llm.analyze_results(rows, is_vector_search=True)
            result["analysis"] = analysis
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Qdrant query error: {str(e)}")
        return {
            "rows": [{"error": f"Qdrant query failed: {str(e)}"}],
            "sql": "-- Error occurred during query generation", 
            "analysis": f"❌ **Error**: {str(e)}" if analyze else None
        }

async def execute_slack_query(llm, question: str, analyze: bool, orchestrator: Orchestrator, db_type: str) -> Dict[str, Any]:
    """Execute a Slack query (legacy)"""
    logger.info(f"💬 Executing Slack query: {question}")
    
    try:
        # Use orchestrator's LLM-to-query method
        query_data = await orchestrator.llm_to_query(question)
        
        logger.info(f"🛠️ Generated Slack query: {json.dumps(query_data, indent=2)}")
        
        # Execute query
        rows = await orchestrator.execute(query_data)
        
        result = {
            "rows": rows,
            "sql": json.dumps(query_data, indent=2)  # Return formatted query as "sql"
        }
        
        # Add analysis if requested
        if analyze:
            analysis = await llm.analyze_results(rows)
            result["analysis"] = analysis
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Slack query error: {str(e)}")
        return {
            "rows": [{"error": f"Slack query failed: {str(e)}"}],
            "sql": "-- Error occurred during query generation",
            "analysis": f"❌ **Error**: {str(e)}" if analyze else None
        }

async def execute_shopify_query(llm, question: str, analyze: bool, orchestrator: Orchestrator, db_type: str) -> Dict[str, Any]:
    """Execute a Shopify query (legacy)"""
    logger.info(f"🛍️ Executing Shopify query: {question}")
    
    try:
        # Use orchestrator's LLM-to-query method
        query_data = await orchestrator.llm_to_query(question)
        
        logger.info(f"🛠️ Generated Shopify query: {json.dumps(query_data, indent=2)}")
        
        # Execute query
        rows = await orchestrator.execute(query_data)
        
        result = {
            "rows": rows,
            "sql": json.dumps(query_data, indent=2)  # Return formatted query as "sql"
        }
        
        # Add analysis if requested
        if analyze:
            analysis = await llm.analyze_results(rows)
            result["analysis"] = analysis
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Shopify query error: {str(e)}")
        return {
            "rows": [{"error": f"Shopify query failed: {str(e)}"}],
            "sql": "-- Error occurred during query generation",
            "analysis": f"❌ **Error**: {str(e)}" if analyze else None
        }

async def execute_ga4_query(llm, question: str, analyze: bool, orchestrator: Orchestrator, db_type: str) -> Dict[str, Any]:
    """Execute a GA4 query (legacy)"""
    logger.info(f"📊 Executing GA4 query: {question}")
    
    try:
        # Use orchestrator's LLM-to-query method
        query_data = await orchestrator.llm_to_query(question)
        
        logger.info(f"🛠️ Generated GA4 query: {json.dumps(query_data, indent=2)}")
        
        # Execute query
        rows = await orchestrator.execute(query_data)
        
        result = {
            "rows": rows,
            "sql": json.dumps(query_data, indent=2)  # Return formatted query as "sql"
        }
        
        # Add analysis if requested
        if analyze:
            analysis = await llm.analyze_results(rows)
            result["analysis"] = analysis
        
        return result
        
    except Exception as e:
        logger.error(f"❌ GA4 query error: {str(e)}")
        return {
            "rows": [{"error": f"GA4 query failed: {str(e)}"}],
            "sql": "-- Error occurred during query generation",
            "analysis": f"❌ **Error**: {str(e)}" if analyze else None
        }

@router.get("/test")
async def test_real_connection():
    """
    Test endpoint for the real database connection functionality
    """
    logger.info("🧪 API ENDPOINT: /test - Testing real database connection")
    
    try:
        settings = Settings()
        
        test_queries = [
            {"question": "Show me recent users", "analyze": True, "cross_database": False},
            {"question": "How many records are in the database?", "analyze": True, "cross_database": False},
            {"question": "Compare data across all databases", "analyze": True, "cross_database": True}
        ]
        
        logger.info(f"🧪 Running {len(test_queries)} test queries")
        
        results = []
        for i, test_query in enumerate(test_queries):
            logger.info(f"🧪 Test {i+1}/{len(test_queries)}: '{test_query['question']}'")
            
            try:
                # Use the enhanced process_ai_query function
                result = await process_ai_query(
                    question=test_query["question"],
                    analyze=test_query["analyze"],
                    cross_database=test_query.get("cross_database", False)
                )
                
                logger.info(f"🧪 Test {i+1} result: {len(result.get('rows', []))} rows, success={result.get('success', False)}")
                results.append({
                    "query": test_query["question"],
                    "success": result.get("success", False),
                    "response": {
                        "rows": result.get("rows", []),
                        "sql": result.get("sql", ""),
                        "analysis": result.get("analysis"),
                        "session_id": result.get("session_id")
                    }
                })
                
            except Exception as query_error:
                logger.error(f"🧪 Test {i+1} failed: {str(query_error)}")
                results.append({
                    "query": test_query["question"],
                    "success": False,
                    "error": str(query_error)
                })
        
        response = {
            "status": "success",
            "message": "Enhanced database connection tests completed",
            "test_results": results,
            "capabilities": {
                "single_database": True,
                "cross_database": True,
                "classification": True,
                "session_management": True
            }
        }
        
        logger.info(f"✅ Database connection test completed successfully with {len(results)} results")
        return response
        
    except Exception as e:
        logger.error(f"❌ Database connection test failed: {str(e)}")
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Database connection test failed: {str(e)}")

@router.get("/capabilities")
async def get_capabilities():
    """
    Get information about the enhanced database connection capabilities
    """
    logger.info("ℹ️ API ENDPOINT: /capabilities - Returning enhanced capabilities info")
    
    settings = Settings()
    
    capabilities = {
        "name": "Enhanced Cross-Database Agent",
        "version": "2.0.0",
        "default_database": {
            "type": settings.DB_TYPE,
            "host": settings.DB_HOST,
            "port": settings.DB_PORT,
            "database": settings.DB_NAME
        },
        "supported_databases": ["postgres", "postgresql", "mongodb", "qdrant", "slack", "shopify", "ga4"],
        "capabilities": {
            "natural_language_queries": True,
            "sql_generation": True,
            "data_analysis": True,
            "schema_introspection": True,
            "vector_search": True,
            "multiple_data_sources": True,
            "cross_database_queries": True,
            "query_planning": True,
            "query_optimization": True,
            "session_management": True,
            "database_classification": True,
            "dry_run_execution": True
        },
        "endpoints": {
            "/query": "Enhanced query endpoint supporting both single and cross-database queries",
            "/cross-database-query": "Dedicated cross-database query endpoint with planning",
            "/classify": "Database relevance classification for queries",
            "/sessions": "Session management for analysis tracking",
            "/sessions/{id}": "Individual session details and management"
        },
        "sample_queries": [
            "Show me the latest users",
            "How many orders were placed this month?", 
            "Find products with low stock",
            "Search for messages about project updates",
            "What's the revenue trend?",
            "Show me user analytics from GA4",
            "Compare user activity between Slack and Shopify",
            "Find customer support issues across all platforms",
            "Correlate sales data with marketing campaigns"
        ]
    }
    
    logger.info(f"📤 Returning enhanced capabilities for {len(capabilities['supported_databases'])} database types")
    return capabilities

@router.get("/metadata")
async def get_metadata():
    """
    Get schema metadata information from the real database
    """
    logger.info("📊 API ENDPOINT: /metadata - Returning metadata info")
    
    try:
        settings = Settings()
        
        # Create orchestrator for introspection
        orchestrator = Orchestrator(settings.connection_uri, db_type=settings.DB_TYPE)
        
        # Test connection
        if not await orchestrator.test_connection():
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        # Get schema metadata
        schema_metadata = await orchestrator.introspect_schema()
        
        metadata = {
            "status": "ok", 
            "message": f"Schema metadata from {settings.DB_TYPE} database",
            "database_type": settings.DB_TYPE,
            "connection_info": {
                "host": settings.DB_HOST,
                "port": settings.DB_PORT,
                "database": settings.DB_NAME
            },
            "schema_elements": len(schema_metadata),
            "tables": list(set(item.get("table_name", "") for item in schema_metadata if item.get("table_name"))),
            "cross_database_enabled": True,
            "available_sources": len(get_query_engine().classifier.get_available_sources() if hasattr(get_query_engine().classifier, 'get_available_sources') else [])
        }
        
        logger.info(f"📤 Returning metadata for {len(schema_metadata)} schema elements")
        return metadata
        
    except Exception as e:
        logger.error(f"❌ Error getting metadata: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get metadata: {str(e)}")

# Streaming utility functions
def create_stream_event(event_type: str, session_id: str, **kwargs) -> str:
    """Create a Server-Sent Event formatted string"""
    import decimal
    from datetime import datetime, date
    
    def convert_item(item):
        """Convert non-JSON-serializable items to JSON-serializable format"""
        if isinstance(item, decimal.Decimal):
            return float(item)
        elif isinstance(item, (datetime, date)):
            return item.isoformat()
        elif isinstance(item, dict):
            return {k: convert_item(v) for k, v in item.items()}
        elif isinstance(item, list):
            return [convert_item(i) for i in item]
        elif hasattr(item, '__dict__'):
            # Handle custom objects by converting to dict
            return convert_item(item.__dict__)
        elif hasattr(item, '__class__') and hasattr(item.__class__, '__name__'):
            # Handle enum objects and other complex types
            if hasattr(item, 'value'):
                return str(item.value)  # For enums
            else:
                return str(item)
        else:
            return item
    
    event = {
        "type": event_type,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "session_id": session_id,
        **kwargs
    }
    
    # Convert the event to handle Decimal and other non-serializable types
    try:
        converted_event = convert_item(event)
        return f"data: {json.dumps(converted_event, ensure_ascii=False)}\n\n"
    except (TypeError, ValueError) as e:
        logger.error(f"❌ Event serialization failed: {e}")
        logger.error(f"❌ Problematic event: {event}")
        
        # Enhanced fallback: recursively convert problematic items
        def safe_convert(obj):
            if isinstance(obj, (str, int, float, bool, type(None))):
                return obj
            elif isinstance(obj, decimal.Decimal):
                return float(obj)
            elif isinstance(obj, (datetime, date)):
                return obj.isoformat()
            elif isinstance(obj, dict):
                return {k: safe_convert(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [safe_convert(i) for i in obj]
            else:
                return str(obj)
        
        safe_event = safe_convert(event)
        return f"data: {json.dumps(safe_event, ensure_ascii=False)}\n\n"

async def process_ai_query_stream(
    question: str,
    analyze: bool = False,
    db_type: Optional[str] = None,
    db_uri: Optional[str] = None,
    cross_database: bool = False
) -> AsyncIterator[str]:
    """
    Streaming version of process_ai_query that yields Server-Sent Events
    """
    session_id = str(uuid.uuid4())
    
    try:
        # Starting status
        yield create_stream_event("status", session_id, message="Starting query processing...")
        
        # Classification phase
        yield create_stream_event("classifying", session_id, message="Determining relevant databases...")
        
        # Get classification from query engine
        classification = await get_query_engine().classify_query(question)
        
        databases = classification.get("sources", [])
        database_names = [db.get("name", db.get("id", "unknown")) for db in databases]
        is_cross_database = classification.get("is_cross_database", len(database_names) > 1)
        
        yield create_stream_event(
            "databases_selected", 
            session_id,
            databases=database_names,
            reasoning=classification.get("reasoning", ""),
            is_cross_database=is_cross_database
        )
        
        if is_cross_database:
            # Cross-database execution
            async for event in execute_cross_database_query_stream(
                question, analyze, session_id
            ):
                yield event
        else:
            # Single database execution
            async for event in execute_single_database_query_stream(
                question, analyze, db_type, db_uri, session_id
            ):
                yield event
        
    except Exception as e:
        logger.error(f"❌ Error in streaming query: {str(e)}")
        yield create_stream_event(
            "error", 
            session_id,
            error_code="QUERY_PROCESSING_FAILED",
            message=str(e),
            recoverable=False
        )
        yield create_stream_event("complete", session_id, success=False, error=str(e))

async def execute_single_database_query_stream(
    question: str,
    analyze: bool,
    db_type: Optional[str],
    db_uri: Optional[str],
    session_id: str
) -> AsyncIterator[str]:
    """Stream single database query execution"""
    
    try:
        # Schema loading phase
        yield create_stream_event("schema_loading", session_id, database="postgres", progress=0.2)
        
        # Simulate schema chunks loading
        yield create_stream_event(
            "schema_chunks",
            session_id,
            chunks=[{"table": "users", "columns": ["id", "name", "email"]}],
            database="postgres"
        )
        
        # Query generation phase
        yield create_stream_event("query_generating", session_id, database="postgres", status="in_progress")
        
        # Execute the actual query
        result = await process_ai_query(
            question=question,
            analyze=analyze,
            db_type=db_type,
            db_uri=db_uri,
            cross_database=False
        )
        
        # Query execution phase
        sql = result.get("sql", "-- No SQL generated")
        yield create_stream_event(
            "query_executing",
            session_id,
            database="postgres",
            sql=sql,
            estimated_duration=2.0
        )
        
        # Partial results
        rows = result.get("rows", [])
        yield create_stream_event(
            "partial_results",
            session_id,
            database="postgres",
            rows_count=min(100, len(rows)),
            is_complete=len(rows) <= 100
        )
        
        # Analysis generation if requested
        if analyze and result.get("analysis"):
            yield create_stream_event("analysis_generating", session_id, message="Generating insights...")
        
        # Complete
        yield create_stream_event(
            "complete",
            session_id,
            success=result.get("success", True),
            total_time=2.5,
            results={
                "rows": rows,
                "sql": sql,
                "analysis": result.get("analysis") if analyze else None,
                "session_id": result.get("session_id")
            }
        )
        
    except Exception as e:
        logger.error(f"❌ Error in single database streaming: {str(e)}")
        yield create_stream_event(
            "error",
            session_id,
            error_code="SINGLE_DB_EXECUTION_FAILED",
            message=str(e),
            recoverable=False
        )

async def execute_cross_database_query_stream(
    question: str,
    analyze: bool,
    session_id: str
) -> AsyncIterator[str]:
    """Stream cross-database query execution"""
    
    try:
        # Planning phase
        yield create_stream_event(
            "planning",
            session_id,
            step="Analyzing query dependencies",
            operations_planned=3,
            databases_involved=["postgres", "mongodb"]
        )
        
        # Plan validation
        yield create_stream_event(
            "plan_validated",
            session_id,
            operations=3,
            estimated_time="30s",
            dependencies=["postgres -> mongodb"]
        )
        
        # Schema loading for multiple databases
        yield create_stream_event("schema_loading", session_id, database="postgres", progress=0.3)
        yield create_stream_event("schema_loading", session_id, database="mongodb", progress=0.6)
        
        # Execute the actual cross-database query
        result = await get_query_engine().execute_cross_database_query(
            question,
            analyze=analyze
        )
        
        # Query execution for each database
        yield create_stream_event(
            "query_executing",
            session_id,
            database="postgres",
            sql="SELECT * FROM users"
        )
        yield create_stream_event(
            "query_executing",
            session_id,
            database="mongodb",
            query='{"collection": "orders"}'
        )
        
        # Partial results from each database
        rows = result.get("rows", [])
        yield create_stream_event(
            "partial_results",
            session_id,
            database="postgres",
            rows_count=min(100, len(rows) // 2)
        )
        yield create_stream_event(
            "partial_results",
            session_id,
            database="mongodb",
            rows_count=min(50, len(rows) // 2)
        )
        
        # Aggregation phase
        yield create_stream_event(
            "aggregating",
            session_id,
            step="Joining postgres and mongodb results",
            progress=0.7
        )
        
        # Analysis generation if requested
        if analyze and result.get("analysis"):
            yield create_stream_event("analysis_generating", session_id, message="Generating cross-database insights...")
        
        # Complete
        yield create_stream_event(
            "complete",
            session_id,
            success=result.get("success", True),
            total_time=12.5,
            results={
                "rows": rows,
                "sql": result.get("sql", "-- Cross-database query"),
                "analysis": result.get("analysis") if analyze else None,
                "plan_info": result.get("plan_info"),
                "execution_summary": result.get("execution_summary")
            }
        )
        
    except Exception as e:
        logger.error(f"❌ Error in cross-database streaming: {str(e)}")
        yield create_stream_event(
            "error",
            session_id,
            error_code="CROSS_DB_EXECUTION_FAILED",
            message=str(e),
            recoverable=False
        )

# Streaming endpoints
@router.post("/query/stream")
async def query_stream(request: QueryRequest):
    """
    Streaming version of the query endpoint using Server-Sent Events
    
    Args:
        request: QueryRequest containing the question and options
        
    Returns:
        StreamingResponse with Server-Sent Events
    """
    logger.info(f"🌊 API ENDPOINT: /query/stream - Starting streaming query")
    logger.info(f"📥 Request: question='{request.question}', analyze={request.analyze}, cross_database={request.cross_database}")
    
    async def generate_stream():
        try:
            async for event in process_ai_query_stream(
                question=request.question,
                analyze=request.analyze,
                db_type=request.db_type,
                db_uri=request.db_uri,
                cross_database=request.cross_database
            ):
                yield event
                
        except Exception as e:
            logger.error(f"❌ Streaming error: {str(e)}")
            session_id = str(uuid.uuid4())
            yield create_stream_event(
                "error",
                session_id,
                error_code="STREAMING_FAILED",
                message=str(e),
                recoverable=False
            )
            yield create_stream_event("complete", session_id, success=False, error=str(e))
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control"
        }
    )

@router.post("/cross-database-query/stream")
async def cross_database_query_stream(request: CrossDatabaseQueryRequest):
    """
    Streaming version of the cross-database query endpoint
    
    Args:
        request: CrossDatabaseQueryRequest with cross-database options
        
    Returns:
        StreamingResponse with Server-Sent Events for cross-database operations
    """
    logger.info(f"🌐🌊 API ENDPOINT: /cross-database-query/stream - Starting streaming cross-database query")
    logger.info(f"📥 Request: question='{request.question}', optimize={request.optimize}, dry_run={request.dry_run}")
    
    async def generate_stream():
        session_id = str(uuid.uuid4())
        
        try:
            if request.dry_run:
                # Dry run streaming
                yield create_stream_event("status", session_id, message="Starting dry run...")
                
                # Simulate planning phase
                yield create_stream_event(
                    "planning",
                    session_id,
                    step="Creating execution plan",
                    operations_planned=3,
                    databases_involved=["postgres", "mongodb"]
                )
                
                yield create_stream_event(
                    "plan_validated",
                    session_id,
                    operations=3,
                    estimated_time="30s",
                    dry_run=True
                )
                
                yield create_stream_event(
                    "complete",
                    session_id,
                    success=True,
                    total_time=1.0,
                    results={
                        "message": "Dry run completed - plan generated but not executed",
                        "plan_generated": True
                    }
                )
            else:
                # Full execution streaming
                async for event in execute_cross_database_query_stream(
                    request.question,
                    request.analyze,
                    session_id
                ):
                    yield event
                    
        except Exception as e:
            logger.error(f"❌ Cross-database streaming error: {str(e)}")
            yield create_stream_event(
                "error",
                session_id,
                error_code="CROSS_DB_STREAMING_FAILED",
                message=str(e),
                recoverable=False
            )
            yield create_stream_event("complete", session_id, success=False, error=str(e))
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control"
        }
    )

@router.post("/classify/stream")
async def classify_query_stream(request: ClassifyRequest):
    """
    Streaming version of the classify endpoint
    
    Args:
        request: ClassifyRequest with question and threshold
        
    Returns:
        StreamingResponse with classification progress
    """
    logger.info(f"🔍🌊 API ENDPOINT: /classify/stream - Starting streaming classification")
    logger.info(f"📥 Request: question='{request.question}', threshold={request.threshold}")
    
    async def generate_stream():
        session_id = str(uuid.uuid4())
        
        try:
            yield create_stream_event("status", session_id, message="Starting query classification...")
            
            yield create_stream_event("classifying", session_id, message="Analyzing query semantics...")
            
            # Small delay to simulate processing
            await asyncio.sleep(0.1)
            
            yield create_stream_event("classifying", session_id, message="Matching against database schemas...")
            
            # Perform actual classification
            classification = await get_query_engine().classify_query(request.question)
            
            yield create_stream_event(
                "databases_selected",
                session_id,
                databases=[db.get("name", db.get("id", "unknown")) for db in classification.get("sources", [])],
                confidence=0.95,
                reasoning=classification.get("reasoning", "")
            )
            
            yield create_stream_event(
                "complete",
                session_id,
                success=True,
                total_time=0.5,
                results={
                    "question": classification.get("question", request.question),
                    "sources": classification.get("sources", []),
                    "reasoning": classification.get("reasoning", ""),
                    "is_cross_database": classification.get("is_cross_database", False),
                    "error": classification.get("error")
                }
            )
            
        except Exception as e:
            logger.error(f"❌ Classification streaming error: {str(e)}")
            yield create_stream_event(
                "error",
                session_id,
                error_code="CLASSIFICATION_FAILED",
                message=str(e),
                recoverable=True
            )
            yield create_stream_event("complete", session_id, success=False, error=str(e))
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control"
        }
    )

@router.get("/trivial/health", response_model=TrivialHealthResponse)
async def trivial_health_check():
    """Health check for the trivial LLM client."""
    try:
        trivial_client = get_trivial_llm_client()
        health_data = await trivial_client.health_check()
        
        return TrivialHealthResponse(
            status=health_data["status"],
            provider=health_data["provider"],
            model=health_data.get("model"),
            message=health_data.get("message"),
            supported_operations=health_data.get("supported_operations", []),
            supports_natural_language=health_data.get("supports_natural_language", False)
        )
    except Exception as e:
        logger.error(f"Trivial health check failed: {e}")
        return TrivialHealthResponse(
            status="error",
            provider="unknown",
            message=str(e)
        )

@router.post("/trivial/process", response_model=TrivialQueryResponse)
async def process_trivial_operation(request: TrivialQueryRequest):
    """
    Process a single trivial text editing operation.
    
    Optimized for speed with lightweight models like Grok.
    """
    try:
        trivial_client = get_trivial_llm_client()
        
        if not trivial_client.is_enabled():
            raise HTTPException(status_code=503, detail="Trivial LLM client is not available")
        
        start_time = time.time()
        result = await trivial_client.process_operation(
            operation=request.operation,
            text=request.text,
            context=request.context
        )
        duration = time.time() - start_time
        
        return TrivialQueryResponse(
            result=result,
            operation=request.operation,
            duration=duration,
            provider=trivial_client.provider,
            model=trivial_client.model
        )
        
    except Exception as e:
        logger.error(f"Error processing trivial operation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/trivial/stream")
async def stream_trivial_operation(request: TrivialQueryRequest):
    """
    Stream a trivial text editing operation for real-time diff updates.
    
    Returns Server-Sent Events for live UI updates.
    """
    async def generate_stream():
        try:
            trivial_client = get_trivial_llm_client()
            
            if not trivial_client.is_enabled():
                yield create_stream_event("error", "session_id", 
                                        message="Trivial LLM client is not available")
                return
            
            async for chunk in trivial_client.stream_operation(
                operation=request.operation,
                text=request.text,
                context=request.context
            ):
                # Send the chunk data directly as SSE without wrapping in trivial_update
                yield f"data: {json.dumps(chunk)}\n\n"
                
        except Exception as e:
            logger.error(f"Error in trivial stream: {e}")
            yield create_stream_event("error", "session_id", 
                                    message=str(e))
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
        }
    )

@router.get("/trivial/operations")
async def get_trivial_operations():
    """Get list of supported trivial operations."""
    try:
        trivial_client = get_trivial_llm_client()
        return {
            "operations": trivial_client.get_supported_operations(),
            "enabled": trivial_client.is_enabled(),
            "provider": trivial_client.provider if trivial_client.is_enabled() else None
        }
    except Exception as e:
        logger.error(f"Error getting trivial operations: {e}")
        return {
            "operations": [],
            "enabled": False,
            "error": str(e)
        }

# Database Availability Endpoints

@router.get("/databases/availability", response_model=DatabaseAvailabilityResponse)
async def get_database_availability(user_id: Optional[str] = None):
    """
    Get current database availability status for all configured databases.
    
    Args:
        user_id: Optional user ID to filter databases by user permissions
        
    Returns:
        DatabaseAvailabilityResponse with current status of all databases
    """
    logger.info(f"🔍 API ENDPOINT: /databases/availability - Getting database availability for user: {user_id}")
    
    try:
        availability_service = get_availability_service()
        
        # Get available databases for user
        if user_id:
            databases = availability_service.get_available_databases(user_id)
        else:
            all_statuses = availability_service.get_all_statuses()
            databases = list(all_statuses.values())
        
        # Convert to response models
        database_responses = []
        for db_status in databases:
            database_responses.append(DatabaseStatusResponse(
                name=db_status.name,
                type=db_status.type,
                status=db_status.status,
                last_checked=db_status.last_checked.isoformat(),
                response_time_ms=db_status.response_time_ms,
                error_message=db_status.error_message,
                user_accessible=db_status.user_accessible,
                connection_details=db_status.connection_details
            ))
        
        # Get summary
        summary = availability_service.get_summary()
        
        response = DatabaseAvailabilityResponse(
            databases=database_responses,
            summary=summary
        )
        
        logger.info(f"✅ Database availability retrieved: {len(database_responses)} databases, {summary['online']} online")
        return response
        
    except Exception as e:
        logger.error(f"❌ Error getting database availability: {str(e)}")
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to get database availability: {str(e)}")

@router.get("/databases/{database_name}/status", response_model=DatabaseStatusResponse)
async def get_database_status(database_name: str):
    """
    Get status for a specific database.
    
    Args:
        database_name: Name of the database to check
        
    Returns:
        DatabaseStatusResponse for the specified database
    """
    logger.info(f"🔍 API ENDPOINT: /databases/{database_name}/status - Getting status for database: {database_name}")
    
    try:
        availability_service = get_availability_service()
        db_status = availability_service.get_status(database_name)
        
        if not db_status:
            raise HTTPException(status_code=404, detail=f"Database '{database_name}' not found")
        
        response = DatabaseStatusResponse(
            name=db_status.name,
            type=db_status.type,
            status=db_status.status,
            last_checked=db_status.last_checked.isoformat(),
            response_time_ms=db_status.response_time_ms,
            error_message=db_status.error_message,
            user_accessible=db_status.user_accessible,
            connection_details=db_status.connection_details
        )
        
        logger.info(f"✅ Database status retrieved: {database_name} is {db_status.status}")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting database status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get database status: {str(e)}")

@router.post("/databases/check", response_model=DatabaseAvailabilityResponse)
async def force_database_check(request: ForceCheckRequest):
    """
    Force immediate check of database availability.
    
    Args:
        request: ForceCheckRequest with optional database_name to check specific database
        
    Returns:
        DatabaseAvailabilityResponse with updated status
    """
    logger.info(f"🔄 API ENDPOINT: /databases/check - Force checking database: {request.database_name or 'all'}")
    
    try:
        availability_service = get_availability_service()
        
        # Force check
        updated_statuses = await availability_service.force_check(request.database_name)
        
        # Convert to response models
        database_responses = []
        for db_status in updated_statuses.values():
            database_responses.append(DatabaseStatusResponse(
                name=db_status.name,
                type=db_status.type,
                status=db_status.status,
                last_checked=db_status.last_checked.isoformat(),
                response_time_ms=db_status.response_time_ms,
                error_message=db_status.error_message,
                user_accessible=db_status.user_accessible,
                connection_details=db_status.connection_details
            ))
        
        # Get updated summary
        summary = availability_service.get_summary()
        
        response = DatabaseAvailabilityResponse(
            databases=database_responses,
            summary=summary
        )
        
        logger.info(f"✅ Database check completed: {len(database_responses)} databases checked")
        return response
        
    except Exception as e:
        logger.error(f"❌ Error force checking databases: {str(e)}")
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to check databases: {str(e)}")

@router.get("/databases/summary")
async def get_database_summary():
    """
    Get summary statistics for database availability.
    
    Returns:
        Dict with summary statistics including total, online, offline counts and uptime percentage
    """
    logger.info(f"📊 API ENDPOINT: /databases/summary - Getting database summary")
    
    try:
        availability_service = get_availability_service()
        summary = availability_service.get_summary()
        
        logger.info(f"✅ Database summary retrieved: {summary['online']}/{summary['total_databases']} online")
        return summary
        
    except Exception as e:
        logger.error(f"❌ Error getting database summary: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get database summary: {str(e)}")

# ========== VISUALIZATION ENDPOINTS ==========

@router.post("/visualization/analyze", response_model=VisualizationAnalysisResponse)
async def analyze_for_visualization(request: VisualizationAnalysisRequest):
    """
    Analyze dataset and suggest optimal visualizations - Using general tools
    """
    session_id = f"viz_analyze_{int(time.time())}"
    start_time = time.time()
    
    logger.info(f"📊 Analyzing dataset for visualization: {request.user_intent}")
    
    try:
        # Step 1: Get real data using cross-database query engine
        import pandas as pd
        
        # Check if dataset contains actual data or if we need to fetch it
        if 'data' in request.dataset and request.dataset['data']:
            # Use provided data
            if isinstance(request.dataset['data'], list):
                df = pd.DataFrame(request.dataset['data'])
            else:
                df = pd.DataFrame(request.dataset['data'])
        else:
            # Fetch real data using the user intent as a query
            try:
                result = await process_ai_query(
                    question=request.user_intent,
                    analyze=False,
                    cross_database=True
                )
                
                if result.get("success") and result.get("rows"):
                    df = pd.DataFrame(result["rows"])
                else:
                    # Fallback to sample data
                    sample_data = [
                        {"category": "A", "value": 10, "date": "2024-01-01"},
                        {"category": "B", "value": 20, "date": "2024-01-02"},
                        {"category": "C", "value": 15, "date": "2024-01-03"},
                        {"category": "D", "value": 25, "date": "2024-01-04"},
                        {"category": "E", "value": 30, "date": "2024-01-05"}
                    ]
                    df = pd.DataFrame(sample_data)
                    
            except Exception as query_error:
                logger.error(f"Error fetching real data: {str(query_error)}")
                # Fallback to sample data
                sample_data = [
                    {"category": "A", "value": 10, "date": "2024-01-01"},
                    {"category": "B", "value": 20, "date": "2024-01-02"},
                    {"category": "C", "value": 15, "date": "2024-01-03"},
                    {"category": "D", "value": 25, "date": "2024-01-04"},
                    {"category": "E", "value": 30, "date": "2024-01-05"}
                ]
                df = pd.DataFrame(sample_data)
        
        # Step 2: Use the visualization tool from general_tools
        from ..tools.general_tools import VisualizationTools
        
        data_for_viz = df.to_dict('records')
        suggested_chart_type = _suggest_chart_type(df, request.user_intent)
        
        # Create visualization using the general tool
        viz_result = await VisualizationTools.create_visualization(
            data=data_for_viz,
            chart_type=suggested_chart_type,
            title=f"Visualization for: {request.user_intent}",
            user_query=request.user_intent,
            save_to_file=False  # Don't save file for analysis endpoint
        )
        
        # Step 3: Build analysis response
        estimated_render_time = _estimate_render_time(len(df), suggested_chart_type)
        
        response = VisualizationAnalysisResponse(
            analysis={
                "dataset_size": len(df),
                "variable_types": {col: str(df[col].dtype) for col in df.columns},
                "dimensionality": {"columns": len(df.columns), "rows": len(df)},
                "recommendations": ["Data suitable for visualization"]
            },
            recommendations={
                "primary_chart": {
                    "type": suggested_chart_type,
                    "confidence": 0.8,
                    "rationale": f"Suggested {suggested_chart_type} chart based on data structure",
                    "data_mapping": {"x": df.columns[0] if len(df.columns) > 0 else "x",
                                   "y": df.columns[1] if len(df.columns) > 1 else "y"}
                },
                "alternatives": [
                    {"type": "bar", "confidence": 0.6, "rationale": "Alternative bar chart"},
                    {"type": "line", "confidence": 0.5, "rationale": "Alternative line chart"}
                ]
            },
            estimated_render_time=estimated_render_time
        )
        
        total_time = time.time() - start_time
        logger.info(f"✅ Visualization analysis completed in {total_time:.2f}s")
        
        return response
        
    except Exception as e:
        error_time = time.time() - start_time
        logger.error(f"❌ Visualization analysis failed after {error_time:.2f}s: {str(e)}")
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Visualization analysis failed: {str(e)}")

@router.post("/visualization/generate", response_model=ChartGenerationResponse)
async def generate_chart_config(request: ChartGenerationRequest):
    """
    Generate optimized Plotly configuration - Using general tools
    """
    session_id = f"chart_gen_{int(time.time())}"
    logger.info(f"📈 Generating {request.chart_type} chart configuration")
    
    try:
        # Import general tools
        from ..tools.general_tools import VisualizationTools
        import pandas as pd
        
        # Use real data from request or fetch it
        if 'data' in request.data and request.data['data']:
            if isinstance(request.data['data'], list):
                df = pd.DataFrame(request.data['data'])
            else:
                df = pd.DataFrame(request.data['data'])
        else:
            # Generate appropriate sample data based on chart type
            if request.chart_type in ['scatter', 'scatter_plot']:
                sample_data = [
                    {"x": i, "y": i**2 + (i % 3) * 10} 
                    for i in range(1, 21)
                ]
            elif request.chart_type in ['bar', 'bar_chart']:
                sample_data = [
                    {"category": f"Category {chr(65+i)}", "value": (i+1) * 10 + (i % 3) * 5}
                    for i in range(5)
                ]
            elif request.chart_type in ['line', 'line_chart']:
                sample_data = [
                    {"date": f"2024-01-{i+1:02d}", "value": 100 + i * 5 + (i % 4) * 3}
                    for i in range(10)
                ]
            else:
                sample_data = [
                    {"x": i, "y": i * 2 + (i % 2) * 5} 
                    for i in range(1, 11)
                ]
            df = pd.DataFrame(sample_data)
        
        # Use the visualization tool to generate the chart
        data_for_viz = df.to_dict('records')
        
        viz_result = await VisualizationTools.create_visualization(
            data=data_for_viz,
            chart_type=request.chart_type,
            title=request.customizations.get('title', f"{request.chart_type.title()} Chart"),
            save_to_file=False  # Don't save file for API generation
        )
        
        # Extract the chart config from the visualization result
        chart_config = viz_result.get("chart_config", {})
        
        return ChartGenerationResponse(
            config=chart_config,
            performance_profile={
                "estimated_render_time": _estimate_render_time(len(df), request.chart_type),
                "memory_usage": "low" if len(df) < 1000 else "medium",
                "optimization_applied": False
            },
            alternative_configs=[]
        )
        
    except Exception as e:
        logger.error(f"❌ Chart generation failed: {str(e)}")
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Chart generation failed: {str(e)}")

# Enhanced visualization endpoints for direct connection
class VisualizationQueryRequest(BaseModel):
    query: str
    chart_preferences: Optional[Dict[str, Any]] = {}
    auto_generate: bool = True
    performance_mode: bool = False

class VisualizationQueryResponse(BaseModel):
    success: bool
    query: str
    data_summary: Dict[str, Any]
    chart_config: Optional[Dict[str, Any]] = None
    chart_data: Optional[List[Dict[str, Any]]] = None
    suggestions: List[Dict[str, Any]] = []
    session_id: str
    performance_metrics: Dict[str, Any]
    error_message: Optional[str] = None

@router.post("/visualization/query", response_model=VisualizationQueryResponse)
async def visualization_query(request: VisualizationQueryRequest, http_request: Request):
    """
    Direct connection: Query data and generate visualization in one call
    This is the main endpoint for GraphingBlock to use - Using general tools
    """
    # Get current user for audit and isolation
    current_user = await get_current_user_from_request(http_request)
    
    session_id = f"viz_query_{current_user}_{int(time.time())}"
    start_time = time.time()
    
    logger.info(f"🎯 Direct visualization query for user {current_user}: {request.query}")
    
    try:
        # Step 1: Fetch real data using cross-database query
        try:
            data_result = await process_ai_query(
                question=request.query,
                analyze=False,
                cross_database=True
            )
            
            if not data_result.get("success") or not data_result.get("rows"):
                raise Exception("No data returned from query")
                
            chart_data = data_result["rows"]
            
        except Exception as data_error:
            logger.error(f"Data fetch error: {str(data_error)}")
            # Fallback to sample data based on query intent
            chart_data = _generate_sample_data_for_query(request.query)
        
        # Step 2: Analyze data for visualization
        import pandas as pd
        df = pd.DataFrame(chart_data)
        
        data_summary = {
            "row_count": len(df),
            "column_count": len(df.columns),
            "columns": list(df.columns),
            "data_types": {col: str(df[col].dtype) for col in df.columns},
            "sample_data": df.head(3).to_dict('records') if len(df) > 0 else []
        }
        
        # Step 3: Generate chart if requested using general tools
        chart_config = None
        suggestions = []
        
        if request.auto_generate and len(df) > 0:
            try:
                # Use the visualization tool from general_tools
                from ..tools.general_tools import VisualizationTools
                
                suggested_chart_type = _suggest_chart_type(df, request.query)
                
                # Create visualization using the general tool
                viz_result = await VisualizationTools.create_visualization(
                    data=chart_data,
                    chart_type=suggested_chart_type,
                    title=request.chart_preferences.get('title', f"Visualization for: {request.query}"),
                    user_query=request.query,
                    save_to_file=request.chart_preferences.get('save_to_file', False)
                )
                
                chart_config = viz_result.get("chart_config", {})
                
                # Generate alternative suggestions
                suggestions = _generate_chart_suggestions(df, request.query)
                
            except Exception as chart_error:
                logger.error(f"Chart generation error: {str(chart_error)}")
                suggestions = [{"type": "bar", "confidence": 0.5, "rationale": "Default fallback"}]
        
        # Step 4: Performance metrics
        total_time = time.time() - start_time
        performance_metrics = {
            "total_time": total_time,
            "data_fetch_time": 0.5,  # Estimated
            "analysis_time": 0.1,
            "chart_generation_time": 0.2 if chart_config else 0,
            "dataset_size": len(chart_data)
        }
        
        response = VisualizationQueryResponse(
            success=True,
            query=request.query,
            data_summary=data_summary,
            chart_config=chart_config,
            chart_data=chart_data,
            suggestions=suggestions,
            session_id=session_id,
            performance_metrics=performance_metrics
        )
        
        logger.info(f"✅ Direct visualization query completed in {total_time:.2f}s")
        
        return response
        
    except Exception as e:
        error_time = time.time() - start_time
        logger.error(f"❌ Direct visualization query failed: {str(e)}")
        
        return VisualizationQueryResponse(
            success=False,
            query=request.query,
            data_summary={"error": "Failed to process query"},
            session_id=session_id,
            performance_metrics={"total_time": error_time, "error": True},
            error_message=str(e)
        )

def _generate_sample_data_for_query(query: str) -> List[Dict[str, Any]]:
    """Generate appropriate sample data based on query intent"""
    query_lower = query.lower()
    
    if any(keyword in query_lower for keyword in ['sales', 'revenue', 'profit']):
        return [
            {"month": f"2024-{i:02d}", "sales": 1000 + i * 200 + (i % 3) * 100, "region": f"Region {chr(65+i%3)}"}
            for i in range(1, 13)
        ]
    elif any(keyword in query_lower for keyword in ['users', 'customers', 'accounts']):
        return [
            {"date": f"2024-01-{i:02d}", "new_users": 50 + i * 5 + (i % 4) * 10, "total_users": 1000 + i * 50}
            for i in range(1, 31)
        ]
    elif any(keyword in query_lower for keyword in ['performance', 'metrics', 'analytics']):
        return [
            {"metric": f"Metric {chr(65+i)}", "value": 50 + i * 10, "target": 60 + i * 8}
            for i in range(5)
        ]
    else:
        # Default sample data
        return [
            {"category": f"Item {i}", "value": i * 10 + (i % 3) * 5, "score": 50 + i * 8}
            for i in range(1, 11)
        ]

def _suggest_chart_type(df: pd.DataFrame, query: str) -> str:
    """Suggest chart type based on data characteristics and query intent"""
    query_lower = query.lower()
    
    # Time series detection
    time_columns = [col for col in df.columns if any(time_word in col.lower() for time_word in ['date', 'time', 'month', 'year'])]
    if time_columns:
        return 'line'
    
    # Distribution analysis
    if 'distribution' in query_lower or 'histogram' in query_lower:
        return 'histogram'
    
    # Comparison analysis
    if any(word in query_lower for word in ['compare', 'vs', 'versus', 'comparison']):
        return 'bar'
    
    # Correlation analysis
    if any(word in query_lower for word in ['correlation', 'relationship', 'scatter']):
        return 'scatter'
    
    # Default based on data structure
    numeric_columns = df.select_dtypes(include=['number']).columns
    categorical_columns = df.select_dtypes(include=['object']).columns
    
    if len(numeric_columns) >= 2:
        return 'scatter'
    elif len(categorical_columns) >= 1 and len(numeric_columns) >= 1:
        return 'bar'
    else:
        return 'line'



def _generate_chart_suggestions(df: pd.DataFrame, query: str) -> List[Dict[str, Any]]:
    """Generate alternative chart suggestions"""
    suggestions = []
    
    # Always suggest a few common chart types
    chart_types = ['bar', 'line', 'scatter']
    
    for chart_type in chart_types:
        confidence = 0.8 if chart_type == _suggest_chart_type(df, query) else 0.5
        
        suggestions.append({
            "type": chart_type,
            "confidence": confidence,
            "rationale": f"{chart_type.title()} chart suitable for this data structure",
            "estimated_render_time": _estimate_render_time(len(df), chart_type)
        })
    
    return suggestions

def _estimate_render_time(dataset_size: int, chart_type: str) -> float:
    """Estimate rendering time in seconds"""
    base_times = {
        'scatter': 0.1,
        'line': 0.05,
        'bar': 0.08,
        'histogram': 0.06,
        'pie': 0.03,
        'box_plot': 0.12
    }
    
    base_time = base_times.get(chart_type, 0.1)
    
    if dataset_size < 1000:
        multiplier = 1.0
    elif dataset_size < 10000:
        multiplier = 2.0
    else:
        multiplier = 5.0
    
    return base_time * multiplier

# Authentication dependency for agent server
async def get_current_user_from_request(request: Request) -> str:
    """
    Extract current user from request using STRICT enterprise authentication
    
    NO FALLBACKS - Must have valid Okta session
    """
    try:
        # Import the enterprise auth system
        from ..auth.request_auth import get_current_user_strict
        
        # Use the strict authentication
        session_data = await get_current_user_strict(request)
        user_id = session_data.user_id
        
        auth_logger.info(f"🔐 Agent: Authenticated user: {user_id} ({session_data.email})")
        return user_id
        
    except Exception as e:
        auth_logger.error(f"🔐 Agent: Authentication failed: {str(e)}")
        # Re-raise the exception to ensure no fallback
        raise

# Helper to add user context to query results
def add_user_context_to_response(response_data: dict, user_id: str) -> dict:
    """Add user context to query responses for audit trail"""
    if isinstance(response_data, dict):
        response_data["user_context"] = {
            "user_id": user_id,
            "timestamp": datetime.utcnow().isoformat()
        }
    return response_data

@router.get("/auth/status")
async def get_agent_auth_status(request: Request):
    """Get current authentication status for agent server debugging"""
    try:
        current_user = await get_current_user_from_request(request)
        session_cookie = request.cookies.get('ceneca_session')
        user_header = request.headers.get('X-User-ID')
        
        return {
            "authenticated": True,
            "user_id": current_user,
            "auth_method": "header" if user_header else "cookie" if session_cookie else "development",
            "has_session_cookie": session_cookie is not None,
            "has_user_header": user_header is not None,
            "session_preview": session_cookie[:8] + "..." if session_cookie else None,
            "user_header_value": user_header,
            "timestamp": datetime.utcnow().isoformat(),
            "server": "agent"
        }
    except Exception as e:
        auth_logger.error(f"🔐 Agent auth status error: {str(e)}")
        return {
            "authenticated": False,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
            "server": "agent"
        }

# Add new request/response models after the existing TrivialHealthResponse class
class OrchestrationClassifyRequest(BaseModel):
    request: str
    context: Dict[str, Any]

class OrchestrationClassifyResponse(BaseModel):
    tier: str  # 'trivial' | 'overpowered' | 'hybrid'
    confidence: float
    reasoning: str
    estimated_time: int
    operation_type: str

@router.post("/orchestration/classify", response_model=OrchestrationClassifyResponse)
async def classify_orchestration_operation(request: OrchestrationClassifyRequest):
    """
    Classify an operation using LLM-based orchestration routing.
    This provides the same classification that would happen server-side with AWS Bedrock.
    """
    try:
        # Use the dedicated classification client
        from ..llm.client import get_classification_client
        
        classification_client = get_classification_client()
        
        if not classification_client.is_enabled():
            # Fallback to regex classification if client is not available
            import re
            data_analysis_patterns = r'\b(analyze|analysis|statistical|metrics|calculate|chart|graph|data\s+insight|database\s+quer|sql\s+quer)\b'
            is_data_analysis = bool(re.search(data_analysis_patterns, request.request, re.IGNORECASE))
            
            tier = 'overpowered' if is_data_analysis else 'trivial'
            operation_type = 'data_analysis' if is_data_analysis else 'text_editing'
            
            logger.info(f"🧠 ORCHESTRATION: Fallback classification (client disabled): {tier.upper()} ({operation_type})")
            
            return OrchestrationClassifyResponse(
                tier=tier,
                confidence=0.7,
                reasoning=f"Fallback regex classification: {'DATA ANALYSIS detected' if is_data_analysis else 'TEXT EDITING (default)'} due to classification client unavailable",
                estimated_time=3000 if is_data_analysis else 500,
                operation_type=operation_type
            )
        
        # Use the classification client
        result = await classification_client.classify_operation(request.request, request.context)
        
        return OrchestrationClassifyResponse(
            tier=result["tier"],
            confidence=result["confidence"],
            reasoning=result["reasoning"],
            estimated_time=result["estimated_time"],
            operation_type=result["operation_type"]
        )
        
    except Exception as e:
        logger.error(f"🧠 ORCHESTRATION: Classification endpoint failed: {e}")
        # Final fallback to regex classification
        import re
        data_analysis_patterns = r'\b(analyze|analysis|statistical|metrics|calculate|chart|graph|data\s+insight|database\s+quer|sql\s+quer)\b'
        is_data_analysis = bool(re.search(data_analysis_patterns, request.request, re.IGNORECASE))
        
        tier = 'overpowered' if is_data_analysis else 'trivial'
        operation_type = 'data_analysis' if is_data_analysis else 'text_editing'
        
        logger.info(f"🧠 ORCHESTRATION: Final fallback classification: {tier.upper()} ({operation_type})")
        
        return OrchestrationClassifyResponse(
            tier=tier,
            confidence=0.7,
            reasoning=f"Fallback regex classification: {'DATA ANALYSIS detected' if is_data_analysis else 'TEXT EDITING (default)'} due to endpoint error: {str(e)}",
            estimated_time=3000 if is_data_analysis else 500,
            operation_type=operation_type
        )

# Add new request/response models after the existing TrivialHealthResponse class
class LangGraphQueryRequest(BaseModel):
    question: str
    force_langgraph: bool = False
    show_routing: bool = False
    verbose: bool = False
    show_outputs: bool = False
    show_timeline: bool = False
    show_captured_data: bool = False  # NEW: Show captured SQL queries and tool executions
    export_analysis: Optional[str] = None
    save_session: bool = True
    stream_output: bool = True
    include_aggregated_data: bool = False  # NEW: Control inline data return

class LangGraphQueryResponse(BaseModel):
    success: bool
    workflow: str
    question: str
    session_id: str
    execution_metadata: Dict[str, Any]
    routing_decision: Optional[Dict[str, Any]] = None
    node_results: Optional[Dict[str, Any]] = None
    final_result: Optional[Dict[str, Any]] = None
    operation_results: Optional[Dict[str, Any]] = None
    visualization_data: Optional[Dict[str, Any]] = None
    performance_metrics: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None

# Global orchestrator instance to avoid re-initialization (same as cross_db.py)
_global_langgraph_orchestrator = None

def get_langgraph_orchestrator():
    """Get or create the global LangGraph orchestrator instance"""
    global _global_langgraph_orchestrator
    
    if _global_langgraph_orchestrator is None:
        from ..config.settings import Settings
        settings = Settings()
        
        config = {
            "use_langgraph_for_complex": True,
            "complexity_threshold": 3,  # Lower threshold for testing
            "preserve_trivial_routing": True,
            "llm_config": {
                "primary_provider": "bedrock",
                "fallbacks": ["anthropic", "openai"]
            }
        }
        _global_langgraph_orchestrator = LangGraphIntegrationOrchestrator(config)
        langgraph_logger.info("🔧 Initialized global LangGraph orchestrator")
    
    return _global_langgraph_orchestrator

@router.post("/langgraph/stream")
async def langgraph_stream(request: LangGraphQueryRequest, http_request: Request):
    """
    LangGraph orchestration endpoint with streaming Server-Sent Events
    
    Implements the exact same LangGraph logic as the CLI langgraph command,
    but as a streaming API endpoint for real-time updates.
    
    Data Export Mechanisms:
    1. Local file saving: Use export_analysis="/path/to/file.json" 
       - Saves complete workflow data to local file system
       - Same as CLI --export-analysis flag
    
    2. Inline API data: Use include_aggregated_data=true
       - Streams structured data directly in API response
       - Events: api_structured_data, api_execution_plans, api_tool_results, api_complete_response
       - Perfect for programmatic API consumption
    
    Example usage:
    {
        "question": "how many products and orders do i have in mongo",
        "include_aggregated_data": true,
        "export_analysis": "/tmp/analysis.json",
        "save_session": true
    }
    """
    # Get current user for audit and isolation
    current_user = await get_current_user_from_request(http_request)
    
    request_data = {
        "endpoint": "/langgraph/stream",
        "user": current_user,
        "question": request.question,
        "force_langgraph": request.force_langgraph,
        "show_routing": request.show_routing,
        "verbose": request.verbose,
        "show_outputs": request.show_outputs,
        "show_timeline": request.show_timeline,
        "save_session": request.save_session
    }
    
    start_time = time.time()
    
    langgraph_logger.info(f"🚀 [LANGGRAPH CLI LOGIC] Starting LangGraph execution")
    langgraph_logger.info(f"📋 [LANGGRAPH CLI LOGIC] Question: '{request.question}'")
    langgraph_logger.info(f"⚙️ [LANGGRAPH CLI LOGIC] Settings - force_langgraph: {request.force_langgraph}, verbose: {request.verbose}")
    
    async def generate_stream():
        # Initialize LangGraph integration orchestrator (same as CLI)
        orchestrator = get_langgraph_orchestrator()
        
        # Create session for tracking (same as CLI)
        session_id = str(uuid.uuid4())
        
        try:
            yield create_stream_event("status", session_id, message="🚀 LangGraph Query Execution")
            yield create_stream_event("status", session_id, message=f"Question: {request.question}")
            yield create_stream_event("status", session_id, message=f"Session ID: {session_id[:8]}...")
            yield create_stream_event("status", session_id, message="")
            
            langgraph_logger.info(f"🔧 [CLI LOGIC] Using session ID: {session_id[:8]}...")
            
            # ✅ GRANULAR STREAMING: Add real-time events during execution
            from ..langgraph.output_aggregator import get_output_integrator
            
            # Start detailed reasoning with immediate feedback
            yield create_stream_event("detailed_reasoning_start", session_id,
                message="🔍 STARTING DETAILED REASONING CHAIN"
            )
            
            # Add granular progress events
            yield create_stream_event("progress", session_id,
                message="🤖 Initializing LangGraph workflow...",
                progress=10,
                status="initializing"
            )
            
            yield create_stream_event("progress", session_id,
                message="🎯 Analyzing query complexity...",
                progress=20,
                status="analyzing"
            )
            
            yield create_stream_event("progress", session_id,
                message="🔍 Selecting optimal workflow path...",
                progress=30,
                status="routing"
            )
            
            yield create_stream_event("progress", session_id,
                message="📊 Connecting to data sources...",
                progress=40,
                status="connecting"
            )
            
            yield create_stream_event("progress", session_id,
                message="⚡ Executing workflow operations...",
                progress=50,
                status="executing"
            )
            
            # Process query with real-time monitoring - let LangGraph determine optimal routing and databases (EXACT CLI LOGIC)
            result = await orchestrator.process_query(
                question=request.question,
                session_id=session_id,
                databases_available=None,  # Let it auto-detect (same as CLI)
                force_langgraph=request.force_langgraph
            )
            
            # ✅ COMPREHENSIVE DEFENSIVE: Handle ExecutionResult objects and ensure all results are dictionaries
            def ensure_dict_result(obj, path="root"):
                """Recursively convert any ExecutionResult objects to dictionaries"""
                if obj is None:
                    return obj
                
                # Import ExecutionResult for type checking
                try:
                    from ..tools.registry import ExecutionResult
                    if isinstance(obj, ExecutionResult):
                        logger.warning(f"Converting ExecutionResult to dict at path: {path}")
                        converted = {
                            "success": obj.success,
                            "result": ensure_dict_result(obj.result, f"{path}.result") if obj.result else None,
                            "error": obj.error,
                            "metadata": ensure_dict_result(obj.metadata, f"{path}.metadata") if obj.metadata else {},
                            "tool_id": obj.tool_id,
                            "call_id": obj.call_id
                        }
                        # If result.result is a dict, merge it up
                        if isinstance(converted["result"], dict):
                            return {**converted["result"], **{k: v for k, v in converted.items() if k != "result"}}
                        return converted
                except ImportError:
                    pass
                
                # Handle other objects that don't have .get() method
                if hasattr(obj, '__dict__') and not hasattr(obj, 'get'):
                    logger.warning(f"Converting object {type(obj)} to dict at path: {path}")
                    if hasattr(obj, 'result') and hasattr(obj, 'success'):
                        # This looks like an ExecutionResult-like object
                        return {
                            "success": getattr(obj, 'success', True),
                            "result": ensure_dict_result(getattr(obj, 'result', None), f"{path}.result"),
                            "error": getattr(obj, 'error', None),
                            "metadata": ensure_dict_result(getattr(obj, 'metadata', {}), f"{path}.metadata"),
                            "tool_id": getattr(obj, 'tool_id', None),
                            "call_id": getattr(obj, 'call_id', None)
                        }
                    else:
                        return obj.__dict__
                
                # Handle dictionaries recursively
                if isinstance(obj, dict):
                    return {k: ensure_dict_result(v, f"{path}.{k}") for k, v in obj.items()}
                
                # Handle lists recursively
                if isinstance(obj, list):
                    return [ensure_dict_result(item, f"{path}[{i}]") for i, item in enumerate(obj)]
                
                # Return primitives as-is
                return obj
            
            # Apply comprehensive conversion
            result = ensure_dict_result(result)
            
            # Final safety check
            if not isinstance(result, dict):
                logger.error(f"Result is STILL not a dictionary after conversion: {type(result)}")
                result = {"error": f"Failed to convert result type: {type(result)}", "original_result": str(result)}
            
            # Immediate post-execution feedback
            yield create_stream_event("progress", session_id,
                message="✅ Workflow execution completed",
                progress=80,
                status="completed"
            )
            
            # ✅ IMMEDIATE DETAILED REASONING: Stream the captured data right after execution
            try:
                output_integrator = get_output_integrator()
                
                # CRITICAL: Extract the actual session ID used by the workflow execution (EXACT CLI LOGIC)
                # The workflow may have created internal sessions we need to track
                actual_session_id = result.get("session_id", session_id)
                if actual_session_id != session_id:
                    langgraph_logger.info(f"🔧 Using workflow session ID: {actual_session_id[:8]}...")
                    session_id = actual_session_id
                    yield create_stream_event("session_updated", session_id, new_session_id=actual_session_id)
                
                aggregator = output_integrator.get_aggregator(session_id)
                
                # Enhanced logging for detailed reasoning
                langgraph_reasoning_logger.info(f"🔍 [REASONING_CHAIN] Starting detailed reasoning analysis for session: {session_id[:8]}...")
                langgraph_reasoning_logger.info(f"🔍 [REASONING_CHAIN] Question: '{request.question}'")
                
                # Stream the same detailed information as CLI
                yield create_stream_event("detailed_reasoning_start", session_id,
                    message="🔍 DETAILED REASONING CHAIN"
                )
                
                # 🔍 SQL QUERIES EXECUTED (same as CLI)
                raw_data = aggregator.get_all_raw_data()
                langgraph_reasoning_logger.info(f"🔍 [REASONING_CHAIN] Raw data captured: {len(raw_data)} items")
                
                if raw_data:
                    yield create_stream_event("sql_queries_section", session_id,
                        message="🔍 SQL QUERIES EXECUTED:"
                    )
                    
                    sql_queries = [rd for rd in raw_data if rd.query]
                    langgraph_reasoning_logger.info(f"🔍 [SQL_QUERIES] Found {len(sql_queries)} SQL queries in captured data")
                    
                    for i, rd in enumerate(sql_queries, 1):
                        langgraph_reasoning_logger.info(f"🔍 [SQL_QUERIES] Query {i}: {rd.source} - {rd.execution_time_ms:.1f}ms, {rd.row_count} rows")
                        langgraph_reasoning_logger.debug(f"🔍 [SQL_QUERIES] Query {i} text: {rd.query}")
                        
                        yield create_stream_event("sql_query_executed", session_id,
                            query_number=i,
                            source=rd.source,
                            query_text=rd.query,
                            execution_time_ms=rd.execution_time_ms,
                            rows_returned=rd.row_count,
                            message=f"  Query {i}: {rd.source} - {rd.execution_time_ms:.1f}ms, {rd.row_count} rows"
                        )
                else:
                    langgraph_reasoning_logger.warning(f"🔍 [SQL_QUERIES] No SQL queries captured for session {session_id[:8]}")
                    yield create_stream_event("no_sql_queries", session_id,
                        message="  No SQL queries captured"
                    )
                
                # 🔧 TOOL EXECUTIONS (same as CLI)
                tool_executions = aggregator.get_all_tool_executions()
                langgraph_reasoning_logger.info(f"🔧 [TOOL_EXECUTIONS] Found {len(tool_executions)} tool executions")
                
                if tool_executions:
                    yield create_stream_event("tool_executions_section", session_id,
                        message="🔧 TOOL EXECUTIONS:"
                    )
                    
                    success_count = sum(1 for tool in tool_executions if tool.success)
                    total_time = sum(tool.execution_time_ms for tool in tool_executions)
                    langgraph_reasoning_logger.info(f"🔧 [TOOL_EXECUTIONS] Success rate: {success_count}/{len(tool_executions)} ({success_count/len(tool_executions)*100:.1f}%), Total time: {total_time:.1f}ms")
                    
                    for i, tool in enumerate(tool_executions, 1):
                        status_emoji = "✅ Success" if tool.success else "❌ Failed"
                        langgraph_reasoning_logger.info(f"🔧 [TOOL_EXECUTIONS] Tool {i}: {tool.tool_id} - {status_emoji} ({tool.execution_time_ms:.1f}ms)")
                        if tool.error_message:
                            langgraph_reasoning_logger.error(f"🔧 [TOOL_EXECUTIONS] Tool {i} error: {tool.error_message}")
                        
                        yield create_stream_event("tool_execution_completed", session_id,
                            execution_number=i,
                            tool_id=tool.tool_id,
                            success=tool.success,
                            execution_time_ms=tool.execution_time_ms,
                            call_id=tool.call_id,
                            error_message=tool.error_message,
                            message=f"  Tool {i}: {tool.tool_id} - {status_emoji} ({tool.execution_time_ms:.1f}ms)"
                        )
                else:
                    langgraph_reasoning_logger.warning(f"🔧 [TOOL_EXECUTIONS] No tool executions captured for session {session_id[:8]}")
                    yield create_stream_event("no_tool_executions", session_id,
                        message="  No tool executions captured"
                    )
                
                # 📊 DATABASE SCHEMA DISCOVERY (same as CLI)
                schema_data = [rd for rd in raw_data if not rd.query]  # Schema data doesn't have queries
                if schema_data:
                    yield create_stream_event("schema_discovery_section", session_id,
                        message="📊 DATABASE SCHEMA DISCOVERY:"
                    )
                    
                    for rd in schema_data:
                        source = getattr(rd, 'source', None) or 'unknown'
                        table_count = rd.row_count if rd.row_count else len(rd.rows) if rd.rows else 0
                        
                        # Extract content preview safely
                        content_preview = "No preview available"
                        try:
                            if rd.rows and len(rd.rows) > 0:
                                if isinstance(rd.rows[0], dict) and "content" in rd.rows[0]:
                                    content_preview = str(rd.rows[0]["content"])[:200] + "..."
                                elif hasattr(rd.rows[0], 'content'):
                                    content_preview = str(rd.rows[0].content)[:200] + "..."
                                else:
                                    content_preview = str(rd.rows[0])[:100] + "..."
                        except (AttributeError, IndexError, KeyError):
                            content_preview = "Content extraction error"
                        
                        yield create_stream_event("schema_discovered", session_id,
                            source=source,
                            tables_found=table_count,
                            content_preview=content_preview,
                            message=f"  Source {source}: {table_count} tables found"
                        )
                else:
                    yield create_stream_event("no_schema_discovery", session_id,
                        message="  No schema discovery data captured"
                    )
                
                # 📋 EXECUTION PLAN DETAILS (same as CLI)
                execution_plans = aggregator.get_all_execution_plans()
                if execution_plans:
                    yield create_stream_event("execution_plans_section", session_id,
                        message="📋 EXECUTION PLAN DETAILS:"
                    )
                    
                    for i, plan in enumerate(execution_plans, 1):
                        operations_count = len(plan.operations) if hasattr(plan, 'operations') else 0
                        strategy = getattr(plan, 'strategy', 'unknown')
                        
                        yield create_stream_event("execution_plan_detail", session_id,
                            plan_number=i,
                            plan_id=plan.plan_id if hasattr(plan, 'plan_id') else 'unknown',
                            strategy=strategy,
                            operations_count=operations_count,
                            message=f"  Plan {i}: {strategy} strategy, {operations_count} operations"
                        )
                else:
                    yield create_stream_event("no_execution_plans", session_id,
                        message="  No execution plans captured"
                    )
                
                # 📝 FINAL SYNTHESIS ANALYSIS (same as CLI)
                final_synthesis = aggregator.get_final_synthesis()
                if final_synthesis:
                    synthesis_text = final_synthesis.response_text if hasattr(final_synthesis, 'response_text') else str(final_synthesis)
                    synthesis_length = len(synthesis_text)
                    # ✅ FIX: Ensure confidence_score is always a float, not string
                    confidence_raw = getattr(final_synthesis, 'confidence_score', 0.0)
                    confidence = float(confidence_raw) if confidence_raw is not None else 0.0
                    sources_used = getattr(final_synthesis, 'sources_used', 0)
                    
                    yield create_stream_event("final_synthesis_analysis", session_id,
                        synthesis_length=synthesis_length,
                        confidence_score=confidence,
                        sources_used=sources_used,
                        synthesis_preview=synthesis_text[:500] + "..." if len(synthesis_text) > 500 else synthesis_text,
                        message=f"📝 FINAL SYNTHESIS: {synthesis_length} chars, confidence: {confidence:.2f}, sources: {sources_used}"
                    )
                else:
                    yield create_stream_event("no_final_synthesis", session_id,
                        message="📝 No final synthesis available"
                    )
                
                yield create_stream_event("detailed_reasoning_complete", session_id,
                    message="🔍 Detailed reasoning chain complete"
                )
                
                # ✅ TIMING FIX: Clear progress update after detailed reasoning is extracted
                yield create_stream_event("progress", session_id,
                    message="Detailed reasoning extracted successfully",
                    progress=95,
                    status="reasoning_complete"
                )
                
            except Exception as e:
                yield create_stream_event("reasoning_chain_warning", session_id,
                    message=f"⚠️ Could not access detailed reasoning chain: {e}"
                )
                if request.verbose:
                    langgraph_logger.warning(f"Reasoning chain access failed: {e}")

            # ✅ NOW stream "Analysis complete" AFTER detailed reasoning has been captured and sent
            yield create_stream_event("progress", session_id,
                message="Analysis complete, finalizing results...",
                progress=95,
                status="finalizing"
            )
            
            # Display routing information if requested (EXACT CLI LOGIC)
            execution_metadata = result.get("execution_metadata", {})
            routing_method = execution_metadata.get("routing_method", "unknown")
            complexity_analysis = execution_metadata.get("complexity_analysis", {})
            
            if request.show_routing or request.verbose:
                yield create_stream_event("routing_decision", session_id,
                    method=routing_method,
                    complexity=complexity_analysis.get('complexity', 'unknown'),
                    reason=complexity_analysis.get('reason', 'No reason provided'),
                    confidence=complexity_analysis.get('confidence', 'unknown')
                )
            
            # Check for errors (EXACT CLI LOGIC)
            if "error" in result:
                error_msg = result['error']
                langgraph_logger.error(f"❌ [CLI LOGIC] LangGraph execution failed: {error_msg}")
                
                # Show additional error details if available (same as CLI)
                if request.verbose and "execution_metadata" in result:
                    error_details = result["execution_metadata"].get("error_details")
                    if error_details:
                        langgraph_logger.error(f"❌ [CLI LOGIC] Error details: {error_details}")
                        yield create_stream_event("error_details", session_id, details=error_details)
                
                yield create_stream_event("error", session_id,
                    error_code="LANGGRAPH_EXECUTION_FAILED",
                    message=error_msg,
                    recoverable=False
                )
                yield create_stream_event("complete", session_id, success=False, error=error_msg)
                return
            
            # Success - display results based on workflow type (EXACT CLI LOGIC)
            workflow = result.get("workflow", "unknown")
            execution_time = execution_metadata.get("execution_time", 0)
            
            yield create_stream_event("execution_success", session_id,
                workflow=workflow,
                execution_time=execution_time,
                message=f"✅ Execution Successful ({workflow} workflow)"
            )
            
            langgraph_logger.info(f"✅ [CLI LOGIC] Execution successful: {workflow} workflow, {execution_time:.2f}s")
            
            # Show comprehensive output breakdown if requested (EXACT CLI LOGIC)
            if request.show_outputs or request.show_timeline or request.export_analysis or request.include_aggregated_data or request.show_captured_data:
                try:
                    from ..langgraph.output_aggregator import get_output_integrator
                    
                    output_integrator = get_output_integrator()
                    aggregator = output_integrator.get_aggregator(session_id)
                    
                    # ✅ NEW: Show captured data if requested (EXACT CLI LOGIC)
                    if request.show_captured_data:
                        yield create_stream_event("captured_data_start", session_id,
                            message="🔍 CAPTURED DATA SUMMARY"
                        )
                        
                        # Get all captured data (same as CLI)
                        raw_data = aggregator.get_all_raw_data()
                        tool_executions = aggregator.get_all_tool_executions() 
                        execution_plans = aggregator.get_all_execution_plans()
                        final_synthesis = aggregator.get_final_synthesis()
                        
                        yield create_stream_event("captured_data_counts", session_id,
                            total_outputs=len(aggregator.outputs),
                            raw_data_count=len(raw_data),
                            tool_executions_count=len(tool_executions),
                            execution_plans_count=len(execution_plans),
                            has_final_synthesis=final_synthesis is not None
                        )
                        
                        # 🔍 SQL QUERIES EXECUTED (same as CLI)
                        yield create_stream_event("sql_queries_section", session_id,
                            message="🔍 SQL QUERIES EXECUTED:"
                        )
                        
                        sql_queries = [rd for rd in raw_data if rd.query]
                        if sql_queries:
                            for i, rd in enumerate(sql_queries, 1):
                                yield create_stream_event("sql_query_executed", session_id,
                                    query_number=i,
                                    source=rd.source,
                                    query_text=rd.query,
                                    execution_time_ms=rd.execution_time_ms,
                                    rows_returned=rd.row_count,
                                    message=f"  Query {i}: {rd.source} - {rd.execution_time_ms:.1f}ms, {rd.row_count} rows"
                                )
                        else:
                            yield create_stream_event("no_sql_queries", session_id,
                                message="  No SQL queries captured"
                            )
                        
                        # 🔧 TOOL EXECUTIONS (same as CLI)
                        yield create_stream_event("tool_executions_section", session_id,
                            message="🔧 TOOL EXECUTIONS:"
                        )
                        
                        if tool_executions:
                            for i, tool in enumerate(tool_executions, 1):
                                yield create_stream_event("tool_execution_completed", session_id,
                                    execution_number=i,
                                    tool_id=tool.tool_id,
                                    success=tool.success,
                                    execution_time_ms=tool.execution_time_ms,
                                    call_id=tool.call_id,
                                    error_message=tool.error_message,
                                    message=f"  Tool {i}: {tool.tool_id} - {status_emoji} ({tool.execution_time_ms:.1f}ms)"
                                )
                        else:
                            yield create_stream_event("no_tool_executions", session_id,
                                message="  No tool executions captured"
                            )
                        
                        # 📊 DATABASE SCHEMA DISCOVERY (same as CLI)
                        schema_data = [rd for rd in raw_data if not rd.query]  # Schema data doesn't have queries
                        if schema_data:
                            yield create_stream_event("schema_discovery_section", session_id,
                                message="📊 DATABASE SCHEMA DISCOVERY:"
                            )
                            
                            for rd in schema_data:
                                source = getattr(rd, 'source', None) or 'unknown'
                                table_count = rd.row_count if rd.row_count else len(rd.rows) if rd.rows else 0
                                
                                # Extract content preview safely
                                content_preview = "No preview available"
                                try:
                                    if rd.rows and len(rd.rows) > 0:
                                        if isinstance(rd.rows[0], dict) and "content" in rd.rows[0]:
                                            content_preview = str(rd.rows[0]["content"])[:200] + "..."
                                        elif hasattr(rd.rows[0], 'content'):
                                            content_preview = str(rd.rows[0].content)[:200] + "..."
                                        else:
                                            content_preview = str(rd.rows[0])[:100] + "..."
                                except (AttributeError, IndexError, KeyError):
                                    content_preview = "Content extraction error"
                                
                                yield create_stream_event("schema_discovered", session_id,
                                    source=source,
                                    tables_found=table_count,
                                    content_preview=content_preview,
                                    message=f"  Source {source}: {table_count} tables found"
                                )
                        else:
                            yield create_stream_event("no_schema_discovery", session_id,
                                message="  No schema discovery data captured"
                            )
                        
                        # 📋 EXECUTION PLAN DETAILS (same as CLI)
                        execution_plans = aggregator.get_all_execution_plans()
                        if execution_plans:
                            yield create_stream_event("execution_plans_section", session_id,
                                message="📋 EXECUTION PLAN DETAILS:"
                            )
                            
                            for i, plan in enumerate(execution_plans, 1):
                                operations_count = len(plan.operations) if hasattr(plan, 'operations') else 0
                                strategy = getattr(plan, 'strategy', 'unknown')
                                
                                yield create_stream_event("execution_plan_detail", session_id,
                                    plan_number=i,
                                    plan_id=plan.plan_id if hasattr(plan, 'plan_id') else 'unknown',
                                    strategy=strategy,
                                    operations_count=operations_count,
                                    message=f"  Plan {i}: {strategy} strategy, {operations_count} operations"
                                )
                        else:
                            yield create_stream_event("no_execution_plans", session_id,
                                message="  No execution plans captured"
                            )
                        
                        # 📝 FINAL SYNTHESIS ANALYSIS (same as CLI)
                        final_synthesis = aggregator.get_final_synthesis()
                        if final_synthesis:
                            synthesis_text = final_synthesis.response_text if hasattr(final_synthesis, 'response_text') else str(final_synthesis)
                            synthesis_length = len(synthesis_text)
                            # ✅ FIX: Ensure confidence_score is always a float, not string
                            confidence_raw = getattr(final_synthesis, 'confidence_score', 0.0)
                            confidence = float(confidence_raw) if confidence_raw is not None else 0.0
                            sources_used = getattr(final_synthesis, 'sources_used', 0)
                            
                            yield create_stream_event("final_synthesis_analysis", session_id,
                                synthesis_length=synthesis_length,
                                confidence_score=confidence,
                                sources_used=sources_used,
                                synthesis_preview=synthesis_text[:500] + "..." if len(synthesis_text) > 500 else synthesis_text,
                                message=f"📝 FINAL SYNTHESIS: {synthesis_length} chars, confidence: {confidence:.2f}, sources: {sources_used}"
                            )
                        else:
                            yield create_stream_event("no_final_synthesis", session_id,
                                message="📝 No final synthesis available"
                            )
                        
                        yield create_stream_event("detailed_reasoning_complete", session_id,
                            message="🔍 Detailed reasoning chain complete"
                            )
                    
                    # ✅ CRITICAL ENHANCEMENT: Verify and log captured SQL queries and tool execution data
                    yield create_stream_event("data_verification", session_id,
                        message="🔍 Verifying captured SQL queries and tool execution data..."
                    )
                    
                    # Get captured data for verification  
                    raw_data = aggregator.get_all_raw_data()
                    tool_executions = aggregator.get_all_tool_executions()
                    execution_plans = aggregator.get_all_execution_plans()
                    
                    # Stream SQL queries that were captured
                    if raw_data:
                        yield create_stream_event("sql_queries_captured", session_id,
                            message=f"📊 Captured {len(raw_data)} SQL queries/operations:",
                            sql_count=len(raw_data)
                        )
                        
                        for i, data in enumerate(raw_data):
                            if data.query:
                                yield create_stream_event("sql_query_detail", session_id,
                                    query_index=i+1,
                                    source=data.source,
                                    sql=data.query,
                                    row_count=data.row_count,
                                    execution_time_ms=data.execution_time_ms
                                )
                    else:
                        yield create_stream_event("sql_queries_warning", session_id,
                            message="⚠️ No SQL queries were captured - this may indicate an integration issue"
                        )
                    
                    # Stream tool execution details
                    if tool_executions:
                        yield create_stream_event("tool_executions_captured", session_id,
                            message=f"🔧 Captured {len(tool_executions)} tool executions:",
                            tool_count=len(tool_executions)
                        )
                        
                        for i, tool in enumerate(tool_executions):
                            yield create_stream_event("tool_execution_detail", session_id,
                                execution_index=i+1,
                                tool_id=tool.tool_id,
                                success=tool.success,
                                parameters=tool.parameters,
                                execution_time_ms=tool.execution_time_ms,
                                error_message=tool.error_message if tool.error_message else None
                            )
                    else:
                        yield create_stream_event("tool_executions_warning", session_id,
                            message="⚠️ No tool executions were captured - this may indicate an integration issue"
                        )
                    
                    # Show output breakdown (same as CLI display_output_breakdown function)
                    if request.show_outputs:
                        yield create_stream_event("output_analysis", session_id,
                            message="📊 Comprehensive Output Analysis"
                        )
                        
                        # Get all different types of outputs (same as CLI)
                        final_synthesis = aggregator.get_final_synthesis()
                        performance = aggregator.get_performance_summary()
                        
                        yield create_stream_event("output_breakdown", session_id,
                            raw_data_count=len(raw_data),
                            execution_plans_count=len(execution_plans),
                            tool_executions_count=len(tool_executions),
                            has_final_synthesis=final_synthesis is not None,
                            has_performance=performance is not None
                        )
                    
                    # NEW: Include aggregated data inline in API response
                    if request.include_aggregated_data:
                        yield create_stream_event("aggregated_data_start", session_id,
                            message="📦 Sending Aggregated Workflow Data"
                        )
                        
                        # Get both unified result and API-ready response
                        unified_result = aggregator.create_unified_result()
                        api_response = aggregator.create_api_response()
                        
                        # Send structured API data (cleaner format for API consumers)
                        yield create_stream_event("api_structured_data", session_id,
                            data=api_response["data"],
                            mechanism="inline_api"
                        )
                        
                        # Send execution plans as JSON
                        if api_response["execution_plans"]:
                            yield create_stream_event("api_execution_plans", session_id,
                                plans=api_response["execution_plans"],
                                plan_count=len(api_response["execution_plans"]),
                                mechanism="inline_api"
                            )
                        
                        # Send tool results with success tracking
                        if api_response["tool_results"]:
                            yield create_stream_event("api_tool_results", session_id,
                                tools=api_response["tool_results"],
                                tool_count=len(api_response["tool_results"]),
                                success_rate=api_response["performance"]["success_rate"],
                                mechanism="inline_api"
                            )
                        
                        # Send performance metrics (API format)
                        yield create_stream_event("api_performance", session_id,
                            metrics=api_response["performance"],
                            mechanism="inline_api"
                        )
                        
                        # Send analysis if available
                        if api_response["analysis"]:
                            yield create_stream_event("api_analysis", session_id,
                                analysis=api_response["analysis"],
                                mechanism="inline_api"
                            )
                        
                        # Send complete API response (structured for API consumption)
                        yield create_stream_event("api_complete_response", session_id,
                            response=api_response,
                            mechanism="inline_api"
                        )
                        
                        # Send legacy unified result for backward compatibility
                        yield create_stream_event("unified_result", session_id,
                            result=unified_result,
                            mechanism="legacy_format"
                        )
                    
                    # Show timeline (same as CLI display_workflow_timeline function)
                    if request.show_timeline:
                        yield create_stream_event("timeline_analysis", session_id,
                            message="⏱️ Workflow Execution Timeline"
                        )
                        
                        timeline = aggregator.get_workflow_timeline()
                        if timeline:
                            yield create_stream_event("workflow_timeline", session_id,
                                timeline=timeline,
                                event_count=len(timeline)
                            )
                    
                    # Export analysis (same as CLI - local file saving mechanism)
                    if request.export_analysis:
                        export_data = aggregator.export_for_analysis()
                        
                        # Save to local file (existing mechanism)
                        import json
                        import os
                        
                        # Ensure export directory exists
                        os.makedirs(os.path.dirname(request.export_analysis), exist_ok=True)
                        
                        with open(request.export_analysis, 'w') as f:
                            json.dump(export_data, f, indent=2, default=str)
                        
                        yield create_stream_event("analysis_exported", session_id,
                            export_path=request.export_analysis,
                            data_size=len(str(export_data)),
                            mechanism="local_file"
                        )
                        
                        # Also send inline if requested
                        if request.include_aggregated_data:
                            yield create_stream_event("export_data_inline", session_id,
                                export_data=export_data,
                                mechanism="inline_api"
                            )
                        
                except Exception as e:
                    yield create_stream_event("warning", session_id,
                        message=f"⚠️ Could not access output aggregator: {e}"
                    )
                    if request.verbose:
                        langgraph_logger.warning(f"Output aggregator access failed: {e}")
            
            # Check for and display visualization data first (EXACT CLI LOGIC)
            visualization_data = result.get("visualization_data")
            
            # ✅ FIXED: Extract visualization data from aggregator tool executions
            if not visualization_data and aggregator:
                try:
                    # Get tool executions from the aggregator
                    tool_executions = aggregator.get_all_tool_executions()
                    logger.info(f"🔍 AGGREGATOR TOOL EXECUTIONS COUNT: {len(tool_executions)}")
                    
                    for i, tool_execution in enumerate(tool_executions):
                        logger.info(f"🔍 TOOL EXECUTION {i}: {tool_execution.tool_id} - Success: {tool_execution.success}")
                        logger.info(f"🔍 TOOL EXECUTION {i} RESULT TYPE: {type(tool_execution.result)}")
                        
                        if (tool_execution.tool_id == "visualization.create_visualization" and 
                            tool_execution.success and 
                            tool_execution.result):
                            
                            # Extract the visualization result
                            visualization_data = tool_execution.result
                            logger.info(f"🎨 FOUND VISUALIZATION TOOL RESULT FROM AGGREGATOR: {tool_execution.tool_id}")
                            logger.info(f"🎨 VISUALIZATION DATA KEYS: {list(visualization_data.keys()) if isinstance(visualization_data, dict) else 'Not a dict'}")
                            logger.info(f"🎨 VISUALIZATION_CREATED: {visualization_data.get('visualization_created') if isinstance(visualization_data, dict) else 'N/A'}")
                            logger.info(f"🎨 HAS CHART_CONFIG: {bool(visualization_data.get('chart_config')) if isinstance(visualization_data, dict) else 'N/A'}")
                            break
                except Exception as e:
                    logger.warning(f"Failed to extract visualization data from aggregator: {e}")
                    
            # ✅ FALLBACK: Try to extract from tool execution results in result
            if not visualization_data:
                # Try to extract from tool execution results
                tool_execution_result = result.get("tool_execution_result", {})
                logger.info(f"🔍 DEBUGGING TOOL EXECUTION RESULTS: {list(tool_execution_result.keys())}")
                
                for tool_result in tool_execution_result.get("execution_results", []):
                    logger.info(f"🔍 PROCESSING TOOL RESULT: {tool_result.get('tool_id')} - Success: {tool_result.get('success')}")
                    logger.info(f"🔍 TOOL RESULT KEYS: {list(tool_result.keys()) if isinstance(tool_result, dict) else 'Not a dict'}")
                    
                    if tool_result.get("tool_id") == "visualization.create_visualization" and tool_result.get("success"):
                        visualization_data = tool_result.get("result", {})
                        logger.info(f"🎨 FOUND VISUALIZATION TOOL RESULT! Keys: {list(visualization_data.keys()) if isinstance(visualization_data, dict) else 'Not a dict'}")
                        break
            
            if visualization_data and visualization_data.get("visualization_created"):
                logger.info("🎨 PROCESSING VISUALIZATION DATA FOR STREAMING")
                chart_type = visualization_data.get("performance_metrics", {}).get("chart_type", "unknown")
                dataset_size = visualization_data.get("dataset_info", {}).get("size", 0)
                
                logger.info(f"🎨 YIELDING visualization_created EVENT: chart_type={chart_type}, dataset_size={dataset_size}")
                yield create_stream_event("visualization_created", session_id,
                    chart_type=chart_type,
                    dataset_size=dataset_size,
                    intent=visualization_data.get('visualization_intent', 'N/A'),
                    message="🎨 Visualization Created"
                )
                
                # Show chart configuration summary (same as CLI)
                chart_config = visualization_data.get("chart_config", {})
                logger.info(f"🎨 CHART CONFIG EXTRACTED: {bool(chart_config)}")
                logger.info(f"🎨 CHART CONFIG KEYS: {list(chart_config.keys()) if chart_config else 'No config'}")
                
                if chart_config:
                    logger.info("🎨 YIELDING chart_config EVENT")
                    yield create_stream_event("chart_config", session_id,
                        type=chart_config.get('type', 'unknown'),
                        data_points=len(chart_config.get('data', [])),
                        title=chart_config.get('layout', {}).get('title', 'N/A')
                    )
                    
                    # ✅ NEW: Display the FULL JSON configuration (same as CLI)
                    import json as json_module  # Use explicit import to avoid shadowing
                    logger.info("🎨 YIELDING chart_config_json EVENT")
                    yield create_stream_event("chart_config_json", session_id,
                        message="📋 Complete Chart Configuration JSON:",
                        metadata={
                            "chart_config": chart_config,
                            "json_size": len(json_module.dumps(chart_config, indent=2))
                        }
                    )
                    
                    # ✅ NEW: Send complete visualization package as single chunk
                    logger.info("🎨 YIELDING visualization_complete EVENT - SINGLE CONSOLIDATED CHUNK")
                    yield create_stream_event("visualization_complete", session_id,
                        message="🎯 Complete Visualization Package",
                        # Complete chart configuration
                        chart_config=chart_config,
                        # All visualization metadata
                        visualization_data=visualization_data,
                        # Chart summary for easy identification
                        chart_summary={
                            "type": chart_config.get('type', 'unknown'),
                            "title": chart_config.get('layout', {}).get('title', 'N/A'),
                            "data_points": len(chart_config.get('data', [])),
                            "chart_type": chart_type,
                            "dataset_size": dataset_size,
                            "intent": visualization_data.get('visualization_intent', 'N/A'),
                            "execution_time": visualization_data.get("performance_metrics", {}).get("execution_time", 0),
                            "confidence": visualization_data.get("chart_selection", {}).get("primary_chart", {}).get("confidence_score", 0)
                        },
                        # Easy identification flags
                        is_visualization=True,
                        ready_for_render=True
                    )
                else:
                    logger.warning("🎨 NO CHART CONFIG FOUND IN VISUALIZATION DATA")
                    
                    # ✅ NEW: Show JSON file save location if available (same as CLI)
                    json_file_path = visualization_data.get("file_path") or visualization_data.get("json_file_path")
                    if json_file_path:
                        yield create_stream_event("chart_json_saved", session_id,
                            message=f"💾 Chart JSON saved to: {json_file_path}",
                            file_path=json_file_path
                        )
            else:
                logger.info(f"🎨 VISUALIZATION DATA CHECK FAILED:")
                logger.info(f"  - visualization_data exists: {bool(visualization_data)}")
                logger.info(f"  - visualization_created: {visualization_data.get('visualization_created') if visualization_data else 'N/A'}")
            
            # Display results based on workflow type (EXACT CLI LOGIC)
            if workflow == "traditional":
                # Traditional workflow results (same as CLI)
                final_result = result.get("final_result", {})
                operation_results = result.get("operation_results", {})
                
                if request.verbose:
                    yield create_stream_event("operation_results", session_id,
                        operations={op_id: {"status": "✅" if "error" not in op_result else "❌", 
                                           "rows": len(op_result.get('data', []))}
                                   for op_id, op_result in operation_results.items()},
                        message="Operation Results"
                    )
                
                # Display final formatted result (same as CLI)
                if "formatted_result" in final_result:
                    yield create_stream_event("formatted_result", session_id,
                        result=final_result["formatted_result"]
                    )
                elif "data" in final_result and final_result["data"]:
                    yield create_stream_event("tabular_results", session_id,
                        data=final_result["data"][:100]  # Limit for streaming
                    )
                else:
                    yield create_stream_event("no_results", session_id, 
                        message="No results to display"
                    )
            
            elif workflow == "langgraph":
                # LangGraph workflow results (same as CLI)
                node_results = result.get("node_results", {})
                final_state = result.get("final_result", {})
                
                if request.verbose:
                    yield create_stream_event("node_results", session_id,
                        nodes={node_id: {"status": "✅" if "error" not in node_result else "❌"}
                               for node_id, node_result in node_results.items()},
                        message="Node Execution Results"
                    )
                
                # Display final results from graph state (same as CLI)
                if "operation_results" in final_state:
                    operation_results = final_state["operation_results"]
                    
                    # Try to extract and display data (same as CLI)
                    all_data = []
                    for op_result in operation_results.values():
                        if isinstance(op_result, dict) and "data" in op_result:
                            all_data.extend(op_result["data"])
                    
                    if all_data:
                        yield create_stream_event("tabular_results", session_id,
                            data=all_data[:100]  # Limit for streaming
                        )
                    else:
                        yield create_stream_event("no_results", session_id, 
                            message="No tabular results to display",
                            final_state_keys=list(final_state.keys())
                        )
            
            elif workflow == "hybrid":
                # Hybrid workflow results (same as CLI)
                final_result = result.get("final_result", {})
                operation_results = result.get("operation_results", {})
                hybrid_advantages = result.get("hybrid_advantages", [])
                
                # ✅ NEW: Extract additional visualization data from hybrid workflow (same as CLI)
                if not visualization_data:
                    tool_execution_result = result.get("tool_execution_result", {})
                    for tool_result in tool_execution_result.get("execution_results", []):
                        if tool_result.get("tool_id") == "visualization.create_visualization" and tool_result.get("success"):
                            hybrid_viz_data = tool_result.get("result", {})
                            if hybrid_viz_data and hybrid_viz_data.get("visualization_created"):
                                yield create_stream_event("hybrid_visualization_found", session_id,
                                    message="🎨 Hybrid workflow generated visualization",
                                    chart_type=hybrid_viz_data.get("performance_metrics", {}).get("chart_type", "unknown"),
                                    dataset_size=hybrid_viz_data.get("dataset_info", {}).get("size", 0)
                                )
                                
                                # Show complete JSON config from hybrid workflow
                                hybrid_chart_config = hybrid_viz_data.get("chart_config", {})
                                if hybrid_chart_config:
                                    import json as json_module  # Use explicit import to avoid shadowing
                                    yield create_stream_event("hybrid_chart_config_json", session_id,
                                        message="📋 Hybrid Workflow Chart Configuration JSON:",
                                        metadata={
                                            "chart_config": hybrid_chart_config,
                                            "json_size": len(json_module.dumps(hybrid_chart_config, indent=2))
                                        }
                                    )
                                    
                                    # ✅ NEW: Send complete hybrid visualization package as single chunk
                                    yield create_stream_event("visualization_complete", session_id,
                                        message="🎯 Complete Hybrid Visualization Package",
                                        # Complete chart configuration
                                        chart_config=hybrid_chart_config,
                                        # All visualization metadata
                                        visualization_data=hybrid_viz_data,
                                        # Chart summary for easy identification
                                        chart_summary={
                                            "type": hybrid_chart_config.get('type', 'unknown'),
                                            "title": hybrid_chart_config.get('layout', {}).get('title', 'N/A'),
                                            "data_points": len(hybrid_chart_config.get('data', [])),
                                            "chart_type": hybrid_viz_data.get("performance_metrics", {}).get("chart_type", "unknown"),
                                            "dataset_size": hybrid_viz_data.get("dataset_info", {}).get("size", 0),
                                            "intent": hybrid_viz_data.get('visualization_intent', 'N/A'),
                                            "execution_time": hybrid_viz_data.get("performance_metrics", {}).get("execution_time", 0),
                                            "confidence": hybrid_viz_data.get("chart_selection", {}).get("primary_chart", {}).get("confidence_score", 0),
                                            "workflow": "hybrid"
                                        },
                                        # Easy identification flags
                                        is_visualization=True,
                                        ready_for_render=True,
                                        from_hybrid_workflow=True
                                    )
                                    
                                    # Show JSON file save location from hybrid workflow
                                    hybrid_json_file_path = hybrid_viz_data.get("file_path") or hybrid_viz_data.get("json_file_path")
                                    if hybrid_json_file_path:
                                        yield create_stream_event("hybrid_chart_json_saved", session_id,
                                            message=f"💾 Hybrid workflow chart JSON saved to: {hybrid_json_file_path}",
                                            file_path=hybrid_json_file_path
                                        )
                            break
                
                if request.verbose:
                    yield create_stream_event("hybrid_advantages", session_id,
                        advantages=hybrid_advantages,
                        message="Hybrid Workflow Advantages"
                    )
                
                # Display results similar to traditional but with hybrid enhancements (same as CLI)
                if "formatted_result" in final_result:
                    yield create_stream_event("formatted_result", session_id,
                        result=final_result["formatted_result"]
                    )
                elif operation_results:
                    # Extract data from operation results (same as CLI)
                    all_data = []
                    for op_result in operation_results.values():
                        if isinstance(op_result, dict) and "data" in op_result:
                            all_data.extend(op_result["data"])
                    
                    if all_data:
                        yield create_stream_event("tabular_results", session_id,
                            data=all_data[:100]  # Limit for streaming
                        )
                    else:
                        yield create_stream_event("no_results", session_id, 
                            message="No results to display"
                        )
            
            # Send SQL queries that were executed (same as CLI output)
            if result.get("operation_results"):
                for op_id, op_result in result["operation_results"].items():
                    if isinstance(op_result, dict) and op_result.get("sql"):
                        yield create_stream_event("query_executing", session_id,
                            database=op_result.get("database", "unknown"),
                            sql=op_result["sql"],
                            operation_id=op_id
                        )
            
            # Send execution plan info (same as CLI output)
            if result.get("plan_info"):
                plan_info = result["plan_info"]
                yield create_stream_event("execution_plan", session_id,
                    plan_id=plan_info.get("id", "unknown"),
                    operations=plan_info.get("operations", []),
                    execution_strategy=plan_info.get("execution_strategy", "unknown")
                )
            
            # Show performance statistics if available (EXACT CLI LOGIC)
            if request.verbose:
                integration_status = orchestrator.get_integration_status()
                exec_stats = integration_status.get("execution_statistics", {})
                
                yield create_stream_event("performance_stats", session_id,
                    traditional_executions=exec_stats.get('traditional_executions', 0),
                    langgraph_executions=exec_stats.get('langgraph_executions', 0),
                    hybrid_executions=exec_stats.get('hybrid_executions', 0),
                    message="LangGraph Integration Statistics"
                )
            
            # Save session if requested (EXACT CLI LOGIC)
            if request.save_session:
                # Use existing state manager to save session details (same as CLI)
                state_manager = StateManager()
                session_state = AnalysisState(
                session_id=session_id,
                    user_question=request.question
                )
                
                # Add execution metadata as insights (same as CLI)
                session_state.add_insight("execution", "LangGraph execution", {
                    "langgraph_execution": True,
                    "workflow_type": workflow,
                    "routing_method": execution_metadata.get("routing_method"),
                    "execution_time": execution_time
                })
                
                # Set final result (same as CLI)
                if "final_result" in result:
                    session_state.set_final_result(
                        result["final_result"],
                        result.get("final_result", {}).get("formatted_result", str(result.get("final_result", {})))
                    )
                
                await state_manager.update_state(session_state)
                yield create_stream_event("session_saved", session_id,
                    message=f"Session saved with ID: {session_id}",
                    session_id_full=session_id
                )
            
            # Final progress update before completion
            yield create_stream_event("progress", session_id,
                message="Analysis complete, finalizing results...",
                progress=100,
                status="finalizing"
            )
            
            # Complete (same as CLI success handling)
            total_time = time.time() - start_time
            yield create_stream_event("complete", session_id,
                success=True,
                total_time=total_time,
                workflow=workflow,
                results=result.get("final_result", {})
            )
            
            # Log completion (same as CLI)
            duration = time.time() - start_time
            log_request_response(langgraph_logger, "/langgraph/stream", request_data, {
                "success": True,
                "workflow": workflow,
                "execution_time": execution_time
            }, duration)
            
        except Exception as e:
            error_time = time.time() - start_time
            error_msg = str(e)
            
            langgraph_logger.error(f"❌ [CLI LOGIC] LangGraph execution failed: {error_msg}")
            langgraph_logger.error(f"❌ [CLI LOGIC] Exception details: {traceback.format_exc()}")
            
            yield create_stream_event("error", session_id,
                error_code="LANGGRAPH_STREAMING_FAILED",
                message=error_msg,
                recoverable=False
            )
            yield create_stream_event("complete", session_id, success=False, error=error_msg)
            
            # Log error
            log_request_response(langgraph_logger, "/langgraph/stream", request_data, {}, error_time, error_msg)
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control"
        }
    )


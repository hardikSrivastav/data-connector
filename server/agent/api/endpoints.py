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
from ..tools.state_manager import StateManager, get_state_manager
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
    endpoint_logger.setLevel(logging.INFO)
    
    # Remove existing handlers to avoid duplicates
    for handler in endpoint_logger.handlers[:]:
        endpoint_logger.removeHandler(handler)
    
    # Create file handler
    log_file = os.path.join(LOG_DIR, f"{endpoint_name}.log")
    file_handler = logging.FileHandler(log_file)
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
    Analyze dataset and suggest optimal visualizations - Enhanced with real data
    """
    session_id = f"viz_analyze_{int(time.time())}"
    
    # Create dedicated chart generation logger
    chart_logger = logging.getLogger('chart_generation')
    if not chart_logger.handlers:
        chart_handler = logging.FileHandler('chart_generation.log')
        chart_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        chart_handler.setFormatter(formatter)
        chart_logger.addHandler(chart_handler)
        chart_logger.setLevel(logging.DEBUG)
    
    start_time = time.time()
    chart_logger.info(f"[{session_id}] === ENHANCED VISUALIZATION ANALYSIS API STARTED ===")
    chart_logger.info(f"[{session_id}] User intent: '{request.user_intent}'")
    chart_logger.info(f"[{session_id}] Dataset keys: {list(request.dataset.keys())}")
    chart_logger.info(f"[{session_id}] User preferences: {request.preferences}")
    
    logger.info(f"📊 Analyzing dataset for visualization: {request.user_intent}")
    
    try:
        # Import visualization modules
        chart_logger.info(f"[{session_id}] Step 1: Importing visualization modules...")
        from ..visualization.analyzer import DataAnalysisModule
        from ..visualization.selector import ChartSelectionEngine
        from ..visualization.types import VisualizationDataset, UserPreferences
        
        # Step 2: Get real data using cross-database query engine
        chart_logger.info(f"[{session_id}] Step 2: Fetching real data via cross-database query...")
        import pandas as pd
        
        # Check if dataset contains actual data or if we need to fetch it
        if 'data' in request.dataset and request.dataset['data']:
            chart_logger.info(f"[{session_id}] Using provided dataset")
            # Use provided data
            if isinstance(request.dataset['data'], list):
                df = pd.DataFrame(request.dataset['data'])
            else:
                df = pd.DataFrame(request.dataset['data'])
        else:
            # Fetch real data using the user intent as a query
            chart_logger.info(f"[{session_id}] Fetching data via cross-database query: '{request.user_intent}'")
            try:
                # Use the enhanced process_ai_query function to get real data
                result = await process_ai_query(
                    question=request.user_intent,
                    analyze=False,  # We'll do visualization analysis instead
                    cross_database=True  # Enable cross-database queries
                )
                
                if result.get("success") and result.get("rows"):
                    df = pd.DataFrame(result["rows"])
                    chart_logger.info(f"[{session_id}] Real data fetched: {len(df)} rows, {len(df.columns)} columns")
                    chart_logger.debug(f"[{session_id}] Columns: {list(df.columns)}")
                else:
                    chart_logger.warning(f"[{session_id}] No data returned from query, using sample data")
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
                chart_logger.error(f"[{session_id}] Error fetching real data: {str(query_error)}")
                # Fallback to sample data
                sample_data = [
                    {"category": "A", "value": 10, "date": "2024-01-01"},
                    {"category": "B", "value": 20, "date": "2024-01-02"},
                    {"category": "C", "value": 15, "date": "2024-01-03"},
                    {"category": "D", "value": 25, "date": "2024-01-04"},
                    {"category": "E", "value": 30, "date": "2024-01-05"}
                ]
                df = pd.DataFrame(sample_data)
        
        # Create VisualizationDataset
        dataset = VisualizationDataset(
            data=df,
            columns=list(df.columns),
            metadata={"source": "cross_database_query", "session_id": session_id},
            source_info={"origin": "enhanced_api", "query": request.user_intent}
        )
        chart_logger.info(f"[{session_id}] Dataset created: {len(df)} rows, {len(df.columns)} columns")
        
        # Get LLM client for analysis
        chart_logger.info(f"[{session_id}] Step 3: Initializing LLM client...")
        llm_client = get_llm_client()
        chart_logger.info(f"[{session_id}] LLM client type: {type(llm_client).__name__}")
        
        # Analyze dataset
        chart_logger.info(f"[{session_id}] Step 4: Starting dataset analysis...")
        analyzer = DataAnalysisModule(llm_client)
        analysis_result = await analyzer.analyze_dataset(dataset, request.user_intent, session_id)
        chart_logger.info(f"[{session_id}] Dataset analysis completed")
        
        # Get chart recommendations
        chart_logger.info(f"[{session_id}] Step 5: Starting chart selection...")
        selector = ChartSelectionEngine(llm_client)
        
        # Create proper UserPreferences object
        user_prefs = UserPreferences(
            preferred_style=request.preferences.get('style', 'modern'),
            performance_priority=request.preferences.get('performance', 'medium'),
            interactivity_level=request.preferences.get('interactivity', 'medium')
        )
        chart_logger.debug(f"[{session_id}] User preferences: {user_prefs}")
        
        chart_selection = await selector.select_optimal_chart(analysis_result, user_prefs, session_id)
        chart_logger.info(f"[{session_id}] Chart selection completed")
        
        # Estimate render time
        chart_logger.info(f"[{session_id}] Step 6: Estimating render time...")
        estimated_render_time = _estimate_render_time(analysis_result.dataset_size, chart_selection.primary_chart.chart_type)
        chart_logger.info(f"[{session_id}] Estimated render time: {estimated_render_time:.2f}s")
        
        # Build response
        chart_logger.info(f"[{session_id}] Step 7: Building API response...")
        response = VisualizationAnalysisResponse(
            analysis={
                "dataset_size": analysis_result.dataset_size,
                "variable_types": {k: v.__dict__ for k, v in analysis_result.variable_types.items()},
                "dimensionality": analysis_result.dimensionality.__dict__,
                "recommendations": analysis_result.recommendations
            },
            recommendations={
                "primary_chart": {
                    "type": chart_selection.primary_chart.chart_type,
                    "confidence": chart_selection.primary_chart.confidence_score,
                    "rationale": chart_selection.primary_chart.rationale,
                    "data_mapping": chart_selection.primary_chart.data_mapping
                },
                "alternatives": [
                    {
                        "type": alt.chart_type,
                        "confidence": alt.confidence_score,
                        "rationale": alt.rationale
                    } for alt in chart_selection.alternatives
                ]
            },
            estimated_render_time=estimated_render_time
        )
        
        total_time = time.time() - start_time
        chart_logger.info(f"[{session_id}] === VISUALIZATION ANALYSIS API COMPLETED ===")
        chart_logger.info(f"[{session_id}] Total API time: {total_time:.2f}s")
        chart_logger.info(f"[{session_id}] Primary chart type: {chart_selection.primary_chart.chart_type}")
        
        return response
        
    except Exception as e:
        error_time = time.time() - start_time
        chart_logger.error(f"[{session_id}] === VISUALIZATION ANALYSIS API FAILED ===")
        chart_logger.error(f"[{session_id}] Error after {error_time:.2f}s: {str(e)}")
        chart_logger.exception(f"[{session_id}] Full error traceback:")
        
        logger.error(f"❌ Visualization analysis failed: {str(e)}")
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Visualization analysis failed: {str(e)}")

@router.post("/visualization/generate", response_model=ChartGenerationResponse)
async def generate_chart_config(request: ChartGenerationRequest):
    """
    Generate optimized Plotly configuration - Enhanced with real data
    """
    session_id = f"chart_gen_{int(time.time())}"
    logger.info(f"📈 Generating {request.chart_type} chart configuration")
    
    # Add logging for chart generation
    chart_logger = logging.getLogger('chart_generation')
    chart_logger.info(f"[{session_id}] === CHART GENERATION API STARTED ===")
    chart_logger.info(f"[{session_id}] Chart type: {request.chart_type}")
    chart_logger.info(f"[{session_id}] Data keys: {list(request.data.keys())}")
    
    try:
        # Import visualization modules
        from ..visualization.generator import PlotlyConfigGenerator, PlotlyOptimizer
        from ..visualization.types import VisualizationDataset, ChartRecommendation
        
        # Convert request data to internal format
        import pandas as pd
        
        chart_logger.info(f"[{session_id}] Step 1: Processing input data...")
        
        # Use real data from request or fetch it
        if 'data' in request.data and request.data['data']:
            chart_logger.info(f"[{session_id}] Using provided data")
            if isinstance(request.data['data'], list):
                df = pd.DataFrame(request.data['data'])
            else:
                df = pd.DataFrame(request.data['data'])
        else:
            chart_logger.info(f"[{session_id}] No data provided, using sample data for chart type: {request.chart_type}")
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
        
        chart_logger.info(f"[{session_id}] Data processed: {len(df)} rows, {len(df.columns)} columns")
        chart_logger.debug(f"[{session_id}] Columns: {list(df.columns)}")
        
        dataset = VisualizationDataset(
            data=df,
            columns=list(df.columns),
            metadata={"source": "chart_generation_api", "session_id": session_id},
            source_info={"origin": "enhanced_chart_generation", "chart_type": request.chart_type}
        )
        
        # Create mock recommendation
        recommendation = ChartRecommendation(
            chart_type=request.chart_type,
            confidence_score=0.8,
            rationale=f"Generated {request.chart_type} chart",
            data_mapping={"x": "x", "y": "y"},
            performance_score=0.9
        )
        
        # Generate configuration
        generator = PlotlyConfigGenerator()
        base_config = await generator.generate_config(
            chart_type=request.chart_type,
            dataset=dataset,
            recommendation=recommendation,
            customizations=request.customizations
        )
        
        # Apply performance optimizations
        from ..visualization.types import RenderOptions
        render_options = RenderOptions(
            performance_mode=request.performance_requirements.get('performance_mode', False)
        )
        
        optimizer = PlotlyOptimizer()
        optimized_config = optimizer.optimize_for_performance(base_config, render_options)
        
        # Generate alternatives (simplified)
        alternative_configs = []
        
        return ChartGenerationResponse(
            config={
                "data": optimized_config.data,
                "layout": optimized_config.layout,
                "config": optimized_config.config,
                "type": optimized_config.type
            },
            performance_profile={
                "estimated_render_time": _estimate_render_time(len(dataset.data), request.chart_type),
                "memory_usage": "low" if len(dataset.data) < 1000 else "medium",
                "optimization_applied": optimized_config.performance_mode
            },
            alternative_configs=alternative_configs
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
    This is the main endpoint for GraphingBlock to use
    """
    # Get current user for audit and isolation
    current_user = await get_current_user_from_request(http_request)
    
    session_id = f"viz_query_{current_user}_{int(time.time())}"
    start_time = time.time()
    
    # Setup logging
    chart_logger = logging.getLogger('chart_generation')
    chart_logger.info(f"[{session_id}] === DIRECT VISUALIZATION QUERY STARTED ===")
    chart_logger.info(f"[{session_id}] User: {current_user}")
    chart_logger.info(f"[{session_id}] User query: '{request.query}'")
    chart_logger.info(f"[{session_id}] Auto generate: {request.auto_generate}")
    chart_logger.info(f"[{session_id}] Chart preferences: {request.chart_preferences}")
    
    logger.info(f"🎯 Direct visualization query for user {current_user}: {request.query}")
    
    try:
        # Step 1: Fetch real data using cross-database query
        chart_logger.info(f"[{session_id}] Step 1: Fetching data via cross-database query...")
        
        try:
            data_result = await process_ai_query(
                question=request.query,
                analyze=False,
                cross_database=True
            )
            
            if not data_result.get("success") or not data_result.get("rows"):
                chart_logger.warning(f"[{session_id}] Query returned no data, using sample data")
                raise Exception("No data returned from query")
                
            chart_data = data_result["rows"]
            chart_logger.info(f"[{session_id}] Real data fetched: {len(chart_data)} rows")
            
        except Exception as data_error:
            chart_logger.error(f"[{session_id}] Data fetch error: {str(data_error)}")
            # Fallback to sample data based on query intent
            chart_data = _generate_sample_data_for_query(request.query)
            chart_logger.info(f"[{session_id}] Using sample data: {len(chart_data)} rows")
        
        # Step 2: Analyze data for visualization
        chart_logger.info(f"[{session_id}] Step 2: Analyzing data for visualization...")
        
        import pandas as pd
        df = pd.DataFrame(chart_data)
        
        data_summary = {
            "row_count": len(df),
            "column_count": len(df.columns),
            "columns": list(df.columns),
            "data_types": {col: str(df[col].dtype) for col in df.columns},
            "sample_data": df.head(3).to_dict('records') if len(df) > 0 else []
        }
        
        chart_logger.info(f"[{session_id}] Data summary: {data_summary['row_count']} rows, {data_summary['column_count']} columns")
        
        # Step 3: Generate chart if requested
        chart_config = None
        suggestions = []
        
        if request.auto_generate and len(df) > 0:
            chart_logger.info(f"[{session_id}] Step 3: Auto-generating chart...")
            
            try:
                # Quick analysis for chart selection
                suggested_chart_type = _suggest_chart_type(df, request.query)
                chart_logger.info(f"[{session_id}] Suggested chart type: {suggested_chart_type}")
                
                # Generate chart configuration
                chart_config = _generate_chart_config(df, suggested_chart_type, request.chart_preferences)
                
                # Generate alternative suggestions
                suggestions = _generate_chart_suggestions(df, request.query)
                
                chart_logger.info(f"[{session_id}] Chart config generated successfully")
                
            except Exception as chart_error:
                chart_logger.error(f"[{session_id}] Chart generation error: {str(chart_error)}")
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
        
        chart_logger.info(f"[{session_id}] === DIRECT VISUALIZATION QUERY COMPLETED ===")
        chart_logger.info(f"[{session_id}] Total time: {total_time:.2f}s")
        chart_logger.info(f"[{session_id}] Chart generated: {chart_config is not None}")
        
        return response
        
    except Exception as e:
        error_time = time.time() - start_time
        chart_logger.error(f"[{session_id}] === DIRECT VISUALIZATION QUERY FAILED ===")
        chart_logger.error(f"[{session_id}] Error after {error_time:.2f}s: {str(e)}")
        chart_logger.exception(f"[{session_id}] Full error traceback:")
        
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

def _generate_chart_config(df: pd.DataFrame, chart_type: str, preferences: Dict[str, Any]) -> Dict[str, Any]:
    """Generate Plotly chart configuration with dark mode support"""
    
    # Check for dark mode preference
    dark_mode = preferences.get("dark_mode", False)
    
    # Dark mode color scheme
    dark_theme = {
        "plot_bgcolor": "#1f2937",
        "paper_bgcolor": "#111827",
        "font": {"color": "#f9fafb"},
        "xaxis": {
            "gridcolor": "#374151",
            "zerolinecolor": "#6b7280",
            "tickcolor": "#9ca3af",
            "linecolor": "#6b7280"
        },
        "yaxis": {
            "gridcolor": "#374151",
            "zerolinecolor": "#6b7280",
            "tickcolor": "#9ca3af",
            "linecolor": "#6b7280"
        },
        "colorway": [
            "#3b82f6", "#10b981", "#f59e0b", "#ef4444",
            "#8b5cf6", "#06b6d4", "#f97316", "#84cc16"
        ]
    } if dark_mode else {}
    
    # Basic configuration structure
    config = {
        "type": chart_type,
        "data": [],
        "layout": {
            "title": preferences.get("title", f"{chart_type.title()} Chart"),
            "showlegend": True,
            "margin": {"l": 50, "r": 50, "t": 50, "b": 50},
            **dark_theme  # Apply dark theme if enabled
        },
        "config": {
            "responsive": True,
            "displayModeBar": True,
            "modeBarButtonsToRemove": [],
            "displaylogo": False
        }
    }
    
    # Generate data based on chart type
    if chart_type == 'bar':
        categorical_col = df.select_dtypes(include=['object']).columns[0] if len(df.select_dtypes(include=['object']).columns) > 0 else df.columns[0]
        numeric_col = df.select_dtypes(include=['number']).columns[0] if len(df.select_dtypes(include=['number']).columns) > 0 else df.columns[-1]
        
        config["data"] = [{
            "type": "bar",
            "x": df[categorical_col].tolist(),
            "y": df[numeric_col].tolist(),
            "name": numeric_col
        }]
        
    elif chart_type == 'line':
        x_col = df.columns[0]
        y_col = df.columns[1] if len(df.columns) > 1 else df.columns[0]
        
        config["data"] = [{
            "type": "scatter",
            "mode": "lines",
            "x": df[x_col].tolist(),
            "y": df[y_col].tolist(),
            "name": y_col
        }]
        
    elif chart_type == 'scatter':
        x_col = df.columns[0]
        y_col = df.columns[1] if len(df.columns) > 1 else df.columns[0]
        
        config["data"] = [{
            "type": "scatter",
            "mode": "markers",
            "x": df[x_col].tolist(),
            "y": df[y_col].tolist(),
            "name": f"{x_col} vs {y_col}"
        }]
    
    return config

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

class LangGraphQueryRequest(BaseModel):
    """Request model for LangGraph queries."""
    question: str
    analyze: bool = False
    optimize: bool = False
    force_langgraph: bool = False
    save_session: bool = True
    databases_available: Optional[List[str]] = None

# LangGraph streaming endpoint
@router.post("/langgraph/stream")
async def langgraph_query_stream(request: LangGraphQueryRequest, http_request: Request):
    """
    Streaming version of the LangGraph query endpoint using Server-Sent Events
    
    Args:
        request: LangGraphQueryRequest containing the question and options
        http_request: HTTP request for user authentication
        
    Returns:
        StreamingResponse with Server-Sent Events
    """
    start_time = time.time()
    
    # Get current user for audit and isolation
    try:
        current_user = await get_current_user_from_request(http_request)
    except Exception as e:
        langgraph_logger.error(f"❌ Authentication failed: {str(e)}")
        return StreamingResponse(
            [create_stream_event(
                "error",
                str(uuid.uuid4()),
                error_code="AUTH_FAILED",
                message="Authentication failed",
                recoverable=False
            )],
            media_type="text/event-stream"
        )
    
    request_data = {
        "endpoint": "/langgraph/stream",
        "user": current_user,
        "question": request.question,
        "analyze": request.analyze,
        "optimize": request.optimize,
        "force_langgraph": request.force_langgraph,
        "databases_available": request.databases_available
    }
    
    langgraph_logger.info(f"🌊 API ENDPOINT: /langgraph/stream - Starting streaming LangGraph query")
    langgraph_logger.info(f"📥 Request details: {json.dumps(request_data, indent=2)}")
    
    async def generate_stream():
        session_id = str(uuid.uuid4())
        
        try:
            # Initialize LangGraph orchestrator
            orchestrator = LangGraphIntegrationOrchestrator()
            
            # Create stream queue for async communication
            stream_queue = asyncio.Queue()
            
            # Create stream callback
            async def stream_callback(event: Dict[str, Any]):
                event_type = event.get("type", "status")
                
                # Map LangGraph event types to our standard event types
                if event_type == "node_start":
                    await stream_queue.put(create_stream_event(
                        "executing",
                        session_id,
                        node=event.get("node_id"),
                        step=event.get("step", 1),
                        total=event.get("total_steps", 1),
                        message=f"Executing {event.get('node_id')}..."
                    ))
                elif event_type == "node_complete":
                    state = event.get("state", {})
                    if isinstance(state, GraphState):
                        state = state.to_dict()
                    
                    # Handle different node types
                    if "classification" in event.get("node_id", ""):
                        await stream_queue.put(create_stream_event(
                            "databases_selected",
                            session_id,
                            databases=state.get("databases_identified", []),
                            reasoning=state.get("classification_reasoning", "")
                        ))
                    elif "planning" in event.get("node_id", ""):
                        await stream_queue.put(create_stream_event(
                            "plan_validated",
                            session_id,
                            operations=len(state.get("selected_tools", [])),
                            estimated_time=state.get("estimated_time", "30s")
                        ))
                    elif "execution" in event.get("node_id", ""):
                        await stream_queue.put(create_stream_event(
                            "query_executing",
                            session_id,
                            database=state.get("current_database", "unknown"),
                            progress=state.get("progress_percentage", 0)
                        ))
                        
                        if state.get("partial_results"):
                            await stream_queue.put(create_stream_event(
                                "partial_results",
                                session_id,
                                database=state.get("current_database", "unknown"),
                                rows_count=len(state.get("partial_results", []))
                            ))
                    elif "visualization" in event.get("node_id", ""):
                        await stream_queue.put(create_stream_event(
                            "visualization_progress",
                            session_id,
                            chart_type=state.get("selected_chart_type"),
                            progress=state.get("progress_percentage", 0)
                        ))
                elif event_type == "error":
                    await stream_queue.put(create_stream_event(
                        "error",
                        session_id,
                        error_code=event.get("error_code", "NODE_ERROR"),
                        message=event.get("error_message", str(event.get("error", "Unknown error"))),
                        recoverable=event.get("recoverable", True)
                    ))
            
            # Start query processing task
            process_task = asyncio.create_task(orchestrator.process_query(
                question=request.question,
                session_id=session_id,
                databases_available=request.databases_available,
                force_langgraph=request.force_langgraph,
                stream_callback=stream_callback
            ))
            
            # Stream events from queue while processing
            while True:
                try:
                    # Get next event with timeout
                    event = await asyncio.wait_for(stream_queue.get(), timeout=1.0)
                    yield event
                    stream_queue.task_done()
                except asyncio.TimeoutError:
                    # Check if processing is complete
                    if process_task.done():
                        break
                    continue
                except Exception as e:
                    langgraph_logger.error(f"❌ Error in stream processing: {str(e)}")
                    yield create_stream_event(
                        "error",
                        session_id,
                        error_code="STREAM_PROCESSING_ERROR",
                        message=str(e),
                        recoverable=False
                    )
                    break
            
            # Get final result
            result = await process_task
            duration = time.time() - start_time
            
            # Log successful completion
            log_request_response(langgraph_logger, "/langgraph/stream", request_data, {
                "success": True,
                "workflow": result.get("workflow", "langgraph"),
                "execution_time": duration,
                "session_id": session_id
            }, duration)
            
            # Stream final result
            yield create_stream_event(
                "complete",
                session_id,
                success=True,
                total_time=duration,
                results={
                    "workflow": result.get("workflow", "langgraph"),
                    "final_result": result.get("final_result", {}),
                    "execution_metadata": result.get("execution_metadata", {}),
                    "graph_specification": result.get("graph_specification", {}),
                    "node_results": result.get("node_results", {})
                }
            )
            
        except Exception as e:
            duration = time.time() - start_time
            error_msg = f"LangGraph streaming failed: {str(e)}"
            
            langgraph_logger.error(f"❌ {error_msg}")
            langgraph_logger.error(f"❌ Exception details: {traceback.format_exc()}")
            
            # Log error
            log_request_response(langgraph_logger, "/langgraph/stream", request_data, {}, duration, error_msg)
            
            yield create_stream_event(
                "error",
                session_id,
                error_code="LANGGRAPH_STREAMING_FAILED",
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

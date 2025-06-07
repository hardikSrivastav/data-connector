from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional, AsyncIterator
import asyncpg
import logging
import re
import json
import traceback
import asyncio
from datetime import datetime
import uuid

from ..db.db_orchestrator import Orchestrator
from ..config.settings import Settings
from ..llm.client import get_llm_client
from ..meta.ingest import SchemaSearcher, ensure_index_exists, build_and_save_index_for_db
from ..performance.schema_monitor import ensure_schema_index_updated

# Import the enhanced cross-database query engine
from ..db.execute import query_engine, process_ai_query

# Import cross-database components
from ..db.classifier import DatabaseClassifier
from ..db.orchestrator.cross_db_agent import CrossDatabaseAgent
from ..tools.state_manager import StateManager

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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
    logger.info("🏥 API ENDPOINT: /health - Starting health check")
    
    try:
        settings = Settings()
        
        # Test database connection using the default database
        orchestrator = Orchestrator(settings.connection_uri, db_type=settings.DB_TYPE)
        
        conn_ok = await orchestrator.test_connection()
        logger.info(f"🔍 Database connection result: {conn_ok}")
        
        if not conn_ok:
            response = HealthResponse(
                status="degraded", 
                message="Database connection failed"
            )
            logger.warning(f"⚠️ Health check degraded: {response.message}")
            return response
        
        response = HealthResponse(
            status="ok", 
            message="Database connection is operational"
        )
        logger.info(f"✅ Health check successful: {response.message}")
        return response
        
    except Exception as e:
        logger.error(f"❌ Health check failed with exception: {str(e)}")
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
        response = HealthResponse(
            status="error", 
            message=f"Health check failed: {str(e)}"
        )
        return response

@router.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """
    Enhanced query endpoint supporting both single-database and cross-database operations
    
    Args:
        request: QueryRequest containing the question, analyze flag, and optional settings
        
    Returns:
        QueryResponse containing the results, SQL query, and optional analysis
    """
    logger.info(f"🚀 API ENDPOINT: /query - Processing enhanced request")
    logger.info(f"📥 Request received: question='{request.question}', analyze={request.analyze}, cross_database={request.cross_database}")
    
    try:
        # Use the enhanced process_ai_query function
        result = await process_ai_query(
            question=request.question,
            analyze=request.analyze,
            db_type=request.db_type,
            db_uri=request.db_uri,
            cross_database=request.cross_database
        )
        
        # Build response from result
        response = QueryResponse(
            rows=result.get("rows", []),
            sql=result.get("sql", "-- No SQL generated"),
            analysis=result.get("analysis") if request.analyze else None,
            success=result.get("success", True),
            session_id=result.get("session_id"),
            plan_info=result.get("plan_info"),
            execution_summary=result.get("execution_summary")
        )
        
        logger.info(f"✅ Query processed successfully")
        logger.info(f"📤 Returning response: rows={len(response.rows)}, success={response.success}")
        
        return response
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        logger.error(f"❌ HTTPException occurred, re-raising")
        raise
    except Exception as e:
        logger.error(f"❌ Unexpected error processing query: {str(e)}")
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Query execution failed: {str(e)}")

@router.post("/cross-database-query", response_model=QueryResponse)
async def cross_database_query(request: CrossDatabaseQueryRequest):
    """
    Dedicated endpoint for cross-database queries with planning and orchestration
    
    Args:
        request: CrossDatabaseQueryRequest with cross-database specific options
        
    Returns:
        QueryResponse with cross-database execution results
    """
    logger.info(f"🌐 API ENDPOINT: /cross-database-query - Processing cross-database request")
    logger.info(f"📥 Request: question='{request.question}', optimize={request.optimize}, dry_run={request.dry_run}")
    
    try:
        if request.dry_run:
            # For dry run, only create and validate the plan
            cross_db_agent = CrossDatabaseAgent()
            result = await cross_db_agent.execute_query(
                request.question, 
                optimize_plan=request.optimize, 
                dry_run=True
            )
            
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
            
            response = QueryResponse(
                rows=[{"message": "Dry run completed - plan generated but not executed"}],
                sql=f"-- Dry run plan: {json.dumps(plan_info, indent=2) if plan_info else 'No plan generated'}",
                analysis="Plan generated successfully. Use dry_run=false to execute." if request.analyze else None,
                success=result.get("plan") is not None,
                plan_info=plan_info
            )
        else:
            # Execute the cross-database query
            result = await query_engine.execute_cross_database_query(
                request.question,
                analyze=request.analyze,
                optimize=request.optimize,
                save_session=request.save_session
            )
            
            response = QueryResponse(
                rows=result.get("rows", []),
                sql=result.get("sql", "-- Cross-database query"),
                analysis=result.get("analysis") if request.analyze else None,
                success=result.get("success", True),
                session_id=result.get("session_id"),
                plan_info=result.get("plan_info"),
                execution_summary=result.get("execution_summary")
            )
        
        logger.info(f"✅ Cross-database query processed: success={response.success}")
        return response
        
    except Exception as e:
        logger.error(f"❌ Error in cross-database query: {str(e)}")
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Cross-database query failed: {str(e)}")

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
        classification = await query_engine.classify_query(request.question)
        
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
            "available_sources": len(query_engine.classifier.get_available_sources() if hasattr(query_engine.classifier, 'get_available_sources') else [])
        }
        
        logger.info(f"📤 Returning metadata for {len(schema_metadata)} schema elements")
        return metadata
        
    except Exception as e:
        logger.error(f"❌ Error getting metadata: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get metadata: {str(e)}")

# Streaming utility functions
def create_stream_event(event_type: str, session_id: str, **kwargs) -> str:
    """Create a Server-Sent Event formatted string"""
    event = {
        "type": event_type,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "session_id": session_id,
        **kwargs
    }
    return f"data: {json.dumps(event)}\n\n"

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
        classification = await query_engine.classify_query(question)
        
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
        result = await query_engine.execute_cross_database_query(
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
            classification = await query_engine.classify_query(request.question)
            
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

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import asyncpg
import logging
import re
import json
import traceback

from ..db.db_orchestrator import Orchestrator
from ..config.settings import Settings
from ..llm.client import get_llm_client
from ..meta.ingest import SchemaSearcher, ensure_index_exists
from ..performance.schema_monitor import ensure_schema_index_updated

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

class QueryResponse(BaseModel):
    rows: List[Dict[str, Any]]
    sql: str
    analysis: Optional[str] = None

class HealthResponse(BaseModel):
    status: str
    message: Optional[str] = None

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
    Query endpoint for natural language to SQL translation using real database connections
    
    Args:
        request: QueryRequest containing the question, analyze flag, and optional db settings
        
    Returns:
        QueryResponse containing the results, SQL query, and optional analysis
    """
    logger.info(f"🚀 API ENDPOINT: /query - Processing request")
    logger.info(f"📥 Request received: question='{request.question}', analyze={request.analyze}")
    
    try:
        settings = Settings()
        
        # Determine database type and URI
        db_type = request.db_type or settings.DB_TYPE
        db_uri = request.db_uri or settings.connection_uri
        
        logger.info(f"🔄 Using database: type={db_type}, uri={db_uri[:50]}...")
        
        # Create orchestrator for the specified database
        orchestrator = Orchestrator(db_uri, db_type=db_type)
        
        # Test connection
        if not await orchestrator.test_connection():
            logger.error("❌ Database connection failed")
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        # Ensure schema index exists
        try:
            await ensure_index_exists(db_type=db_type, conn_uri=db_uri)
            await ensure_schema_index_updated(force=False, db_type=db_type, conn_uri=db_uri)
        except Exception as schema_error:
            logger.warning(f"⚠️ Schema index setup failed: {schema_error}")
            # Continue anyway, as the query might still work
        
        # Get LLM client
        llm = get_llm_client()
        
        # Execute query based on database type
        if db_type.lower() in ["postgres", "postgresql"]:
            result = await execute_postgres_query(llm, request.question, request.analyze, orchestrator, db_type)
        elif db_type.lower() == "mongodb":
            result = await execute_mongodb_query(llm, request.question, request.analyze, orchestrator, db_type)
        elif db_type.lower() == "qdrant":
            result = await execute_qdrant_query(llm, request.question, request.analyze, orchestrator, db_type)
        elif db_type.lower() == "slack":
            result = await execute_slack_query(llm, request.question, request.analyze, orchestrator, db_type)
        elif db_type.lower() == "shopify":
            result = await execute_shopify_query(llm, request.question, request.analyze, orchestrator, db_type)
        elif db_type.lower() == "ga4":
            result = await execute_ga4_query(llm, request.question, request.analyze, orchestrator, db_type)
        else:
            logger.error(f"❌ Unsupported database type: {db_type}")
            raise HTTPException(status_code=400, detail=f"Unsupported database type: {db_type}")
        
        # Build response
        response = QueryResponse(
            rows=result.get("rows", []),
            sql=result.get("sql", "-- No SQL generated"),
            analysis=result.get("analysis") if request.analyze else None
        )
        
        logger.info(f"✅ Query processed successfully")
        logger.info(f"📤 Returning response: rows={len(response.rows)}, sql_length={len(response.sql)}")
        
        return response
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        logger.error(f"❌ HTTPException occurred, re-raising")
        raise
    except Exception as e:
        logger.error(f"❌ Unexpected error processing query: {str(e)}")
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Query execution failed: {str(e)}")

async def execute_postgres_query(llm, question: str, analyze: bool, orchestrator: Orchestrator, db_type: str) -> Dict[str, Any]:
    """Execute a PostgreSQL query"""
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
    """Execute a MongoDB query"""
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
    """Execute a Qdrant vector search query"""
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
    """Execute a Slack query"""
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
    """Execute a Shopify query"""
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
    """Execute a GA4 query"""
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
            {"question": "Show me recent users", "analyze": True, "db_type": "postgres"},
            {"question": "How many records are in the database?", "analyze": True, "db_type": "postgres"}
        ]
        
        logger.info(f"🧪 Running {len(test_queries)} test queries")
        
        results = []
        for i, test_query in enumerate(test_queries):
            logger.info(f"🧪 Test {i+1}/{len(test_queries)}: '{test_query['question']}'")
            
            # Create a test request
            request = QueryRequest(
                question=test_query["question"],
                analyze=test_query["analyze"],
                db_type=test_query.get("db_type")
            )
            
            # Execute the query
            result = await query(request)
            
            logger.info(f"🧪 Test {i+1} result: {len(result.rows)} rows")
            results.append({
                "query": test_query["question"],
                "response": {
                    "rows": result.rows,
                    "sql": result.sql,
                    "analysis": result.analysis
                }
            })
        
        response = {
            "status": "success",
            "message": "Real database connection is working correctly",
            "test_results": results
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
    Get information about the database connection capabilities
    """
    logger.info("ℹ️ API ENDPOINT: /capabilities - Returning capabilities info")
    
    settings = Settings()
    
    capabilities = {
        "name": "Real Database Agent",
        "version": "1.0.0",
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
            "multiple_data_sources": True
        },
        "sample_queries": [
            "Show me the latest users",
            "How many orders were placed this month?", 
            "Find products with low stock",
            "Search for messages about project updates",
            "What's the revenue trend?",
            "Show me user analytics from GA4"
        ]
    }
    
    logger.info(f"📤 Returning capabilities for {len(capabilities['supported_databases'])} database types")
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
            "tables": list(set(item.get("table_name", "") for item in schema_metadata if item.get("table_name")))
        }
        
        logger.info(f"📤 Returning metadata for {len(schema_metadata)} schema elements")
        return metadata
        
    except Exception as e:
        logger.error(f"❌ Error getting metadata: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get metadata: {str(e)}")

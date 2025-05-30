from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import asyncpg
import logging
import re
import json
import traceback

from ..db.execute import test_conn, process_ai_query
from ..config.settings import Settings

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Create API router
router = APIRouter()

# Create connection pool
pool: Optional[asyncpg.Pool] = None

# Define request and response models
class QueryRequest(BaseModel):
    question: str
    analyze: bool = False

class QueryResponse(BaseModel):
    rows: List[Dict[str, Any]]
    sql: str
    analysis: Optional[str] = None

class HealthResponse(BaseModel):
    status: str
    message: Optional[str] = None

async def get_db_pool():
    """
    Get database connection pool (dependency)
    """
    global pool
    if pool is None:
        settings = Settings()
        pool = await asyncpg.create_pool(
            dsn=settings.db_dsn,
            min_size=2,
            max_size=10
        )
    return pool

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint - tests database connection and demo LLM client
    """
    logger.info("🏥 API ENDPOINT: /health - Starting health check")
    
    try:
        # Test database connection
        logger.info("🔍 Testing database connection...")
        conn_ok = await test_conn()
        logger.info(f"🔍 Database connection result: {conn_ok}")
        
        if not conn_ok:
            response = HealthResponse(
                status="degraded", 
                message="Database connection failed, but demo LLM client is available"
            )
            logger.warning(f"⚠️ Health check degraded: {response.message}")
            return response
        
        # Test demo LLM client
        logger.info("🤖 Testing demo LLM client...")
        demo_result = await process_ai_query("Hello", analyze=False)
        logger.info(f"🤖 Demo LLM client test result: {type(demo_result)} with keys: {list(demo_result.keys())}")
        
        if not demo_result or "error" in demo_result.get("rows", [{}])[0]:
            response = HealthResponse(
                status="degraded", 
                message="Database OK, but demo LLM client failed"
            )
            logger.warning(f"⚠️ Health check degraded: {response.message}")
            return response
        
        response = HealthResponse(
            status="ok", 
            message="Database and demo LLM client are operational"
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
    Query endpoint for natural language to SQL translation using demo LLM client
    
    Args:
        request: QueryRequest containing the question and analyze flag
        
    Returns:
        QueryResponse containing the results, SQL query, and optional analysis
    """
    logger.info(f"🚀 API ENDPOINT: /query - Processing request")
    logger.info(f"📥 Request received: question='{request.question}', analyze={request.analyze}")
    
    try:
        logger.info(f"🔄 Calling process_ai_query with question='{request.question}', analyze={request.analyze}")
        
        # Use the demo LLM client to process the query
        result = await process_ai_query(request.question, request.analyze)
        
        logger.info(f"🔄 process_ai_query returned: {type(result)}")
        logger.info(f"🔄 Result keys: {list(result.keys())}")
        logger.info(f"🔄 Result structure: rows={len(result.get('rows', []))}, sql={len(result.get('sql', ''))}, analysis={len(result.get('analysis', '')) if result.get('analysis') else 0}")
        
        # Validate the result structure
        if not isinstance(result, dict):
            logger.error(f"❌ Invalid result type: {type(result)}")
            raise HTTPException(status_code=500, detail="Invalid response from demo LLM client")
        
        # Check for errors in the response
        rows = result.get("rows", [])
        logger.info(f"📊 Processing {len(rows)} rows from result")
        
        if rows and isinstance(rows[0], dict) and "error" in rows[0]:
            error_msg = rows[0]["error"]
            logger.error(f"❌ Demo LLM client returned error: {error_msg}")
            raise HTTPException(status_code=500, detail=f"Query processing failed: {error_msg}")
        
        # Build response
        response = QueryResponse(
            rows=result.get("rows", []),
            sql=result.get("sql", "-- No SQL generated"),
            analysis=result.get("analysis") if request.analyze else None
        )
        
        logger.info(f"✅ Query processed successfully")
        logger.info(f"📤 Returning response: rows={len(response.rows)}, sql_length={len(response.sql)}")
        logger.info(f"📤 SQL Query: {response.sql}")
        
        if response.analysis:
            logger.info(f"📤 Analysis length: {len(response.analysis)} characters")
            logger.info(f"📤 Analysis preview: {response.analysis[:100]}...")
        
        # Log sample data for debugging
        if response.rows:
            logger.info(f"📤 Sample row keys: {list(response.rows[0].keys())}")
            logger.info(f"📤 First row preview: {json.dumps(response.rows[0], default=str)[:200]}...")
        
        return response
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        logger.error(f"❌ HTTPException occurred, re-raising")
        raise
    except Exception as e:
        logger.error(f"❌ Unexpected error processing query: {str(e)}")
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Query execution failed: {str(e)}")

@router.get("/test")
async def test_demo_client():
    """
    Test endpoint for the demo LLM client functionality
    """
    logger.info("🧪 API ENDPOINT: /test - Testing demo client")
    
    try:
        test_queries = [
            {"question": "Hello there!", "analyze": False},
            {"question": "Show me recent users", "analyze": True},
            {"question": "How many orders do we have?", "analyze": True}
        ]
        
        logger.info(f"🧪 Running {len(test_queries)} test queries")
        
        results = []
        for i, test_query in enumerate(test_queries):
            logger.info(f"🧪 Test {i+1}/{len(test_queries)}: '{test_query['question']}'")
            result = await process_ai_query(test_query["question"], test_query["analyze"])
            logger.info(f"🧪 Test {i+1} result: {len(result.get('rows', []))} rows, {len(result.get('sql', ''))} char SQL")
            results.append({
                "query": test_query["question"],
                "response": result
            })
        
        response = {
            "status": "success",
            "message": "Demo LLM client is working correctly",
            "test_results": results
        }
        
        logger.info(f"✅ Demo client test completed successfully with {len(results)} results")
        return response
        
    except Exception as e:
        logger.error(f"❌ Demo client test failed: {str(e)}")
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Demo client test failed: {str(e)}")

@router.get("/capabilities")
async def get_capabilities():
    """
    Get information about the demo LLM client capabilities
    """
    logger.info("ℹ️ API ENDPOINT: /capabilities - Returning capabilities info")
    
    capabilities = {
        "name": "Demo LLM Client",
        "version": "1.0.0",
        "capabilities": {
            "natural_language_queries": True,
            "sql_generation": True,
            "data_analysis": True,
            "multiple_data_types": ["users", "orders", "products", "analytics"],
            "query_intents": ["greetings", "data_queries", "analytics", "performance"],
            "supported_patterns": {
                "greetings": ["hello", "hi", "hey"],
                "data_queries": ["show", "list", "find", "get", "fetch"],
                "analytics": ["analyze", "insights", "trends", "statistics"],
                "users": ["user", "customer", "account", "profile"],
                "orders": ["order", "purchase", "sale", "transaction", "revenue"],
                "products": ["product", "item", "inventory", "catalog"]
            }
        },
        "sample_queries": [
            "Hello! What can you help me with?",
            "Show me the latest users",
            "How many orders were placed recently?", 
            "Analyze product performance",
            "Find products with low stock",
            "What's the revenue trend?",
            "Show me user analytics"
        ]
    }
    
    logger.info(f"📤 Returning capabilities: {len(capabilities['capabilities']['sample_queries'])} sample queries")
    return capabilities

@router.get("/metadata")
async def get_metadata():
    """
    Get schema metadata information
    """
    logger.info("📊 API ENDPOINT: /metadata - Returning metadata info")
    
    metadata = {
        "status": "ok", 
        "message": "Demo LLM client provides built-in sample data",
        "available_entities": ["users", "orders", "products", "analytics"],
        "sample_schemas": {
            "users": ["id", "name", "email", "created_at", "last_login"],
            "orders": ["id", "customer_id", "total_amount", "status", "created_at"],
            "products": ["id", "name", "price", "category", "stock_quantity"],
            "analytics": ["metric", "value", "change", "period"]
        }
    }
    
    logger.info(f"📤 Returning metadata for {len(metadata['available_entities'])} entities")
    return metadata

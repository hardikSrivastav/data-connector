from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import asyncpg
import logging
import re

from ..db.execute import test_conn
from ..config.settings import Settings
from ..llm.client import get_llm_client, LLMClient
from ..meta.ingest import SchemaSearcher, ensure_index_exists

# Set up logging
logging.basicConfig(level=logging.INFO)
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

async def get_db_pool() -> asyncpg.Pool:
    """
    Get or create the database connection pool
    """
    global pool
    if pool is None:
        settings = Settings()
        pool = await asyncpg.create_pool(
            dsn=settings.db_dsn,
            min_size=5,
            max_size=20
        )
    return pool

async def get_llm() -> LLMClient:
    """
    Get the LLM client
    """
    return get_llm_client()

def sanitize_sql(sql: str) -> str:
    """
    Sanitize SQL query to ensure it's read-only
    
    Args:
        sql: SQL query to sanitize
        
    Returns:
        Sanitized SQL query
        
    Raises:
        HTTPException: If the query is not read-only
    """
    # Remove SQL comments
    sql = re.sub(r'--.*$', '', sql, flags=re.MULTILINE)
    
    # Check if query is read-only
    if re.search(r'\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE|GRANT|REVOKE)\b', sql, re.IGNORECASE):
        raise HTTPException(status_code=400, detail="Only SELECT queries are allowed")
    
    # Ensure query starts with SELECT
    if not re.search(r'^\s*SELECT\b', sql, re.IGNORECASE):
        raise HTTPException(status_code=400, detail="Query must start with SELECT")
    
    # Add LIMIT if not present
    if not re.search(r'\bLIMIT\b', sql, re.IGNORECASE):
        sql = sql.rstrip(';')
        sql += " LIMIT 1000;"
    
    return sql

@router.get("/health")
async def health_check():
    """
    Health check endpoint
    """
    conn_ok = await test_conn()
    if not conn_ok:
        raise HTTPException(status_code=500, detail="Database connection failed")
    return {"status": "ok"}

@router.post("/query", response_model=QueryResponse)
async def query(
    request: QueryRequest,
    pool = Depends(get_db_pool),
    llm = Depends(get_llm)
):
    """
    Query endpoint for natural language to SQL translation
    
    Args:
        request: QueryRequest containing the question and analyze flag
        pool: Database connection pool
        llm: LLM client
        
    Returns:
        QueryResponse containing the results, SQL query, and optional analysis
    """
    # Ensure FAISS index exists
    if not await ensure_index_exists():
        raise HTTPException(status_code=500, detail="Failed to create schema index")
    
    # Search schema metadata
    searcher = SchemaSearcher()
    schema_chunks = await searcher.search(request.question, top_k=5)
    
    # Render prompt template
    prompt = llm.render_template("nl2sql.tpl", schema_chunks=schema_chunks, user_question=request.question)
    
    # Generate SQL
    sql = await llm.generate_sql(prompt)
    
    # Sanitize SQL
    validated_sql = sanitize_sql(sql)
    
    try:
        # Execute query
        async with pool.acquire() as conn:
            results = await conn.fetch(validated_sql)
            rows = [dict(row) for row in results]
        
        # Convert any non-serializable types to strings
        for row in rows:
            for key, value in row.items():
                if not isinstance(value, (str, int, float, bool, type(None))):
                    row[key] = str(value)
        
        # Build response
        response = {
            "rows": rows,
            "sql": validated_sql
        }
        
        # Add analysis if requested
        if request.analyze:
            analysis = await llm.analyze_results(rows)
            response["analysis"] = analysis
        
        return response
    
    except Exception as e:
        logger.error(f"Error executing query: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Query execution failed: {str(e)}")

@router.get("/metadata")
async def get_metadata():
    """
    Get schema metadata
    """
    # Ensure FAISS index exists
    if not await ensure_index_exists():
        raise HTTPException(status_code=500, detail="Failed to create schema index")
    
    # Return success
    return {"status": "ok", "message": "Schema metadata loaded successfully"}

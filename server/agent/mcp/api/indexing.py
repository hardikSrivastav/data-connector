from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Security
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import logging
import time
from typing import List, Optional, Dict, Any

from ..db.database import get_db
from ..db import crud, models
from ..models.indexing import IndexingStatus, IndexingRequest, SearchQuery, SearchResult
from ..security import verify_jwt_token, JWTData, decode_jwt_token
from ..qdrant_client import get_qdrant_client, initialize_collection
from ..indexer import start_indexing
from qdrant_client.http.models import VectorParams, Distance, CollectionStatus

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter()

# Define API dependencies
security = HTTPBearer(auto_error=False)

def get_optional_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[JWTData]:
    """
    Get the JWT token data if available, but don't require it
    This allows endpoints to accept either token or direct credentials
    """
    if not credentials:
        return None
        
    try:
        token = credentials.credentials
        return decode_jwt_token(token)
    except Exception as e:
        logger.warning(f"Invalid token: {str(e)}")
        return None

@router.get("/test")
async def test_endpoint():
    """Simple test endpoint that requires no auth or DB access"""
    return {"status": "ok", "message": "Test endpoint is working", "time": datetime.now().isoformat()}

@router.get("/status/{workspace_id}", response_model=IndexingStatus)
async def get_status(
    workspace_id: int,
    db: Session = Depends(get_db)
):
    """Get indexing status for a workspace"""
    # For testing: Allow any access (remove token verification for now)
    # Get the status
    status = crud.get_indexing_status(db, workspace_id)
    if not status:
        raise HTTPException(status_code=404, detail="No indexing status found for this workspace")
    
    # Convert to response model
    oldest_date = None
    newest_date = None
    
    if status.oldest_message_ts:
        try:
            ts_float = float(status.oldest_message_ts)
            oldest_date = datetime.fromtimestamp(ts_float)
        except (ValueError, TypeError):
            pass
    
    if status.newest_message_ts:
        try:
            ts_float = float(status.newest_message_ts)
            newest_date = datetime.fromtimestamp(ts_float)
        except (ValueError, TypeError):
            pass
    
    return IndexingStatus(
        workspace_id=status.workspace_id,
        collection_name=status.collection_name,
        last_indexed_at=status.last_indexed_at,
        total_messages=status.total_messages,
        indexed_messages=status.indexed_messages,
        oldest_message_date=oldest_date,
        newest_message_date=newest_date,
        is_indexing=status.is_indexing
    )

@router.post("/run")
async def run_indexing(
    request: IndexingRequest,
    background_tasks: BackgroundTasks,
    token_data: Optional[JWTData] = Depends(get_optional_token),
    db: Session = Depends(get_db)
):
    """
    Start or update message indexing for a workspace
    
    This endpoint accepts either:
    1. JWT token in Authorization header (preferred)
    2. Direct credentials (user_id) in the request body
    """
    # Handle authentication
    user_id = None
    workspace_id = request.workspace_id
    
    # If we have token data, use it
    if token_data:
        user_id = token_data.user_id
        # Verify user has access to workspace
        if token_data.workspace_id != workspace_id:
            raise HTTPException(status_code=403, detail="Access to this workspace is not allowed")
    # Otherwise check for direct credentials in the request
    elif hasattr(request, 'user_id'):
        user_id = request.user_id
    else:
        # No authentication
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Provide token or credentials."
        )
    
    # Get workspace
    workspace = crud.get_workspace(db, workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    # Check if user has access to workspace
    if user_id:
        user_workspace = crud.get_user_workspace(db, user_id, workspace_id)
        if not user_workspace:
            raise HTTPException(
                status_code=403, 
                detail="User does not have access to this workspace"
            )
    
    # Check if workspace has tokens
    if not workspace.bot_token:
        raise HTTPException(status_code=400, detail="Workspace has no bot token - cannot index messages")
    
    # Check if indexing is already configured
    status = crud.get_indexing_status(db, workspace_id)
    
    # If no indexing configured yet, create new configuration
    if not status:
        # Create a unique collection name
        collection_name = f"slack_messages_{workspace.team_id}"
        
        # Create indexing status
        status = crud.create_indexing_status(
            db, 
            workspace_id=workspace_id, 
            collection_name=collection_name
        )
    
    # Ensure the collection exists in Qdrant
    try:
        # Always verify collection exists, whether new or existing
        qdrant_client = get_qdrant_client()
        collections = qdrant_client.get_collections().collections
        collection_names = [c.name for c in collections]
        
        # If collection doesn't exist, create it
        if status.collection_name not in collection_names:
            logger.info(f"Collection {status.collection_name} does not exist, creating it now")
            try:
                # Define vector size for the embedding model
                vector_size = 384  # Default for all-MiniLM-L6-v2
                
                # Create the collection
                qdrant_client.create_collection(
                    collection_name=status.collection_name,
                    vectors_config=VectorParams(
                        size=vector_size,
                        distance=Distance.COSINE
                    )
                )
                
                # Wait for collection to be available
                for i in range(5):
                    try:
                        collection_info = qdrant_client.get_collection(status.collection_name)
                        if collection_info.status == CollectionStatus.GREEN:
                            logger.info(f"Collection {status.collection_name} created successfully")
                            break
                    except Exception as inner_e:
                        logger.warning(f"Waiting for collection to be ready: {str(inner_e)}")
                    time.sleep(1)
            except Exception as create_e:
                logger.error(f"Failed to create collection: {str(create_e)}")
                raise HTTPException(status_code=500, detail=f"Failed to create vector collection: {str(create_e)}")
        else:
            logger.info(f"Collection {status.collection_name} already exists")
    except Exception as e:
        logger.error(f"Error checking/creating collection: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to initialize vector store: {str(e)}")
    
    # Don't start if already indexing
    if status.is_indexing and not request.force_full:
        return JSONResponse(content={
            "status": "already_running",
            "message": "Indexing is already in progress"
        })
    
    # Update status to indicate indexing is starting
    crud.update_indexing_status(
        db, 
        status.id, 
        is_indexing=True,
        updated_at=datetime.utcnow()
    )
    
    # Start indexing in background
    background_tasks.add_task(
        index_workspace_messages,
        workspace_id=workspace_id,
        force_full=request.force_full
    )
    
    return JSONResponse(content={
        "status": "started",
        "message": "Indexing started in the background"
    })

@router.post("/search", response_model=SearchResult)
async def search_messages(
    query: SearchQuery,
    token_data: Optional[JWTData] = Depends(get_optional_token),
    db: Session = Depends(get_db)
):
    """
    Search for messages using vector similarity
    
    This endpoint accepts either:
    1. JWT token in Authorization header (preferred)
    2. Direct credentials (user_id) in the query model
    """
    # Handle authentication
    user_id = None
    workspace_id = query.workspace_id
    
    # If we have token data, use it
    if token_data:
        user_id = token_data.user_id
        # Verify user has access to workspace
        if token_data.workspace_id != workspace_id:
            raise HTTPException(status_code=403, detail="Access to this workspace is not allowed")
    # Otherwise check for direct credentials in the request
    elif hasattr(query, 'user_id'):
        user_id = query.user_id
    else:
        # No authentication
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Provide token or credentials."
        )
    
    # Check if user has access to workspace (if user_id is provided)
    if user_id:
        user_workspace = crud.get_user_workspace(db, user_id, workspace_id)
        if not user_workspace:
            raise HTTPException(
                status_code=403, 
                detail="User does not have access to this workspace"
            )
    
    # Get indexing status to get collection name
    status = crud.get_indexing_status(db, workspace_id)
    if not status:
        raise HTTPException(status_code=404, detail="No index found for this workspace")
    
    # Check if collection exists
    try:
        qdrant_client = get_qdrant_client()
        
        # Build filter based on query parameters
        search_filter = {}
        
        if query.channels:
            search_filter["channel_id"] = {"$in": query.channels}
        
        if query.users:
            search_filter["user_id"] = {"$in": query.users}
        
        # Add date filters if provided
        if query.date_from or query.date_to:
            timestamp_filter = {}
            
            if query.date_from:
                timestamp_filter["$gte"] = query.date_from.timestamp()
            
            if query.date_to:
                timestamp_filter["$lte"] = query.date_to.timestamp()
            
            if timestamp_filter:
                search_filter["ts"] = timestamp_filter
        
        # Perform the search
        start_time = time.time()
        from sentence_transformers import SentenceTransformer
        
        # Get embedding for query
        model = SentenceTransformer(status.embedding_model)
        query_embedding = model.encode(query.query).tolist()
        
        # Search in Qdrant
        search_results = qdrant_client.search(
            collection_name=status.collection_name,
            query_vector=query_embedding,
            limit=query.limit,
            query_filter=search_filter if search_filter else None
        )
        
        # Process results
        messages = []
        for result in search_results:
            # Get the payload
            message_data = result.payload
            
            # Add score from search result
            message_data["score"] = result.score
            
            messages.append(message_data)
        
        # Calculate query time
        query_time_ms = (time.time() - start_time) * 1000
        
        return SearchResult(
            messages=messages,
            total=len(messages),
            query_time_ms=query_time_ms
        )
        
    except Exception as e:
        logger.error(f"Search error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

# Background task for indexing
async def index_workspace_messages(workspace_id: int, force_full: bool = False):
    """
    Background task to index messages from a Slack workspace
    
    Args:
        workspace_id: ID of the workspace to index
        force_full: If True, re-index all messages (within history_days), 
                   otherwise just index new messages
    """
    try:
        # Use the improved start_indexing function
        result = await start_indexing(workspace_id, force_full)
        
        # Log the result
        if result["success"]:
            logger.info(f"Indexing completed successfully for workspace {workspace_id}")
            logger.info(f"Processed {result.get('total_messages', 0)} messages, indexed {result.get('indexed_messages', 0)}")
        else:
            logger.error(f"Indexing failed for workspace {workspace_id}: {result.get('error', 'Unknown error')}")
    except Exception as e:
        logger.exception(f"Unexpected error in indexing: {str(e)}")
        # Make sure indexing status is updated
        db = next(get_db())
        status = crud.get_indexing_status(db, workspace_id)
        if status:
            crud.update_indexing_status(db, status.id, is_indexing=False) 
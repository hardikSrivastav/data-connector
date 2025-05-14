import os
import logging
from typing import Optional, Dict, Any, List
from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.http.models import Distance, VectorParams, PointStruct
from qdrant_client.http.models import CollectionStatus
import time

from .config import settings

# Configure logging
logger = logging.getLogger(__name__)

# Global client instance
_qdrant_client = None

def get_qdrant_client() -> QdrantClient:
    """
    Get or create the Qdrant client
    
    Returns:
        Initialized Qdrant client
    """
    global _qdrant_client
    
    if _qdrant_client is None:
        # Initialize client from settings
        try:
            # In Docker, use the container port (6333) rather than the mapped port (7750)
            # We need to use the container name and internal Docker network
            host = settings.QDRANT_HOST
            port = 6333  # Use the container's internal port
            
            logger.info(f"Connecting to Qdrant at {host}:{port}")
            _qdrant_client = QdrantClient(
                host=host,
                port=port,
                prefer_grpc=settings.QDRANT_PREFER_GRPC,
                timeout=settings.QDRANT_TIMEOUT
            )
            # Test connection
            _qdrant_client.get_collections()
            logger.info(f"Successfully connected to Qdrant at {host}:{port}")
        except Exception as e:
            logger.error(f"Failed to connect to Qdrant: {str(e)}")
            raise
    
    return _qdrant_client

def initialize_collection(client: QdrantClient, collection_name: str):
    """
    Initialize a collection in Qdrant for storing message embeddings
    
    Args:
        client: QdrantClient instance
        collection_name: Name of the collection to create
    """
    try:
        # Check if collection already exists
        collections = client.get_collections().collections
        collection_names = [c.name for c in collections]
        
        if collection_name in collection_names:
            logger.info(f"Collection {collection_name} already exists")
            return
        
        # Create collection with proper schema
        logger.info(f"Creating collection {collection_name}")
        
        # Default to all-MiniLM-L6-v2 which uses 384-dimensional embeddings
        vector_size = 384
        
        # Create collection
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=vector_size,
                distance=Distance.COSINE
            )
        )
        
        # Wait for collection to be created
        max_retries = 5
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                collection_info = client.get_collection(collection_name)
                if collection_info.status == CollectionStatus.GREEN:
                    logger.info(f"Collection {collection_name} created successfully")
                    return
            except Exception as e:
                logger.warning(f"Collection not ready yet: {str(e)}")
            
            # Wait before retrying
            retry_count += 1
            time.sleep(1)
        
        logger.error(f"Collection {collection_name} creation may have failed")
    except Exception as e:
        logger.error(f"Error initializing collection: {str(e)}")
        raise

def store_message_embeddings(
    client: QdrantClient,
    collection_name: str,
    embeddings: List[List[float]],
    payloads: List[Dict[str, Any]]
) -> int:
    """
    Store message embeddings in Qdrant
    
    Args:
        client: QdrantClient instance
        collection_name: Name of the collection
        embeddings: List of embedding vectors
        payloads: List of message payloads
        
    Returns:
        Number of points stored
    """
    if not embeddings or not payloads:
        return 0
    
    if len(embeddings) != len(payloads):
        raise ValueError("Must have same number of embeddings and payloads")
    
    # Create points
    points = []
    for i, (embedding, payload) in enumerate(zip(embeddings, payloads)):
        # Use timestamp as ID to avoid duplicates
        # Convert to int and ensure it's unique by adding index
        ts = payload.get("ts", 0)
        point_id = int(ts * 1000000) + i
        
        points.append(PointStruct(
            id=point_id,
            vector=embedding,
            payload=payload
        ))
    
    # Store in Qdrant
    try:
        logger.info(f"Storing {len(points)} points in collection {collection_name}")
        client.upsert(
            collection_name=collection_name,
            points=points
        )
        logger.info(f"Successfully stored {len(points)} points")
        return len(points)
    except Exception as e:
        logger.error(f"Error storing points: {str(e)}")
        raise

def delete_old_messages(client: QdrantClient, collection_name: str, cutoff_ts: float) -> int:
    """
    Delete messages older than the cutoff timestamp
    
    Args:
        client: QdrantClient instance
        collection_name: Name of the collection
        cutoff_ts: Timestamp to cutoff older messages
        
    Returns:
        Number of points deleted
    """
    try:
        # Check if collection exists
        collections = client.get_collections().collections
        collection_names = [c.name for c in collections]
        
        if collection_name not in collection_names:
            logger.warning(f"Collection {collection_name} does not exist, nothing to delete")
            return 0
        
        # Delete points where ts < cutoff_ts
        logger.info(f"Deleting messages older than {cutoff_ts}")
        result = client.delete(
            collection_name=collection_name,
            filter={
                "ts": {
                    "$lt": cutoff_ts
                }
            }
        )
        
        logger.info(f"Deleted {result.status.deleted} points")
        return result.status.deleted
    except Exception as e:
        logger.error(f"Error deleting points: {str(e)}")
        return 0 
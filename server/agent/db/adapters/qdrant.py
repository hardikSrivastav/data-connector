"""
Qdrant adapter implementation.
Provides Qdrant vector database support through the DBAdapter interface.
"""

import logging
import json
from typing import Any, Dict, List, Optional, Union
from qdrant_client import QdrantClient
from qdrant_client.http.models import Filter, FieldCondition, MatchValue

from .base import DBAdapter
from ...config.settings import Settings

# Configure logging
logger = logging.getLogger(__name__)

class EmbeddingProvider:
    """
    Handles embedding generation for vector search.
    Supports multiple embedding models/providers.
    """
    
    def __init__(self, settings: Settings):
        """
        Initialize the embedding provider.
        
        Args:
            settings: Application settings
        """
        self.settings = settings
        self.provider = settings.VECTOR_EMBEDDING_PROVIDER
        self.model = settings.VECTOR_EMBEDDING_MODEL
        self.dimensions = settings.VECTOR_EMBEDDING_DIMENSIONS
        self.api_key = settings.VECTOR_EMBEDDING_API_KEY
        self.custom_endpoint = settings.VECTOR_EMBEDDING_ENDPOINT
        
    async def get_embedding(self, text: str) -> List[float]:
        """
        Generate an embedding vector for the given text.
        
        Args:
            text: Input text to embed
            
        Returns:
            List of floats representing the embedding vector
        """
        # Use OpenAI embeddings
        if self.provider.lower() == "openai":
            return await self._get_openai_embedding(text)
        
        # Use custom embedding API
        elif self.provider.lower() == "custom":
            return await self._get_custom_embedding(text)
        
        else:
            raise ValueError(f"Unsupported embedding provider: {self.provider}")
    
    async def _get_openai_embedding(self, text: str) -> List[float]:
        """
        Generate an OpenAI embedding.
        
        Args:
            text: Input text
            
        Returns:
            Embedding vector
        """
        try:
            import openai
            
            # Configure OpenAI client
            if self.api_key:
                openai.api_key = self.api_key
            
            # Get embedding
            response = await openai.embeddings.create(
                input=text,
                model=self.model or "text-embedding-ada-002"
            )
            
            # Extract and return the embedding vector
            return response.data[0].embedding
            
        except ImportError:
            logger.error("OpenAI package not installed. Install with: pip install openai")
            raise
        except Exception as e:
            logger.error(f"Error generating OpenAI embedding: {e}")
            raise
    
    async def _get_custom_embedding(self, text: str) -> List[float]:
        """
        Get embedding from custom API endpoint.
        
        Args:
            text: Input text
            
        Returns:
            Embedding vector
        """
        if not self.custom_endpoint:
            raise ValueError("Custom embedding endpoint not configured")
            
        try:
            import aiohttp
            import json
            
            # Prepare request based on configured format
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}" if self.api_key else ""
            }
            
            # Default to JSON request format
            payload = {
                "text": text,
                "model": self.model
            }
            
            # Make the request
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.custom_endpoint,
                    headers=headers,
                    json=payload
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise ValueError(f"Embedding API error ({response.status}): {error_text}")
                        
                    # Parse response
                    response_data = await response.json()
                    
                    # Response field path defaulted to "embedding"
                    embedding_field = self.settings.VECTOR_EMBEDDING_RESPONSE_FIELD or "embedding"
                    
                    # Extract embedding from response based on field path
                    embedding = response_data
                    for key in embedding_field.split("."):
                        embedding = embedding.get(key, {})
                    
                    if not isinstance(embedding, list):
                        raise ValueError(f"Invalid embedding format returned from API: {type(embedding)}")
                        
                    return embedding
                    
        except ImportError:
            logger.error("aiohttp package not installed. Install with: pip install aiohttp")
            raise
        except Exception as e:
            logger.error(f"Error with custom embedding API: {e}")
            raise

class QdrantAdapter(DBAdapter):
    """
    Qdrant vector database adapter implementation.
    
    This adapter provides Qdrant support through the DBAdapter interface,
    focusing on vector similarity search.
    """
    
    def __init__(self, conn_uri: str, **kwargs):
        """
        Initialize the Qdrant adapter.
        
        Args:
            conn_uri: Qdrant connection URI
            **kwargs: Additional parameters
                - api_key: Qdrant API key for cloud deployments (optional)
                - collection_name: Default collection to query (required)
                - prefer_grpc: Whether to use gRPC connection (optional, default: False)
        """
        super().__init__(conn_uri)
        
        # Fix conn_uri if it uses qdrant:// scheme
        if conn_uri.startswith("qdrant://"):
            conn_uri = conn_uri.replace("qdrant://", "http://")
            logger.info(f"Converted qdrant:// scheme to http:// for client: {conn_uri}")
        
        # Initialize settings
        settings = Settings()
        
        # Get collection name with fallbacks:
        # 1. From kwargs
        # 2. From environment variable
        # 3. Default to 'corporate_knowledge' if available
        self.collection_name = kwargs.get('collection_name') or settings.QDRANT_COLLECTION
        
        # If still no collection name, try to get first available collection
        if not self.collection_name:
            try:
                # Initialize temporary client to get collections
                temp_client = QdrantClient(url=conn_uri, api_key=kwargs.get('api_key'))
                collections = temp_client.get_collections().collections
                if collections:
                    self.collection_name = collections[0].name
                    logger.info(f"No collection_name provided, using first available: {self.collection_name}")
            except Exception as e:
                logger.error(f"Error getting collections: {e}")
        
        # If still no collection, raise error
        if not self.collection_name:
            raise ValueError("collection_name is required for Qdrant adapter")
        
        # Optional parameters
        self.api_key = kwargs.get('api_key') or settings.QDRANT_API_KEY
        self.prefer_grpc = kwargs.get('prefer_grpc', settings.QDRANT_PREFER_GRPC)
        
        # Initialize Qdrant client
        self.client = QdrantClient(
            url=conn_uri, 
            api_key=self.api_key,
            prefer_grpc=self.prefer_grpc
        )
        
        # Initialize embedding provider
        self.embedding_provider = EmbeddingProvider(settings)
        
        logger.info(f"Initialized Qdrant adapter for collection: {self.collection_name}")
    
    async def llm_to_query(self, nl_prompt: str, **kwargs) -> Dict:
        """
        Convert natural language to a Qdrant vector search query.
        
        Args:
            nl_prompt: Natural language query
            **kwargs: Additional parameters:
                - top_k: Number of results to return (optional, default: 10)
                - filter_json: Filter to apply (optional)
                - collection: Target collection name (optional)
                
        Returns:
            Dict containing:
                - vector: Query vector
                - top_k: Number of results to return
                - filter: Query filter (optional)
                - collection: Target collection name
        """
        # Get embedding for the query
        vector = await self.embedding_provider.get_embedding(nl_prompt)
        
        # Get parameters
        top_k = kwargs.get('top_k', 10)
        filter_json = kwargs.get('filter_json')
        collection = kwargs.get('collection', self.collection_name)
        
        # Prepare query
        query = {
            "vector": vector,
            "top_k": top_k,
            "collection": collection
        }
        
        # Add filter if provided
        if filter_json:
            query["filter"] = filter_json
        
        return query
    
    async def execute(self, query: Dict) -> List[Dict]:
        """
        Execute a Qdrant search query.
        
        Args:
            query: Dict containing:
                - vector: Query vector
                - top_k: Number of results to return
                - filter: Optional query filter
                - collection: Target collection name
                
        Returns:
            List of dictionaries with search results
        """
        if not isinstance(query, dict):
            raise ValueError("Query must be a dictionary with 'vector' and other fields")
            
        vector = query.get("vector")
        top_k = query.get("top_k", 10)
        filter_json = query.get("filter")
        collection_name = query.get("collection", self.collection_name)
        
        if not vector:
            raise ValueError("Query missing 'vector' field")
        
        # Convert filter_json to Qdrant Filter format if provided
        filter_obj = None
        if filter_json:
            filter_obj = self._parse_filter(filter_json)
        
        # Execute the search
        try:
            search_results = self.client.search(
                collection_name=collection_name,
                query_vector=vector,
                limit=top_k,
                query_filter=filter_obj
            )
            
            # Format results
            results = []
            for hit in search_results:
                # Combine score, id, and payload into one dict
                result = {
                    "id": hit.id,
                    "score": hit.score,
                    **hit.payload
                }
                results.append(result)
                
            return results
            
        except Exception as e:
            logger.error(f"Error executing Qdrant query: {e}")
            raise
            
    async def execute_query(self, query: Dict) -> List[Dict]:
        """
        Execute a Qdrant search query (alias for execute).
        
        This method exists for compatibility with the implementation agent.
        
        Args:
            query: Dict containing:
                - vector: Query vector
                - top_k: Number of results to return
                - filter: Optional query filter
                - collection: Target collection name
                
        Returns:
            List of dictionaries with search results
        """
        return await self.execute(query)
    
    def _parse_filter(self, filter_json: Dict) -> Filter:
        """
        Parse a JSON filter into a Qdrant Filter object.
        
        Args:
            filter_json: Filter as a JSON dict
            
        Returns:
            Qdrant Filter object
        """
        # This is a simplified implementation
        # For a production system, this would need to be more robust
        
        if not filter_json:
            return None
            
        # Simple exact match on a field
        if "exact_match" in filter_json:
            field = filter_json["exact_match"]["field"]
            value = filter_json["exact_match"]["value"]
            return Filter(
                must=[
                    FieldCondition(
                        key=field,
                        match=MatchValue(value=value)
                    )
                ]
            )
            
        # Return as-is if it's already in the correct format
        return filter_json
    
    async def introspect_schema(self) -> List[Dict[str, str]]:
        """
        Introspect Qdrant collections and vector configurations.
        
        Returns:
            List of document dictionaries for embedding
        """
        documents = []
        
        try:
            # Get all collection names using the more flexible list_collections API
            try:
                collections_list = self.client.get_collections().collections
                collection_names = [collection.name for collection in collections_list]
            except Exception as e:
                logger.warning(f"Error using get_collections API, falling back to simplified approach: {e}")
                # Fallback approach if get_collections() API changed
                collection_names = [self.collection_name]
            
            # Process each collection
            for collection_name in collection_names:
                try:
                    # Basic collection info to add regardless of errors
                    content_lines = [f"COLLECTION: {collection_name}"]
                    
                    # Variable to store raw response data
                    data = {}
                    
                    # Try to get collection info using the high-level client API first
                    try:
                        # Get the actual URL from the client's configuration
                        collection_info = self.client.get_collection(collection_name)
                        
                        # Safe access to nested attributes with fallbacks
                        if hasattr(collection_info, 'config') and hasattr(collection_info.config, 'params'):
                            params = collection_info.config.params
                            
                            if hasattr(params, 'vectors'):
                                vectors = params.vectors
                                
                                # Handle new vector configuration format (multiple named vectors)
                                if hasattr(vectors, 'items') and callable(vectors.items):
                                    for vec_name, vec_config in vectors.items():
                                        vec_size = getattr(vec_config, 'size', 'Unknown')
                                        vec_distance = getattr(vec_config, 'distance', 'Unknown')
                                        content_lines.append(f"VECTOR {vec_name} DIMENSIONS: {vec_size}")
                                        content_lines.append(f"VECTOR {vec_name} DISTANCE: {vec_distance}")
                                else:
                                    # Legacy single vector configuration
                                    content_lines.append(f"VECTOR DIMENSIONS: {getattr(vectors, 'size', 'Unknown')}")
                                    content_lines.append(f"VECTOR DISTANCE: {getattr(vectors, 'distance', 'Unknown')}")
                        
                        # Try to access the raw response data if possible
                        if hasattr(collection_info, '_raw_response') and collection_info._raw_response:
                            data = collection_info._raw_response
                            
                    except Exception as high_level_error:
                        logger.warning(f"Error with high-level API for {collection_name}: {high_level_error}")
                        content_lines.append("VECTOR DIMENSIONS: Unknown (error accessing collection info)")
                        content_lines.append("VECTOR DISTANCE: Unknown (error accessing collection info)")
                    
                    # Get payload schema with better error handling
                    try:
                        # Extract schema from the raw response if available
                        schema_dict = {}
                        if data and "result" in data and "payload_schema" in data["result"]:
                            raw_schema = data["result"]["payload_schema"]
                            for field_name, field_info in raw_schema.items():
                                schema_dict[field_name] = {
                                    "type": field_info.get("data_type", "unknown"),
                                    "indexed": field_info.get("indexed", False)
                                }
                        else:
                            # Fall back to using the extraction method
                            schema_dict = self._extract_payload_schema(collection_name)
                        
                        # Format schema as text
                        schema_lines = []
                        for field, schema in schema_dict.items():
                            if field == "error" and "message" in schema:
                                continue  # Skip error messages in the schema
                                
                            field_type = schema.get('type', 'unknown')
                            is_indexed = schema.get('indexed', False)
                            schema_lines.append(f"- {field}: {field_type}" + 
                                            (f" (indexed: {is_indexed})" if is_indexed else ""))
                        
                        schema_text = "\n".join(schema_lines) if schema_lines else "No schema information available"
                        content_lines.append("\nPAYLOAD SCHEMA:")
                        content_lines.append(schema_text)
                    except Exception as schema_error:
                        logger.warning(f"Error extracting schema for {collection_name}: {schema_error}")
                        content_lines.append("\nPAYLOAD SCHEMA: Error retrieving schema information")
                    
                    # Try to get points count
                    try:
                        # Use the standard high-level API
                        count_response = self.client.count(collection_name)
                        points_count = getattr(count_response, 'count', 'Unknown')
                        content_lines.append(f"\nPOINTS COUNT: {points_count}")
                    except Exception as count_error:
                        logger.warning(f"Error getting points count for {collection_name}: {count_error}")
                        content_lines.append("\nPOINTS COUNT: Unknown (error counting points)")
                    
                    # Add collection document
                    documents.append({
                        "id": f"collection:{collection_name}",
                        "content": "\n".join(content_lines).strip()
                    })
                    
                except Exception as coll_error:
                    logger.error(f"Error processing collection {collection_name}: {coll_error}")
                    # Add minimal information for failed collection
                    documents.append({
                        "id": f"collection:{collection_name}",
                        "content": f"COLLECTION: {collection_name}\nERROR: Could not retrieve collection details"
                    })
            
            # If no documents were created, add a placeholder
            if not documents:
                documents.append({
                    "id": "qdrant:info",
                    "content": "Qdrant database with no accessible collections or schema information."
                })
            
            return documents
            
        except Exception as e:
            logger.error(f"Error introspecting Qdrant schema: {e}")
            # Return a minimal document rather than an empty list
            return [{
                "id": "qdrant:error",
                "content": f"Error introspecting Qdrant database: {e}"
            }]
    
    def _extract_payload_schema(self, collection_name: str) -> Dict[str, Dict[str, Any]]:
        """
        Extract payload schema from collection with improved error handling.
        
        Args:
            collection_name: Collection name
            
        Returns:
            Dict of field name to schema info
        """
        schema = {}
        
        try:
            # Get collection info including payload schema
            collection_info = self.client.get_collection(collection_name)
            
            # Try to extract schema from collection info if available
            if hasattr(collection_info, 'config') and hasattr(collection_info.config, 'params'):
                if hasattr(collection_info.config.params, 'payload_schema'):
                    raw_schema = collection_info.config.params.payload_schema
                    if raw_schema:
                        for field_name, field_info in raw_schema.items():
                            schema[field_name] = {
                                "type": getattr(field_info, 'data_type', type(field_info).__name__),
                                "indexed": getattr(field_info, 'indexed', False)
                            }
                        
                        if schema:
                            return schema
            
            # For older Qdrant versions or if schema not available,
            # sample a few points to infer schema
            logger.info(f"No schema information found in collection info for {collection_name}, sampling points to infer schema")
            
            # Use scroll API to get sample points
            try:
                # Try to sample at least 5 points
                scroll_result = self.client.scroll(
                    collection_name=collection_name,
                    limit=5,
                    with_payload=True
                )
                
                # Handle tuple response format (points, next_page_offset)
                if isinstance(scroll_result, tuple):
                    points = scroll_result[0]
                else:
                    points = scroll_result
                
                # Extract fields and their types from the sample points
                for point in points:
                    # Skip points without payload
                    if not hasattr(point, 'payload') or not point.payload:
                        continue
                    
                    # Process each field in the payload
                    for field, value in point.payload.items():
                        # Skip already processed fields
                        if field in schema:
                            continue
                        
                        # Determine the field type
                        field_type = type(value).__name__
                        
                        # Add to schema
                        schema[field] = {
                            "type": field_type,
                            "indexed": False  # We can't determine indexing from sampling
                        }
                
                return schema
                
            except Exception as scroll_error:
                logger.warning(f"Error sampling points: {scroll_error}")
            
            # If we don't have any schema info yet, try a different approach with search
            # This might work with some versions of Qdrant
            if not schema:
                try:
                    # Try searching with an empty query to get sample points
                    search_results = self.client.search(
                        collection_name=collection_name,
                        query_vector=[0.0] * 1536,  # Use default dimension
                        limit=5,
                        with_payload=True
                    )
                    
                    # Process search results to infer schema
                    for hit in search_results:
                        if not hasattr(hit, 'payload') or not hit.payload:
                            continue
                            
                        for field, value in hit.payload.items():
                            if field in schema:
                                continue
                                
                            schema[field] = {
                                "type": type(value).__name__,
                                "indexed": False
                            }
                        
                    return schema
                    
                except Exception as search_error:
                    logger.warning(f"Error using search to infer schema: {search_error}")
            
            return schema or {"unknown": {"type": "unknown"}}
            
        except Exception as e:
            logger.error(f"Error extracting payload schema: {e}")
            return {"error": {"type": "error", "message": str(e)}}
    
    async def test_connection(self) -> bool:
        """
        Test the Qdrant connection.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Try to get collection list first - this is the basic test
            collections_response = self.client.get_collections()
            
            # If we can get collections, that's enough to consider the connection working
            if hasattr(collections_response, 'collections'):
                logger.info(f"Connected to Qdrant - Found collections: {[c.name for c in collections_response.collections]}")
                
                # Do a basic check if our collection exists
                collection_names = [c.name for c in collections_response.collections]
                if self.collection_name in collection_names:
                    logger.info(f"Collection '{self.collection_name}' exists")
                    return True
                else:
                    logger.warning(f"Collection '{self.collection_name}' does not exist")
                    return False
            
            return True
        except Exception as e:
            logger.error(f"Qdrant connection test failed: {e}")
            return False 
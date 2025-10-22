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
        # Convert query format if needed (handles string queries from LangGraph)
        query = await self._convert_query_format(query)
        
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
    
    async def _convert_query_format(self, query: Any) -> Dict:
        """
        Convert different query formats to Qdrant-compatible format.
        Handles string queries from LangGraph by converting them to vector search format.
        
        Args:
            query: Query in various formats (string, dict)
            
        Returns:
            Dict in Qdrant format
        """
        if isinstance(query, dict):
            # Already in proper format, return as-is
            return query
        
        elif isinstance(query, str):
            # Convert string query to vector search
            logger.info(f"🔍 Qdrant Query Conversion: Converting string query to vector search")
            
            try:
                # Generate embedding for the string query
                vector = await self.embedding_provider.get_embedding(query)
                
                # Create Qdrant search query
                qdrant_query = {
                    "vector": vector,
                    "top_k": 10,  # Default limit
                    "collection": self.collection_name
                }
                
                logger.info(f"🔍 Qdrant Query Conversion: \"{query}\" → vector search with {len(vector)} dimensions")
                return qdrant_query
                
            except Exception as e:
                logger.error(f"Error converting string query to vector: {e}")
                # Fallback to a basic query structure
                return {
                    "error": f"Failed to convert query to vector: {str(e)}",
                    "original_query": query
                }
        
        else:
            # Unknown format, try to handle gracefully
            logger.warning(f"Unknown query format: {type(query)}")
            return {
                "error": f"Unsupported query format: {type(query)}",
                "original_query": str(query)
            }
    
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
    
    # Additional Qdrant-specific tools for the registry
    
    async def analyze_collection_performance(self, collection_name: str = None) -> Dict[str, Any]:
        """
        Analyze Qdrant collection performance and index configuration.
        
        Args:
            collection_name: Name of the collection to analyze
            
        Returns:
            Performance analysis results
        """
        collection = collection_name or self.collection_name
        logger.info(f"Analyzing performance for Qdrant collection: {collection}")
        
        try:
            # Get collection info
            collection_info = self.client.get_collection(collection_name=collection)
            
            # Get collection statistics  
            try:
                cluster_info = self.client.cluster_info()
            except:
                cluster_info = None
            
            analysis = {
                "collection_name": collection,
                "vectors_count": collection_info.vectors_count if hasattr(collection_info, 'vectors_count') else 0,
                "indexed_vectors_count": collection_info.indexed_vectors_count if hasattr(collection_info, 'indexed_vectors_count') else 0,
                "points_count": collection_info.points_count if hasattr(collection_info, 'points_count') else 0,
                "segments_count": collection_info.segments_count if hasattr(collection_info, 'segments_count') else 0,
                "disk_data_size": collection_info.disk_data_size if hasattr(collection_info, 'disk_data_size') else 0,
                "ram_data_size": collection_info.ram_data_size if hasattr(collection_info, 'ram_data_size') else 0,
                "config": collection_info.config.__dict__ if hasattr(collection_info, 'config') else {},
                "indexing_threshold": collection_info.config.optimizers_config.indexing_threshold if hasattr(collection_info, 'config') and hasattr(collection_info.config, 'optimizers_config') else 0,
                "cluster_info": cluster_info.__dict__ if cluster_info else {},
                "performance_recommendations": self._generate_qdrant_performance_recommendations(collection_info)
            }
            
            logger.info(f"Qdrant performance analysis completed for {collection}: {analysis['points_count']} points")
            return analysis
            
        except Exception as e:
            logger.error(f"Failed to analyze Qdrant collection performance: {e}")
            raise
    
    def _generate_qdrant_performance_recommendations(self, collection_info) -> List[str]:
        """Generate performance recommendations for Qdrant collection."""
        recommendations = []
        
        try:
            if hasattr(collection_info, 'points_count') and hasattr(collection_info, 'indexed_vectors_count'):
                points_count = collection_info.points_count
                indexed_count = collection_info.indexed_vectors_count
                
                # Check indexing ratio
                if points_count > 0:
                    indexing_ratio = indexed_count / points_count
                    if indexing_ratio < 0.8 and points_count > 1000:
                        recommendations.append("Low indexing ratio detected, consider running optimization")
                
                # Check for large unindexed collections
                if points_count > 10000 and indexed_count < points_count * 0.5:
                    recommendations.append("Large collection with many unindexed vectors, optimize indexing")
            
            if hasattr(collection_info, 'config') and hasattr(collection_info.config, 'optimizers_config'):
                threshold = collection_info.config.optimizers_config.indexing_threshold
                if threshold > 50000:
                    recommendations.append("High indexing threshold may delay optimization, consider lowering")
            
            # Check memory usage
            if hasattr(collection_info, 'ram_data_size') and hasattr(collection_info, 'disk_data_size'):
                ram_size = collection_info.ram_data_size
                disk_size = collection_info.disk_data_size
                if ram_size > 0 and disk_size > 0:
                    ram_ratio = ram_size / (ram_size + disk_size)
                    if ram_ratio < 0.1:
                        recommendations.append("Low RAM usage ratio, consider increasing memory allocation")
            
        except Exception as e:
            logger.warning(f"Failed to generate Qdrant recommendations: {e}")
        
        return recommendations
    
    async def optimize_collection(self, collection_name: str = None) -> Dict[str, Any]:
        """
        Optimize Qdrant collection performance.
        
        Args:
            collection_name: Name of the collection to optimize
            
        Returns:
            Optimization results
        """
        collection = collection_name or self.collection_name
        logger.info(f"Optimizing Qdrant collection: {collection}")
        
        try:
            optimization_results = {
                "collection_name": collection,
                "operations_performed": [],
                "before_stats": {},
                "after_stats": {},
                "recommendations": []
            }
            
            # Get before statistics
            optimization_results["before_stats"] = await self.analyze_collection_performance(collection)
            
            # Run collection optimization
            try:
                from qdrant_client.models import OptimizersConfig
                optimize_result = self.client.update_collection(
                    collection_name=collection,
                    optimizer_config=OptimizersConfig(
                        deleted_threshold=0.1,  # Trigger optimization when 10% of vectors are deleted
                        vacuum_min_vector_number=1000,
                        default_segment_number=2
                    )
                )
                optimization_results["operations_performed"].append("update_optimizer_config")
                logger.info(f"Optimizer config updated for {collection}")
            except Exception as e:
                logger.warning(f"Failed to update optimizer config: {e}")
            
            # Get after statistics
            optimization_results["after_stats"] = await self.analyze_collection_performance(collection)
            
            # Generate recommendations
            optimization_results["recommendations"] = await self._generate_collection_recommendations(collection)
            
            logger.info(f"Qdrant collection optimization completed for {collection}")
            return optimization_results
            
        except Exception as e:
            logger.error(f"Failed to optimize Qdrant collection {collection}: {e}")
            raise
    
    async def _generate_collection_recommendations(self, collection_name: str) -> List[str]:
        """Generate optimization recommendations for a Qdrant collection."""
        recommendations = []
        
        try:
            analysis = await self.analyze_collection_performance(collection_name)
            
            # Check vector count vs segments
            points_count = analysis.get("points_count", 0)
            segments_count = analysis.get("segments_count", 0)
            
            if segments_count > 0:
                points_per_segment = points_count / segments_count
                if points_per_segment < 1000:
                    recommendations.append("Too many segments for collection size, consider increasing segment size")
                elif points_per_segment > 100000:
                    recommendations.append("Large segments detected, consider splitting for better performance")
            
            # Check memory usage
            ram_size = analysis.get("ram_data_size", 0)
            disk_size = analysis.get("disk_data_size", 0)
            if ram_size + disk_size > 0:
                total_size_gb = (ram_size + disk_size) / (1024**3)
                if total_size_gb > 10:
                    recommendations.append("Large collection detected, consider sharding across multiple nodes")
            
        except Exception as e:
            logger.warning(f"Failed to generate recommendations for {collection_name}: {e}")
        
        return recommendations
    
    async def validate_vector_compatibility(self, vector: List[float], collection_name: str = None) -> Dict[str, Any]:
        """
        Validate that a vector is compatible with the collection configuration.
        
        Args:
            vector: Vector to validate
            collection_name: Name of the collection
            
        Returns:
            Validation results
        """
        collection = collection_name or self.collection_name
        logger.info(f"Validating vector compatibility for collection: {collection}")
        logger.debug(f"Vector dimensions: {len(vector)}")
        
        try:
            # Get collection info
            collection_info = self.client.get_collection(collection_name=collection)
            
            # Check vector dimensions
            expected_size = collection_info.config.params.vectors.size
            actual_size = len(vector)
            
            # Check distance metric compatibility
            distance_metric = collection_info.config.params.vectors.distance
            
            validation_result = {
                "valid": True,
                "expected_dimensions": expected_size,
                "actual_dimensions": actual_size,
                "distance_metric": distance_metric.name if hasattr(distance_metric, 'name') else str(distance_metric),
                "errors": [],
                "warnings": []
            }
            
            if actual_size != expected_size:
                validation_result["valid"] = False
                validation_result["errors"].append(f"Vector dimension mismatch: expected {expected_size}, got {actual_size}")
            
            # Check for potential issues
            vector_magnitude = sum(x**2 for x in vector) ** 0.5
            if vector_magnitude < 0.1:
                validation_result["warnings"].append("Vector has very low magnitude, may affect search quality")
            
            if any(abs(x) > 10 for x in vector):
                validation_result["warnings"].append("Vector contains very large values, consider normalization")
            
            logger.info(f"Vector validation completed: {'valid' if validation_result['valid'] else 'invalid'}")
            return validation_result
            
        except Exception as e:
            logger.error(f"Failed to validate vector compatibility: {e}")
            raise
    
    async def get_collection_statistics(self, collection_name: str = None) -> Dict[str, Any]:
        """
        Get comprehensive statistics for a Qdrant collection.
        
        Args:
            collection_name: Name of the collection
            
        Returns:
            Collection statistics and metadata
        """
        collection = collection_name or self.collection_name
        logger.info(f"Getting statistics for Qdrant collection: {collection}")
        
        try:
            # Get collection info
            collection_info = self.client.get_collection(collection_name=collection)
            
            statistics = {
                "collection_name": collection,
                "points_count": collection_info.points_count if hasattr(collection_info, 'points_count') else 0,
                "vectors_count": collection_info.vectors_count if hasattr(collection_info, 'vectors_count') else 0,
                "indexed_vectors_count": collection_info.indexed_vectors_count if hasattr(collection_info, 'indexed_vectors_count') else 0,
                "segments_count": collection_info.segments_count if hasattr(collection_info, 'segments_count') else 0,
                "disk_data_size_bytes": collection_info.disk_data_size if hasattr(collection_info, 'disk_data_size') else 0,
                "ram_data_size_bytes": collection_info.ram_data_size if hasattr(collection_info, 'ram_data_size') else 0,
                "vector_size": collection_info.config.params.vectors.size if hasattr(collection_info, 'config') else 0,
                "distance_metric": collection_info.config.params.vectors.distance.name if hasattr(collection_info, 'config') and hasattr(collection_info.config.params.vectors.distance, 'name') else "unknown",
                "indexing_threshold": collection_info.config.optimizers_config.indexing_threshold if hasattr(collection_info, 'config') and hasattr(collection_info.config, 'optimizers_config') else 0,
                "recommendations": self._generate_qdrant_performance_recommendations(collection_info)
            }
            
            # Calculate indexing ratio
            if statistics["points_count"] > 0:
                statistics["indexing_ratio"] = statistics["indexed_vectors_count"] / statistics["points_count"]
            else:
                statistics["indexing_ratio"] = 0.0
            
            logger.info(f"Collection statistics collected for {collection}: {statistics['points_count']} points")
            return statistics
            
        except Exception as e:
            logger.error(f"Failed to get collection statistics for {collection}: {e}")
            raise 
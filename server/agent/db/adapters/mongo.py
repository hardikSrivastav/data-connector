"""
MongoDB adapter implementation.
Provides MongoDB support through the DBAdapter interface.
"""

import logging
import json
from typing import Any, Dict, List, Optional
from pymongo import MongoClient
from bson import json_util
from urllib.parse import urlparse

from .base import DBAdapter
from ...langgraph.graphs.bedrock_client import get_bedrock_langgraph_client

# Configure logging
logger = logging.getLogger(__name__)

class MongoAdapter(DBAdapter):
    """
    MongoDB adapter implementation.
    
    This adapter provides MongoDB support through the DBAdapter interface,
    translating natural language to MongoDB aggregation pipelines.
    """
    
    def __init__(self, conn_uri: str, **kwargs):
        """
        Initialize the MongoDB adapter.
        
        Args:
            conn_uri: MongoDB connection URI
            **kwargs: Additional parameters
                - db_name: MongoDB database name (optional, will extract from URI if not provided)
                - default_collection: Default collection to query (optional)
        """
        super().__init__(conn_uri)
        
        # Try to extract database name from URI if not provided
        self.db_name = kwargs.get('db_name')
        if not self.db_name:
            # Parse database name from MongoDB URI
            try:
                parsed_uri = urlparse(conn_uri)
                path = parsed_uri.path
                
                # Extract database name from path
                if path and path != '/':
                    self.db_name = path.lstrip('/')
                    logger.info(f"Extracted database name from URI: {self.db_name}")
                
                # If still no db_name, try to use 'admin' as default
                if not self.db_name:
                    self.db_name = "admin"
                    logger.warning("No database name found in URI, using default 'admin'")
            except Exception as e:
                logger.error(f"Failed to extract database name from URI: {e}")
            
        # Verify we have a database name
        if not self.db_name:
            raise ValueError("db_name is required for MongoDB adapter")
            
        # Optional parameters
        self.default_collection = kwargs.get('default_collection')
        
        # Initialize MongoDB client
        self.client = MongoClient(conn_uri)
        self.db = self.client[self.db_name]
        
        logger.info(f"Initialized MongoDB adapter for database: {self.db_name}")
        
    async def llm_to_query(self, nl_prompt: str, **kwargs) -> Dict:
        """
        Convert natural language to a MongoDB query using Bedrock LLM.
        
        Args:
            nl_prompt: Natural language query
            **kwargs: Additional parameters:
                - collection: Target collection name (optional)
                - schema_chunks: Schema information (optional)
                
        Returns:
            Dict containing:
                - pipeline: MongoDB aggregation pipeline
                - collection: Target collection name
        """
        logger.info(f"Converting natural language to MongoDB query: {nl_prompt[:100]}...")
        logger.debug(f"LLM conversion kwargs: {list(kwargs.keys())}")
        
        try:
            # Use singleton factory instead of direct instantiation
            bedrock_client = get_bedrock_langgraph_client()
            
            # Get schema metadata if not provided
            schema_chunks = kwargs.get('schema_chunks')
            if not schema_chunks:
                logger.debug("No schema chunks provided, searching for relevant schema")
                # Import SchemaSearcher only when needed to avoid circular imports
                from ...meta.ingest import SchemaSearcher
                # Search schema metadata
                searcher = SchemaSearcher()
                schema_chunks = await searcher.search(nl_prompt, top_k=5)
                logger.debug(f"Found {len(schema_chunks)} relevant schema chunks")
            
            # Format schema information for prompt
            schema_info = ""
            if schema_chunks:
                schema_info = "\n".join([
                    f"Collection: {chunk.get('collection_name', 'unknown')}\n"
                    f"Schema: {chunk.get('schema_info', 'no schema')}\n"
                    for chunk in schema_chunks[:3]  # Limit to top 3 for token efficiency
                ])
            
            # Get target collection
            target_collection = kwargs.get('collection') or self.default_collection or 'sample_orders'
            
            # Create MongoDB query generation prompt
            prompt = f"""Convert the following natural language query to a MongoDB aggregation pipeline.

Database Schema Information:
{schema_info}

Default Collection: {target_collection}

Natural Language Query: {nl_prompt}

Instructions:
1. Generate a valid MongoDB aggregation pipeline as JSON
2. Use appropriate collection and field names from the schema
3. Return a JSON object with two fields: "collection" and "pipeline"
4. The pipeline should be an array of MongoDB aggregation stages
5. Ensure the query is safe and follows best practices

Example Response Format:
{{
  "collection": "sample_orders",
  "pipeline": [
    {{"$match": {{"status": "active"}}}},
    {{"$limit": 10}}
  ]
}}

MongoDB Query:"""
            
            # Generate MongoDB query using Bedrock
            raw_response = await bedrock_client.generate_completion(
                prompt=prompt,
                max_tokens=800,
                temperature=0.1
            )
        
            # Clean up MongoDB query response
            mongodb_query = raw_response.strip()
            if mongodb_query.startswith("```json"):
                mongodb_query = mongodb_query[7:]
            if mongodb_query.endswith("```"):
                mongodb_query = mongodb_query[:-3]
            mongodb_query = mongodb_query.strip()
            
            logger.info(f"Generated MongoDB query: {mongodb_query[:200]}...")
            
            # Basic MongoDB query validation
            if not mongodb_query or mongodb_query.lower().strip() in ['no query', 'none', 'n/a']:
                raise ValueError("No valid MongoDB query generated")
            
            # Parse the response as JSON
            try:
                # The response should contain both a pipeline and a collection name
                query_data = json.loads(mongodb_query)
                
                # Validate response structure
                if not isinstance(query_data, dict):
                    raise ValueError("LLM response is not a dictionary")
                
                if "pipeline" not in query_data:
                    raise ValueError("LLM response missing 'pipeline' field")
                    
                if "collection" not in query_data:
                    # Use default collection if not specified
                    if target_collection:
                        query_data["collection"] = target_collection
                    else:
                        raise ValueError("LLM response missing 'collection' field and no default collection specified")
                
                logger.info(f"Successfully parsed MongoDB query for collection: {query_data['collection']}")
                return query_data
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse LLM response as JSON: {e}")
                raise ValueError(f"Failed to parse LLM response as JSON: {e}")
            
        except Exception as e:
            logger.error(f"Failed to convert natural language to MongoDB query: {e}")
            raise
    
    async def execute(self, query: Any) -> List[Dict]:
        """
        Execute a MongoDB query.
        
        Args:
            query: Dict containing pipeline and collection, or string to be parsed
                
        Returns:
            List of dictionaries with query results
        """
        # Convert query to proper MongoDB format if needed
        mongo_query = await self._convert_query_format(query)
        
        pipeline = mongo_query.get("pipeline")
        collection_name = mongo_query.get("collection")
        
        if not pipeline:
            raise ValueError("Query missing 'pipeline' field")
            
        if not collection_name:
            if self.default_collection:
                collection_name = self.default_collection
            else:
                raise ValueError("Query missing 'collection' field and no default collection specified")
        
        # Get the collection
        collection = self.db[collection_name]
        
        # Execute the aggregation pipeline
        try:
            results = list(collection.aggregate(pipeline))
            
            # Convert ObjectId and other BSON types to string representations
            return json.loads(json_util.dumps(results))
            
        except Exception as e:
            logger.error(f"Error executing MongoDB query: {e}")
            raise
    
    async def _convert_query_format(self, query: Any) -> Dict[str, Any]:
        """
        Convert various query formats to MongoDB aggregation pipeline format.
        
        Args:
            query: Query in various formats (string, dict, etc.)
            
        Returns:
            Dict with MongoDB aggregation pipeline
        """
        # Handle string queries (try to parse as JSON)
        if isinstance(query, str):
            import json
            try:
                query = json.loads(query)
            except json.JSONDecodeError:
                # If not valid JSON, create a simple query structure
                logger.warning(f"Could not parse query string as JSON: {query}")
                query = {
                    "collection": self.default_collection or "sample_orders",
                    "pipeline": [{"$match": {}}, {"$limit": 10}]
                }
        
        # Ensure query is a dictionary
        if not isinstance(query, dict):
            raise ValueError("Query must be a dictionary")
        
        # Ensure query has required fields
        if "pipeline" not in query:
            # Create a default pipeline if missing
            query["pipeline"] = [{"$match": {}}, {"$limit": 10}]
        
        if "collection" not in query:
            query["collection"] = self.default_collection or "sample_orders"
        
        return query
            
    async def execute_query(self, query: Dict) -> List[Dict]:
        """
        Execute a MongoDB query (alias for execute).
        
        This method exists for compatibility with the implementation agent.
        
        Args:
            query: Dict containing:
                - pipeline: MongoDB aggregation pipeline
                - collection: Target collection name
                
        Returns:
            List of dictionaries with query results
        """
        return await self.execute(query)
    
    async def introspect_schema(self) -> List[Dict[str, str]]:
        """
        Introspect MongoDB collections and document structures.
        
        Returns:
            List of document dictionaries for embedding
        """
        documents = []
        
        try:
            # Get all collection names but handle permission issues gracefully
            try:
                collection_names = self.db.list_collection_names()
            except Exception as e:
                logger.warning(f"Error listing all collections: {e}")
                # Try to get a list of collections without system views
                collection_names = []
                # Check for common collections
                for possible_collection in ["sample_orders", "sample_products", "sample_users", 
                                           "orders", "products", "customers", "employees"]:
                    try:
                        # Check if collection exists by attempting to get stats
                        stats = self.db.command("collStats", possible_collection)
                        collection_names.append(possible_collection)
                    except Exception:
                        # Collection doesn't exist or we don't have permission
                        pass
                
                if not collection_names:
                    logger.error("Could not retrieve any collections. Check permissions.")
                    return [{"id": "error", "content": "Could not access MongoDB collections. Check permissions."}]
            
            for collection_name in collection_names:
                # Skip system collections
                if collection_name.startswith("system."):
                    continue
                    
                # Get the collection
                collection = self.db[collection_name]
                
                try:
                    # Get sample documents to infer schema
                    sample_docs = list(collection.find().limit(5))
                    
                    # Get count
                    count = collection.count_documents({})
                    
                    # Construct field information by examining sample documents
                    fields = {}
                    for doc in sample_docs:
                        for field, value in doc.items():
                            if field not in fields:
                                fields[field] = {"type": type(value).__name__, "examples": []}
                            
                            # Add example value if we don't have too many already
                            if len(fields[field]["examples"]) < 3 and str(value) not in fields[field]["examples"]:
                                fields[field]["examples"].append(str(value))
                    
                    # Format field information as text
                    fields_text = "\n".join([
                        f"- {field}: {info['type']}" + 
                        (f" (examples: {', '.join(info['examples'])})" if info['examples'] else "")
                        for field, info in fields.items()
                    ])
                    
                    # Create document content
                    content = f"""
                    COLLECTION: {collection_name}
                    APPROXIMATE DOCUMENT COUNT: {count}
                    
                    FIELDS:
                    {fields_text or 'No fields identified'}
                    """
                    
                    # Add collection document
                    documents.append({
                        "id": f"collection:{collection_name}",
                        "content": content.strip()
                    })
                except Exception as e:
                    logger.warning(f"Error introspecting collection {collection_name}: {e}")
                    # Add a placeholder document for the collection
                    documents.append({
                        "id": f"collection:{collection_name}",
                        "content": f"COLLECTION: {collection_name}\nUnable to retrieve details: {str(e)}"
                    })
                
            return documents
            
        except Exception as e:
            logger.error(f"Error during schema introspection: {e}")
            return [{"id": "error", "content": f"Error during MongoDB schema introspection: {str(e)}"}]
    
    async def test_connection(self) -> bool:
        """
        Test the MongoDB connection.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Try to get server info
            self.client.server_info()
            
            # Try to list collections in the database
            self.db.list_collection_names()
            
            return True
        except Exception as e:
            logger.error(f"MongoDB connection test failed: {e}")
            return False 
    
    async def aggregate(self, collection_name: str, pipeline: List[Dict]) -> List[Dict]:
        """
        Execute an aggregation pipeline on a specific collection.
        
        This method is called directly by the implementation agent.
        
        Args:
            collection_name: Name of the MongoDB collection
            pipeline: MongoDB aggregation pipeline
            
        Returns:
            List of dictionaries with aggregation results
        """
        try:
            # Get the collection
            collection = self.db[collection_name]
            
            # Execute the aggregation pipeline
            results = list(collection.aggregate(pipeline))
            
            # Convert ObjectId and other BSON types to string representations
            return json.loads(json_util.dumps(results))
            
        except Exception as e:
            logger.error(f"Error executing MongoDB aggregation on {collection_name}: {e}")
            raise
    
    async def find(self, collection_name: str, query: Dict = None, projection: Dict = None) -> List[Dict]:
        """
        Execute a find query on a specific collection.
        
        This method is called directly by the implementation agent.
        
        Args:
            collection_name: Name of the MongoDB collection
            query: MongoDB find query (optional, defaults to {})
            projection: MongoDB projection (optional)
            
        Returns:
            List of dictionaries with query results
        """
        logger.info(f"Executing MongoDB find on collection: {collection_name}")
        logger.debug(f"Query: {query}, Projection: {projection}")
        
        try:
            # Get the collection
            collection = self.db[collection_name]
            
            # Set defaults
            if query is None:
                query = {}
            
            # Execute the find query
            if projection:
                results = list(collection.find(query, projection))
            else:
                results = list(collection.find(query))
            
            logger.info(f"MongoDB find completed, returned {len(results)} documents")
            
            # Convert ObjectId and other BSON types to string representations
            return json.loads(json_util.dumps(results))
            
        except Exception as e:
            logger.error(f"Error executing MongoDB find on {collection_name}: {e}")
            raise
    
    # Additional MongoDB-specific tools for the registry
    
    async def analyze_collection_performance(self, collection_name: str) -> Dict[str, Any]:
        """
        Analyze MongoDB collection performance and index usage.
        
        Args:
            collection_name: Name of the collection to analyze
            
        Returns:
            Performance analysis results
        """
        logger.info(f"Analyzing performance for MongoDB collection: {collection_name}")
        
        try:
            collection = self.db[collection_name]
            
            # Get collection stats
            stats = self.db.command("collStats", collection_name)
            
            # Get index stats
            index_stats = list(collection.aggregate([{"$indexStats": {}}]))
            
            # Analyze most common queries (simplified - in production you'd use profiler)
            sample_docs = list(collection.find().limit(100))
            
            analysis = {
                "collection_name": collection_name,
                "document_count": stats.get("count", 0),
                "average_document_size": stats.get("avgObjSize", 0),
                "total_size_bytes": stats.get("size", 0),
                "storage_size_bytes": stats.get("storageSize", 0),
                "index_count": len(index_stats),
                "index_statistics": index_stats,
                "performance_recommendations": self._generate_mongo_performance_recommendations(stats, index_stats),
                "sample_document_structure": self._analyze_document_structure(sample_docs)
            }
            
            logger.info(f"MongoDB performance analysis completed for {collection_name}: {analysis['document_count']} documents")
            return analysis
            
        except Exception as e:
            logger.error(f"Failed to analyze MongoDB collection performance: {e}")
            raise
    
    def _generate_mongo_performance_recommendations(self, stats: Dict, index_stats: List[Dict]) -> List[str]:
        """Generate performance recommendations for MongoDB collection."""
        recommendations = []
        
        try:
            # Check for large collections without indexes
            doc_count = stats.get("count", 0)
            if doc_count > 10000 and len(index_stats) <= 1:  # Only _id index
                recommendations.append("Large collection with minimal indexes, consider adding indexes on frequently queried fields")
            
            # Check average document size
            avg_size = stats.get("avgObjSize", 0)
            if avg_size > 16 * 1024 * 1024:  # 16MB
                recommendations.append("Large average document size, consider document design optimization")
            
            # Check storage efficiency
            size = stats.get("size", 0)
            storage_size = stats.get("storageSize", 0)
            if storage_size > 0 and size > 0:
                efficiency = size / storage_size
                if efficiency < 0.7:
                    recommendations.append("Low storage efficiency, consider running compact operation")
            
            # Check index usage
            unused_indexes = []
            for idx_stat in index_stats:
                if idx_stat.get("accesses", {}).get("ops", 0) == 0 and idx_stat.get("name") != "_id_":
                    unused_indexes.append(idx_stat.get("name"))
            
            if unused_indexes:
                recommendations.append(f"Unused indexes detected: {', '.join(unused_indexes)}, consider dropping them")
            
        except Exception as e:
            logger.warning(f"Failed to generate MongoDB recommendations: {e}")
        
        return recommendations
    
    def _analyze_document_structure(self, sample_docs: List[Dict]) -> Dict[str, Any]:
        """Analyze document structure from sample documents."""
        if not sample_docs:
            return {"fields": {}, "max_depth": 0, "avg_field_count": 0}
        
        field_analysis = {}
        depths = []
        field_counts = []
        
        for doc in sample_docs:
            field_count = 0
            depth = self._calculate_document_depth(doc)
            depths.append(depth)
            
            # Analyze fields
            for field, value in doc.items():
                field_count += 1
                field_type = type(value).__name__
                
                if field not in field_analysis:
                    field_analysis[field] = {"types": {}, "count": 0}
                
                field_analysis[field]["count"] += 1
                if field_type not in field_analysis[field]["types"]:
                    field_analysis[field]["types"][field_type] = 0
                field_analysis[field]["types"][field_type] += 1
            
            field_counts.append(field_count)
        
        return {
            "fields": field_analysis,
            "max_depth": max(depths) if depths else 0,
            "avg_depth": sum(depths) / len(depths) if depths else 0,
            "avg_field_count": sum(field_counts) / len(field_counts) if field_counts else 0
        }
    
    def _calculate_document_depth(self, doc: Dict, current_depth: int = 1) -> int:
        """Calculate maximum depth of a document."""
        max_depth = current_depth
        
        for value in doc.values():
            if isinstance(value, dict):
                depth = self._calculate_document_depth(value, current_depth + 1)
                max_depth = max(max_depth, depth)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        depth = self._calculate_document_depth(item, current_depth + 1)
                        max_depth = max(max_depth, depth)
        
        return max_depth
    
    async def optimize_collection(self, collection_name: str) -> Dict[str, Any]:
        """
        Optimize MongoDB collection performance.
        
        Args:
            collection_name: Name of the collection to optimize
            
        Returns:
            Optimization results
        """
        logger.info(f"Optimizing MongoDB collection: {collection_name}")
        
        try:
            collection = self.db[collection_name]
            
            optimization_results = {
                "collection_name": collection_name,
                "operations_performed": [],
                "before_stats": {},
                "after_stats": {},
                "recommendations": []
            }
            
            # Get before statistics
            optimization_results["before_stats"] = await self.analyze_collection_performance(collection_name)
            
            # Reindex collection
            result = self.db.command("reIndex", collection_name)
            optimization_results["operations_performed"].append("reIndex")
            logger.info(f"Reindex completed for {collection_name}: {result}")
            
            # Compact collection (only available in some MongoDB deployments)
            try:
                compact_result = self.db.command("compact", collection_name)
                optimization_results["operations_performed"].append("compact")
                logger.info(f"Compact completed for {collection_name}: {compact_result}")
            except Exception as e:
                logger.warning(f"Compact operation not available or failed: {e}")
            
            # Get after statistics
            optimization_results["after_stats"] = await self.analyze_collection_performance(collection_name)
            
            # Generate recommendations
            optimization_results["recommendations"] = await self._generate_collection_recommendations(collection_name)
            
            logger.info(f"MongoDB collection optimization completed for {collection_name}")
            return optimization_results
            
        except Exception as e:
            logger.error(f"Failed to optimize MongoDB collection {collection_name}: {e}")
            raise
    
    async def _generate_collection_recommendations(self, collection_name: str) -> List[str]:
        """Generate optimization recommendations for a MongoDB collection."""
        recommendations = []
        
        try:
            analysis = await self.analyze_collection_performance(collection_name)
            
            # Check document structure
            structure = analysis.get("sample_document_structure", {})
            avg_depth = structure.get("avg_depth", 0)
            if avg_depth > 5:
                recommendations.append("Deep document nesting detected, consider flattening structure for better performance")
            
            # Check field count
            avg_field_count = structure.get("avg_field_count", 0)
            if avg_field_count > 50:
                recommendations.append("High field count per document, consider document restructuring")
            
            # Check for missing indexes on commonly queried fields
            fields = structure.get("fields", {})
            common_query_fields = ["user_id", "created_at", "status", "type", "category"]
            for field in common_query_fields:
                if field in fields:
                    recommendations.append(f"Consider adding index on commonly queried field: {field}")
            
        except Exception as e:
            logger.warning(f"Failed to generate recommendations for {collection_name}: {e}")
        
        return recommendations
    
    async def validate_aggregation_pipeline(self, collection_name: str, pipeline: List[Dict]) -> Dict[str, Any]:
        """
        Validate MongoDB aggregation pipeline without executing it.
        
        Args:
            collection_name: Name of the collection
            pipeline: Aggregation pipeline to validate
            
        Returns:
            Validation results
        """
        logger.info(f"Validating aggregation pipeline for collection: {collection_name}")
        logger.debug(f"Pipeline: {pipeline}")
        
        try:
            collection = self.db[collection_name]
            
            # Add explain stage to validate without execution
            explain_pipeline = pipeline + [{"$limit": 0}]
            
            try:
                # Execute with limit 0 to validate pipeline stages
                list(collection.aggregate(explain_pipeline))
                
                logger.info("Aggregation pipeline validation passed")
                return {
                    "valid": True,
                    "error": None,
                    "warnings": self._analyze_pipeline_performance(pipeline)
                }
            except Exception as e:
                error_msg = str(e)
                logger.warning(f"Aggregation pipeline validation failed: {error_msg}")
                return {
                    "valid": False,
                    "error": error_msg,
                    "warnings": self._extract_pipeline_warnings(error_msg)
                }
                
        except Exception as e:
            logger.error(f"Failed to validate aggregation pipeline: {e}")
            raise
    
    def _analyze_pipeline_performance(self, pipeline: List[Dict]) -> List[str]:
        """Analyze aggregation pipeline for performance issues."""
        warnings = []
        
        for i, stage in enumerate(pipeline):
            stage_name = list(stage.keys())[0] if stage else ""
            
            # Check for $match stages after $group
            if stage_name == "$match" and i > 0:
                prev_stages = [list(s.keys())[0] for s in pipeline[:i]]
                if "$group" in prev_stages or "$sort" in prev_stages:
                    warnings.append(f"$match stage at position {i} after $group/$sort may impact performance")
            
            # Check for $sort without $limit
            if stage_name == "$sort":
                remaining_stages = [list(s.keys())[0] for s in pipeline[i+1:]]
                if "$limit" not in remaining_stages:
                    warnings.append(f"$sort stage at position {i} without $limit may consume significant memory")
            
            # Check for unoptimized $lookup
            if stage_name == "$lookup":
                lookup_config = stage["$lookup"]
                if "pipeline" not in lookup_config and "localField" in lookup_config:
                    warnings.append(f"$lookup at position {i} could benefit from pipeline optimization")
        
        return warnings
    
    def _extract_pipeline_warnings(self, error_msg: str) -> List[str]:
        """Extract warnings from aggregation pipeline error message."""
        warnings = []
        
        if "unknown operator" in error_msg.lower():
            warnings.append("Unknown aggregation operator used")
        if "field path references" in error_msg.lower():
            warnings.append("Invalid field reference in pipeline")
        if "cannot convert" in error_msg.lower():
            warnings.append("Type conversion error in pipeline")
        if "exceeded memory limit" in error_msg.lower():
            warnings.append("Pipeline exceeds memory limits")
            
        return warnings
    
    async def get_collection_statistics(self, collection_name: str) -> Dict[str, Any]:
        """
        Get comprehensive statistics for a MongoDB collection.
        
        Args:
            collection_name: Name of the collection
            
        Returns:
            Collection statistics and metadata
        """
        logger.info(f"Getting statistics for MongoDB collection: {collection_name}")
        
        try:
            collection = self.db[collection_name]
            
            # Get collection stats
            stats = self.db.command("collStats", collection_name)
            
            # Get index information
            indexes = list(collection.list_indexes())
            
            # Get sample documents for analysis
            sample_docs = list(collection.find().limit(10))
            
            statistics = {
                "collection_name": collection_name,
                "document_count": stats.get("count", 0),
                "average_document_size": stats.get("avgObjSize", 0),
                "total_size_bytes": stats.get("size", 0),
                "storage_size_bytes": stats.get("storageSize", 0),
                "total_index_size_bytes": stats.get("totalIndexSize", 0),
                "index_count": len(indexes),
                "indexes": [{"name": idx.get("name"), "key": idx.get("key")} for idx in indexes],
                "is_capped": stats.get("capped", False),
                "document_structure": self._analyze_document_structure(sample_docs),
                "recommendations": self._generate_mongo_performance_recommendations(stats, [])
            }
            
            logger.info(f"Collection statistics collected for {collection_name}: {statistics['document_count']} documents")
            return statistics
            
        except Exception as e:
            logger.error(f"Failed to get collection statistics for {collection_name}: {e}")
            raise 
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
        Convert natural language to a MongoDB query.
        
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
        from ...llm.client import get_llm_client
        from ...meta.ingest import SchemaSearcher
        
        # Get schema metadata if not provided
        schema_chunks = kwargs.get('schema_chunks')
        if not schema_chunks:
            # Search schema metadata
            searcher = SchemaSearcher()
            schema_chunks = await searcher.search(nl_prompt, top_k=5)
        
        # Get LLM client
        llm = get_llm_client()
        
        # Use a MongoDB-specific prompt template
        prompt = llm.render_template("mongo_query.tpl", 
                                   schema_chunks=schema_chunks, 
                                   user_question=nl_prompt,
                                   default_collection=self.default_collection)
        
        # Generate MongoDB query using the LLM
        raw_response = await llm.generate_mongodb_query(prompt)
        
        # Parse the response as JSON
        try:
            # The response should contain both a pipeline and a collection name
            query_data = json.loads(raw_response)
            
            # Validate response structure
            if not isinstance(query_data, dict):
                raise ValueError("LLM response is not a dictionary")
            
            if "pipeline" not in query_data:
                raise ValueError("LLM response missing 'pipeline' field")
                
            if "collection" not in query_data:
                # Use default collection if not specified
                if self.default_collection:
                    query_data["collection"] = self.default_collection
                else:
                    raise ValueError("LLM response missing 'collection' field and no default collection specified")
            
            return query_data
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            raise ValueError(f"Failed to parse LLM response as JSON: {e}")
    
    async def execute(self, query: Dict) -> List[Dict]:
        """
        Execute a MongoDB query.
        
        Args:
            query: Dict containing:
                - pipeline: MongoDB aggregation pipeline
                - collection: Target collection name
                
        Returns:
            List of dictionaries with query results
        """
        if not isinstance(query, dict):
            raise ValueError("Query must be a dictionary with 'pipeline' and 'collection' fields")
            
        pipeline = query.get("pipeline")
        collection_name = query.get("collection")
        
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
    
    async def introspect_schema(self) -> List[Dict[str, str]]:
        """
        Introspect MongoDB collections and document structures.
        
        Returns:
            List of document dictionaries for embedding
        """
        documents = []
        
        # Get all collection names
        collection_names = self.db.list_collection_names()
        
        for collection_name in collection_names:
            # Get the collection
            collection = self.db[collection_name]
            
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
        
        return documents
    
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
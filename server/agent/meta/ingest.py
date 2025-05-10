import os
import json
import asyncio
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
import faiss
from ..db.introspect import get_schema_metadata
from ..config.settings import Settings
import logging
from pathlib import Path
from urllib.parse import urlparse

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
EMBEDDING_DIMENSION = 1536  # Default dimension for OpenAI embeddings

class SchemaEmbedder:
    """Class for embedding schema metadata and creating a FAISS index"""
    
    def __init__(self, db_type: str = "postgres"):
        """
        Initialize the embedder for a specific database type
        
        Args:
            db_type: Type of database ('postgres', 'mongodb', etc.)
        """
        self.settings = Settings()
        self.documents = []
        self.metadata = []
        self.db_type = db_type.lower()
    
    @property
    def index_file_path(self) -> str:
        """Get the path to the FAISS index file for this database type"""
        return os.path.join(os.path.dirname(__file__), f"index_{self.db_type}.faiss")
    
    @property
    def metadata_file_path(self) -> str:
        """Get the path to the metadata file for this database type"""
        return os.path.join(os.path.dirname(__file__), f"metadata_{self.db_type}.json")
    
    async def fetch_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Fetch embeddings for a list of texts using the configured LLM API
        
        This is a placeholder - in a real implementation, you would:
        1. Use OpenAI embeddings API if LLM_API_URL is set to OpenAI
        2. Use a local embedding model if MODEL_PATH is set
        
        Args:
            texts: List of text strings to embed
            
        Returns:
            List of embedding vectors (list of floats)
        """
        # For demonstration purposes, return random embeddings of correct dimension
        # In a real implementation, this would call the embedding API
        logger.info(f"Generating embeddings for {len(texts)} texts")
        
        if self.settings.LLM_API_URL and self.settings.LLM_API_KEY:
            # Here you would implement the call to your embedding API
            # For example with OpenAI:
            # import openai
            # openai.api_key = self.settings.LLM_API_KEY
            # response = openai.Embedding.create(input=texts, model="text-embedding-ada-002")
            # return [item.embedding for item in response.data]
            pass
        
        # For now, return random embeddings (placeholder)
        return [np.random.uniform(-1, 1, EMBEDDING_DIMENSION).tolist() for _ in texts]
    
    async def build_index(self, conn_uri: Optional[str] = None, **kwargs) -> Tuple[Any, List[Dict[str, Any]]]:
        """
        Build a FAISS index from schema metadata
        
        Args:
            conn_uri: Optional connection URI for the database
            **kwargs: Additional parameters for the database connection
            
        Returns:
            Tuple containing (FAISS index, metadata list)
        """
        # Fetch schema metadata for the specified database
        logger.info(f"Fetching schema metadata for {self.db_type}")
        self.documents = await get_schema_metadata(conn_uri, **kwargs)
        
        # Add database type to document IDs for clarity
        for doc in self.documents:
            # Only add prefix if not already present
            if not doc["id"].startswith(f"{self.db_type}:"):
                doc["id"] = f"{self.db_type}:{doc['id']}"
        
        # Extract texts for embedding
        texts = [doc["content"] for doc in self.documents]
        ids = [doc["id"] for doc in self.documents]
        
        # Get embeddings
        embeddings = await self.fetch_embeddings(texts)
        
        # Convert to numpy array for FAISS
        embeddings_np = np.array(embeddings).astype('float32')
        
        # Create FAISS index
        logger.info(f"Creating FAISS index for {self.db_type}")
        index = faiss.IndexFlatL2(EMBEDDING_DIMENSION)
        
        # Add vectors to the index
        index.add(embeddings_np)
        
        # Create metadata
        self.metadata = [
            {
                "id": doc["id"],
                "content": doc["content"],
                "embedding_id": i,
                "db_type": self.db_type
            }
            for i, doc in enumerate(self.documents)
        ]
        
        return index, self.metadata
    
    async def save_index(self, index: Any, metadata: List[Dict[str, Any]]) -> None:
        """
        Save FAISS index and metadata to disk
        
        Args:
            index: FAISS index
            metadata: List of document metadata
        """
        # Save FAISS index
        logger.info(f"Saving FAISS index to {self.index_file_path}")
        faiss.write_index(index, self.index_file_path)
        
        # Save metadata
        logger.info(f"Saving metadata to {self.metadata_file_path}")
        with open(self.metadata_file_path, 'w') as f:
            json.dump(metadata, f)

class SchemaSearcher:
    """Class for searching schema metadata using FAISS"""
    
    def __init__(self, db_type: Optional[str] = None):
        """
        Initialize the schema searcher.
        
        Args:
            db_type: Optional database type to restrict search to.
                    If None, will attempt to search all available indexes.
        """
        self.db_type = db_type.lower() if db_type else None
        self.indexes = {}  # Dict mapping db_type to loaded FAISS index
        self.metadata = {}  # Dict mapping db_type to metadata
        self.loaded_types = set()  # Set of loaded db types
    
    def get_db_types(self) -> List[str]:
        """
        Get a list of all database types with available indexes
        
        Returns:
            List of database type strings
        """
        # Look for index_*.faiss files in the meta directory
        index_files = list(Path(os.path.dirname(__file__)).glob("index_*.faiss"))
        return [f.stem.replace("index_", "") for f in index_files]
    
    def load_indexes(self) -> bool:
        """
        Load all available FAISS indexes and metadata.
        If db_type is specified in constructor, only load that index.
        
        Returns:
            True if at least one index was loaded, False otherwise
        """
        if self.db_type:
            # Only load the specified database type
            db_types = [self.db_type]
        else:
            # Load all available database types
            db_types = self.get_db_types()
        
        if not db_types:
            logger.warning("No database indexes found")
            return False
        
        for db_type in db_types:
            if self.load_index_for_type(db_type):
                self.loaded_types.add(db_type)
        
        return len(self.loaded_types) > 0
    
    def load_index_for_type(self, db_type: str) -> bool:
        """
        Load the FAISS index and metadata for a specific database type
        
        Args:
            db_type: Database type to load
            
        Returns:
            True if loading was successful, False otherwise
        """
        index_path = os.path.join(os.path.dirname(__file__), f"index_{db_type}.faiss")
        metadata_path = os.path.join(os.path.dirname(__file__), f"metadata_{db_type}.json")
        
        try:
            # Check if files exist
            if not os.path.exists(index_path) or not os.path.exists(metadata_path):
                logger.warning(f"Index or metadata files don't exist for {db_type}")
                return False
            
            # Load FAISS index
            logger.info(f"Loading FAISS index from {index_path}")
            self.indexes[db_type] = faiss.read_index(index_path)
            
            # Load metadata
            logger.info(f"Loading metadata from {metadata_path}")
            with open(metadata_path, 'r') as f:
                self.metadata[db_type] = json.load(f)
            
            return True
        except Exception as e:
            logger.error(f"Error loading index for {db_type}: {str(e)}")
            return False
    
    async def search(self, query: str, top_k: int = 5, db_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Search for schema metadata matching the query
        
        Args:
            query: Search query
            top_k: Number of results to return
            db_type: Optional database type to search in. Overrides the instance db_type.
            
        Returns:
            List of metadata for matching documents
        """
        # Determine which database type(s) to search
        search_db_type = db_type or self.db_type
        
        # Load indexes if they haven't been loaded yet
        if not self.loaded_types:
            if not self.load_indexes():
                logger.error("Failed to load indexes for search")
                return []
        
        # Get embedding for query
        embedder = SchemaEmbedder()
        query_embedding = await embedder.fetch_embeddings([query])
        query_embedding_np = np.array(query_embedding).astype('float32')
        
        all_results = []
        
        # Search in the specified database type(s)
        if search_db_type:
            if search_db_type in self.indexes:
                # Search in the specific database type
                results = self._search_in_db_type(search_db_type, query_embedding_np, top_k)
                all_results.extend(results)
            else:
                logger.warning(f"No index loaded for database type: {search_db_type}")
        else:
            # Search in all loaded database types
            for db_type in self.loaded_types:
                # Get top_k/2 results from each database to ensure diversity
                # But ensure at least 1 result per database
                per_db_top_k = max(1, top_k // len(self.loaded_types))
                results = self._search_in_db_type(db_type, query_embedding_np, per_db_top_k)
                all_results.extend(results)
        
        # Sort all results by distance
        all_results.sort(key=lambda x: x["distance"])
        
        # Return the top k results
        return all_results[:top_k]
    
    def _search_in_db_type(self, db_type: str, query_embedding_np: np.ndarray, top_k: int) -> List[Dict[str, Any]]:
        """
        Search in a specific database type's index
        
        Args:
            db_type: Database type to search in
            query_embedding_np: Query embedding as numpy array
            top_k: Number of results to return
            
        Returns:
            List of metadata for matching documents
        """
        # Search FAISS index
        distances, indices = self.indexes[db_type].search(query_embedding_np, top_k)
        
        # Get metadata for matching documents
        results = []
        for i, idx in enumerate(indices[0]):
            if idx < len(self.metadata[db_type]):
                result = self.metadata[db_type][idx].copy()
                result["distance"] = float(distances[0][i])
                result["db_type"] = db_type  # Add database type to result
                results.append(result)
        
        return results

async def build_and_save_index_for_db(db_type: str, conn_uri: Optional[str] = None, **kwargs) -> bool:
    """
    Build and save FAISS index for a specific database type
    
    Args:
        db_type: Database type ('postgres', 'mongodb', etc.)
        conn_uri: Optional connection URI
        **kwargs: Additional database connection parameters
        
    Returns:
        True if successful, False otherwise
    """
    try:
        embedder = SchemaEmbedder(db_type=db_type)
        index, metadata = await embedder.build_index(conn_uri, **kwargs)
        await embedder.save_index(index, metadata)
        return True
    except Exception as e:
        logger.error(f"Error building index for {db_type}: {str(e)}")
        return False

async def ensure_index_exists(db_type: Optional[str] = None, conn_uri: Optional[str] = None, **kwargs) -> bool:
    """
    Ensure that the FAISS index exists for the specified database type, building it if necessary
    
    Args:
        db_type: Optional database type. If None, uses the type from conn_uri or settings.
        conn_uri: Optional connection URI. If None, uses default from settings.
        **kwargs: Additional database connection parameters
        
    Returns:
        True if index exists or was successfully built, False otherwise
    """
    settings = Settings()
    
    # Determine database type
    if not db_type:
        if conn_uri:
            db_type = urlparse(conn_uri).scheme
        else:
            # Get from settings
            uri = settings.connection_uri
            db_type = urlparse(uri).scheme
    
    # Fall back to PostgreSQL if detection fails
    if not db_type:
        db_type = "postgres"
    
    # Normalize database type
    db_type = db_type.lower()
    
    # Check if index exists
    searcher = SchemaSearcher(db_type=db_type)
    if searcher.load_index_for_type(db_type):
        logger.info(f"FAISS index for {db_type} loaded successfully")
        return True
    
    # Build new index
    logger.info(f"Building new FAISS index for {db_type}")
    return await build_and_save_index_for_db(db_type, conn_uri, **kwargs)

if __name__ == "__main__":
    async def main():
        # Build indexes for all supported database types
        db_types = ["postgres", "mongodb"]
        
        for db_type in db_types:
            logger.info(f"Ensuring index exists for {db_type}")
            if await ensure_index_exists(db_type=db_type):
                print(f"Index for {db_type} is ready")
        
        # Test combined search
        searcher = SchemaSearcher()
        results = await searcher.search("users who made purchases")
        
        print("\nSearch results:")
        for result in results:
            print(f"\n=== {result['db_type']}: {result['id']} (distance: {result['distance']:.4f}) ===")
            print(result['content'])
            print("="*50)
    
    asyncio.run(main())

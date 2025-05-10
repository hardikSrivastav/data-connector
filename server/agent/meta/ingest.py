import os
import json
import asyncio
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
import faiss
from ..db.introspect import get_schema_metadata
from ..config.settings import Settings
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
EMBEDDING_DIMENSION = 1536  # Default dimension for OpenAI embeddings
FAISS_INDEX_FILE = os.path.join(os.path.dirname(__file__), "index.faiss")
METADATA_FILE = os.path.join(os.path.dirname(__file__), "metadata.json")

class SchemaEmbedder:
    """Class for embedding schema metadata and creating a FAISS index"""
    
    def __init__(self):
        self.settings = Settings()
        self.documents = []
        self.metadata = []
    
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
    
    async def build_index(self) -> Tuple[Any, List[Dict[str, Any]]]:
        """
        Build a FAISS index from schema metadata
        
        Returns:
            Tuple containing (FAISS index, metadata list)
        """
        # Fetch schema metadata
        logger.info("Fetching schema metadata")
        self.documents = await get_schema_metadata()
        
        # Extract texts for embedding
        texts = [doc["content"] for doc in self.documents]
        ids = [doc["id"] for doc in self.documents]
        
        # Get embeddings
        embeddings = await self.fetch_embeddings(texts)
        
        # Convert to numpy array for FAISS
        embeddings_np = np.array(embeddings).astype('float32')
        
        # Create FAISS index
        logger.info("Creating FAISS index")
        index = faiss.IndexFlatL2(EMBEDDING_DIMENSION)
        
        # Add vectors to the index
        index.add(embeddings_np)
        
        # Create metadata
        self.metadata = [
            {
                "id": doc["id"],
                "content": doc["content"],
                "embedding_id": i
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
        logger.info(f"Saving FAISS index to {FAISS_INDEX_FILE}")
        faiss.write_index(index, FAISS_INDEX_FILE)
        
        # Save metadata
        logger.info(f"Saving metadata to {METADATA_FILE}")
        with open(METADATA_FILE, 'w') as f:
            json.dump(metadata, f)

class SchemaSearcher:
    """Class for searching schema metadata using FAISS"""
    
    def __init__(self):
        self.index = None
        self.metadata = []
        self.loaded = False
    
    def load_index(self) -> bool:
        """
        Load FAISS index and metadata from disk
        
        Returns:
            True if loading was successful, False otherwise
        """
        try:
            # Check if files exist
            if not os.path.exists(FAISS_INDEX_FILE) or not os.path.exists(METADATA_FILE):
                logger.warning("Index or metadata files don't exist")
                return False
            
            # Load FAISS index
            logger.info(f"Loading FAISS index from {FAISS_INDEX_FILE}")
            self.index = faiss.read_index(FAISS_INDEX_FILE)
            
            # Load metadata
            logger.info(f"Loading metadata from {METADATA_FILE}")
            with open(METADATA_FILE, 'r') as f:
                self.metadata = json.load(f)
            
            self.loaded = True
            return True
        except Exception as e:
            logger.error(f"Error loading index: {str(e)}")
            return False
    
    async def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Search for schema metadata matching the query
        
        Args:
            query: Search query
            top_k: Number of results to return
            
        Returns:
            List of metadata for matching documents
        """
        if not self.loaded:
            if not self.load_index():
                logger.error("Failed to load index for search")
                return []
        
        # Get embedding for query
        embedder = SchemaEmbedder()
        query_embedding = await embedder.fetch_embeddings([query])
        query_embedding_np = np.array(query_embedding).astype('float32')
        
        # Search FAISS index
        distances, indices = self.index.search(query_embedding_np, top_k)
        
        # Get metadata for matching documents
        results = []
        for i, idx in enumerate(indices[0]):
            if idx < len(self.metadata):
                result = self.metadata[idx].copy()
                result["distance"] = float(distances[0][i])
                results.append(result)
        
        return results

async def build_and_save_index() -> bool:
    """
    Build and save FAISS index from schema metadata
    
    Returns:
        True if successful, False otherwise
    """
    try:
        embedder = SchemaEmbedder()
        index, metadata = await embedder.build_index()
        await embedder.save_index(index, metadata)
        return True
    except Exception as e:
        logger.error(f"Error building index: {str(e)}")
        return False

async def ensure_index_exists() -> bool:
    """
    Ensure that the FAISS index exists, building it if necessary
    
    Returns:
        True if index exists or was successfully built, False otherwise
    """
    searcher = SchemaSearcher()
    if searcher.load_index():
        logger.info("FAISS index loaded successfully")
        return True
    
    logger.info("Building new FAISS index")
    return await build_and_save_index()

if __name__ == "__main__":
    async def main():
        if await ensure_index_exists():
            print("Index is ready")
            
            # Test search
            searcher = SchemaSearcher()
            results = await searcher.search("users who made purchases")
            
            print("\nSearch results:")
            for result in results:
                print(f"\n=== {result['id']} (distance: {result['distance']:.4f}) ===")
                print(result['content'])
                print("="*50)
        else:
            print("Failed to create index")
    
    asyncio.run(main())

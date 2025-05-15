#!/usr/bin/env python3
import asyncio
import logging
import json
import sys
from pathlib import Path

# Add parent directory to path to import registry
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agent.db.registry import (
    init_registry,
    list_data_sources,
    get_data_source,
    upsert_data_source,
    list_tables,
    upsert_table_meta,
    get_table_schema,
    set_ontology_mapping,
    list_ontology_entities
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_registry():
    """Test the schema registry functionality"""
    
    # Initialize the registry
    logger.info("Initializing schema registry...")
    init_registry()
    
    # Add test data sources
    logger.info("Adding test data sources...")
    upsert_data_source(
        "test_postgres", 
        "postgresql://user:pass@localhost:5432/testdb", 
        "postgres",
        "1.0.0"
    )
    
    upsert_data_source(
        "test_mongodb", 
        "mongodb://user:pass@localhost:27017/testdb", 
        "mongodb",
        "1.0.0"
    )
    
    upsert_data_source(
        "test_qdrant",
        "http://localhost:6333",
        "qdrant",
        "1.0.0"
    )
    
    # List data sources
    sources = list_data_sources()
    logger.info(f"Data sources: {json.dumps(sources, indent=2)}")
    
    # Add test table metadata
    logger.info("Adding test table metadata...")
    
    # Postgres table
    upsert_table_meta(
        "test_postgres",
        "customers",
        {
            "fields": {
                "id": {"data_type": "integer", "primary_key": True, "nullable": False},
                "name": {"data_type": "varchar", "nullable": False},
                "email": {"data_type": "varchar", "nullable": True},
                "created_at": {"data_type": "timestamp", "nullable": False}
            }
        },
        "1.0.0"
    )
    
    # MongoDB collection
    upsert_table_meta(
        "test_mongodb",
        "users",
        {
            "fields": {
                "_id": {"data_type": "objectid", "primary_key": True},
                "username": {"data_type": "string"},
                "email": {"data_type": "string"},
                "profile": {"data_type": "object"}
            }
        },
        "1.0.0"
    )
    
    # Qdrant collection
    upsert_table_meta(
        "test_qdrant",
        "documents",
        {
            "fields": {
                "vector_main": {"data_type": "vector", "dimensions": "1536", "distance": "Cosine"},
                "id": {"data_type": "keyword", "indexed": True},
                "content": {"data_type": "text", "indexed": False},
                "metadata": {"data_type": "object", "indexed": False},
                "points_count": {"data_type": "integer", "value": "1024"}
            }
        },
        "1.0.0"
    )
    
    # List tables for each source
    for source_id in ["test_postgres", "test_mongodb", "test_qdrant"]:
        tables = list_tables(source_id)
        logger.info(f"Tables in {source_id}: {tables}")
        
        # Get schema for each table
        for table in tables:
            schema = get_table_schema(source_id, table)
            logger.info(f"Schema for {source_id}.{table}: {json.dumps(schema, indent=2)}")
    
    # Test ontology mapping
    logger.info("Testing ontology mapping...")
    
    # Map customer entity to customers table
    set_ontology_mapping("customer", "test_postgres.customers")
    
    # Map user entity to users collection
    set_ontology_mapping("user", "test_mongodb.users")
    
    # Map document entity to documents collection
    set_ontology_mapping("document", "test_qdrant.documents")
    
    # List all ontology entities
    entities = list_ontology_entities()
    logger.info(f"Ontology entities: {entities}")
    
    logger.info("Schema registry test completed successfully!")

if __name__ == "__main__":
    asyncio.run(test_registry()) 
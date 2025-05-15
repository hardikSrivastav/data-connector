#!/usr/bin/env python3
"""
Test script for the schema registry client.
This script tests the client interface with real data from the registry.
"""
import logging
import json
import sys
from pathlib import Path

# Add parent directory to path to import registry
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import the client
from agent.db.registry.integrations import SchemaRegistryClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_client():
    """Test the schema registry client with real data"""
    logger.info("Testing schema registry client...")
    
    # Create client
    client = SchemaRegistryClient()
    
    # 1. Get all data sources
    sources = client.get_all_sources()
    logger.info(f"Found {len(sources)} data sources:")
    for source in sources:
        logger.info(f"  - {source['id']} (type: {source['type']})")
    
    if not sources:
        logger.warning("No data sources found in registry. Run introspection first.")
        return
    
    # 2. Get all tables by source
    tables_by_source = client.get_all_tables_by_source()
    for source_id, tables in tables_by_source.items():
        logger.info(f"Tables in {source_id}: {', '.join(tables)}")
    
    # 3. Test table field search
    test_fields = ["id", "name", "product_id", "email"]
    for field in test_fields:
        matching_tables = client.get_tables_containing_field(field)
        if matching_tables:
            logger.info(f"Tables containing '{field}': {matching_tables}")
    
    # 4. Test query recommendations with real data
    test_queries = [
        "Show me all users who made purchases",
        "List all products in the database",
        "Find information about categories",
        "Get order details for user 123"
    ]
    
    for query in test_queries:
        sources = client.get_recommended_sources_for_query(query)
        logger.info(f"Recommended sources for '{query}': {sources}")
    
    # 5. Test schema summary
    if sources:
        # Get the first source for schema summary
        source_id = sources.pop() if isinstance(sources, set) else sources[0]['id']
        schema_summary = client.get_schema_summary_for_sources([source_id])
        logger.info(f"Schema summary for {source_id}:\n{schema_summary[:500]}...")  # Truncate for readability
    
    logger.info("Schema registry client tests completed successfully!")

if __name__ == "__main__":
    test_client() 
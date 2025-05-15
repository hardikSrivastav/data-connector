#!/usr/bin/env python3
"""
Script to check the schema registry with general queries across all data sources.
This script only queries existing data sources without adding any test data.
"""
import json
import sys
from pathlib import Path
import logging

# Add parent directory to path to import registry
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agent.db.registry import (
    init_registry,
    list_data_sources,
    list_tables,
    get_table_schema,
    search_tables_by_name,
    search_schema_content
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_registry():
    """Check the schema registry with general queries across all data sources"""
    logger.info("Initializing schema registry...")
    init_registry()
    
    # 1. Get all data sources
    sources = list_data_sources()
    logger.info(f"Found {len(sources)} data sources:")
    for source in sources:
        logger.info(f"- {source['id']} (type: {source['type']}, uri: {source['uri']})")
    
    # 2. List tables/collections from each data source
    for source in sources:
        source_id = source['id']
        source_type = source['type']
        
        tables = list_tables(source_id)
        logger.info(f"\n{'-'*40}")
        logger.info(f"Tables/Collections in {source_id} ({source_type}): {len(tables)}")
        
        if not tables:
            logger.warning(f"No tables found in {source_id}")
            continue
        
        # Display table names
        for i, table in enumerate(tables[:10], 1):  # Limit to first 10 tables
            logger.info(f"{i}. {table}")
        
        if len(tables) > 10:
            logger.info(f"... and {len(tables) - 10} more")
        
        # 3. Get schema for first table in each source
        if tables:
            first_table = tables[0]
            logger.info(f"\nSchema for {source_id}.{first_table}:")
            
            schema = get_table_schema(source_id, first_table)
            if schema:
                # Extract fields information
                fields = schema.get('schema', {}).get('fields', {})
                
                # Show field names and types
                for field_name, field_info in list(fields.items())[:10]:  # Limit to first 10 fields
                    field_type = field_info.get('data_type', 'unknown')
                    logger.info(f"- {field_name}: {field_type}")
                
                if len(fields) > 10:
                    logger.info(f"... and {len(fields) - 10} more fields")
            else:
                logger.warning(f"No schema found for {source_id}.{first_table}")
    
    # 4. Test search functionality
    logger.info(f"\n{'-'*40}")
    logger.info("Testing search functionality:")
    
    # Search for tables containing common terms
    common_terms = ["user", "product", "order", "document", "category"]
    for term in common_terms:
        search_results = search_tables_by_name(term)
        if search_results:
            logger.info(f"\nTables containing '{term}':")
            for result in search_results:
                logger.info(f"- {result['source_id']}.{result['table_name']} ({result['type']})")
    
    # Search for common field types
    common_fields = ["id", "name", "email", "price", "description", "created"]
    for field in common_fields:
        logger.info(f"\nSearching for field '{field}':")
        # Try to find tables with this field across all sources
        for source in sources:
            source_id = source['id']
            tables = list_tables(source_id)
            
            for table in tables:
                schema = get_table_schema(source_id, table)
                if not schema:
                    continue
                
                fields = schema.get('schema', {}).get('fields', {})
                if field in fields or any(field.lower() in f.lower() for f in fields):
                    logger.info(f"- Found in {source_id}.{table}")
    
    # 5. Check schema content search (useful for complex queries)
    logger.info(f"\n{'-'*40}")
    logger.info("Testing schema content search:")
    
    search_terms = ["vector", "customer", "product", "timestamp"]
    for term in search_terms:
        results = search_schema_content(term)
        if results:
            logger.info(f"\nSchema entries containing '{term}':")
            for result in results[:5]:  # Limit to 5 results
                logger.info(f"- {result['source_id']}.{result['table_name']} ({result['type']})")
            
            if len(results) > 5:
                logger.info(f"... and {len(results) - 5} more results")
    
    logger.info(f"\n{'-'*40}")
    logger.info("Schema registry check completed")

if __name__ == "__main__":
    check_registry() 
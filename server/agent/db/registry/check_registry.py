#!/usr/bin/env python3
"""
Script to check the schema registry with general queries across all data sources.
This script only queries existing data sources without adding any test data.
"""
import json
import sys
from pathlib import Path
import logging
import argparse

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

def check_registry(db_type=None):
    """
    Check the schema registry with general queries across all data sources
    
    Args:
        db_type: Optional database type to focus on (e.g., 'postgres', 'ga4', 'slack')
    """
    logger.info("Initializing schema registry...")
    init_registry()
    
    # 1. Get all data sources
    sources = list_data_sources()
    
    # Filter by db_type if specified
    if db_type:
        sources = [s for s in sources if s['type'] == db_type]
        if not sources:
            logger.warning(f"No {db_type} data sources found in registry!")
            return
    
    logger.info(f"Found {len(sources)} data sources:")
    for source in sources:
        source_id = source['id']
        source_type = source['type']
        
        logger.info(f"- {source_id} (type: {source_type}, uri: {source['uri']})")
        
        # 2. List tables/collections from each data source
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
        
        # 4. Add data source specific checks
        if source_type == 'ga4':
            check_ga4_source(source_id, tables)
    
    # 5. Test search functionality
    if not db_type or db_type not in ['ga4', 'slack']:  # Skip general search for specific db types
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
    
    logger.info(f"\n{'-'*40}")
    logger.info("Schema registry check completed")

def check_ga4_source(source_id, tables):
    """
    Perform GA4-specific checks on the registry
    
    Args:
        source_id: The GA4 source ID to check
        tables: List of tables in the source
    """
    logger.info(f"\n{'-'*40}")
    logger.info(f"GA4-specific checks for {source_id}:")
    
    # Check for dimensions and metrics tables
    if 'dimensions' in tables and 'metrics' in tables:
        # Check dimensions
        dimensions_schema = get_table_schema(source_id, 'dimensions')
        if dimensions_schema:
            dimension_fields = dimensions_schema.get('schema', {}).get('fields', {})
            logger.info(f"Found {len(dimension_fields)} dimensions")
            # Show some example dimensions
            for i, (name, info) in enumerate(list(dimension_fields.items())[:5]):
                logger.info(f"Dimension {i+1}: {name} - {info.get('description', '')[:50]}...")
            
            if len(dimension_fields) > 5:
                logger.info(f"... and {len(dimension_fields) - 5} more dimensions")
        
        # Check metrics
        metrics_schema = get_table_schema(source_id, 'metrics')
        if metrics_schema:
            metric_fields = metrics_schema.get('schema', {}).get('fields', {})
            logger.info(f"Found {len(metric_fields)} metrics")
            # Show some example metrics
            for i, (name, info) in enumerate(list(metric_fields.items())[:5]):
                logger.info(f"Metric {i+1}: {name} - {info.get('description', '')[:50]}...")
            
            if len(metric_fields) > 5:
                logger.info(f"... and {len(metric_fields) - 5} more metrics")
        
        # Check GA4-specific metadata
        ga4_metadata = dimensions_schema.get('schema', {}).get('ga4_metadata', {})
        if ga4_metadata:
            logger.info(f"GA4 Property ID: {ga4_metadata.get('property_id')}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check the schema registry")
    parser.add_argument("--db-type", help="Specific database type to check (e.g., postgres, ga4, slack)")
    args = parser.parse_args()
    
    check_registry(args.db_type) 
#!/usr/bin/env python3
"""
Script to display detailed schema information about Qdrant collections in the registry.
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
    get_table_schema
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def show_qdrant_collections():
    """Display detailed information about Qdrant collections in the registry"""
    logger.info("Initializing schema registry...")
    init_registry()
    
    # Get all data sources
    sources = list_data_sources()
    
    # Filter for Qdrant sources
    qdrant_sources = [s for s in sources if s['type'] == 'qdrant']
    
    if not qdrant_sources:
        logger.warning("No Qdrant data sources found in registry")
        return
    
    logger.info(f"Found {len(qdrant_sources)} Qdrant data sources:")
    
    # For each Qdrant source
    for source in qdrant_sources:
        source_id = source['id']
        logger.info(f"\n{'='*40}\nQdrant Source: {source_id}\nConnection URI: {source['uri']}\n{'='*40}")
        
        # List collections (tables) in this source
        collections = list_tables(source_id)
        
        if not collections:
            logger.warning(f"No collections found in {source_id}")
            continue
            
        logger.info(f"Found {len(collections)} collections: {', '.join(collections)}")
        
        # Get schema for each collection
        for collection in collections:
            logger.info(f"\n{'-'*40}\nCollection: {collection}\n{'-'*40}")
            
            schema = get_table_schema(source_id, collection)
            if not schema:
                logger.warning(f"No schema information found for {collection}")
                continue
                
            # Extract and display fields
            fields = schema.get('schema', {}).get('fields', {})
            
            # Show vector information first
            vector_fields = {name: info for name, info in fields.items() 
                           if info.get('data_type') == 'vector'}
            
            if vector_fields:
                logger.info("Vector Configuration:")
                for name, info in vector_fields.items():
                    dims = info.get('dimensions', 'Unknown')
                    dist = info.get('distance', 'Unknown')
                    logger.info(f"  - {name}: {dims} dimensions, {dist} distance")
            
            # Show points count if available
            if 'points_count' in fields:
                count = fields['points_count'].get('value', 'Unknown')
                logger.info(f"Points Count: {count}")
            
            # Show payload fields
            payload_fields = {name: info for name, info in fields.items() 
                             if info.get('data_type') != 'vector' and name != 'points_count'}
            
            if payload_fields:
                logger.info("Payload Schema:")
                for name, info in payload_fields.items():
                    data_type = info.get('data_type', 'Unknown')
                    indexed = " (indexed)" if info.get('indexed') else ""
                    logger.info(f"  - {name}: {data_type}{indexed}")
            
            # Show raw content if needed
            raw_content = schema.get('schema', {}).get('raw_content')
            if raw_content and '--raw' in sys.argv:
                logger.info("\nRaw Schema Content:")
                logger.info(raw_content)

if __name__ == "__main__":
    show_qdrant_collections() 
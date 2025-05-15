#!/usr/bin/env python3
"""
Cleanup script to remove test databases from the schema registry.
This is useful after running tests to leave only production data sources in the registry.
"""
import logging
import sys
from pathlib import Path

# Add parent directory to path to import registry
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agent.db.registry import (
    init_registry,
    list_data_sources,
    delete_data_source
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def cleanup_test_dbs():
    """Remove test databases from the schema registry"""
    logger.info("Cleaning up test databases from schema registry...")
    
    # Initialize registry
    init_registry()
    
    # Get all data sources
    sources = list_data_sources()
    test_sources = [s['id'] for s in sources if s['id'].startswith('test_')]
    
    if not test_sources:
        logger.info("No test databases found in registry.")
        return
    
    # Delete each test data source
    for source_id in test_sources:
        logger.info(f"Removing data source: {source_id}")
        delete_data_source(source_id)
    
    # Verify removal
    remaining = list_data_sources()
    logger.info(f"Cleanup complete. Remaining data sources: {[s['id'] for s in remaining]}")

if __name__ == "__main__":
    cleanup_test_dbs() 
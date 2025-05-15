#!/usr/bin/env python3
"""
Script to run the introspection worker for all configured data sources.
This will populate the schema registry with metadata from all data sources.
"""
import asyncio
import logging
import os
import sys
from pathlib import Path

# Add parent directory to path to import registry
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agent.db.registry.introspect_worker import run_introspection
from agent.db.registry.config_sources import DATA_SOURCES, DOCKER_DATA_SOURCES

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def main():
    # Determine if we're running in Docker
    in_docker = os.environ.get('RUNNING_IN_DOCKER', '').lower() == 'true'
    
    # Use Docker data sources if in Docker, otherwise use local data sources
    data_sources = DOCKER_DATA_SOURCES if in_docker else DATA_SOURCES
    
    logger.info(f"Running introspection for {len(data_sources)} data sources...")
    
    # Run the introspection worker
    await run_introspection(data_sources)
    
    logger.info("Introspection completed successfully!")

if __name__ == "__main__":
    asyncio.run(main()) 
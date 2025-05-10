#!/usr/bin/env python
"""
Schema watcher script that periodically checks for database schema changes 
and triggers reindexing when needed.

This script can be run as a background process or scheduled task.
"""

import asyncio
import logging
import os
import sys
import time
import argparse
from pathlib import Path

# Add parent directory to path for imports
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir.parent.parent.parent))

from agent.performance import SchemaMonitor
from agent.db.execute import test_conn

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(Path.home() / "schema_watcher.log")
    ]
)
logger = logging.getLogger(__name__)

DEFAULT_CHECK_INTERVAL = 300  # 5 minutes in seconds

async def watch_schema(interval: int = DEFAULT_CHECK_INTERVAL, once: bool = False):
    """
    Continuously watch for schema changes and update the index when needed.
    
    Args:
        interval: Time in seconds between checks
        once: If True, run only once instead of continuously
    """
    monitor = SchemaMonitor(check_interval=0)  # Always check
    
    try:
        logger.info(f"Schema watcher started. Check interval: {interval}s")
        
        while True:
            # Test database connection first
            conn_ok = await test_conn()
            if not conn_ok:
                logger.error("Database connection failed")
                await asyncio.sleep(interval)
                continue
            
            # Check for schema changes and reindex if needed
            logger.info("Checking for schema changes...")
            updated, message = await monitor.check_and_reindex()
            
            if updated:
                logger.info(f"Schema updated: {message}")
            else:
                logger.info(f"Schema check: {message}")
            
            # Exit if running just once
            if once:
                break
                
            # Sleep until next check
            logger.info(f"Next check in {interval} seconds")
            await asyncio.sleep(interval)
            
    except KeyboardInterrupt:
        logger.info("Schema watcher stopped by user")
    except Exception as e:
        logger.error(f"Error in schema watcher: {e}")

def main():
    """Parse arguments and run the schema watcher."""
    parser = argparse.ArgumentParser(description="Database schema watcher")
    parser.add_argument(
        "--interval", 
        type=int, 
        default=DEFAULT_CHECK_INTERVAL,
        help="Check interval in seconds"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run once and exit instead of running continuously"
    )
    
    args = parser.parse_args()
    
    asyncio.run(watch_schema(interval=args.interval, once=args.once))

if __name__ == "__main__":
    main() 
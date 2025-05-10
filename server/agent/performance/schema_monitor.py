import asyncio
import hashlib
import json
import logging
import time
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path

from agent.db.introspect import get_schema_metadata
from agent.meta.ingest import build_and_save_index
from agent.config.settings import Settings

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
SCHEMA_HASH_FILE = Path(Settings().get_app_dir()) / "schema_hash.json"
DEFAULT_CHECK_INTERVAL = 3600  # 1 hour in seconds


class SchemaMonitor:
    """Monitor database schema for changes and trigger reindexing when needed."""

    def __init__(self, check_interval: int = DEFAULT_CHECK_INTERVAL):
        """Initialize the schema monitor.
        
        Args:
            check_interval: Time in seconds between schema checks
        """
        self.check_interval = check_interval
        self._create_hash_file_if_not_exists()

    def _create_hash_file_if_not_exists(self) -> None:
        """Create the schema hash file and directory if they don't exist."""
        try:
            SCHEMA_HASH_FILE.parent.mkdir(parents=True, exist_ok=True)
            if not SCHEMA_HASH_FILE.exists():
                # Initialize with empty data
                self._save_hash_data({
                    "schema_hash": "",
                    "last_check_time": 0
                })
        except Exception as e:
            logger.error(f"Error creating schema hash file: {e}")

    def _save_hash_data(self, data: Dict[str, Any]) -> None:
        """Save hash data to the hash file."""
        try:
            with SCHEMA_HASH_FILE.open('w') as f:
                json.dump(data, f)
        except Exception as e:
            logger.error(f"Error saving schema hash: {e}")

    def _load_hash_data(self) -> Dict[str, Any]:
        """Load hash data from the hash file."""
        try:
            if SCHEMA_HASH_FILE.exists():
                with SCHEMA_HASH_FILE.open('r') as f:
                    return json.load(f)
            return {"schema_hash": "", "last_check_time": 0}
        except Exception as e:
            logger.error(f"Error loading schema hash: {e}")
            return {"schema_hash": "", "last_check_time": 0}

    async def get_schema_hash(self) -> str:
        """Generate a hash of the current database schema.
        
        Returns:
            A string hash representing the current schema state
        """
        try:
            # Get current schema metadata
            schema_metadata = await get_schema_metadata()
            
            # Convert to a sorted, normalized string representation
            schema_json = json.dumps(schema_metadata, sort_keys=True)
            
            # Create a hash of the schema
            return hashlib.sha256(schema_json.encode()).hexdigest()
        except Exception as e:
            logger.error(f"Error generating schema hash: {e}")
            return ""

    def get_stored_hash(self) -> str:
        """Get the previously stored schema hash.
        
        Returns:
            The stored schema hash string
        """
        data = self._load_hash_data()
        return data.get("schema_hash", "")

    def store_hash(self, schema_hash: str) -> None:
        """Store the current schema hash.
        
        Args:
            schema_hash: The current schema hash to store
        """
        data = self._load_hash_data()
        data["schema_hash"] = schema_hash
        data["last_check_time"] = time.time()
        self._save_hash_data(data)

    def should_check_schema(self) -> bool:
        """Check if enough time has passed since the last schema check.
        
        Returns:
            True if it's time to check the schema, False otherwise
        """
        data = self._load_hash_data()
        last_check_time = data.get("last_check_time", 0)
        return (time.time() - last_check_time) >= self.check_interval

    def update_last_check(self) -> None:
        """Update the timestamp of the last schema check."""
        data = self._load_hash_data()
        data["last_check_time"] = time.time()
        self._save_hash_data(data)

    async def check_and_reindex(self, force: bool = False) -> Tuple[bool, str]:
        """Check for schema changes and reindex if necessary.
        
        Args:
            force: Force reindexing even if no changes are detected
            
        Returns:
            A tuple of (reindexed, message) where:
                reindexed: True if reindexing was performed
                message: A descriptive message about what happened
        """
        try:
            current_hash = await self.get_schema_hash()
            stored_hash = self.get_stored_hash()
            
            # Skip if no hash could be generated (error)
            if not current_hash:
                return False, "Could not generate schema hash"
            
            # Check if schema has changed or force reindex
            schema_changed = current_hash != stored_hash
            
            if schema_changed or force:
                # Rebuild the index
                success = await build_and_save_index()
                if success:
                    # Update the stored hash
                    self.store_hash(current_hash)
                    action = "forced" if force else "detected changes and triggered"
                    return True, f"Successfully {action} reindexing"
                else:
                    return False, "Failed to rebuild index"
            else:
                # Update the last check time
                self.update_last_check()
                return False, "No schema changes detected"
        
        except Exception as e:
            logger.error(f"Error in check_and_reindex: {e}")
            return False, f"Error checking schema: {str(e)}"


async def ensure_schema_index_updated(force: bool = False) -> Tuple[bool, str]:
    """Utility function to ensure the schema index is up-to-date.
    
    Args:
        force: Force reindexing even if no changes detected
        
    Returns:
        A tuple of (updated, message) where:
            updated: True if the index was updated
            message: A descriptive message about what happened
    """
    monitor = SchemaMonitor()
    
    # Only check if enough time has passed or forced
    if monitor.should_check_schema() or force:
        return await monitor.check_and_reindex(force=force)
    return False, "Schema check skipped (checked recently)"

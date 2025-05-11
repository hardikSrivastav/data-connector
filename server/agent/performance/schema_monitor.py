import asyncio
import hashlib
import json
import logging
import time
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
from urllib.parse import urlparse

from agent.db.introspect import get_schema_metadata
from agent.meta.ingest import build_and_save_index_for_db, ensure_index_exists
from agent.config.settings import Settings

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
DEFAULT_CHECK_INTERVAL = 3600  # 1 hour in seconds


class SchemaMonitor:
    """Monitor database schema for changes and trigger reindexing when needed."""

    def __init__(self, db_type: str = "postgres", check_interval: int = DEFAULT_CHECK_INTERVAL, conn_uri: Optional[str] = None, **kwargs):
        """Initialize the schema monitor.
        
        Args:
            db_type: Database type ('postgres', 'mongodb', etc.)
            check_interval: Time in seconds between schema checks
            conn_uri: Optional connection URI
            **kwargs: Additional adapter-specific parameters
        """
        self.db_type = db_type.lower()
        self.check_interval = check_interval
        self.conn_uri = conn_uri
        self.kwargs = kwargs
        self._create_hash_file_if_not_exists()

    @property
    def hash_file_path(self) -> Path:
        """Get the path to the schema hash file for this database type."""
        return Path(Settings().get_app_dir()) / f"schema_hash_{self.db_type}.json"

    def _create_hash_file_if_not_exists(self) -> None:
        """Create the schema hash file and directory if they don't exist."""
        try:
            self.hash_file_path.parent.mkdir(parents=True, exist_ok=True)
            if not self.hash_file_path.exists():
                # Initialize with empty data
                self._save_hash_data({
                    "schema_hash": "",
                    "last_check_time": 0,
                    "db_type": self.db_type
                })
        except Exception as e:
            logger.error(f"Error creating schema hash file for {self.db_type}: {e}")

    def _save_hash_data(self, data: Dict[str, Any]) -> None:
        """Save hash data to the hash file."""
        try:
            with self.hash_file_path.open('w') as f:
                json.dump(data, f)
        except Exception as e:
            logger.error(f"Error saving schema hash for {self.db_type}: {e}")

    def _load_hash_data(self) -> Dict[str, Any]:
        """Load hash data from the hash file."""
        try:
            if self.hash_file_path.exists():
                with self.hash_file_path.open('r') as f:
                    return json.load(f)
            return {"schema_hash": "", "last_check_time": 0, "db_type": self.db_type}
        except Exception as e:
            logger.error(f"Error loading schema hash for {self.db_type}: {e}")
            return {"schema_hash": "", "last_check_time": 0, "db_type": self.db_type}

    async def get_schema_hash(self) -> str:
        """Generate a hash of the current database schema.
        
        Returns:
            A string hash representing the current schema state
        """
        try:
            # Get current schema metadata for this database type
            schema_metadata = await get_schema_metadata(
                conn_uri=self.conn_uri, 
                db_type=self.db_type, 
                **self.kwargs
            )
            
            # Convert to a sorted, normalized string representation
            schema_json = json.dumps(schema_metadata, sort_keys=True)
            
            # Create a hash of the schema
            return hashlib.sha256(schema_json.encode()).hexdigest()
        except Exception as e:
            logger.error(f"Error generating schema hash for {self.db_type}: {e}")
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
        data["db_type"] = self.db_type
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
                return False, f"Could not generate schema hash for {self.db_type}"
            
            # Check if schema has changed or force reindex
            schema_changed = current_hash != stored_hash
            
            if schema_changed or force:
                # Rebuild the index for this database type
                success = await build_and_save_index_for_db(db_type=self.db_type, conn_uri=self.conn_uri)
                if success:
                    # Update the stored hash
                    self.store_hash(current_hash)
                    action = "forced" if force else "detected changes and triggered"
                    return True, f"Successfully {action} reindexing for {self.db_type}"
                else:
                    return False, f"Failed to rebuild index for {self.db_type}"
            else:
                # Update the last check time
                self.update_last_check()
                return False, f"No schema changes detected for {self.db_type}"
        
        except Exception as e:
            logger.error(f"Error in check_and_reindex for {self.db_type}: {e}")
            return False, f"Error checking schema for {self.db_type}: {str(e)}"


async def ensure_schema_index_updated(
    force: bool = False, 
    db_type: Optional[str] = None, 
    conn_uri: Optional[str] = None,
    **kwargs
) -> Tuple[bool, str]:
    """Utility function to ensure the schema index is up-to-date.
    
    Args:
        force: Force reindexing even if no changes detected
        db_type: Optional database type. If None, uses the type from conn_uri or settings.
        conn_uri: Optional connection URI. If None, uses default from settings.
        **kwargs: Additional adapter-specific parameters (e.g., db_name for MongoDB)
        
    Returns:
        A tuple of (updated, message) where:
            updated: True if the index was updated
            message: A descriptive message about what happened
    """
    settings = Settings()
    
    # Determine database type if not specified
    if not db_type:
        # Get URI from connection_uri or settings
        uri = conn_uri or settings.connection_uri
        parsed_uri = urlparse(uri)
        
        # For HTTP-based URIs, don't use the scheme as db_type
        # Instead, use the type from settings
        if parsed_uri.scheme in ['http', 'https']:
            db_type = settings.DB_TYPE
        else:
            # Use scheme for other database URIs
            db_type = parsed_uri.scheme
    
    # Fall back to configured default if still no type detected
    if not db_type:
        db_type = settings.DB_TYPE
    
    # Create a schema monitor for this database type
    monitor = SchemaMonitor(db_type=db_type, conn_uri=conn_uri, **kwargs)
    
    # Only check if enough time has passed or forced
    if monitor.should_check_schema() or force:
        try:
            current_hash = await monitor.get_schema_hash()
            stored_hash = monitor.get_stored_hash()
            
            # Skip if no hash could be generated (error)
            if not current_hash:
                return False, f"Could not generate schema hash for {db_type}"
            
            # Check if schema has changed or force reindex
            schema_changed = current_hash != stored_hash
            
            if schema_changed or force:
                # Rebuild the index for this database type
                success = await build_and_save_index_for_db(db_type=db_type, conn_uri=conn_uri, **kwargs)
                if success:
                    # Update the stored hash
                    monitor.store_hash(current_hash)
                    action = "forced" if force else "detected changes and triggered"
                    return True, f"Successfully {action} reindexing for {db_type}"
                else:
                    return False, f"Failed to rebuild index for {db_type}"
            else:
                # Update the last check time
                monitor.update_last_check()
                return False, f"No schema changes detected for {db_type}"
        
        except Exception as e:
            logger.error(f"Error in ensure_schema_index_updated for {db_type}: {e}")
            return False, f"Error checking schema for {db_type}: {str(e)}"
    
    return False, f"Schema check skipped for {db_type} (checked recently)"

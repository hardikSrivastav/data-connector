#!/usr/bin/env python3
"""
Schema Watcher - Monitors databases for schema changes

This module provides functionality to detect schema changes in various database types
and update the schema registry accordingly, without constant polling.
"""
import logging
import asyncio
import json
import hashlib
import sys
from pathlib import Path
from typing import Dict, Any, Set, List, Optional, Tuple
import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agent.db.registry import (
    init_registry,
    list_data_sources,
    get_data_source,
    list_tables,
    get_table_schema,
    upsert_table_meta
)
from agent.db.registry.run_introspection import run_introspection
from agent.db.registry.config_sources import get_data_sources
from agent.config.settings import Settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SchemaWatcher:
    """Schema change detector for various database types"""
    
    def __init__(self):
        """Initialize the schema watcher"""
        # Initialize registry
        init_registry()
        
        # Will store schema fingerprints
        self.schema_cache: Dict[str, Dict[str, str]] = {}
        
        # Store Qdrant collection fingerprints separately
        self.qdrant_cache: Dict[str, Dict[str, Any]] = {}
        
    async def calculate_schema_fingerprints(self) -> Dict[str, Dict[str, str]]:
        """
        Calculate fingerprints for all schemas in the registry
        
        Returns:
            Dictionary mapping source_id to table_name to fingerprint hash
        """
        fingerprints = {}
        sources = list_data_sources()
        
        for source in sources:
            source_id = source["id"]
            source_type = source["type"]
            fingerprints[source_id] = {}
            
            # Skip Qdrant sources - they're handled separately
            if source_type == "qdrant":
                continue
                
            tables = list_tables(source_id)
            for table_name in tables:
                schema = get_table_schema(source_id, table_name)
                if schema:
                    # Create a fingerprint hash from the schema
                    schema_json = json.dumps(schema, sort_keys=True)
                    fingerprint = hashlib.sha256(schema_json.encode()).hexdigest()
                    fingerprints[source_id][table_name] = fingerprint
        
        return fingerprints
    
    async def detect_schema_changes(self) -> Tuple[bool, Set[str]]:
        """
        Detect if any schema changes have occurred
        
        Returns:
            Tuple of (changes_detected, changed_sources)
        """
        # Get fingerprints for regular databases
        new_fingerprints = await self.calculate_schema_fingerprints()
        
        # Get fingerprints for Qdrant collections
        new_qdrant_fingerprints = await self.calculate_qdrant_fingerprints()
        
        changes_detected = False
        changed_sources: Set[str] = set()
        
        # First run - just store fingerprints
        if not self.schema_cache:
            self.schema_cache = new_fingerprints
            self.qdrant_cache = new_qdrant_fingerprints
            return False, set()
        
        # Compare with cached fingerprints for regular databases
        for source_id, tables in new_fingerprints.items():
            # Check if source is new
            if source_id not in self.schema_cache:
                logger.info(f"New data source detected: {source_id}")
                changes_detected = True
                changed_sources.add(source_id)
                continue
                
            # Check each table
            for table_name, fingerprint in tables.items():
                # Check if table is new or changed
                if (table_name not in self.schema_cache[source_id] or 
                        self.schema_cache[source_id][table_name] != fingerprint):
                    logger.info(f"Schema change detected in {source_id}.{table_name}")
                    changes_detected = True
                    changed_sources.add(source_id)
        
        # Check for removed tables or sources
        for source_id, tables in self.schema_cache.items():
            # Check if source was removed
            if source_id not in new_fingerprints:
                logger.info(f"Data source removed: {source_id}")
                changes_detected = True
                continue
                
            # Check if tables were removed
            for table_name in tables:
                if table_name not in new_fingerprints[source_id]:
                    logger.info(f"Table removed: {source_id}.{table_name}")
                    changes_detected = True
                    changed_sources.add(source_id)
        
        # Compare Qdrant fingerprints
        for source_id, collections in new_qdrant_fingerprints.items():
            # Check if source is new
            if source_id not in self.qdrant_cache:
                logger.info(f"New Qdrant source detected: {source_id}")
                changes_detected = True
                changed_sources.add(source_id)
                continue
                
            # Check each collection
            for coll_name, fingerprint in collections.items():
                # Check if collection is new or changed
                if (coll_name not in self.qdrant_cache[source_id] or 
                        self.qdrant_cache[source_id][coll_name] != fingerprint):
                    logger.info(f"Schema change detected in Qdrant collection {source_id}.{coll_name}")
                    changes_detected = True
                    changed_sources.add(source_id)
        
        # Check for removed Qdrant collections or sources
        for source_id, collections in self.qdrant_cache.items():
            # Check if source was removed
            if source_id not in new_qdrant_fingerprints:
                if source_id not in new_fingerprints:  # Avoid duplicate log if already logged
                    logger.info(f"Qdrant data source removed: {source_id}")
                    changes_detected = True
                continue
                
            # Check if collections were removed
            for coll_name in collections:
                if coll_name not in new_qdrant_fingerprints[source_id]:
                    logger.info(f"Qdrant collection removed: {source_id}.{coll_name}")
                    changes_detected = True
                    changed_sources.add(source_id)
        
        # Update caches
        self.schema_cache = new_fingerprints
        self.qdrant_cache = new_qdrant_fingerprints
        return changes_detected, changed_sources

    async def calculate_qdrant_fingerprints(self) -> Dict[str, Dict[str, str]]:
        """
        Calculate fingerprints for all Qdrant collections in the registry
        
        Returns:
            Dictionary mapping source_id to collection_name to fingerprint hash
        """
        fingerprints = {}
        sources = list_data_sources()
        
        # Filter for Qdrant sources only
        qdrant_sources = [s for s in sources if s["type"] == "qdrant"]
        
        for source in qdrant_sources:
            source_id = source["id"]
            uri = source["uri"]
            fingerprints[source_id] = {}
            
            # Get Qdrant collection information
            try:
                collections_info = await self.get_qdrant_collections(uri)
                
                # Calculate fingerprint for each collection
                for collection in collections_info:
                    coll_name = collection["name"]
                    # Create a fingerprint hash from the collection info
                    coll_json = json.dumps(collection, sort_keys=True)
                    fingerprint = hashlib.sha256(coll_json.encode()).hexdigest()
                    fingerprints[source_id][coll_name] = fingerprint
                    
            except Exception as e:
                logger.error(f"Error getting Qdrant collections for {source_id}: {str(e)}")
        
        return fingerprints
    
    async def get_qdrant_collections(self, uri: str) -> List[Dict[str, Any]]:
        """
        Get collection information from a Qdrant instance
        
        Args:
            uri: Qdrant connection URI
            
        Returns:
            List of collection information dictionaries
        """
        from qdrant_client import QdrantClient
        
        try:
            # Get settings
            settings = Settings()
            
            # Create Qdrant client
            client = QdrantClient(
                url=uri, 
                api_key=settings.QDRANT_API_KEY,
                prefer_grpc=settings.QDRANT_PREFER_GRPC
            )
            
            # Get collections
            collections_response = client.get_collections()
            
            # Extract collection information
            collections = []
            for collection in collections_response.collections:
                # Get detailed collection info
                try:
                    collection_info = client.get_collection(collection.name)
                    
                    # Convert to dict for easier serialization and fingerprinting
                    collection_dict = {
                        "name": collection.name,
                        "vectors_count": getattr(collection_info, 'vectors_count', 0),
                        "status": getattr(collection_info, 'status', None),
                    }
                    
                    # Add vector and payload schema info if available
                    if hasattr(collection_info, 'config') and hasattr(collection_info.config, 'params'):
                        params = collection_info.config.params
                        
                        # Vector config
                        if hasattr(params, 'vectors'):
                            vectors = params.vectors
                            # Handle both dictionary and object format
                            if hasattr(vectors, 'items') and callable(vectors.items):
                                vector_dict = {}
                                for vec_name, vec_config in vectors.items():
                                    vector_dict[vec_name] = {
                                        "size": getattr(vec_config, 'size', None),
                                        "distance": getattr(vec_config, 'distance', None)
                                    }
                                collection_dict["vectors"] = vector_dict
                            else:
                                collection_dict["vectors"] = {
                                    "size": getattr(vectors, 'size', None),
                                    "distance": getattr(vectors, 'distance', None)
                                }
                        
                        # Payload schema
                        if hasattr(params, 'payload_schema'):
                            payload_schema = params.payload_schema
                            if payload_schema:
                                schema_dict = {}
                                for field_name, field_info in payload_schema.items():
                                    schema_dict[field_name] = {
                                        "data_type": getattr(field_info, 'data_type', None),
                                        "indexed": getattr(field_info, 'indexed', False)
                                    }
                                collection_dict["payload_schema"] = schema_dict
                    
                    collections.append(collection_dict)
                except Exception as e:
                    logger.warning(f"Error getting details for collection {collection.name}: {str(e)}")
                    # Add basic info only
                    collections.append({"name": collection.name})
            
            return collections
            
        except Exception as e:
            logger.error(f"Error getting Qdrant collections: {str(e)}")
            return []

    async def setup_postgres_listener(self, source_id: str, conn_uri: str):
        """
        Set up a listener for PostgreSQL schema changes using LISTEN/NOTIFY
        
        Args:
            source_id: The data source ID
            conn_uri: PostgreSQL connection URI
        """
        import asyncpg
        
        try:
            # Connect to PostgreSQL
            conn = await asyncpg.connect(conn_uri)
            
            # Create a notification function if it doesn't exist
            await conn.execute("""
                CREATE OR REPLACE FUNCTION notify_schema_change()
                RETURNS event_trigger AS $$
                BEGIN
                    PERFORM pg_notify('schema_change', TG_TAG || ' - ' || current_database());
                END;
                $$ LANGUAGE plpgsql;
            """)
            
            # Create event trigger if it doesn't exist
            # This might require superuser privileges
            try:
                await conn.execute("""
                    CREATE EVENT TRIGGER schema_change_trigger
                    ON ddl_command_end
                    WHEN TAG IN ('CREATE TABLE', 'ALTER TABLE', 'DROP TABLE', 
                                'CREATE SCHEMA', 'ALTER SCHEMA', 'DROP SCHEMA')
                    EXECUTE FUNCTION notify_schema_change();
                """)
            except asyncpg.exceptions.InsufficientPrivilegeError:
                logger.warning(f"Insufficient privileges to create event trigger for {source_id}.")
                logger.warning("Will fall back to periodic fingerprint checking.")
            
            # Listen for notifications
            await conn.add_listener('schema_change', self._handle_postgres_notification)
            
            logger.info(f"Set up PostgreSQL schema change listener for {source_id}")
            return conn
            
        except Exception as e:
            logger.error(f"Error setting up PostgreSQL listener for {source_id}: {str(e)}")
            logger.info(f"Will fall back to periodic fingerprint checking for {source_id}")
            return None
    
    async def _handle_postgres_notification(self, connection, pid, channel, payload):
        """Handle PostgreSQL schema change notification"""
        logger.info(f"PostgreSQL schema change detected: {payload}")
        # Run introspection for this source only
        # This would need to map from connection to source_id
        await self.update_registry()
    
    async def setup_mongodb_watcher(self, source_id: str, conn_uri: str):
        """
        Set up a watcher for MongoDB schema changes using Change Streams
        
        Args:
            source_id: The data source ID
            conn_uri: MongoDB connection URI
        """
        from motor.motor_asyncio import AsyncIOMotorClient
        
        try:
            # Connect to MongoDB
            client = AsyncIOMotorClient(conn_uri)
            db = client.get_database()
            
            # Get existing collections
            collections = await db.list_collection_names()
            
            # Set up change stream on admin database to detect collection changes
            # Note: This requires MongoDB replica set
            try:
                change_stream = db.watch(
                    pipeline=[
                        {
                            '$match': {
                                'operationType': {
                                    '$in': ['create', 'drop', 'rename', 'modify']
                                }
                            }
                        }
                    ]
                )
                
                # Create task to listen for changes
                asyncio.create_task(self._handle_mongodb_changes(change_stream, source_id))
                logger.info(f"Set up MongoDB change stream for {source_id}")
                return client
                
            except Exception as e:
                logger.warning(f"Could not set up MongoDB change stream for {source_id}: {str(e)}")
                logger.info(f"Will fall back to periodic fingerprint checking for {source_id}")
                return None
            
        except Exception as e:
            logger.error(f"Error setting up MongoDB watcher for {source_id}: {str(e)}")
            logger.info(f"Will fall back to periodic fingerprint checking for {source_id}")
            return None
    
    async def _handle_mongodb_changes(self, change_stream, source_id):
        """Handle MongoDB change stream events"""
        try:
            async for change in change_stream:
                logger.info(f"MongoDB schema change detected in {source_id}: {change}")
                # Update registry for this source
                await self.update_registry(changed_sources=[source_id])
        except Exception as e:
            logger.error(f"Error in MongoDB change stream for {source_id}: {str(e)}")
            logger.info("Will fall back to periodic fingerprint checking")
    
    async def setup_qdrant_watcher(self, source_id: str, uri: str):
        """
        Set up a watcher for Qdrant collections
        
        Args:
            source_id: The data source ID
            conn_uri: Qdrant connection URI
            
        Returns:
            QdrantClient instance or None
        """
        from qdrant_client import QdrantClient
        
        try:
            # Get settings
            settings = Settings()
            
            # Create Qdrant client
            client = QdrantClient(
                url=uri, 
                api_key=settings.QDRANT_API_KEY,
                prefer_grpc=settings.QDRANT_PREFER_GRPC
            )
            
            # Test connection and get collections
            collections = client.get_collections()
            
            logger.info(f"Set up Qdrant watcher for {source_id} with {len(collections.collections)} collections")
            return client
            
        except Exception as e:
            logger.error(f"Error setting up Qdrant watcher for {source_id}: {str(e)}")
            logger.info(f"Will fall back to periodic fingerprint checking for {source_id}")
            return None
    
    async def update_registry(self, changed_sources: Optional[List[str]] = None):
        """
        Update the schema registry for changed sources
        
        Args:
            changed_sources: Optional list of source IDs to update. If None, updates all.
        """
        # Get data sources from config
        data_sources = get_data_sources()
        
        # Filter sources if needed
        if changed_sources:
            data_sources = [s for s in data_sources if s["id"] in changed_sources]
        
        # Run introspection
        if data_sources:
            logger.info(f"Updating schema registry for {len(data_sources)} data sources")
            await run_introspection(data_sources)
            logger.info(f"Schema registry updated at {datetime.datetime.now()}")
    
    async def watch_for_changes(self, check_interval: int = 3600):
        """
        Main function to watch for schema changes
        
        Args:
            check_interval: How often to check for changes using fingerprints (in seconds)
        """
        # Get data sources
        sources = list_data_sources()
        if not sources:
            logger.warning("No data sources found in registry. Run introspection first.")
            return
        
        # Set up database-specific watchers
        postgres_connections = {}
        mongodb_connections = {}
        qdrant_clients = {}
        
        for source in sources:
            source_id = source["id"]
            source_type = source["type"]
            uri = source["uri"]
            
            if source_type == "postgres":
                conn = await self.setup_postgres_listener(source_id, uri)
                if conn:
                    postgres_connections[source_id] = conn
            
            elif source_type == "mongodb":
                client = await self.setup_mongodb_watcher(source_id, uri)
                if client:
                    mongodb_connections[source_id] = client
            
            elif source_type == "qdrant":
                client = await self.setup_qdrant_watcher(source_id, uri)
                if client:
                    qdrant_clients[source_id] = client
        
        # Initial fingerprint calculation
        self.schema_cache = await self.calculate_schema_fingerprints()
        self.qdrant_cache = await self.calculate_qdrant_fingerprints()
        logger.info(f"Initial schema fingerprints calculated for {len(self.schema_cache)} data sources")
        logger.info(f"Initial Qdrant fingerprints calculated for {len(self.qdrant_cache)} Qdrant sources")
        
        # Main loop - periodically check for changes using fingerprints
        try:
            while True:
                logger.debug(f"Checking for schema changes (interval: {check_interval}s)")
                
                changes_detected, changed_sources = await self.detect_schema_changes()
                
                if changes_detected:
                    logger.info(f"Schema changes detected in {len(changed_sources)} sources")
                    # Update registry for changed sources
                    await self.update_registry(list(changed_sources))
                
                # Wait for next check
                await asyncio.sleep(check_interval)
                
        except asyncio.CancelledError:
            logger.info("Schema watcher task cancelled")
            
        finally:
            # Clean up connections
            for conn in postgres_connections.values():
                await conn.close()
            
            for client in mongodb_connections.values():
                client.close()
            
            # Qdrant clients don't have async close method
            qdrant_clients.clear()


async def main():
    """Main function to start the schema watcher"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Database Schema Watcher")
    parser.add_argument(
        "--interval", 
        type=int, 
        default=3600,
        help="Interval in seconds for checking schema changes (default: 3600)"
    )
    parser.add_argument(
        "--one-time", 
        action="store_true",
        help="Run a one-time check instead of continuous watching"
    )
    
    args = parser.parse_args()
    
    watcher = SchemaWatcher()
    
    if args.one_time:
        # Run a one-time check
        changes, sources = await watcher.detect_schema_changes()
        if changes:
            await watcher.update_registry(list(sources))
            logger.info("Schema registry updated")
        else:
            logger.info("No schema changes detected")
    else:
        # Continuous watching
        logger.info(f"Starting schema watcher (check interval: {args.interval}s)")
        await watcher.watch_for_changes(args.interval)


if __name__ == "__main__":
    asyncio.run(main()) 
import asyncio
import logging
import os
import json
import yaml
from typing import Any, Dict, List, Optional
from pathlib import Path
import sys

# Add parent directory to path to import registry
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agent.db.registry import (
    init_registry,
    upsert_data_source,
    upsert_table_meta
)
from agent.db.adapters import postgres, mongo, qdrant, slack
from agent.db.introspect import get_schema_metadata

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def introspect_postgres(source_id: str, uri: str, version: str = "1.0.0"):
    """
    Introspect a PostgreSQL database and store its schema in the registry
    
    Args:
        source_id: Unique identifier for this data source
        uri: PostgreSQL connection URI
        version: Version for this data source
    """
    logger.info(f"Introspecting PostgreSQL database: {source_id}")
    
    # Register the data source
    upsert_data_source(source_id, uri, "postgres", version)
    
    try:
        # Using the existing introspection mechanism
        documents = await get_schema_metadata(uri, "postgres")
        
        # Extract table information and store in registry
        for doc in documents:
            doc_id = doc.get("id", "")
            if doc_id.startswith("table:"):
                table_name = doc_id.split(":", 1)[1]
                
                # Process the content to create a schema dictionary
                content = doc.get("content", "")
                schema_dict = {
                    "raw_content": content,
                    "fields": parse_postgres_schema_content(content)
                }
                
                # Store in registry
                upsert_table_meta(source_id, table_name, schema_dict, version)
                logger.info(f"  - Added table: {table_name}")
    
    except Exception as e:
        logger.error(f"Error introspecting PostgreSQL {source_id}: {str(e)}")
        raise

def parse_postgres_schema_content(content: str) -> Dict[str, Dict[str, Any]]:
    """
    Parse PostgreSQL schema content string into structured field information
    
    Args:
        content: The schema content string from introspection
        
    Returns:
        Dictionary of field information
    """
    fields = {}
    
    # Simple parsing of the content format from introspect.py
    lines = content.strip().split("\n")
    in_columns_section = False
    
    for line in lines:
        line = line.strip()
        
        if line.startswith("COLUMNS:"):
            in_columns_section = True
            continue
        elif line.startswith("PRIMARY KEY:") or line.startswith("FOREIGN KEYS:"):
            in_columns_section = False
            continue
        
        if in_columns_section and line.startswith("-"):
            # Column format: "- column_name (data_type)[, PRIMARY KEY][, NOT NULL]"
            parts = line[1:].strip().split(" ", 1)
            if len(parts) < 2:
                continue
                
            col_name = parts[0].strip()
            
            # Extract data type
            type_part = parts[1].strip()
            data_type = type_part.split("(")[0].strip()
            if data_type.endswith(")"):
                data_type = data_type[:-1]
            
            # Check for constraints
            is_primary = "PRIMARY KEY" in type_part
            not_null = "NOT NULL" in type_part
            
            fields[col_name] = {
                "data_type": data_type,
                "primary_key": is_primary,
                "nullable": not not_null
            }
    
    return fields

async def introspect_mongodb(source_id: str, uri: str, version: str = "1.0.0"):
    """
    Introspect a MongoDB database and store its schema in the registry
    
    Args:
        source_id: Unique identifier for this data source
        uri: MongoDB connection URI
        version: Version for this data source
    """
    logger.info(f"Introspecting MongoDB database: {source_id}")
    
    # Register the data source
    upsert_data_source(source_id, uri, "mongodb", version)
    
    try:
        # Use the existing introspection mechanism
        documents = await get_schema_metadata(uri, "mongodb")
        
        # Process each collection document
        collections_added = 0
        for doc in documents:
            doc_id = doc.get("id", "")
            if doc_id.startswith("collection:"):
                collection_name = doc_id.split(":", 1)[1]
                content = doc.get("content", "")
                
                # Process the content to create a schema dictionary
                schema_dict = {
                    "raw_content": content,
                    "fields": parse_mongodb_schema_content(content)
                }
                
                # Store in registry as a table
                upsert_table_meta(source_id, collection_name, schema_dict, version)
                logger.info(f"  - Added collection: {collection_name}")
                collections_added += 1
        
        if collections_added == 0:
            # Direct approach if no collections were found in the metadata
            # Connect to MongoDB directly to get collections
            from motor.motor_asyncio import AsyncIOMotorClient
            from pymongo.errors import ConnectionFailure
            
            client = AsyncIOMotorClient(uri)
            db_name = uri.split("/")[-1].split("?")[0]
            db = client[db_name]
            
            try:
                # Verify connection
                await db.command("ping")
                
                # Get collection names
                collection_names = await db.list_collection_names()
                
                for collection_name in collection_names:
                    # Skip system collections
                    if collection_name.startswith("system.") and collection_name != "system.views":
                        continue
                    
                    # Get a sample document to infer schema
                    sample = await db[collection_name].find_one()
                    
                    # Create a schema dictionary from the sample
                    if sample:
                        fields = {}
                        for field_name, value in sample.items():
                            # Determine field type
                            field_type = type(value).__name__
                            is_primary = field_name == "_id"
                            
                            fields[field_name] = {
                                "data_type": field_type,
                                "primary_key": is_primary
                            }
                        
                        schema_dict = {
                            "raw_content": f"Collection: {collection_name}\nSample fields: {', '.join(fields.keys())}",
                            "fields": fields
                        }
                        
                        # Store in registry
                        upsert_table_meta(source_id, collection_name, schema_dict, version)
                        logger.info(f"  - Added collection: {collection_name}")
                
            except ConnectionFailure as e:
                logger.error(f"MongoDB connection failed: {str(e)}")
        
        logger.info(f"MongoDB introspection for {source_id} completed")
    
    except Exception as e:
        logger.error(f"Error introspecting MongoDB {source_id}: {str(e)}")
        raise

def parse_mongodb_schema_content(content: str) -> Dict[str, Dict[str, Any]]:
    """
    Parse MongoDB schema content string into structured field information
    
    Args:
        content: The schema content string from introspection
        
    Returns:
        Dictionary of field information
    """
    fields = {}
    
    # Simple parsing of the content
    lines = content.strip().split("\n")
    in_fields_section = False
    
    for line in lines:
        line = line.strip()
        
        if line.startswith("FIELDS:"):
            in_fields_section = True
            continue
        elif line.startswith("INDEXES:") or line.startswith("STATS:"):
            in_fields_section = False
            continue
        
        if in_fields_section and line.startswith("-"):
            # Field format: "- field_name (data_type)"
            parts = line[1:].strip().split(" ", 1)
            if len(parts) < 2:
                continue
                
            field_name = parts[0].strip()
            
            # Extract data type
            type_part = parts[1].strip()
            if "(" in type_part and ")" in type_part:
                data_type = type_part.split("(")[1].split(")")[0].strip()
            else:
                data_type = type_part
            
            # Check if it's the primary key
            is_primary = field_name == "_id"
            
            fields[field_name] = {
                "data_type": data_type,
                "primary_key": is_primary
            }
    
    return fields

async def introspect_qdrant(source_id: str, uri: str, version: str = "1.0.0"):
    """
    Introspect a Qdrant vector database and store its schema in the registry
    
    Args:
        source_id: Unique identifier for this data source
        uri: Qdrant connection URI
        version: Version for this data source
    """
    logger.info(f"Introspecting Qdrant database: {source_id}")
    
    # Register the data source
    upsert_data_source(source_id, uri, "qdrant", version)
    
    try:
        # Use the existing introspection mechanism
        documents = await get_schema_metadata(uri, "qdrant")
        
        # Process each collection as a "table" in the registry
        for doc in documents:
            doc_id = doc.get("id", "")
            if doc_id.startswith("collection:"):
                collection_name = doc_id.split(":", 1)[1]
                content = doc.get("content", "")
                
                # Process the content to create a schema dictionary
                schema_dict = {
                    "raw_content": content,
                    "fields": parse_qdrant_schema_content(content)
                }
                
                # Store in registry as a table
                upsert_table_meta(source_id, collection_name, schema_dict, version)
                logger.info(f"  - Added collection: {collection_name}")
    
    except Exception as e:
        logger.error(f"Error introspecting Qdrant {source_id}: {str(e)}")
        raise

def parse_qdrant_schema_content(content: str) -> Dict[str, Dict[str, Any]]:
    """
    Parse Qdrant schema content string into structured field information
    
    Args:
        content: The schema content string from introspection
        
    Returns:
        Dictionary of field information
    """
    fields = {}
    
    # Parse the Qdrant collection content
    lines = content.strip().split("\n")
    in_schema_section = False
    vectors_info = {}
    
    for line in lines:
        line = line.strip()
        
        # Extract vector dimensions info
        if line.startswith("VECTOR DIMENSIONS:"):
            dim_value = line.split(":", 1)[1].strip()
            fields["vector_dimensions"] = {
                "data_type": "vector",
                "dimensions": dim_value
            }
        
        # Extract named vector info
        elif line.startswith("VECTOR ") and "DIMENSIONS:" in line:
            parts = line.split("DIMENSIONS:", 1)
            vec_name = parts[0].replace("VECTOR", "").strip()
            dim_value = parts[1].strip()
            vectors_info[vec_name] = {"dimensions": dim_value}
            
        # Extract distance metrics
        elif line.startswith("VECTOR ") and "DISTANCE:" in line:
            parts = line.split("DISTANCE:", 1)
            vec_name = parts[0].replace("VECTOR", "").strip()
            distance_value = parts[1].strip()
            if vec_name in vectors_info:
                vectors_info[vec_name]["distance"] = distance_value
        
        # Handle payload schema section
        elif line == "PAYLOAD SCHEMA:":
            in_schema_section = True
            continue
        
        # Points count (metadata for the collection)
        elif line.startswith("POINTS COUNT:"):
            points_count = line.split(":", 1)[1].strip()
            fields["points_count"] = {
                "data_type": "integer",
                "value": points_count
            }
            
        # Handle payload fields
        elif in_schema_section and line.startswith("-"):
            # Field format: "- field_name: data_type (indexed: true/false)"
            line = line[1:].strip()  # Remove leading dash
            
            # Split field name and type info
            if ":" in line:
                field_parts = line.split(":", 1)
                field_name = field_parts[0].strip()
                field_info = field_parts[1].strip()
                
                # Extract data type and indexed status
                data_type = field_info
                indexed = False
                
                if "indexed" in field_info:
                    data_type = field_info.split("(", 1)[0].strip()
                    indexed = "indexed: true" in field_info.lower()
                
                fields[field_name] = {
                    "data_type": data_type,
                    "indexed": indexed
                }
    
    # Add vector information if available
    if vectors_info:
        for vec_name, vec_data in vectors_info.items():
            field_name = f"vector_{vec_name}"
            fields[field_name] = {
                "data_type": "vector",
                "dimensions": vec_data.get("dimensions", "Unknown"),
                "distance": vec_data.get("distance", "Unknown")
            }
    
    return fields

async def introspect_slack(source_id: str, uri: str, version: str = "1.0.0"):
    """
    Introspect Slack API and store its schema in the registry
    
    Args:
        source_id: Unique identifier for this data source
        uri: Slack MCP server URL
        version: Version for this data source
    """
    logger.info(f"Introspecting Slack API: {source_id}")
    
    # Register the data source
    upsert_data_source(source_id, uri, "slack", version)
    
    try:
        # Load user credentials from the credentials file
        home_dir = str(Path.home())
        credentials_file = os.path.join(home_dir, ".data-connector", "slack_credentials.json")
        
        if not os.path.exists(credentials_file):
            logger.warning(f"Slack credentials file not found: {credentials_file}")
            return
            
        with open(credentials_file, 'r') as f:
            credentials = json.load(f)
            
        # Extract user_id and workspace_id
        user_id = credentials.get('user_id')
        workspaces = credentials.get('workspaces', [])
        
        if not user_id or not workspaces:
            logger.warning("Missing user_id or workspaces in Slack credentials")
            return
            
        # Find default workspace
        workspace_id = None
        workspace_name = "Unknown"
        for ws in workspaces:
            if ws.get('is_default'):
                workspace_id = ws.get('id')
                workspace_name = ws.get('name', workspace_name)
                break
                
        if not workspace_id and workspaces:
            # Use the first workspace if no default is specified
            workspace_id = workspaces[0].get('id')
            workspace_name = workspaces[0].get('name', 'Unknown')
            
        if not workspace_id:
            logger.warning("No workspace_id found in Slack credentials")
            return
            
        logger.info(f"Using Slack workspace: {workspace_name} (ID: {workspace_id})")
        
        # Initialize Slack adapter with the MCP URL and user/workspace IDs
        # These IDs are important for accessing user token capabilities
        adapter = slack.SlackAdapter(
            uri,
            user_id=user_id,
            workspace_id=workspace_id
        )
        
        # Test connection - this will ensure token is obtained
        if not await adapter.is_connected():
            logger.warning(f"Failed to connect to Slack MCP server at {uri}")
            return
        
        logger.info(f"Successfully connected to Slack MCP server")
        
        # Get schema metadata using the adapter's introspect_schema method
        # The adapter will use both bot and user tokens as appropriate
        documents = await adapter.introspect_schema()
        
        # Process the schema documents and store them in the registry
        workspace_meta = {}
        channels_meta = {}
        query_capabilities = {}
        
        logger.info(f"Got {len(documents)} schema documents from Slack")
        
        for doc in documents:
            doc_id = doc.get("id", "")
            content = doc.get("content", "")
            
            if doc_id == "slack:workspace":
                # Store workspace information
                workspace_meta["workspace"] = {
                    "raw_content": content,
                    "type": "workspace"
                }
                # Store as a special "table" in the registry
                upsert_table_meta(source_id, "_workspace_info", workspace_meta, version)
                logger.info(f"  - Added workspace information")
                
            elif doc_id == "slack:channels":
                # Store channels information
                channels_meta["channels"] = {
                    "raw_content": content,
                    "type": "channels_list"
                }
                # Store as a special "table" in the registry
                upsert_table_meta(source_id, "_channels", channels_meta, version)
                logger.info(f"  - Added channels list")
                
            elif doc_id.startswith("slack:channel:"):
                # Process individual channel information
                channel_id = doc_id.split(":", 2)[2]
                channel_data = {
                    "raw_content": content,
                    "type": "channel",
                    "channel_id": channel_id
                }
                # Store each channel as a "table" in the registry
                upsert_table_meta(source_id, f"channel_{channel_id}", channel_data, version)
                logger.info(f"  - Added channel: {channel_id}")
                
            elif doc_id == "slack:query_capabilities" or doc_id == "slack:semantic_search":
                # Store query capabilities information
                query_part = doc_id.split(":", 1)[1]
                query_capabilities[query_part] = {
                    "raw_content": content,
                    "type": "query_info"
                }
                # Store as a special "table" in the registry
                upsert_table_meta(source_id, f"_query_{query_part}", {
                    "raw_content": content,
                    "type": "query_info"
                }, version)
                logger.info(f"  - Added query info: {query_part}")
        
        # Store a summary of available channels for easier querying
        try:
            # Get channels directly using adapter's _invoke_tool method
            channels_result = await adapter._invoke_tool("slack_list_channels")
            channels = channels_result.get("channels", [])
            
            # Create a summary of channels with membership status
            channels_summary = {
                "total_count": len(channels),
                "channels": {}
            }
            
            # Store basic channel info
            for channel in channels:
                channel_id = channel.get("id")
                is_member = channel.get("is_member", False)
                channels_summary["channels"][channel_id] = {
                    "name": channel.get("name", ""),
                    "is_member": is_member,
                    "topic": channel.get("topic", {}).get("value", ""),
                    "purpose": channel.get("purpose", {}).get("value", ""),
                    "num_members": channel.get("num_members", 0)
                }
            
            # Store the channels summary
            upsert_table_meta(source_id, "_channels_summary", {
                "raw_content": json.dumps(channels_summary, indent=2),
                "type": "channels_summary",
                "data": channels_summary
            }, version)
            logger.info(f"  - Added channels summary with {len(channels)} channels")
        
        except Exception as e:
            logger.warning(f"Could not create channels summary: {str(e)}")
        
        logger.info(f"Slack introspection for {source_id} completed successfully")
    
    except Exception as e:
        logger.error(f"Error introspecting Slack {source_id}: {str(e)}")
        raise

async def run_introspection(
    data_sources: List[Dict[str, str]]
):
    """
    Run introspection for all provided data sources
    
    Args:
        data_sources: List of data source configurations
    """
    # Initialize the registry database
    init_registry()
    
    tasks = []
    
    # Create tasks for each data source
    for source in data_sources:
        source_id = source.get("id")
        uri = source.get("uri")
        source_type = source.get("type", "").lower()
        version = source.get("version", "1.0.0")
        
        if not source_id or not uri:
            logger.warning(f"Skipping data source with missing id or uri: {source}")
            continue
        
        if source_type == "postgres":
            tasks.append(introspect_postgres(source_id, uri, version))
        elif source_type == "mongodb":
            tasks.append(introspect_mongodb(source_id, uri, version))
        elif source_type == "qdrant":
            tasks.append(introspect_qdrant(source_id, uri, version))
        elif source_type == "slack":
            tasks.append(introspect_slack(source_id, uri, version))
        else:
            logger.warning(f"Unsupported data source type: {source_type}")
    
    # Run all introspection tasks
    await asyncio.gather(*tasks)
    logger.info("All introspection tasks completed")

if __name__ == "__main__":
    # Load configuration from config.yaml
    config_path = os.path.join(str(Path.home()), ".data-connector", "config.yaml")
    data_sources = []
    
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
                
            # Create data source entries from config
            if "postgres" in config and "uri" in config["postgres"]:
                data_sources.append({
                    "id": "postgres_main",
                    "uri": config["postgres"]["uri"],
                    "type": "postgres",
                    "version": "1.0.0"
                })
                
            if "mongodb" in config and "uri" in config["mongodb"]:
                data_sources.append({
                    "id": "mongodb_main",
                    "uri": config["mongodb"]["uri"],
                    "type": "mongodb",
                    "version": "1.0.0"
                })
                
            if "qdrant" in config and "uri" in config["qdrant"]:
                data_sources.append({
                    "id": "qdrant_main",
                    "uri": config["qdrant"]["uri"],
                    "type": "qdrant",
                    "version": "1.0.0"
                })
                
            if "slack" in config and "uri" in config["slack"]:
                data_sources.append({
                    "id": "slack_main",
                    "uri": config["slack"]["uri"],
                    "type": "slack",
                    "version": "1.0.0"
                })
                
            logger.info(f"Loaded {len(data_sources)} data sources from config")
        except Exception as e:
            logger.error(f"Error loading config: {str(e)}")
            # Use default data sources from below
    
    # If no config file or loading failed, use these defaults
    if not data_sources:
        data_sources = [
            {
                "id": "postgres_main",
                "uri": "postgresql://dataconnector:dataconnector@localhost:6000/dataconnector",
                "type": "postgres",
                "version": "1.0.0"
            },
            {
                "id": "mongodb_main",
                "uri": "mongodb://dataconnector:dataconnector@localhost:27000/dataconnector_mongo",
                "type": "mongodb",
                "version": "1.0.0"
            }
        ]
    
    # Run the introspection
    logger.info(f"Running introspection for {len(data_sources)} data sources...")
    asyncio.run(run_introspection(data_sources)) 
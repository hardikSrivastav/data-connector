#!/usr/bin/env python3
"""
Integration module for the schema registry.
This provides higher-level functions for interacting with the schema registry
that are useful for the database classification module and cross-db orchestrator.
"""
import logging
from typing import Dict, List, Any, Optional, Set, Tuple
import json

from . import (
    init_registry,
    list_data_sources,
    get_data_source,
    list_tables,
    get_table_schema,
    get_ontology_mapping,
    list_ontology_entities,
    search_tables_by_name,
    search_schema_content
)

# Configure logging
logger = logging.getLogger(__name__)

class SchemaRegistryClient:
    """
    Client for the schema registry that provides high-level functionality
    for the database classification module and cross-db orchestrator.
    """
    
    def __init__(self):
        """Initialize the client and ensure the registry is initialized"""
        init_registry()
    
    def get_source_by_id(self, source_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific data source by ID
        
        Args:
            source_id: ID of the data source to retrieve
            
        Returns:
            Data source information including type and connection info, or None if not found
        """
        source = get_data_source(source_id)
        if not source:
            return None
            
        # Get connection URI from settings based on database type
        connection_uri = self._get_connection_uri_for_source(source)
        
        # Add connection details to the source
        source["connection_uri"] = connection_uri
        source["connection_details"] = {
            "has_connection": connection_uri is not None,
            "source_type": source.get("type", "unknown")
        }
            
        return source
    
    def _get_connection_uri_for_source(self, source: Dict[str, Any]) -> Optional[str]:
        """
        Get connection URI for a source based on its type and configuration
        
        Args:
            source: Source configuration
            
        Returns:
            Connection URI if available
        """
        try:
            from ...config.settings import Settings
            settings = Settings()
            
            db_type = source.get("type", "").lower()
            
            # Map database types to connection URIs from settings
            if db_type in ["postgres", "postgresql"]:
                return settings.connection_uri
            elif db_type == "mongodb":
                return getattr(settings, 'MONGODB_URI', None) or "mongodb://localhost:27017/ceneca"
            elif db_type == "qdrant":
                return getattr(settings, 'QDRANT_URL', None) or "http://localhost:6333"
            elif db_type == "slack":
                # Slack uses token-based authentication
                slack_token = getattr(settings, 'SLACK_BOT_TOKEN', None)
                if slack_token:
                    return f"slack://token:{slack_token}"
                return None
            elif db_type == "shopify":
                # Shopify uses API key authentication
                shopify_key = getattr(settings, 'SHOPIFY_API_KEY', None)
                shopify_secret = getattr(settings, 'SHOPIFY_API_SECRET', None)
                if shopify_key and shopify_secret:
                    return f"shopify://{shopify_key}:{shopify_secret}"
                return None
            elif db_type == "ga4":
                # GA4 uses service account authentication
                ga4_credentials = getattr(settings, 'GA4_CREDENTIALS_PATH', None)
                if ga4_credentials:
                    return f"ga4://credentials:{ga4_credentials}"
                return None
            else:
                logger.warning(f"Unknown database type for connection URI: {db_type}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting connection URI for source type {source.get('type')}: {e}")
            return None
    
    def get_data_source(self, source_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific data source by ID (alias for get_source_by_id for compatibility)
        
        Args:
            source_id: ID of the data source to retrieve
            
        Returns:
            Data source information, or None if not found
        """
        return get_data_source(source_id)
    
    def get_all_sources(self) -> List[Dict[str, Any]]:
        """Get all data sources in the registry"""
        return list_data_sources()
    
    def get_all_tables_by_source(self) -> Dict[str, List[str]]:
        """Get all tables grouped by data source"""
        sources = list_data_sources()
        result = {}
        
        for source in sources:
            source_id = source.get("id")
            tables = list_tables(source_id)
            result[source_id] = tables
        
        return result
    
    def list_tables(self, source_id: str) -> List[str]:
        """
        List all tables for a given data source
        
        Args:
            source_id: The data source ID
            
        Returns:
            List of table names
        """
        return list_tables(source_id)
    
    def get_table_schema(self, source_id: str, table_name: str) -> Optional[Dict[str, Any]]:
        """
        Get schema for a specific table
        
        Args:
            source_id: The data source ID
            table_name: The table name
            
        Returns:
            Table schema information, or None if not found
        """
        return get_table_schema(source_id, table_name)
    
    def get_tables_containing_field(self, field_name: str) -> List[Tuple[str, str]]:
        """
        Get all tables that contain a specific field name
        
        Args:
            field_name: The name of the field to search for
            
        Returns:
            List of (source_id, table_name) tuples that contain the field
        """
        matching_tables = []
        tables_by_source = self.get_all_tables_by_source()
        
        for source_id, tables in tables_by_source.items():
            for table_name in tables:
                schema = get_table_schema(source_id, table_name)
                if not schema:
                    continue
                
                fields = schema.get("schema", {}).get("fields", {})
                if field_name in fields:
                    matching_tables.append((source_id, table_name))
        
        return matching_tables
    
    def search_for_schema_content(self, text: str) -> List[Tuple[str, str]]:
        """
        Search for tables containing specific text in their schema
        
        Args:
            text: The text to search for
            
        Returns:
            List of (source_id, table_name) tuples
        """
        results = search_schema_content(text)
        return [(item["source_id"], item["table_name"]) for item in results]
    
    def search_for_table_name(self, name_pattern: str) -> List[Tuple[str, str]]:
        """
        Search for tables with names matching a pattern
        
        Args:
            name_pattern: The name pattern to search for
            
        Returns:
            List of (source_id, table_name) tuples
        """
        results = search_tables_by_name(name_pattern)
        return [(item["source_id"], item["table_name"]) for item in results]
    
    def get_ontology_to_tables_mapping(self) -> Dict[str, List[str]]:
        """
        Get a mapping of business entities to tables
        
        Returns:
            Dictionary mapping entity names to lists of "source_id.table_name" strings
        """
        entities = list_ontology_entities()
        return {entity["entity_name"]: entity["source_tables"] for entity in entities}
    
    def get_recommended_sources_for_query(self, query: str) -> Set[str]:
        """
        Recommend data sources that might be relevant for a given query
        This is a simple implementation that can be enhanced with more sophisticated logic.
        
        Args:
            query: The natural language query to analyze
            
        Returns:
            Set of source_ids that might be relevant
        """
        recommended_sources = set()
        
        # 1. Look for explicit mentions of tables
        words = [w.lower() for w in query.split()]
        tables_by_source = self.get_all_tables_by_source()
        
        for source_id, tables in tables_by_source.items():
            for table in tables:
                if table.lower() in words:
                    logger.info(f"Found direct table mention: {table}")
                    recommended_sources.add(source_id)
        
        # 2. Look for mentions of business entities from ontology
        ontology_mapping = self.get_ontology_to_tables_mapping()
        for entity, table_refs in ontology_mapping.items():
            if entity.lower() in query.lower():
                logger.info(f"Found ontology entity mention: {entity}")
                for table_ref in table_refs:
                    try:
                        source_id = table_ref.split(".", 1)[0]
                        # Verify that the source_id still exists
                        if get_data_source(source_id):
                            recommended_sources.add(source_id)
                    except (ValueError, IndexError):
                        logger.warning(f"Invalid table reference in ontology: {table_ref}")
        
        # 3. If no explicit mentions found, search for implicit connections
        if not recommended_sources:
            # If query contains keywords that suggest certain data source types
            keywords_to_db_types = {
                "document": ["mongodb"],
                "collection": ["mongodb"],
                "embed": ["qdrant"],
                "vector": ["qdrant"],
                "similarity": ["qdrant"],
                "table": ["postgres"],
                "row": ["postgres"],
                "channel": ["slack"],
                "message": ["slack"],
                "chat": ["slack"],
                # GA4-specific keywords
                "analytics": ["ga4"],
                "session": ["ga4"],
                "pageview": ["ga4"],
                "event": ["ga4"],
                "dimension": ["ga4"],
                "metric": ["ga4"],
                "visitor": ["ga4"],
                "traffic": ["ga4"],
                "user": ["postgres", "ga4"],
                "conversion": ["ga4"],
                # Shopify-specific keywords
                "order": ["shopify"],
                "product": ["shopify", "postgres"],
                "customer": ["shopify", "postgres"],
                "inventory": ["shopify"],
                "checkout": ["shopify"],
                "cart": ["shopify"],
                "purchase": ["shopify"],
                "sale": ["shopify"],
                "revenue": ["shopify"],
                "ecommerce": ["shopify"],
                "e-commerce": ["shopify"],
                "shopify": ["shopify"],
                "store": ["shopify"],
                "merchant": ["shopify"],
                "variant": ["shopify"],
                "fulfillment": ["shopify"],
                "shipping": ["shopify"],
                "billing": ["shopify"],
                "payment": ["shopify"],
                "discount": ["shopify"],
                "coupon": ["shopify"]
            }
            
            # Check for keyword matches
            for keyword, db_types in keywords_to_db_types.items():
                if keyword in query.lower():
                    # Add sources of matching types
                    for source in list_data_sources():
                        if source["type"] in db_types:
                            recommended_sources.add(source["id"])
        
        # 4. If still empty, return all sources
        if not recommended_sources:
            logger.info("No specific database indicators found, recommending all sources")
            recommended_sources = {source["id"] for source in list_data_sources()}
        
        return recommended_sources
    
    def get_schema_summary_for_sources(self, source_ids: List[str]) -> str:
        """
        Generate a summary of the schema for the specified data sources
        
        Args:
            source_ids: List of source IDs to include in the summary
            
        Returns:
            String containing a summary of the schema
        """
        summary = []
        
        for source_id in source_ids:
            source = get_data_source(source_id)
            if not source:
                continue
                
            source_type = source["type"]
            tables = list_tables(source_id)
            
            summary.append(f"\nDATA SOURCE: {source_id} (Type: {source_type})")
            
            for table_name in tables:
                schema = get_table_schema(source_id, table_name)
                if not schema:
                    continue
                    
                fields = schema.get("schema", {}).get("fields", {})
                
                summary.append(f"\n  TABLE/COLLECTION: {table_name}")
                summary.append(f"  FIELDS:")
                
                for field_name, field_info in fields.items():
                    field_type = field_info.get("data_type", "unknown")
                    constraints = []
                    
                    if field_info.get("primary_key"):
                        constraints.append("PRIMARY KEY")
                    if not field_info.get("nullable", True):
                        constraints.append("NOT NULL")
                        
                    constraints_str = f" ({', '.join(constraints)})" if constraints else ""
                    summary.append(f"    - {field_name} ({field_type}){constraints_str}")
        
        return "\n".join(summary)
    
    def _map_source_id(self, source_id: str) -> str:
        """
        Map collection/table-specific source IDs to database-level source IDs.
        
        The planning agent generates specific source IDs like:
        - mongodb:collection:sample_products -> mongodb_main
        - postgres:table:order_items -> postgres_main
        
        Args:
            source_id: Original source ID from the planning agent
            
        Returns:
            Mapped database-level source ID
        """
        # If it's already a simple database-level ID, return as-is
        if ":" not in source_id:
            return source_id
        
        # Parse the source_id format: {db_type}:{object_type}:{object_name}
        parts = source_id.split(":")
        if len(parts) >= 2:
            db_type = parts[0]
            
            # Map to database-level source IDs based on known patterns
            if db_type == "mongodb":
                return "mongodb_main"
            elif db_type == "postgres":
                return "postgres_main"
            elif db_type == "qdrant":
                # Special case: qdrant might have collection-specific sources
                if len(parts) >= 3:
                    collection_name = parts[2]
                    if collection_name in ["product_catalog", "products"]:
                        return "qdrant_products"
                    else:
                        return "qdrant_main"
                return "qdrant_main"
            elif db_type == "slack":
                return "slack_main"
            elif db_type == "shopify":
                return "shopify_main"
            elif db_type == "ga4":
                return "ga4_489665507"  # Or could be dynamically determined
            else:
                # For unknown types, try {db_type}_main
                return f"{db_type}_main"
        
        # If we can't parse it, return the original
        return source_id

    def validate_sql_query(self, source_id: str, sql_query: str) -> Dict[str, Any]:
        """
        Validate a SQL query against the schema registry
        
        Args:
            source_id: The data source ID (can be detailed like 'postgres:table:orders' or simple like 'postgres_main')
            sql_query: The SQL query to validate
            
        Returns:
            Dictionary with validation results
        """
        try:
            # Map detailed source ID to database-level source ID
            mapped_source_id = self._map_source_id(source_id)
            
            # Check if mapped source exists
            source = self.get_data_source(mapped_source_id)
            if not source:
                return {
                    "valid": False,
                    "errors": [f"Data source '{mapped_source_id}' (from '{source_id}') not found in registry"]
                }
            
            # For now, return a basic validation that just checks source existence
            # In the future, this could parse the SQL and validate table/column references
            return {
                "valid": True,
                "errors": [],
                "warnings": []
            }
            
        except Exception as e:
            return {
                "valid": False, 
                "errors": [f"Validation error: {str(e)}"]
            }
    
    def validate_mongo_collection(self, source_id: str, collection_name: str) -> bool:
        """
        Validate that a MongoDB collection exists in the schema registry
        
        Args:
            source_id: The data source ID (can be detailed like 'mongodb:collection:sample_products' or simple like 'mongodb_main')
            collection_name: The collection name to validate
            
        Returns:
            True if collection exists, False otherwise
        """
        try:
            # Map detailed source ID to database-level source ID
            mapped_source_id = self._map_source_id(source_id)
            
            # Check if mapped source exists
            source = self.get_data_source(mapped_source_id)
            if not source:
                logger.warning(f"Data source '{mapped_source_id}' (from '{source_id}') not found in registry")
                return False
            
            # Check if it's a MongoDB source
            if source.get("type") != "mongodb":
                logger.warning(f"Data source '{mapped_source_id}' is not a MongoDB source")
                return False
            
            # Check if collection exists in the schema
            tables = self.list_tables(mapped_source_id)
            collection_exists = collection_name in tables
            
            if not collection_exists:
                logger.warning(f"Collection '{collection_name}' not found in source '{mapped_source_id}'. Available collections: {tables}")
            
            return collection_exists
            
        except Exception as e:
            logger.error(f"Error validating MongoDB collection '{collection_name}' for source '{source_id}': {e}")
            return False
    
    def validate_qdrant_collection(self, source_id: str, collection_name: str) -> bool:
        """
        Validate that a Qdrant collection exists in the schema registry
        
        Args:
            source_id: The data source ID (can be detailed like 'qdrant:collection:products' or simple like 'qdrant_main')
            collection_name: The collection name to validate
            
        Returns:
            True if collection exists, False otherwise
        """
        try:
            # Map detailed source ID to database-level source ID
            mapped_source_id = self._map_source_id(source_id)
            
            # Check if mapped source exists
            source = self.get_data_source(mapped_source_id)
            if not source:
                logger.warning(f"Data source '{mapped_source_id}' (from '{source_id}') not found in registry")
                return False
            
            # Check if it's a Qdrant source
            if source.get("type") != "qdrant":
                logger.warning(f"Data source '{mapped_source_id}' is not a Qdrant source")
                return False
            
            # Check if collection exists in the schema
            tables = self.list_tables(mapped_source_id)
            collection_exists = collection_name in tables
            
            if not collection_exists:
                logger.warning(f"Collection '{collection_name}' not found in source '{mapped_source_id}'. Available collections: {tables}")
            
            return collection_exists
            
        except Exception as e:
            logger.error(f"Error validating Qdrant collection '{collection_name}' for source '{source_id}': {e}")
            return False
    
    def get_source_details(self, source_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a data source including connection details.
        
        Args:
            source_id: The data source ID
            
        Returns:
            Detailed source information including connection details, or None if not found
        """
        source = self.get_source_by_id(source_id)
        if not source:
            return None
            
        # Import settings to get connection URIs
        try:
            from ...config.settings import Settings
            settings = Settings()
            
            # Map source types to settings properties
            db_type = source.get("type", "").lower()
            connection_uri = None
            
            if db_type in ["postgres", "postgresql"]:
                connection_uri = settings.db_dsn
            elif db_type in ["mongo", "mongodb"]:
                connection_uri = settings.MONGODB_URI
            elif db_type == "qdrant":
                connection_uri = settings.QDRANT_URI
            elif db_type == "slack":
                connection_uri = settings.SLACK_URI
            elif db_type == "shopify":
                connection_uri = settings.SHOPIFY_URI
            elif db_type == "ga4":
                if settings.GA4_KEY_FILE and settings.GA4_PROPERTY_ID:
                    connection_uri = f"ga4://{settings.GA4_PROPERTY_ID}"
            
            # Add connection URI to source details
            if connection_uri:
                source["connection_uri"] = connection_uri
                logger.info(f"Added connection URI for {source_id} ({db_type}): {connection_uri[:50]}...")
            else:
                logger.warning(f"No connection URI available for {source_id} ({db_type})")
                
        except Exception as e:
            logger.error(f"Error getting connection details for {source_id}: {e}")
            
        return source


# Singleton instance for easy import
registry_client = SchemaRegistryClient()

if __name__ == "__main__":
    # Test the client
    client = SchemaRegistryClient()
    
    # Get all sources
    sources = client.get_all_sources()
    print(f"Data sources: {json.dumps(sources, indent=2)}")
    
    # Get all tables by source
    tables_by_source = client.get_all_tables_by_source()
    print(f"Tables by source: {json.dumps(tables_by_source, indent=2)}")
    
    # Test query analysis
    test_query = "Find customers who made purchases in the last month"
    recommended_sources = client.get_recommended_sources_for_query(test_query)
    print(f"Recommended sources for query '{test_query}': {recommended_sources}")
    
    # Get schema summary
    schema_summary = client.get_schema_summary_for_sources(list(recommended_sources))
    print(f"Schema summary:\n{schema_summary}") 
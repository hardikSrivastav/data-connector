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
            
        # Extract the connection info from the config
        import os
        import yaml
        from pathlib import Path
        
        # Get config path from environment or use default
        config_path = os.environ.get(
            "DATA_CONNECTOR_CONFIG",
            str(Path.home() / ".data-connector" / "config.yaml")
        )
        
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
                
            # Get connection info from config
            source_type = source.get("type", "")
            connection_info = config.get(source_type, {})
            
            # Add the connection info to the source
            source["connection_info"] = connection_info
            
            return source
            
        except Exception as e:
            logger.error(f"Error getting connection info for source {source_id}: {e}")
            # Return basic source info without connection details
            return source
    
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
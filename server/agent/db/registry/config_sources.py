#!/usr/bin/env python3
"""
Configuration for data sources to be registered in the schema registry.
This script gets connection information from the user's config.yaml file using
an intelligent multi-instance parser that automatically detects and handles
multiple database instances of the same type.
"""
import sys
from pathlib import Path
import os
import logging

# Add parent directory to path to import config modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import the config loader and multi-instance parser
try:
    from agent.config.config_loader import load_config, get_database_uri
    from .multi_instance_parser import parse_multi_instance_config
except ImportError:
    logger.error("Failed to import config_loader or multi_instance_parser. Make sure the modules are available.")
    # Define stubs for when modules can't be imported
    def load_config(): return {}
    def get_database_uri(db_type): return None
    def parse_multi_instance_config(config): 
        class MockParser:
            def to_schema_registry_format(self): return []
            def get_summary(self): return {}
        return MockParser()

# Load YAML configuration
yaml_config = load_config()
logger.debug(f"Loaded YAML config")

# Parse configuration using intelligent multi-instance parser
config_parser = parse_multi_instance_config(yaml_config)
logger.info(f"Configuration parsing summary: {config_parser.get_summary()}")

def get_data_sources():
    """
    Get data sources configuration from the user's config.yaml using intelligent
    multi-instance parser that automatically detects single vs multiple instances.
    
    Returns:
        List of data source configurations for local development
    """
    # Use the intelligent parser to handle all database types automatically
    sources = config_parser.to_schema_registry_format()
    
    # Log details about what was parsed
    try:
        summary = config_parser.get_summary()
        logger.info(f"Parsed {summary['total_instances']} database instances across {summary['database_types']} types")
        
        if summary.get('multi_instance_types'):
            logger.info(f"Multi-instance database types: {summary['multi_instance_types']}")
        
        if summary.get('single_instance_types'):
            logger.info(f"Single-instance database types: {summary['single_instance_types']}")
    except Exception as e:
        logger.warning(f"Could not get parser summary: {e}")
    
    return sources

def get_docker_data_sources():
    """
    Get data sources configuration for Docker environment.
    
    For Docker deployments, we typically use internal Docker network hostnames
    and default configurations. This function provides backward compatibility
    for existing Docker setups while still supporting multi-instance configurations.
    
    Returns:
        List of data source configurations for Docker
    """
    # First, get the user's configured sources using the intelligent parser
    user_sources = config_parser.to_schema_registry_format()
    
    # For Docker, we may want to override certain URIs with Docker-specific hostnames
    # This maintains backward compatibility with existing Docker deployments
    docker_sources = []
    
    # Add Docker-specific default sources if the database types are configured
    if 'postgres' in yaml_config:
        docker_sources.extend([
            {
                "id": "postgres_main",
                "uri": "postgresql://dataconnector:dataconnector@data-connector-postgres:5432/dataconnector",
                "type": "postgres",
                "version": "1.0.0"
            },
            {
                "id": "postgres_slack",
                "uri": "postgresql://slackoauth:slackoauth@slack-mcp-postgres:5432/slackoauth",
                "type": "postgres",
                "version": "1.0.0"
            }
        ])
    
    if 'mongodb' in yaml_config:
        docker_sources.append({
            "id": "mongodb_main",
            "uri": "mongodb://dataconnector:dataconnector@data-connector-mongodb:27017/dataconnector_mongo",
            "type": "mongodb",
            "version": "1.0.0"
        })
    
    if 'qdrant' in yaml_config:
        docker_sources.extend([
            {
                "id": "qdrant_main",
                "uri": "http://data-connector-qdrant:6333",
                "type": "qdrant",
                "version": "1.0.0"
            },
            {
                "id": "qdrant_slack",
                "uri": "http://slack-message-qdrant:6333",
                "type": "qdrant",
                "version": "1.0.0"
            }
        ])
    
    # For other database types (Shopify, PayU, etc.), use the user's configuration as-is
    # since these are typically external services that don't need Docker hostname mapping
    external_db_types = {'shopify', 'uniware', 'payu', 'easebuzz', 'shiprocket', 'ga4', 'slack'}
    for source in user_sources:
        if source.get('type') in external_db_types:
            docker_sources.append(source)
    
    logger.info(f"Generated {len(docker_sources)} Docker data sources")
    return docker_sources

# Dynamic generation of data sources from config
DATA_SOURCES = get_data_sources()
DOCKER_DATA_SOURCES = get_docker_data_sources() 
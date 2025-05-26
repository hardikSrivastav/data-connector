#!/usr/bin/env python3
"""
Configuration for data sources to be registered in the schema registry.
This script gets connection information from the user's config.yaml file.
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

# Import the config loader
try:
    from agent.config.config_loader import load_config, get_database_uri
except ImportError:
    logger.error("Failed to import config_loader. Make sure the module is available.")
    # Define stub for when the module can't be imported
    def load_config(): return {}
    def get_database_uri(db_type): return None

# Load YAML configuration
yaml_config = load_config()
logger.debug(f"Loaded YAML config")

def get_data_sources():
    """
    Get data sources configuration from the user's config.yaml
    
    Returns:
        List of data source configurations for local development
    """
    sources = []
    
    # PostgreSQL
    if 'postgres' in yaml_config:
        postgres_uri = yaml_config.get('postgres', {}).get('uri')
        if postgres_uri:
            sources.append({
                "id": "postgres_main",
                "uri": postgres_uri,
                "type": "postgres",
                "version": "1.0.0"
            })
    
    # MongoDB
    if 'mongodb' in yaml_config:
        mongodb_uri = yaml_config.get('mongodb', {}).get('uri')
        if mongodb_uri:
            sources.append({
                "id": "mongodb_main",
                "uri": mongodb_uri,
                "type": "mongodb",
                "version": "1.0.0"
            })
    
    # Qdrant
    if 'qdrant' in yaml_config:
        qdrant_uri = yaml_config.get('qdrant', {}).get('uri')
        if qdrant_uri:
            sources.append({
                "id": "qdrant_main",
                "uri": qdrant_uri,
                "type": "qdrant",
                "version": "1.0.0"
            })
    
    # Slack
    if 'slack' in yaml_config:
        slack_uri = yaml_config.get('slack', {}).get('uri')
        if slack_uri:
            sources.append({
                "id": "slack_main",
                "uri": slack_uri,
                "type": "slack", 
                "version": "1.0.0"
            })
    
    # Shopify
    if 'shopify' in yaml_config:
        shopify_uri = yaml_config.get('shopify', {}).get('uri')
        if shopify_uri:
            sources.append({
                "id": "shopify_main",
                "uri": shopify_uri,
                "type": "shopify",
                "version": "1.0.0"
            })
    
    return sources

def get_docker_data_sources():
    """
    Get data sources configuration for Docker environment
    
    Returns:
        List of data source configurations for Docker
    """
    # In Docker, we use internal Docker network hostnames
    sources = []
    
    # PostgreSQL
    if 'postgres' in yaml_config:
        sources.append({
            "id": "postgres_main",
            "uri": "postgresql://dataconnector:dataconnector@data-connector-postgres:5432/dataconnector",
            "type": "postgres",
            "version": "1.0.0"
        })
    
    # MongoDB
    if 'mongodb' in yaml_config:
        sources.append({
            "id": "mongodb_main",
            "uri": "mongodb://dataconnector:dataconnector@data-connector-mongodb:27017/dataconnector_mongo",
            "type": "mongodb",
            "version": "1.0.0"
        })
    
    # Qdrant
    if 'qdrant' in yaml_config:
        sources.append({
            "id": "qdrant_main",
            "uri": "http://data-connector-qdrant:6333",
            "type": "qdrant",
            "version": "1.0.0"
        })
    
    # Slack MCP Postgres
    if 'postgres' in yaml_config:
        sources.append({
            "id": "postgres_slack",
            "uri": "postgresql://slackoauth:slackoauth@slack-mcp-postgres:5432/slackoauth",
            "type": "postgres",
            "version": "1.0.0"
        })
    
    # Slack Qdrant
    if 'qdrant' in yaml_config:
        sources.append({
            "id": "qdrant_slack",
            "uri": "http://slack-message-qdrant:6333",
            "type": "qdrant",
            "version": "1.0.0"
        })
    
    # Shopify
    if 'shopify' in yaml_config:
        shopify_uri = yaml_config.get('shopify', {}).get('uri')
        if shopify_uri:
            sources.append({
                "id": "shopify_main",
                "uri": shopify_uri,
                "type": "shopify",
                "version": "1.0.0"
            })
    
    return sources

# Dynamic generation of data sources from config
DATA_SOURCES = get_data_sources()
DOCKER_DATA_SOURCES = get_docker_data_sources() 
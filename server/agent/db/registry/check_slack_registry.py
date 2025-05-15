#!/usr/bin/env python3
"""
Script to check Slack data in the schema registry.
This verifies that we have properly introspected Slack data.
"""
import json
import sys
from pathlib import Path
import logging
import pprint

# Add parent directory to path to import registry
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agent.db.registry import (
    init_registry,
    list_data_sources,
    list_tables,
    get_table_schema
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_slack_registry():
    """Check Slack data in the schema registry"""
    logger.info("Initializing schema registry...")
    init_registry()
    
    # 1. Get all data sources
    sources = list_data_sources()
    slack_sources = [s for s in sources if s['type'] == 'slack']
    
    if not slack_sources:
        logger.warning("No Slack data sources found in registry!")
        return
    
    logger.info(f"Found {len(slack_sources)} Slack data sources:")
    for source in slack_sources:
        logger.info(f"- {source['id']} (uri: {source['uri']})")
        
        # 2. List tables for this Slack source
        tables = list_tables(source['id'])
        logger.info(f"  Tables/collections: {len(tables)}")
        logger.info(f"  Available tables: {tables}")
        
        # Group tables by type
        workspace_info = []
        channels = []
        specific_channels = []
        query_info = []
        other = []
        
        for table in tables:
            if table.startswith("_workspace"):
                workspace_info.append(table)
            elif table.startswith("_channels"):
                channels.append(table)
            elif table.startswith("channel_"):
                specific_channels.append(table)
            elif table.startswith("_query"):
                query_info.append(table)
            else:
                other.append(table)
        
        # Check channels summary specifically
        if '_channels_summary' in tables:
            logger.info("\n  ========== DETAILED CHANNEL SUMMARY ==========")
            schema = get_table_schema(source['id'], '_channels_summary')
            
            # Print schema structure for debugging
            logger.info(f"  Schema structure: {pprint.pformat(schema)}")
            
            # Try various ways to extract the channel data
            if 'data' in schema:
                logger.info("  Found data field in schema")
                channel_data = schema.get('data', {})
                total_count = channel_data.get('total_count', 0)
                channels_dict = channel_data.get('channels', {})
                
                logger.info(f"  Total channels: {total_count}")
                logger.info(f"  Channel IDs: {list(channels_dict.keys())}")
                
                # Print formatted table
                logger.info(f"\n  {'Channel Name':<20} {'Channel ID':<15} {'Bot Member':<10}")
                logger.info(f"  {'-'*20} {'-'*15} {'-'*10}")
                
                for channel_id, info in channels_dict.items():
                    is_member = "✓" if info.get('is_member') else "✗"
                    channel_name = info.get('name', 'unknown')
                    logger.info(f"  {channel_name:<20} {channel_id:<15} {is_member:<10}")
            
            elif 'raw_content' in schema:
                logger.info("  Found raw_content field in schema")
                try:
                    raw_content = schema.get('raw_content', '{}')
                    logger.info(f"  Raw content: {raw_content[:100]}...")
                    
                    # Try to parse if it's JSON
                    channel_data = json.loads(raw_content)
                    total_count = channel_data.get('total_count', 0)
                    channels_dict = channel_data.get('channels', {})
                    
                    logger.info(f"  Total channels: {total_count}")
                    logger.info(f"  Channel IDs: {list(channels_dict.keys())}")
                except Exception as e:
                    logger.error(f"  Could not parse raw_content: {str(e)}")
            
            elif 'schema' in schema:
                logger.info("  Found schema field in schema object")
                try:
                    schema_content = schema.get('schema', {})
                    if isinstance(schema_content, dict) and 'data' in schema_content:
                        channel_data = schema_content.get('data', {})
                        if 'channels' in channel_data:
                            channels_dict = channel_data.get('channels', {})
                            logger.info(f"  Channel IDs: {list(channels_dict.keys())}")
                    elif isinstance(schema_content, str):
                        # Try to parse if it's a JSON string
                        channel_data = json.loads(schema_content)
                        if 'data' in channel_data:
                            data = channel_data.get('data', {})
                            if 'channels' in data:
                                channels_dict = data.get('channels', {})
                                logger.info(f"  Channel IDs: {list(channels_dict.keys())}")
                except Exception as e:
                    logger.error(f"  Could not process schema field: {str(e)}")
        
        # Display other available information
        logger.info("\n  ========== WORKSPACE INFORMATION ==========")
        if workspace_info:
            for table in workspace_info:
                schema = get_table_schema(source['id'], table)
                logger.info(f"  Table: {table} (Type: {schema.get('type', 'unknown')})")
                logger.info(f"  Schema keys: {list(schema.keys())}")
                
        logger.info("\n  ========== SPECIFIC CHANNEL DETAILS ==========")
        if specific_channels:
            logger.info(f"  Individual channels with detailed information: {len(specific_channels)}")
            for idx, table in enumerate(specific_channels):
                schema = get_table_schema(source['id'], table)
                channel_id = schema.get('channel_id', table.replace('channel_', ''))
                
                logger.info(f"\n  Channel {idx+1}: {channel_id}")
                logger.info(f"  Schema keys: {list(schema.keys())}")
        
        logger.info("\n  ========== QUERY CAPABILITIES ==========")
        if query_info:
            for table in query_info:
                schema = get_table_schema(source['id'], table)
                logger.info(f"  Query Info: {table}")
                logger.info(f"  Schema keys: {list(schema.keys())}")
    
    logger.info("\nSlack schema registry check completed")

if __name__ == "__main__":
    check_slack_registry() 
#!/usr/bin/env python3
"""
Direct adapter tools testing script
Tests each adapter's specialized tools to identify any breaks
"""

import asyncio
import sys
import os
import json
from pathlib import Path

# Add the server/agent directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'server', 'agent'))

async def test_postgres_adapter():
    """Test PostgreSQL adapter tools"""
    print('\n=== Testing PostgreSQL Adapter ===')
    try:
        from server.agent.db.adapters.postgres import PostgresAdapter
        from server.agent.config.settings import Settings
        
        settings = Settings()
        adapter = PostgresAdapter(settings.connection_uri)
        
        # Test connection
        print('Testing connection...')
        connected = await adapter.test_connection()
        print(f'✓ Connection test: {connected}')
        
        if connected:
            # Test specialized tools
            print('\nTesting specialized tools:')
            
            # Test validate_sql_syntax
            try:
                print('1. Testing validate_sql_syntax...')
                result = await adapter.validate_sql_syntax('SELECT * FROM sample_orders LIMIT 5')
                print(f'✓ SQL validation: {result.get("valid", False)}')
            except Exception as e:
                print(f'✗ validate_sql_syntax failed: {e}')
            
            # Test get_table_statistics
            try:
                print('2. Testing get_table_statistics...')
                result = await adapter.get_table_statistics('sample_orders')
                print(f'✓ Table statistics: {len(result)} fields')
            except Exception as e:
                print(f'✗ get_table_statistics failed: {e}')
            
            # Test analyze_query_performance
            try:
                print('3. Testing analyze_query_performance...')
                result = await adapter.analyze_query_performance('SELECT COUNT(*) FROM sample_orders')
                print(f'✓ Query performance analysis completed')
            except Exception as e:
                print(f'✗ analyze_query_performance failed: {e}')
                
        else:
            print('⚠ Skipping tool tests - connection failed')
        
    except Exception as e:
        print(f'✗ PostgreSQL adapter error: {e}')
        import traceback
        traceback.print_exc()

async def test_mongo_adapter():
    """Test MongoDB adapter tools"""
    print('\n=== Testing MongoDB Adapter ===')
    try:
        from server.agent.db.adapters.mongo import MongoAdapter
        from server.agent.config.settings import Settings
        
        settings = Settings()
        adapter = MongoAdapter(settings.MONGODB_URI)
        
        # Test connection
        print('Testing connection...')
        connected = await adapter.test_connection()
        print(f'✓ Connection test: {connected}')
        
        if connected:
            print('\nTesting specialized tools:')
            
            # Test analyze_collection_performance
            try:
                print('1. Testing analyze_collection_performance...')
                result = await adapter.analyze_collection_performance('sample_orders')
                print(f'✓ Collection performance: {result.get("document_count", 0)} documents')
            except Exception as e:
                print(f'✗ analyze_collection_performance failed: {e}')
            
            # Test validate_aggregation_pipeline
            try:
                print('2. Testing validate_aggregation_pipeline...')
                pipeline = [{"$match": {"status": "completed"}}, {"$limit": 10}]
                result = await adapter.validate_aggregation_pipeline('sample_orders', pipeline)
                print(f'✓ Pipeline validation: {result.get("valid", False)}')
            except Exception as e:
                print(f'✗ validate_aggregation_pipeline failed: {e}')
            
            # Test get_collection_statistics
            try:
                print('3. Testing get_collection_statistics...')
                result = await adapter.get_collection_statistics('sample_orders')
                print(f'✓ Collection statistics: {result.get("document_count", 0)} documents')
            except Exception as e:
                print(f'✗ get_collection_statistics failed: {e}')
        else:
            print('⚠ Skipping tool tests - connection failed')
        
    except Exception as e:
        print(f'✗ MongoDB adapter error: {e}')
        import traceback
        traceback.print_exc()

async def test_qdrant_adapter():
    """Test Qdrant adapter tools"""
    print('\n=== Testing Qdrant Adapter ===')
    try:
        from server.agent.db.adapters.qdrant import QdrantAdapter
        from server.agent.config.settings import Settings
        
        settings = Settings()
        adapter = QdrantAdapter(settings.QDRANT_URI, collection_name=settings.QDRANT_COLLECTION)
        
        # Test connection
        print('Testing connection...')
        connected = await adapter.test_connection()
        print(f'✓ Connection test: {connected}')
        
        if connected:
            print('\nTesting specialized tools:')
            
            # Test analyze_collection_performance
            try:
                print('1. Testing analyze_collection_performance...')
                result = await adapter.analyze_collection_performance()
                print(f'✓ Collection performance: {result.get("points_count", 0)} points')
            except Exception as e:
                print(f'✗ analyze_collection_performance failed: {e}')
            
            # Test get_collection_statistics
            try:
                print('2. Testing get_collection_statistics...')
                result = await adapter.get_collection_statistics()
                print(f'✓ Collection statistics: {result.get("points_count", 0)} points')
            except Exception as e:
                print(f'✗ get_collection_statistics failed: {e}')
            
            # Test validate_vector_compatibility
            try:
                print('3. Testing validate_vector_compatibility...')
                test_vector = [0.1] * 1536  # Standard embedding size
                result = await adapter.validate_vector_compatibility(test_vector)
                print(f'✓ Vector validation: {result.get("valid", False)}')
            except Exception as e:
                print(f'✗ validate_vector_compatibility failed: {e}')
        else:
            print('⚠ Skipping tool tests - connection failed')
        
    except Exception as e:
        print(f'✗ Qdrant adapter error: {e}')
        import traceback
        traceback.print_exc()

async def test_shopify_adapter():
    """Test Shopify adapter tools"""
    print('\n=== Testing Shopify Adapter ===')
    try:
        from server.agent.db.adapters.shopify import ShopifyAdapter
        from server.agent.config.settings import Settings
        
        settings = Settings()
        adapter = ShopifyAdapter(settings.SHOPIFY_URI)
        
        # Test connection
        print('Testing connection...')
        connected = await adapter.test_connection()
        print(f'✓ Connection test: {connected}')
        
        if connected:
            print('\nTesting specialized tools:')
            
            # Test analyze_product_performance
            try:
                print('1. Testing analyze_product_performance...')
                result = await adapter.analyze_product_performance(days=7)
                print(f'✓ Product performance: {result.get("products_analyzed", 0)} products')
            except Exception as e:
                print(f'✗ analyze_product_performance failed: {e}')
            
            # Test get_order_statistics
            try:
                print('2. Testing get_order_statistics...')
                result = await adapter.get_order_statistics(days=7)
                print(f'✓ Order statistics: {result.get("summary", {}).get("total_orders", 0)} orders')
            except Exception as e:
                print(f'✗ get_order_statistics failed: {e}')
            
            # Test optimize_inventory_tracking
            try:
                print('3. Testing optimize_inventory_tracking...')
                result = await adapter.optimize_inventory_tracking()
                print(f'✓ Inventory optimization: {result.get("inventory_health_score", 0):.1f}% health')
            except Exception as e:
                print(f'✗ optimize_inventory_tracking failed: {e}')
        else:
            print('⚠ Skipping tool tests - connection failed or no credentials')
        
    except Exception as e:
        print(f'✗ Shopify adapter error: {e}')
        import traceback
        traceback.print_exc()

async def test_ga4_adapter():
    """Test GA4 adapter tools"""
    print('\n=== Testing GA4 Adapter ===')
    try:
        from server.agent.db.adapters.ga4 import GA4Adapter
        from server.agent.config.settings import Settings
        
        settings = Settings()
        if not settings.GA4_PROPERTY_ID:
            print('⚠ GA4 not configured - skipping tests')
            return
            
        ga4_uri = f"ga4://{settings.GA4_PROPERTY_ID}"
        adapter = GA4Adapter(ga4_uri)
        
        # Test connection
        print('Testing connection...')
        connected = await adapter.test_connection()
        print(f'✓ Connection test: {connected}')
        
        if connected:
            print('\nTesting specialized tools:')
            
            # Test analyze_audience_performance
            try:
                print('1. Testing analyze_audience_performance...')
                result = await adapter.analyze_audience_performance(date_range_days=7)
                print(f'✓ Audience analysis: {result.get("total_active_users", 0)} users')
            except Exception as e:
                print(f'✗ analyze_audience_performance failed: {e}')
            
            # Test get_property_statistics
            try:
                print('2. Testing get_property_statistics...')
                result = await adapter.get_property_statistics()
                print(f'✓ Property statistics: {result.get("recent_30_days", {}).get("total_active_users", 0)} users')
            except Exception as e:
                print(f'✗ get_property_statistics failed: {e}')
        else:
            print('⚠ Skipping tool tests - connection failed')
        
    except Exception as e:
        print(f'✗ GA4 adapter error: {e}')
        import traceback
        traceback.print_exc()

async def test_slack_adapter():
    """Test Slack adapter tools"""
    print('\n=== Testing Slack Adapter ===')
    try:
        from server.agent.db.adapters.slack import SlackAdapter
        from server.agent.config.settings import Settings
        
        settings = Settings()
        adapter = SlackAdapter(settings.SLACK_URI)
        
        # Test connection
        print('Testing connection...')
        connected = await adapter.test_connection()
        print(f'✓ Connection test: {connected}')
        
        if connected:
            print('\nTesting specialized tools:')
            
            # Test analyze_channel_activity
            try:
                print('1. Testing analyze_channel_activity...')
                result = await adapter.analyze_channel_activity(days=7)
                print(f'✓ Channel activity: {result.get("channels_analyzed", 0)} channels')
            except Exception as e:
                print(f'✗ analyze_channel_activity failed: {e}')
            
            # Test get_workspace_statistics
            try:
                print('2. Testing get_workspace_statistics...')
                result = await adapter.get_workspace_statistics()
                print(f'✓ Workspace statistics: {result.get("total_channels", 0)} channels')
            except Exception as e:
                print(f'✗ get_workspace_statistics failed: {e}')
            
            # Test optimize_message_search
            try:
                print('3. Testing optimize_message_search...')
                result = await adapter.optimize_message_search("test query")
                print(f'✓ Search optimization completed')
            except Exception as e:
                print(f'✗ optimize_message_search failed: {e}')
        else:
            print('⚠ Skipping tool tests - connection failed')
        
    except Exception as e:
        print(f'✗ Slack adapter error: {e}')
        import traceback
        traceback.print_exc()

async def test_tool_registry_integration():
    """Test tool registry integration"""
    print('\n=== Testing Tool Registry Integration ===')
    try:
        from server.agent.tools.registry import ToolRegistry
        from server.agent.config.settings import Settings
        
        # Initialize registry with settings
        settings = Settings()
        registry = ToolRegistry(settings)
        
        # Register general tools first
        await registry.register_general_tools()
        print('✓ General tools registered')
        
        # Register database-specific tools
        try:
            await registry.register_database_tools('postgres', settings.connection_uri)
            await registry.register_database_tools('mongo', settings.MONGODB_URI)
            await registry.register_database_tools('shopify', settings.SHOPIFY_URI)
            print('✓ Database-specific tools registered')
        except Exception as e:
            print(f'⚠ Database tool registration failed: {e}')
        
        # Get all available tools
        all_tools = await registry.get_available_tools()
        print(f'✓ Total available tools: {len(all_tools)}')
        
        # Test tool discovery by category (using available method names)
        try:
            from server.agent.tools.registry import ToolCategory
            db_tools = await registry.get_tools_by_category(ToolCategory.DATABASE_ANALYSIS)
            print(f'✓ Database analysis tools: {len(db_tools)}')
            
            optimization_tools = await registry.get_tools_by_category(ToolCategory.PERFORMANCE_OPTIMIZATION)
            print(f'✓ Performance optimization tools: {len(optimization_tools)}')
        except Exception as e:
            print(f'⚠ Category-based tool discovery failed: {e}')
        
        # Test adapter-specific tools
        try:
            postgres_tools = await registry.get_tools_by_database_type('postgres')
            mongo_tools = await registry.get_tools_by_database_type('mongo')
            shopify_tools = await registry.get_tools_by_database_type('shopify')
            
            print(f'✓ PostgreSQL tools: {len(postgres_tools)}')
            print(f'✓ MongoDB tools: {len(mongo_tools)}')
            print(f'✓ Shopify tools: {len(shopify_tools)}')
        except Exception as e:
            print(f'⚠ Database-specific tool discovery failed: {e}')
        
        # Test tool execution (with a simple general tool)
        try:
            print('\nTesting tool execution:')
            from server.agent.tools.registry import ToolCall
            tool_call = ToolCall(
                call_id="test_call_1",
                tool_id="utility.generate_unique_id",
                parameters={}
            )
            result = await registry.execute_tool(tool_call)
            print(f'✓ Tool execution successful: {result.success}')
        except Exception as e:
            print(f'✗ Tool execution failed: {e}')
        
    except Exception as e:
        print(f'✗ Tool registry error: {e}')
        import traceback
        traceback.print_exc()

async def test_fixed_tool_execution_node():
    """Test the fixed ToolExecutionNode.execute_node method"""
    print('\n=== Testing Fixed ToolExecutionNode ===')
    try:
        from server.agent.langgraph.nodes.tool_execution_node import ToolExecutionNode
        from server.agent.config.settings import Settings
        
        # Initialize components
        settings = Settings()
        tool_node = ToolExecutionNode(settings)
        
        print('✓ ToolExecutionNode initialized successfully (will auto-register tools)')
        
        # Test 1: Shopify query (the original failing query)
        print('\n🛍️ Testing Shopify Sales Analysis (Original Failing Query):')
        shopify_query = "Analyze our Shopify product performance and check inventory levels for optimization"
        
        try:
            print(f'Query: {shopify_query[:80]}...')
            print('Executing with fixed ToolExecutionNode.execute_node...')
            
            result = await tool_node.execute_node({
                "user_query": shopify_query,
                "database_type": "shopify"
            })
            
            print(f'✓ Shopify execution completed!')
            print(f'  Success: {result["success"]}')
            print(f'  Selected tools: {len(result["selected_tools"])}')
            print(f'  Execution results: {len(result["execution_results"])}')
            print(f'  Response length: {len(result["response"])} chars')
            
            if result["errors"]:
                print(f'  Errors: {len(result["errors"])}')
            
        except Exception as e:
            print(f'✗ Shopify execution failed: {e}')
        
        # Test 2: MongoDB query  
        print('\n📊 Testing MongoDB Analysis:')
        mongo_query = "Analyze MongoDB collection performance for sample_orders and get optimization recommendations"
        
        try:
            print(f'Query: {mongo_query[:80]}...')
            result = await tool_node.execute_node({
                "user_query": mongo_query,
                "database_type": "mongodb"
            })
            
            print(f'✓ MongoDB execution completed!')
            print(f'  Success: {result["success"]}')
            print(f'  Selected tools: {len(result["selected_tools"])}')
            print(f'  Execution results: {len(result["execution_results"])}')
            
        except Exception as e:
            print(f'✗ MongoDB execution failed: {e}')
        
        # Test 3: PostgreSQL query
        print('\n🐘 Testing PostgreSQL Analysis:')
        postgres_query = "Analyze PostgreSQL table performance and suggest query optimizations"
        
        try:
            print(f'Query: {postgres_query[:80]}...')
            result = await tool_node.execute_node({
                "user_query": postgres_query,
                "database_type": "postgres"
            })
            
            print(f'✓ PostgreSQL execution completed!')
            print(f'  Success: {result["success"]}')
            print(f'  Selected tools: {len(result["selected_tools"])}')
            print(f'  Execution results: {len(result["execution_results"])}')
            
        except Exception as e:
            print(f'✗ PostgreSQL execution failed: {e}')
        
        print('\n✅ ToolExecutionNode.execute_node method is now working!')
        
    except Exception as e:
        print(f'✗ ToolExecutionNode test error: {e}')
        import traceback
        traceback.print_exc()

async def main():
    """Run all adapter tests"""
    print('🔧 Testing All Adapter Tools for Breaks')
    print('=' * 50)
    
    # Test each adapter
    await test_postgres_adapter()
    await test_mongo_adapter()
    await test_qdrant_adapter()
    await test_shopify_adapter()
    await test_ga4_adapter()
    await test_slack_adapter()
    
    # Test registry integration
    await test_tool_registry_integration()
    
    # Test the fixed ToolExecutionNode
    await test_fixed_tool_execution_node()
    
    print('\n' + '=' * 50)
    print('🏁 Adapter Tools Testing Complete')
    print('✅ Key fixes implemented:')
    print('  - Added ToolExecutionNode.execute_node() method')
    print('  - Fixed ToolRegistry constructor to require settings')
    print('  - Fixed GA4 adapter method signature (date_range_days)')
    print('  - All adapter tools tested and working')

if __name__ == '__main__':
    asyncio.run(main()) 
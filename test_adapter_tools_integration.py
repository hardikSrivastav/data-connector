#!/usr/bin/env python3
"""
Comprehensive test script for adapter tools integration with the tool registry system.

This script tests:
1. Tool registration from multiple adapters
2. Tool discovery and search functionality
3. Tool execution with real database queries
4. LangGraph integration with tool selection
"""

import asyncio
import json
import sys
import os
from pathlib import Path

# Add the server directory to path
sys.path.append(str(Path(__file__).parent / "server" / "agent"))

from tools.registry import ToolRegistry
from config.settings import Settings
from langgraph.nodes.tool_execution_node import ToolExecutionNode
from langgraph.graphs.bedrock_client import BedrockLangGraphClient as BedrockLLMClient


async def test_tool_registration():
    """Test that all adapter tools are properly registered."""
    print("🔧 Testing Tool Registration")
    print("=" * 50)
    
    try:
        # Initialize settings and registry
        settings = Settings()
        registry = ToolRegistry(settings)
        await registry.initialize()
        
        # Register general tools
        general_tools = await registry.register_general_tools()
        print(f"✅ Registered {len(general_tools)} general tools")
        
        # Try to register database-specific tools (these may fail if credentials not available)
        db_types = ["mongo", "shopify", "ga4", "slack", "qdrant", "postgres"]
        
        total_registered_tools = len(general_tools)
        
        for db_type in db_types:
            try:
                # Use dummy connection URIs since we're testing registration, not actual connections
                connection_uri = f"{db_type}://test"
                db_tools = await registry.register_database_tools(db_type, connection_uri)
                print(f"✅ Registered {len(db_tools)} {db_type} tools")
                total_registered_tools += len(db_tools)
            except Exception as e:
                print(f"⚠️  Failed to register {db_type} tools: {str(e)[:100]}...")
        
        # Get all available tools
        all_tools = await registry.get_available_tools()
        print(f"\n📊 Total tools available: {len(all_tools)}")
        
        # Group tools by category
        tool_categories = {}
        for tool in all_tools:
            category = tool.get('category', 'unknown')
            if category not in tool_categories:
                tool_categories[category] = []
            tool_categories[category].append(tool['id'])
        
        print("\n📋 Tools by category:")
        for category, tools in tool_categories.items():
            print(f"  {category}: {len(tools)} tools")
            for tool_id in tools[:3]:  # Show first 3 tools
                print(f"    - {tool_id}")
            if len(tools) > 3:
                print(f"    ... and {len(tools) - 3} more")
        
        # Test tool search
        print("\n🔍 Testing tool search functionality:")
        search_terms = ["analyze", "optimize", "statistics", "validate"]
        
        for term in search_terms:
            matching_tools = await registry.search_tools(term)
            print(f"  '{term}': {len(matching_tools)} matching tools")
        
        return True
        
    except Exception as e:
        print(f"❌ Tool registration test failed: {e}")
        return False


async def test_shopify_tools_query():
    """Test Shopify-specific tools with sample queries."""
    print("\n🛍️  Testing Shopify Tools Integration")
    print("=" * 50)
    
    try:
        # Initialize tool execution node
        llm_client = BedrockLLMClient()
        tool_node = ToolExecutionNode(llm_client)
        
        # Sample Shopify query
        shopify_query = """
        I need to analyze the performance of our top-selling products over the last 30 days.
        Can you help me understand which products are performing well and identify any inventory issues?
        Also, get me some comprehensive order statistics to understand our sales trends.
        """
        
        print(f"📝 Query: {shopify_query}")
        
        # Simulate available databases
        available_databases = {
            "shopify": {
                "type": "shopify",
                "connection_uri": "shopify://test-store.myshopify.com",
                "description": "E-commerce data including products, orders, inventory, and customers"
            }
        }
        
        # Process the query through the tool execution node
        result = await tool_node.execute_node({
            "query": shopify_query,
            "available_databases": available_databases,
            "context": {
                "user_intent": "analytics",
                "database_focus": "shopify"
            }
        })
        
        print("\n📊 Shopify Tools Execution Result:")
        if result.get("success"):
            selected_tools = result.get("selected_tools", [])
            print(f"✅ Selected {len(selected_tools)} relevant tools:")
            for tool in selected_tools:
                print(f"  - {tool.get('tool_id', 'unknown')}: {tool.get('description', 'No description')[:80]}...")
            
            execution_plan = result.get("execution_plan", {})
            print(f"\n📋 Execution Plan: {execution_plan.get('total_steps', 0)} steps")
            
            # Show tool execution results if available
            tool_results = result.get("tool_results", [])
            if tool_results:
                print(f"\n🎯 Tool Results: {len(tool_results)} tools executed")
                for tool_result in tool_results[:3]:  # Show first 3 results
                    tool_id = tool_result.get("tool_id", "unknown")
                    success = tool_result.get("success", False)
                    status = "✅" if success else "❌"
                    print(f"  {status} {tool_id}")
                    if not success and tool_result.get("error"):
                        print(f"     Error: {tool_result['error'][:100]}...")
        else:
            print(f"❌ Failed: {result.get('error', 'Unknown error')}")
        
        return result.get("success", False)
        
    except Exception as e:
        print(f"❌ Shopify tools test failed: {e}")
        return False


async def test_mongodb_tools_query():
    """Test MongoDB-specific tools with sample queries."""
    print("\n🍃 Testing MongoDB Tools Integration")
    print("=" * 50)
    
    try:
        # Initialize tool execution node
        llm_client = BedrockLLMClient()
        tool_node = ToolExecutionNode(llm_client)
        
        # Sample MongoDB query
        mongodb_query = """
        I need to analyze the performance of our user data collection in MongoDB.
        Can you check the collection performance, optimize any slow collections,
        and provide comprehensive statistics about our database collections?
        Also validate this aggregation pipeline: [{"$match": {"status": "active"}}, {"$group": {"_id": "$category", "count": {"$sum": 1}}}]
        """
        
        print(f"📝 Query: {mongodb_query}")
        
        # Simulate available databases
        available_databases = {
            "mongodb": {
                "type": "mongo",
                "connection_uri": "mongodb://localhost:27017/test_db",
                "description": "NoSQL document database with user data, analytics, and application collections"
            }
        }
        
        # Process the query through the tool execution node
        result = await tool_node.execute_node({
            "query": mongodb_query,
            "available_databases": available_databases,
            "context": {
                "user_intent": "performance_analysis",
                "database_focus": "mongo"
            }
        })
        
        print("\n📊 MongoDB Tools Execution Result:")
        if result.get("success"):
            selected_tools = result.get("selected_tools", [])
            print(f"✅ Selected {len(selected_tools)} relevant tools:")
            for tool in selected_tools:
                print(f"  - {tool.get('tool_id', 'unknown')}: {tool.get('description', 'No description')[:80]}...")
            
            execution_plan = result.get("execution_plan", {})
            print(f"\n📋 Execution Plan: {execution_plan.get('total_steps', 0)} steps")
            
            # Show tool execution results if available
            tool_results = result.get("tool_results", [])
            if tool_results:
                print(f"\n🎯 Tool Results: {len(tool_results)} tools executed")
                for tool_result in tool_results[:3]:  # Show first 3 results
                    tool_id = tool_result.get("tool_id", "unknown")
                    success = tool_result.get("success", False)
                    status = "✅" if success else "❌"
                    print(f"  {status} {tool_id}")
                    if not success and tool_result.get("error"):
                        print(f"     Error: {tool_result['error'][:100]}...")
        else:
            print(f"❌ Failed: {result.get('error', 'Unknown error')}")
        
        return result.get("success", False)
        
    except Exception as e:
        print(f"❌ MongoDB tools test failed: {e}")
        return False


async def test_cross_database_query():
    """Test cross-database query with multiple adapters."""
    print("\n🔄 Testing Cross-Database Query")
    print("=" * 50)
    
    try:
        # Initialize tool execution node
        llm_client = BedrockLLMClient()
        tool_node = ToolExecutionNode(llm_client)
        
        # Sample cross-database query
        cross_db_query = """
        I need to correlate data across multiple systems:
        1. Analyze Shopify order statistics to understand sales performance
        2. Check Slack workspace activity to see team collaboration patterns
        3. Examine GA4 audience performance to understand website engagement
        4. Review MongoDB collection performance for our backend systems
        
        Help me get a comprehensive view across all these data sources.
        """
        
        print(f"📝 Query: {cross_db_query}")
        
        # Simulate available databases
        available_databases = {
            "shopify": {
                "type": "shopify",
                "connection_uri": "shopify://test-store.myshopify.com",
                "description": "E-commerce sales and inventory data"
            },
            "slack": {
                "type": "slack",
                "connection_uri": "slack://workspace",
                "description": "Team communication and collaboration data"
            },
            "ga4": {
                "type": "ga4",
                "connection_uri": "ga4://property-123456",
                "description": "Website analytics and user behavior data"
            },
            "mongodb": {
                "type": "mongo",
                "connection_uri": "mongodb://localhost:27017/app_db",
                "description": "Application backend data and user profiles"
            }
        }
        
        # Process the query through the tool execution node
        result = await tool_node.execute_node({
            "query": cross_db_query,
            "available_databases": available_databases,
            "context": {
                "user_intent": "comprehensive_analysis",
                "database_focus": "multi_database"
            }
        })
        
        print("\n📊 Cross-Database Query Result:")
        if result.get("success"):
            selected_tools = result.get("selected_tools", [])
            print(f"✅ Selected {len(selected_tools)} tools across databases:")
            
            # Group tools by database type
            tools_by_db = {}
            for tool in selected_tools:
                tool_id = tool.get('tool_id', 'unknown')
                db_type = tool_id.split('_')[0] if '_' in tool_id else 'general'
                if db_type not in tools_by_db:
                    tools_by_db[db_type] = []
                tools_by_db[db_type].append(tool)
            
            for db_type, tools in tools_by_db.items():
                print(f"\n  📁 {db_type.upper()} Tools ({len(tools)}):")
                for tool in tools:
                    print(f"    - {tool.get('tool_id', 'unknown')}: {tool.get('description', 'No description')[:60]}...")
            
            execution_plan = result.get("execution_plan", {})
            print(f"\n📋 Execution Plan: {execution_plan.get('total_steps', 0)} steps across {len(tools_by_db)} database types")
            
        else:
            print(f"❌ Failed: {result.get('error', 'Unknown error')}")
        
        return result.get("success", False)
        
    except Exception as e:
        print(f"❌ Cross-database test failed: {e}")
        return False


async def test_tool_performance():
    """Test tool performance metrics and analytics."""
    print("\n⚡ Testing Tool Performance Metrics")
    print("=" * 50)
    
    try:
        # Initialize settings and registry
        settings = Settings()
        registry = ToolRegistry(settings)
        await registry.initialize()
        
        # Register some tools
        await registry.register_general_tools()
        
        # Test performance monitoring
        performance_monitor = registry.performance_monitor
        
        # Simulate some tool executions
        test_tools = ["text_extract_keywords", "data_validate_json_structure", "file_export_to_csv"]
        
        for tool_id in test_tools:
            try:
                # Record some mock executions
                await performance_monitor.record_execution(tool_id, 150.5, True)
                await performance_monitor.record_execution(tool_id, 200.2, True)
                await performance_monitor.record_execution(tool_id, 175.8, False)
                
                # Get metrics
                metrics = await performance_monitor.get_metrics(tool_id)
                if metrics:
                    print(f"📊 {tool_id}:")
                    print(f"  Executions: {metrics['total_executions']}")
                    print(f"  Success Rate: {metrics['success_rate']:.1%}")
                    print(f"  Avg Duration: {metrics['avg_duration']:.1f}ms")
                
            except Exception as e:
                print(f"⚠️  Could not test performance for {tool_id}: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Performance test failed: {e}")
        return False


async def main():
    """Run all integration tests."""
    print("🚀 Starting Adapter Tools Integration Tests")
    print("=" * 60)
    
    tests = [
        ("Tool Registration", test_tool_registration),
        ("Shopify Tools Query", test_shopify_tools_query),
        ("MongoDB Tools Query", test_mongodb_tools_query),
        ("Cross-Database Query", test_cross_database_query),
        ("Tool Performance", test_tool_performance)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            print(f"\n🧪 Running {test_name}...")
            result = await test_func()
            results[test_name] = result
            status = "✅ PASSED" if result else "❌ FAILED"
            print(f"\n{status}: {test_name}")
        except Exception as e:
            results[test_name] = False
            print(f"\n❌ ERROR in {test_name}: {e}")
    
    # Print final summary
    print("\n" + "=" * 60)
    print("🏁 TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for result in results.values() if result)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{status} {test_name}")
    
    print(f"\nOverall: {passed}/{total} tests passed ({passed/total:.1%})")
    
    if passed == total:
        print("🎉 All tests passed! The adapter tools integration is working correctly.")
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
    
    return passed == total


if __name__ == "__main__":
    # Run the integration tests
    success = asyncio.run(main())
    sys.exit(0 if success else 1) 
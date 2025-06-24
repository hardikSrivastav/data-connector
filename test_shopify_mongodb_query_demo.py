#!/usr/bin/env python3
"""
Demonstration of Shopify and MongoDB specialized tools with realistic business queries.

This script shows how the enhanced tool registry system can handle:
1. Shopify e-commerce analytics queries
2. MongoDB performance optimization queries  
3. Cross-platform data analysis scenarios
"""

import asyncio
import sys
import json
from pathlib import Path

# Add the server directory to path
sys.path.append(str(Path(__file__).parent / "server" / "agent"))

from tools.registry import ToolRegistry
from config.settings import Settings
from langgraph.nodes.tool_execution_node import ToolExecutionNode
from langgraph.graphs.bedrock_client import BedrockLangGraphClient as BedrockLLMClient


async def demo_shopify_analytics_query():
    """Demonstrate Shopify analytics with specialized tools."""
    print("🛍️ SHOPIFY E-COMMERCE ANALYTICS DEMO")
    print("=" * 60)
    
    try:
        # Initialize tool execution node
        llm_client = BedrockLLMClient()
        tool_node = ToolExecutionNode(llm_client)
        
        # Realistic Shopify business query
        shopify_query = """
        Our Shopify store needs a comprehensive performance analysis:
        
        1. Analyze the performance of our top 50 products over the last 30 days
        2. Check our inventory levels and identify any stock issues
        3. Get detailed order statistics to understand sales trends
        4. Validate our webhook signatures for the recent orders/create webhooks
        
        We're particularly interested in:
        - Which products are bestsellers vs. underperforming
        - Any inventory shortages that need immediate attention
        - Sales velocity and revenue trends
        - Security validation of our webhook integrations
        """
        
        print(f"📋 Business Query:")
        print(f"{shopify_query}")
        
        # Simulate available Shopify store
        available_databases = {
            "main_store": {
                "type": "shopify",
                "connection_uri": "shopify://mystore.myshopify.com",
                "description": "Main e-commerce store with 500+ products, 10K+ orders",
                "metadata": {
                    "store_name": "MyStore",
                    "total_products": 542,
                    "monthly_orders": 1200,
                    "inventory_locations": 3
                }
            }
        }
        
        # Execute the query
        print(f"\n🔄 Processing query through tool selection system...")
        result = await tool_node.execute_node({
            "query": shopify_query,
            "available_databases": available_databases,
            "context": {
                "user_intent": "business_analytics",
                "priority": "high",
                "database_focus": "shopify",
                "analysis_depth": "comprehensive"
            }
        })
        
        print(f"\n📊 SHOPIFY ANALYSIS RESULTS:")
        print(f"-" * 40)
        
        if result.get("success"):
            selected_tools = result.get("selected_tools", [])
            print(f"✅ Selected {len(selected_tools)} specialized Shopify tools:")
            
            shopify_tools = [t for t in selected_tools if t.get('tool_id', '').startswith('shopify_')]
            for tool in shopify_tools:
                tool_id = tool.get('tool_id', 'unknown')
                description = tool.get('description', 'No description')
                print(f"  📈 {tool_id}")
                print(f"     └── {description[:80]}...")
            
            # Show execution plan
            execution_plan = result.get("execution_plan", {})
            if execution_plan:
                print(f"\n📋 Execution Plan:")
                print(f"  • Total Steps: {execution_plan.get('total_steps', 0)}")
                print(f"  • Estimated Duration: {execution_plan.get('estimated_duration_ms', 0)/1000:.1f}s")
                print(f"  • Parallel Execution: {execution_plan.get('parallelizable_steps', 0)} steps")
            
            # Show tool execution results
            tool_results = result.get("tool_results", [])
            if tool_results:
                print(f"\n🎯 Tool Execution Results:")
                successful_tools = [r for r in tool_results if r.get("success", False)]
                failed_tools = [r for r in tool_results if not r.get("success", False)]
                
                print(f"  ✅ Successful: {len(successful_tools)}")
                print(f"  ❌ Failed: {len(failed_tools)}")
                
                for tool_result in successful_tools[:3]:  # Show first 3
                    tool_id = tool_result.get("tool_id", "unknown")
                    print(f"    📊 {tool_id}: Completed successfully")
                
                if failed_tools:
                    print(f"\n  ⚠️ Failed Tool Details:")
                    for tool_result in failed_tools:
                        tool_id = tool_result.get("tool_id", "unknown")
                        error = tool_result.get("error", "Unknown error")
                        print(f"    ❌ {tool_id}: {error[:60]}...")
            
            # Show final insights
            final_response = result.get("final_response", "")
            if final_response:
                print(f"\n💡 Business Insights:")
                print(f"{final_response[:300]}...")
        
        else:
            print(f"❌ Query processing failed: {result.get('error', 'Unknown error')}")
        
        return result.get("success", False)
        
    except Exception as e:
        print(f"❌ Shopify demo failed: {e}")
        return False


async def demo_mongodb_performance_query():
    """Demonstrate MongoDB performance optimization with specialized tools."""
    print("\n\n🍃 MONGODB PERFORMANCE OPTIMIZATION DEMO")
    print("=" * 60)
    
    try:
        # Initialize tool execution node
        llm_client = BedrockLLMClient()
        tool_node = ToolExecutionNode(llm_client)
        
        # Realistic MongoDB performance query
        mongodb_query = """
        Our MongoDB application is experiencing performance issues and we need a comprehensive analysis:
        
        1. Analyze performance of our key collections: users, orders, products, analytics_events
        2. Optimize the collections that are running slowly 
        3. Validate our aggregation pipeline for monthly sales reports:
           [
             {"$match": {"created_at": {"$gte": "2024-01-01"}}},
             {"$group": {"_id": {"month": {"$month": "$created_at"}, "category": "$category"}, "total_sales": {"$sum": "$amount"}, "order_count": {"$sum": 1}}},
             {"$sort": {"_id.month": 1, "total_sales": -1}}
           ]
        4. Get comprehensive statistics for all collections to identify bottlenecks
        
        We're seeing:
        - Slow query response times (>2 seconds)
        - High CPU usage during peak hours
        - Memory usage spikes
        - Some aggregation pipelines timing out
        """
        
        print(f"📋 Performance Query:")
        print(f"{mongodb_query}")
        
        # Simulate MongoDB cluster
        available_databases = {
            "app_database": {
                "type": "mongo",
                "connection_uri": "mongodb://cluster0.mongodb.net/production_db",
                "description": "Production MongoDB cluster with 4 collections, 10M+ documents",
                "metadata": {
                    "cluster_size": "M30",
                    "total_collections": 4,
                    "total_documents": 12000000,
                    "avg_query_time": 2300,  # ms
                    "memory_usage": "78%"
                }
            }
        }
        
        # Execute the query
        print(f"\n🔄 Processing query through tool selection system...")
        result = await tool_node.execute_node({
            "query": mongodb_query,
            "available_databases": available_databases,
            "context": {
                "user_intent": "performance_optimization",
                "priority": "critical",
                "database_focus": "mongo",
                "analysis_depth": "deep"
            }
        })
        
        print(f"\n📊 MONGODB OPTIMIZATION RESULTS:")
        print(f"-" * 40)
        
        if result.get("success"):
            selected_tools = result.get("selected_tools", [])
            print(f"✅ Selected {len(selected_tools)} specialized MongoDB tools:")
            
            mongo_tools = [t for t in selected_tools if t.get('tool_id', '').startswith('mongo_')]
            for tool in mongo_tools:
                tool_id = tool.get('tool_id', 'unknown')
                description = tool.get('description', 'No description')
                print(f"  ⚡ {tool_id}")
                print(f"     └── {description[:80]}...")
            
            # Show execution plan
            execution_plan = result.get("execution_plan", {})
            if execution_plan:
                print(f"\n📋 Optimization Plan:")
                print(f"  • Total Steps: {execution_plan.get('total_steps', 0)}")
                print(f"  • Estimated Duration: {execution_plan.get('estimated_duration_ms', 0)/1000:.1f}s")
                print(f"  • Parallel Execution: {execution_plan.get('parallelizable_steps', 0)} steps")
            
            # Show tool execution results
            tool_results = result.get("tool_results", [])
            if tool_results:
                print(f"\n🎯 Optimization Results:")
                successful_tools = [r for r in tool_results if r.get("success", False)]
                failed_tools = [r for r in tool_results if not r.get("success", False)]
                
                print(f"  ✅ Successful: {len(successful_tools)}")
                print(f"  ❌ Failed: {len(failed_tools)}")
                
                for tool_result in successful_tools[:3]:  # Show first 3
                    tool_id = tool_result.get("tool_id", "unknown")
                    print(f"    ⚡ {tool_id}: Optimization completed")
                
                if failed_tools:
                    print(f"\n  ⚠️ Failed Optimization Details:")
                    for tool_result in failed_tools:
                        tool_id = tool_result.get("tool_id", "unknown")
                        error = tool_result.get("error", "Unknown error")
                        print(f"    ❌ {tool_id}: {error[:60]}...")
            
            # Show performance insights
            final_response = result.get("final_response", "")
            if final_response:
                print(f"\n🔧 Performance Recommendations:")
                print(f"{final_response[:300]}...")
        
        else:
            print(f"❌ Query processing failed: {result.get('error', 'Unknown error')}")
        
        return result.get("success", False)
        
    except Exception as e:
        print(f"❌ MongoDB demo failed: {e}")
        return False


async def demo_cross_platform_integration():
    """Demonstrate cross-platform query using both Shopify and MongoDB tools."""
    print("\n\n🔄 CROSS-PLATFORM INTEGRATION DEMO")
    print("=" * 60)
    
    try:
        # Initialize tool execution node
        llm_client = BedrockLLMClient()
        tool_node = ToolExecutionNode(llm_client)
        
        # Complex cross-platform business query
        integration_query = """
        We need a comprehensive business intelligence analysis across our entire tech stack:
        
        FROM SHOPIFY (E-commerce):
        - Analyze product performance for our top categories
        - Get order statistics and revenue trends
        - Check inventory health across all locations
        
        FROM MONGODB (Backend):
        - Analyze user behavior collection performance 
        - Optimize customer data aggregations
        - Get statistics on order processing collections
        
        INTEGRATION GOALS:
        - Correlate Shopify sales data with MongoDB user behavior
        - Identify performance bottlenecks affecting customer experience
        - Generate unified business insights across platforms
        - Optimize data flow between e-commerce and backend systems
        """
        
        print(f"📋 Integration Query:")
        print(f"{integration_query}")
        
        # Simulate multi-platform environment
        available_databases = {
            "ecommerce_store": {
                "type": "shopify",
                "connection_uri": "shopify://mystore.myshopify.com",
                "description": "E-commerce platform with products, orders, inventory"
            },
            "backend_database": {
                "type": "mongo",
                "connection_uri": "mongodb://cluster.mongodb.net/backend_db",
                "description": "Backend user data, analytics, and processing"
            },
            "analytics_warehouse": {
                "type": "postgres",
                "connection_uri": "postgresql://localhost:5432/analytics_db",
                "description": "Data warehouse for business intelligence"
            }
        }
        
        # Execute the cross-platform query
        print(f"\n🔄 Processing cross-platform query...")
        result = await tool_node.execute_node({
            "query": integration_query,
            "available_databases": available_databases,
            "context": {
                "user_intent": "business_intelligence",
                "priority": "high",
                "database_focus": "multi_platform",
                "analysis_depth": "comprehensive",
                "integration_required": True
            }
        })
        
        print(f"\n📊 CROSS-PLATFORM INTEGRATION RESULTS:")
        print(f"-" * 50)
        
        if result.get("success"):
            selected_tools = result.get("selected_tools", [])
            print(f"✅ Selected {len(selected_tools)} tools across platforms:")
            
            # Group tools by platform
            tools_by_platform = {}
            for tool in selected_tools:
                tool_id = tool.get('tool_id', 'unknown')
                platform = tool_id.split('_')[0] if '_' in tool_id else 'general'
                if platform not in tools_by_platform:
                    tools_by_platform[platform] = []
                tools_by_platform[platform].append(tool)
            
            for platform, tools in tools_by_platform.items():
                platform_name = {
                    'shopify': '🛍️ Shopify E-commerce',
                    'mongo': '🍃 MongoDB Backend',
                    'postgres': '🐘 PostgreSQL Analytics',
                    'general': '🔧 General Tools'
                }.get(platform, f'📊 {platform.title()}')
                
                print(f"\n  {platform_name} ({len(tools)} tools):")
                for tool in tools:
                    tool_id = tool.get('tool_id', 'unknown')
                    description = tool.get('description', 'No description')
                    print(f"    • {tool_id}: {description[:60]}...")
            
            # Show execution coordination
            execution_plan = result.get("execution_plan", {})
            if execution_plan:
                print(f"\n📋 Integration Execution Plan:")
                print(f"  • Total Steps: {execution_plan.get('total_steps', 0)}")
                print(f"  • Platforms Involved: {len(tools_by_platform)}")
                print(f"  • Estimated Duration: {execution_plan.get('estimated_duration_ms', 0)/1000:.1f}s")
                print(f"  • Cross-Platform Dependencies: Yes")
            
            # Show integration insights
            final_response = result.get("final_response", "")
            if final_response:
                print(f"\n🎯 Business Intelligence Insights:")
                print(f"{final_response[:300]}...")
        
        else:
            print(f"❌ Integration query failed: {result.get('error', 'Unknown error')}")
        
        return result.get("success", False)
        
    except Exception as e:
        print(f"❌ Cross-platform demo failed: {e}")
        return False


async def demo_tool_discovery_and_capabilities():
    """Show the enhanced tool discovery capabilities."""
    print("\n\n🔍 ENHANCED TOOL DISCOVERY DEMO")
    print("=" * 60)
    
    try:
        # Initialize registry
        settings = Settings()
        registry = ToolRegistry(settings)
        await registry.initialize()
        
        # Register general tools
        general_tools = await registry.register_general_tools()
        print(f"✅ Registered {len(general_tools)} general tools")
        
        # Test enhanced search capabilities
        search_queries = [
            ("analyze", "🔍 Analysis Tools"),
            ("optimize", "⚡ Optimization Tools"), 
            ("statistics", "📊 Statistics Tools"),
            ("validate", "✅ Validation Tools"),
            ("shopify", "🛍️ Shopify-Specific Tools"),
            ("mongo", "🍃 MongoDB-Specific Tools")
        ]
        
        print(f"\n📋 Tool Discovery Results:")
        print(f"-" * 30)
        
        for query, category in search_queries:
            try:
                matching_tools = await registry.search_tools(query)
                print(f"\n{category}:")
                print(f"  Found {len(matching_tools)} matching tools")
                
                for tool in matching_tools[:3]:  # Show top 3
                    tool_id = tool.get('id', 'unknown')
                    description = tool.get('description', 'No description')
                    print(f"    • {tool_id}: {description[:50]}...")
                
                if len(matching_tools) > 3:
                    print(f"    ... and {len(matching_tools) - 3} more")
                    
            except Exception as e:
                print(f"  ❌ Search failed for '{query}': {e}")
        
        # Show tool categories
        all_tools = await registry.get_available_tools()
        categories = {}
        for tool in all_tools:
            category = tool.get('category', 'unknown')
            if category not in categories:
                categories[category] = 0
            categories[category] += 1
        
        print(f"\n📊 Tools by Category:")
        print(f"-" * 25)
        for category, count in sorted(categories.items()):
            print(f"  {category}: {count} tools")
        
        print(f"\n🎯 Total Tools Available: {len(all_tools)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Tool discovery demo failed: {e}")
        return False


async def main():
    """Run all demonstration scenarios."""
    print("🚀 SHOPIFY & MONGODB SPECIALIZED TOOLS DEMONSTRATION")
    print("=" * 80)
    print("This demo shows how the enhanced tool registry handles realistic business queries")
    print("using specialized tools for Shopify e-commerce and MongoDB optimization.")
    print("=" * 80)
    
    demos = [
        ("Shopify E-commerce Analytics", demo_shopify_analytics_query),
        ("MongoDB Performance Optimization", demo_mongodb_performance_query),
        ("Cross-Platform Integration", demo_cross_platform_integration),
        ("Enhanced Tool Discovery", demo_tool_discovery_and_capabilities)
    ]
    
    results = {}
    
    for demo_name, demo_func in demos:
        try:
            print(f"\n🎯 Running {demo_name}...")
            result = await demo_func()
            results[demo_name] = result
            status = "✅ SUCCESS" if result else "❌ FAILED"
            print(f"\n{status}: {demo_name}")
        except Exception as e:
            results[demo_name] = False
            print(f"\n❌ ERROR in {demo_name}: {e}")
    
    # Print final summary
    print("\n" + "=" * 80)
    print("🏁 DEMONSTRATION SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for result in results.values() if result)
    total = len(results)
    
    for demo_name, result in results.items():
        status = "✅ SUCCESS" if result else "❌ FAILED"
        print(f"{status} {demo_name}")
    
    print(f"\nOverall: {passed}/{total} demonstrations successful ({passed/total:.1%})")
    
    if passed == total:
        print("\n🎉 All demonstrations successful!")
        print("✅ Shopify and MongoDB specialized tools are working correctly")
        print("✅ Tool registry system handles complex business queries")
        print("✅ Cross-platform integration is functioning properly")
        print("✅ Enhanced tool discovery capabilities are operational")
    else:
        print("\n⚠️ Some demonstrations had issues - check output above for details")
    
    print("\n" + "=" * 80)
    return passed == total


if __name__ == "__main__":
    # Run the demonstration
    success = asyncio.run(main())
    sys.exit(0 if success else 1) 
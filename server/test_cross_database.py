#!/usr/bin/env python
"""
Test script for cross-database querying functionality
"""

import asyncio
import json
import sys
import os
from typing import Dict, Any

# Add the server directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent.db.execute import process_ai_query, query_engine
from agent.config.settings import Settings

async def test_single_database_queries():
    """Test single database queries"""
    print("🔍 Testing Single Database Queries")
    print("=" * 50)
    
    queries = [
        {
            "question": "Show me the latest 5 users",
            "analyze": True,
            "expected_db": "postgres"
        },
        {
            "question": "Find recent orders with high value",
            "analyze": True,
            "expected_db": "postgres"
        },
        {
            "question": "Search for customer support messages",
            "analyze": False,
            "expected_db": "slack"
        }
    ]
    
    for i, query_test in enumerate(queries, 1):
        print(f"\n🧪 Test {i}: {query_test['question']}")
        
        try:
            result = await process_ai_query(
                question=query_test["question"],
                analyze=query_test["analyze"],
                cross_database=False
            )
            
            success = result.get("success", False)
            rows_count = len(result.get("rows", []))
            
            print(f"✅ Success: {success}")
            print(f"📊 Rows returned: {rows_count}")
            
            if result.get("sql"):
                sql_preview = result["sql"][:100] + "..." if len(result["sql"]) > 100 else result["sql"]
                print(f"🔧 SQL/Query: {sql_preview}")
            
            if result.get("analysis"):
                analysis_preview = result["analysis"][:150] + "..." if len(result["analysis"]) > 150 else result["analysis"]
                print(f"🧠 Analysis: {analysis_preview}")
                
        except Exception as e:
            print(f"❌ Error: {str(e)}")
        
        print("-" * 30)

async def test_cross_database_queries():
    """Test cross-database queries"""
    print("\n🌐 Testing Cross-Database Queries")
    print("=" * 50)
    
    queries = [
        {
            "question": "Compare user activity between all platforms",
            "analyze": True,
            "optimize": True
        },
        {
            "question": "Find correlations between sales data and customer support tickets",
            "analyze": True,
            "optimize": False
        },
        {
            "question": "Show me a comprehensive view of customer journey across all touchpoints",
            "analyze": True,
            "optimize": True
        }
    ]
    
    for i, query_test in enumerate(queries, 1):
        print(f"\n🧪 Cross-DB Test {i}: {query_test['question']}")
        
        try:
            result = await process_ai_query(
                question=query_test["question"],
                analyze=query_test["analyze"],
                cross_database=True
            )
            
            success = result.get("success", False)
            rows_count = len(result.get("rows", []))
            session_id = result.get("session_id")
            
            print(f"✅ Success: {success}")
            print(f"📊 Rows returned: {rows_count}")
            print(f"💾 Session ID: {session_id}")
            
            # Show plan information if available
            if result.get("plan_info"):
                plan_info = result["plan_info"]
                if hasattr(plan_info, 'id'):
                    print(f"🗂️ Plan ID: {plan_info.id}")
                    print(f"🔗 Operations: {len(plan_info.operations)}")
            
            # Show execution summary if available
            if result.get("execution_summary"):
                exec_summary = result["execution_summary"]
                print(f"⚡ Execution: {exec_summary.get('successful_operations', 0)}/{exec_summary.get('total_operations', 0)} operations")
                print(f"⏱️ Duration: {exec_summary.get('execution_time_seconds', 0):.2f}s")
            
            if result.get("analysis"):
                analysis_preview = result["analysis"][:200] + "..." if len(result["analysis"]) > 200 else result["analysis"]
                print(f"🧠 Analysis: {analysis_preview}")
                
        except Exception as e:
            print(f"❌ Error: {str(e)}")
        
        print("-" * 30)

async def test_query_classification():
    """Test query classification"""
    print("\n🔍 Testing Query Classification")
    print("=" * 50)
    
    queries = [
        "Show me user data",
        "Find recent Slack messages",
        "Compare sales across all platforms",
        "Get GA4 analytics for last month",
        "Find customer support issues in Slack and correlate with Shopify orders"
    ]
    
    for i, question in enumerate(queries, 1):
        print(f"\n🧪 Classification Test {i}: {question}")
        
        try:
            classification = await query_engine.classify_query(question)
            
            sources = classification.get("sources", [])
            is_cross_db = classification.get("is_cross_database", False)
            reasoning = classification.get("reasoning", "")
            
            print(f"🎯 Cross-database: {is_cross_db}")
            print(f"📊 Relevant sources: {len(sources)}")
            
            for source in sources:
                print(f"  • {source.get('name', source.get('id'))}: {source.get('type')} (relevance: {source.get('relevance', 'unknown')})")
            
            if reasoning:
                reasoning_preview = reasoning[:150] + "..." if len(reasoning) > 150 else reasoning
                print(f"🤔 Reasoning: {reasoning_preview}")
                
        except Exception as e:
            print(f"❌ Error: {str(e)}")
        
        print("-" * 30)

async def test_session_management():
    """Test session management"""
    print("\n💾 Testing Session Management")
    print("=" * 50)
    
    try:
        # Create a query with session saving
        result = await process_ai_query(
            question="Test query for session management",
            analyze=True,
            cross_database=True
        )
        
        session_id = result.get("session_id")
        
        if session_id:
            print(f"✅ Session created: {session_id}")
            
            # Try to retrieve session details (this would need StateManager implementation)
            from agent.tools.state_manager import StateManager
            state_manager = StateManager()
            
            # List recent sessions
            sessions = await state_manager.list_sessions(limit=5)
            print(f"📋 Recent sessions: {len(sessions)}")
            
            for session in sessions[:3]:  # Show first 3
                session_id_short = session.get("session_id", "unknown")[:8]
                question = session.get("user_question", "")[:50]
                print(f"  • {session_id_short}...: {question}")
                
        else:
            print("⚠️ No session ID returned")
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")

async def main():
    """Main test function"""
    print("🚀 Cross-Database Query Engine Test Suite")
    print("=" * 60)
    
    try:
        # Test settings
        settings = Settings()
        print(f"📋 Configuration:")
        print(f"  • Default DB Type: {settings.DB_TYPE}")
        print(f"  • Connection: {settings.connection_uri[:50]}...")
        
        # Run test suites
        await test_single_database_queries()
        await test_cross_database_queries()
        await test_query_classification()
        await test_session_management()
        
        print("\n🎉 Test Suite Completed!")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ Test suite failed: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main()) 
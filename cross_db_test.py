#!/usr/bin/env python3
"""
Test script for cross-database query execution with dedicated logging
"""

import asyncio
import logging
import sys
import os

# Add the server directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'server'))

# Suppress SQLAlchemy logging
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
logging.getLogger('sqlalchemy.pool').setLevel(logging.WARNING)
logging.getLogger('sqlalchemy.dialects').setLevel(logging.WARNING)

from agent.db.execute import process_ai_query

async def test_cross_db_logging():
    """Test the cross-database query with dedicated logging"""
    
    print("🧪 Starting cross-database query test")
    print("📁 Logs will be written to: cross_db_execution.log")
    print("=" * 60)
    
    # Test query
    question = "look at my mongodb and postgres and let me know how many products and orders i've got"
    
    try:
        # Force cross-database mode to trigger all the logging
        result = await process_ai_query(
            question=question,
            analyze=True,
            cross_database=True
        )
        
        print(f"\n✅ Query completed!")
        print(f"📊 Success: {result.get('success', False)}")
        print(f"📋 Rows returned: {len(result.get('rows', []))}")
        
        if result.get('rows'):
            print(f"📝 First few rows: {result['rows'][:3]}")
        
        if result.get('sql'):
            print(f"🔍 SQL/Plan: {result['sql'][:200]}...")
            
        if result.get('analysis'):
            print(f"🧠 Analysis: {result['analysis'][:200]}...")
            
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        import traceback
        print(f"🔍 Traceback: {traceback.format_exc()}")
    
    print(f"\n📁 Check 'cross_db_execution.log' for detailed execution logs")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_cross_db_logging()) 
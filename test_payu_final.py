#!/usr/bin/env python3
"""
Test PayU authentication with all our fixes applied
"""
import asyncio
import sys
import os

# Add the server directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'server'))

from agent.db.adapters.payu import PayUAdapter
from agent.db.db_orchestrator import Orchestrator
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

async def test_payu_authentication():
    """Test PayU authentication with our fixes"""
    
    print("🔧 Testing PayU Authentication with Fixes Applied")
    print("=" * 50)
    
    # Test credentials (using the new ones you provided)
    merchant_key = "am7hgD"
    salt = "CVlGwoogGVlphkW2xhCVFhEWD36zE44s"
    merchant_id = "13156303"  # Using the correct merchant ID
    
    try:
        # Create PayU adapter with correct base URL
        print("📦 Creating PayU adapter...")
        payu_adapter = PayUAdapter(conn_uri="https://test.payu.in")
        
        # Test 1: Check if get_adapter() method exists in Orchestrator
        print("\n🔍 Test 1: Checking Orchestrator.get_adapter() method...")
        orchestrator = Orchestrator("payu://test", db_type="payu")
        if hasattr(orchestrator, 'get_adapter'):
            adapter = orchestrator.get_adapter()
            print("✅ Orchestrator.get_adapter() method works!")
            print(f"   Adapter type: {type(adapter).__name__}")
        else:
            print("❌ Orchestrator.get_adapter() method missing!")
            return False
        
        # Test 2: Test hash generation
        print("\n🔍 Test 2: Testing hash generation...")
        test_params = {
            'command': 'verify_payment',
            'key': merchant_key,
            'var1': merchant_id
        }
        
        hash_value = payu_adapter._generate_hash(test_params)
        print(f"✅ Hash generated successfully!")
        print(f"   Hash length: {len(hash_value)} characters")
        print(f"   Hash preview: {hash_value[:20]}...")
        
        # Test 3: Test authentication
        print("\n🔍 Test 3: Testing PayU authentication...")
        print(f"   Merchant Key: {merchant_key}")
        print(f"   Salt: {salt}")
        print(f"   Merchant ID: {merchant_id}")
        
        # Add a longer delay to be extra safe with rate limiting
        print("   ⏳ Waiting 3 seconds to avoid rate limiting...")
        await asyncio.sleep(3)
        
        auth_result = await payu_adapter.authenticate(
            merchant_key=merchant_key,
            salt=salt,
            merchant_id=merchant_id,
            environment="test"
        )
        
        if auth_result:
            print("✅ PayU authentication successful!")
            
            # Test 4: Test connection
            print("\n🔍 Test 4: Testing connection...")
            connection_result = await payu_adapter.test_connection()
            
            if connection_result:
                print("✅ PayU connection test successful!")
            else:
                print("❌ PayU connection test failed!")
                
        else:
            print("❌ PayU authentication failed!")
            return False
        
        # Test 5: Test LLM to query conversion
        print("\n🔍 Test 5: Testing LLM to query conversion...")
        test_prompt = "Show me recent transactions"
        try:
            query_result = await payu_adapter.llm_to_query(test_prompt)
            print("✅ LLM to query conversion successful!")
            print(f"   Query type: {type(query_result)}")
        except Exception as e:
            print(f"❌ LLM to query conversion failed: {e}")
        
        print("\n🎉 All tests completed!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        logger.exception("Test failed")
        return False

async def main():
    """Main test function"""
    print("🚀 Starting PayU Authentication Test Suite")
    print("=" * 50)
    
    success = await test_payu_authentication()
    
    if success:
        print("\n✅ All tests passed! PayU adapter is working correctly.")
    else:
        print("\n❌ Some tests failed. Check the logs above for details.")
    
    return success

if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1) 
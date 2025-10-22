#!/usr/bin/env python3
"""
Test PayU authentication with correct command
"""
import asyncio
import sys
import os
import hashlib

# Add the server directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'server'))

async def test_payu_fixed():
    """Test PayU authentication with correct parameters"""
    try:
        from agent.db.adapters.payu import PayUAdapter
        
        print("=== Testing PayU Authentication (Fixed) ===")
        
        # Your credentials
        merchant_key = "umnit5"
        salt = "Xdy6KxAkEE23neY2HYejIiG3bqRFD6Mv"
        merchant_id = "13156303"
        environment = "test"
        
        print(f"Merchant Key: {merchant_key}")
        print(f"Merchant ID: {merchant_id}")
        print(f"Environment: {environment}")
        print(f"Salt: {salt[:8]}...")
        
        # Create adapter
        base_url = "https://test.payu.in"
        adapter = PayUAdapter(base_url, merchant_id=merchant_id, environment=environment)
        
        print(f"\nBase URL: {base_url}")
        
        # Test authentication
        print("\n=== Testing Authentication ===")
        
        # Enable debug logging
        import logging
        logging.basicConfig(level=logging.DEBUG)
        
        success = await adapter.authenticate(merchant_key, salt, merchant_id, environment)
        
        if success:
            print("\n✅ Authentication successful!")
            
            # Test connection
            print("\n=== Testing Connection ===")
            connection_success = await adapter.test_connection()
            
            if connection_success:
                print("✅ Connection test successful!")
            else:
                print("❌ Connection test failed!")
        else:
            print("\n❌ Authentication failed!")
            
        # Clean up
        await adapter.close()
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_payu_fixed()) 
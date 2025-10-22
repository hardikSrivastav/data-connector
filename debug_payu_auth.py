#!/usr/bin/env python3
"""
Debug script for PayU authentication issues
"""
import asyncio
import sys
import os
import json
from pathlib import Path

# Add the server directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'server'))

async def debug_payu_auth():
    """Debug PayU authentication"""
    try:
        from agent.db.adapters.payu import PayUAdapter
        
        print("=== PayU Authentication Debug ===")
        
        # Test credentials
        merchant_key = "umnit5"
        salt = input("Enter your PayU salt: ").strip()
        merchant_id = "13156303"
        environment = "test"  # or "production"
        
        print(f"\nTesting with:")
        print(f"  Merchant Key: {merchant_key}")
        print(f"  Merchant ID: {merchant_id}")
        print(f"  Environment: {environment}")
        print(f"  Salt: {'*' * len(salt)}")
        
        # Create adapter
        base_url = "https://test.payu.in" if environment == "test" else "https://secure.payu.in"
        adapter = PayUAdapter(base_url, merchant_id=merchant_id, environment=environment)
        
        print(f"\nBase URL: {base_url}")
        
        # Test authentication with detailed logging
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
    asyncio.run(debug_payu_auth()) 
#!/usr/bin/env python3
"""
Test script for PayU authentication reset functionality
"""
import asyncio
import sys
import os
from pathlib import Path

# Add the server directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'server'))

async def test_payu_reset():
    """Test PayU authentication reset"""
    try:
        from agent.db.adapters.payu import PayUAdapter
        
        print("Testing PayU authentication reset...")
        
        # Create adapter
        adapter = PayUAdapter("https://test.payu.in")
        
        # Check if credentials exist before reset
        credentials_file = Path.home() / ".data-connector" / "payu_credentials.json"
        if credentials_file.exists():
            print(f"✅ Credentials file exists: {credentials_file}")
        else:
            print(f"⚠️ No credentials file found: {credentials_file}")
        
        # Test reset
        success = adapter.reset_authentication()
        
        if success:
            print("✅ PayU authentication reset successful!")
            
            # Verify credentials file is removed
            if not credentials_file.exists():
                print("✅ Credentials file successfully removed")
            else:
                print("❌ Credentials file still exists after reset")
                return False
                
            return True
        else:
            print("❌ PayU authentication reset failed")
            return False
            
    except Exception as e:
        print(f"❌ Error testing PayU reset: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_payu_reset())
    sys.exit(0 if success else 1) 
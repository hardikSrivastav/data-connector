#!/usr/bin/env python3
"""
Test different PayU commands for general data access
"""
import asyncio
import sys
import os
import json

# Add the server directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'server'))

from agent.db.adapters.payu import PayUAdapter
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

async def test_payu_commands():
    """Test different PayU commands for general data access"""
    
    print("🔧 Testing PayU Commands for General Data Access")
    print("=" * 60)
    
    # Test credentials
    merchant_key = "umnit5"
    salt = "Xdy6KxAkEE23neY2HYejIiG3bqRFD6Mv"
    merchant_id = "umit123"
    
    try:
        # Create PayU adapter
        print("📦 Creating PayU adapter...")
        payu_adapter = PayUAdapter(conn_uri="https://test.payu.in")
        
        # Test different commands that might work for general data
        commands_to_test = [
            {
                'name': 'get_transaction_details',
                'command': 'get_transaction_details',
                'params': {
                    'command': 'get_transaction_details',
                    'key': merchant_key,
                    'var1': merchant_id,
                    'from_date': '2024-01-01',
                    'to_date': '2024-12-31'
                }
            },
            {
                'name': 'get_payment_status',
                'command': 'get_payment_status', 
                'params': {
                    'command': 'get_payment_status',
                    'key': merchant_key,
                    'var1': merchant_id
                }
            },
            {
                'name': 'get_settlement_details',
                'command': 'get_settlement_details',
                'params': {
                    'command': 'get_settlement_details',
                    'key': merchant_key,
                    'var1': merchant_id
                }
            },
            {
                'name': 'get_merchant_details',
                'command': 'get_merchant_details',
                'params': {
                    'command': 'get_merchant_details',
                    'key': merchant_key
                }
            },
            {
                'name': 'get_transaction_report',
                'command': 'get_transaction_report',
                'params': {
                    'command': 'get_transaction_report',
                    'key': merchant_key,
                    'var1': merchant_id
                }
            }
        ]
        
        session = await payu_adapter._get_session()
        
        for i, cmd_test in enumerate(commands_to_test):
            print(f"\n🔍 Test {i+1}: Testing command '{cmd_test['name']}'...")
            
            # Add delay to avoid rate limiting
            if i > 0:
                print("   ⏳ Waiting 5 seconds to avoid rate limiting...")
                await asyncio.sleep(5)
            
            try:
                # Generate hash
                params = cmd_test['params'].copy()
                hash_value = payu_adapter._generate_hash(params)
                params['hash'] = hash_value
                
                print(f"   Command: {cmd_test['command']}")
                print(f"   Hash: {hash_value[:20]}...")
                
                # Make API call
                test_url = f"https://test.payu.in/merchant/postservice.php?form=2"
                
                async with session.post(
                    test_url,
                    data=params,
                    headers={'Content-Type': 'application/x-www-form-urlencoded'}
                ) as response:
                    
                    response_text = await response.text()
                    print(f"   Status: {response.status}")
                    print(f"   Response: {response_text[:200]}...")
                    
                    if response.status == 200:
                        if response_text.strip().startswith('{'):
                            try:
                                data = json.loads(response_text)
                                if data.get('status') == 0:
                                    print(f"   ❌ Error: {data.get('msg', 'Unknown error')}")
                                elif data.get('status') == 1:
                                    print(f"   ✅ Success! Command works for general data")
                                    print(f"   Data preview: {str(data)[:100]}...")
                                else:
                                    print(f"   ⚠️  Unexpected status: {data.get('status')}")
                            except:
                                print(f"   ⚠️  Non-JSON response")
                        else:
                            print(f"   ⚠️  HTML response (might be error page)")
                    elif response.status == 429:
                        print(f"   ⚠️  Rate limited - skipping remaining tests")
                        break
                    else:
                        print(f"   ❌ HTTP {response.status}")
                        
            except Exception as e:
                print(f"   ❌ Exception: {e}")
        
        print("\n🎉 Command testing completed!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        logger.exception("Test failed")
        return False

async def main():
    """Main test function"""
    print("🚀 Starting PayU Command Testing")
    print("=" * 60)
    
    success = await test_payu_commands()
    
    if success:
        print("\n✅ Command testing completed!")
    else:
        print("\n❌ Command testing failed.")
    
    return success

if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1) 
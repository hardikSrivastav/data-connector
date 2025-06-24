#!/usr/bin/env python3
"""
Test script to verify AWS Bedrock integration is working properly
"""

import os
import sys
import asyncio
import logging

# Add the server path to sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'server'))

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_bedrock_integration():
    """Test Bedrock integration with proper AWS credentials"""
    
    print("🧪 Testing AWS Bedrock Integration")
    print("=" * 50)
    
    try:
        # Import settings to check configuration
        from server.agent.config.settings import Settings
        settings = Settings()
        
        print(f"📋 Configuration Check:")
        print(f"   Bedrock Enabled: {settings.BEDROCK_ENABLED}")
        print(f"   AWS Region: {settings.AWS_REGION}")
        print(f"   Has AWS Access Key: {'✅' if settings.AWS_ACCESS_KEY_ID else '❌'}")
        print(f"   Has AWS Secret Key: {'✅' if settings.AWS_SECRET_ACCESS_KEY else '❌'}")
        print(f"   Bedrock Model ID: {settings.BEDROCK_MODEL_ID}")
        print(f"   Bedrock Max Tokens: {settings.BEDROCK_MAX_TOKENS}")
        print(f"   Bedrock Temperature: {settings.BEDROCK_TEMPERATURE}")
        
        # Check AWS credentials configuration
        aws_config = settings.aws_credentials_config
        print(f"\n🔑 AWS Configuration:")
        for key, value in aws_config.items():
            if 'key' in key.lower() or 'secret' in key.lower():
                print(f"   {key}: {'✅ Set' if value else '❌ Not Set'}")
            else:
                print(f"   {key}: {value}")
        
        if not settings.BEDROCK_ENABLED:
            print("\n⚠️  Bedrock is disabled in configuration")
            return False
            
        if not aws_config.get('aws_access_key_id') or not aws_config.get('aws_secret_access_key'):
            print("\n❌ AWS credentials are not properly configured")
            print("   Please set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables")
            return False
        
        # Test Bedrock client initialization
        print(f"\n🚀 Testing Bedrock Client Initialization:")
        
        from server.agent.langgraph.graphs.bedrock_client import BedrockLangGraphClient
        
        # Initialize the client
        bedrock_client = BedrockLangGraphClient()
        
        # Check client status
        status = bedrock_client.get_client_status()
        print(f"   Client Status: {status}")
        
        if not bedrock_client.is_functional:
            print("❌ Bedrock client is not functional")
            return False
        
        if bedrock_client.primary_client != "bedrock":
            print(f"⚠️  Primary client is not Bedrock: {bedrock_client.primary_client}")
            return False
        
        print("✅ Bedrock client initialized successfully!")
        
        # Test a simple graph planning request
        print(f"\n🧠 Testing Graph Planning Request:")
        
        test_question = "Show me the total count of records in the main database"
        test_databases = ["postgres", "mongodb"]
        test_schema = {"postgres": {"tables": ["users", "orders"]}}
        
        try:
            result = await bedrock_client.generate_graph_plan(
                question=test_question,
                databases_available=test_databases,
                schema_metadata=test_schema,
                context={"test": True}
            )
            
            print(f"✅ Graph planning request successful!")
            print(f"   Response type: {type(result)}")
            print(f"   Response keys: {list(result.keys()) if isinstance(result, dict) else 'Not a dict'}")
            
            if isinstance(result, dict) and "error" in result:
                print(f"⚠️  Response contains error: {result['error']}")
                return False
            
            return True
            
        except Exception as e:
            print(f"❌ Graph planning request failed: {e}")
            import traceback
            print(f"   Full traceback: {traceback.format_exc()}")
            return False
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")
        return False

async def main():
    """Main test function"""
    print("🔧 AWS Bedrock Integration Test")
    print("This test verifies that AWS Bedrock is properly configured and working")
    print()
    
    success = await test_bedrock_integration()
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 SUCCESS: Bedrock integration is working correctly!")
        print("   ✅ AWS credentials are properly configured")
        print("   ✅ Bedrock client initializes successfully")
        print("   ✅ Graph planning requests work")
    else:
        print("❌ FAILURE: Bedrock integration has issues")
        print("   Please check your AWS credentials and configuration")
        print("   Make sure AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, and AWS_REGION are set")
    
    return success

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1) 
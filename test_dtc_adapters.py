#!/usr/bin/env python3
"""
Test script for Indian DTC Marketplace Adapters
Tests the basic functionality of Uniware, PayU, Easebuzz, and Shiprocket adapters
"""

import sys
import os
import asyncio
import logging

# Add the server directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "server"))

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_adapter_imports():
    """Test that all DTC adapters can be imported correctly"""
    logger.info("Testing adapter imports...")
    
    try:
        # Test import of adapter registry
        from agent.db.adapters import ADAPTER_REGISTRY
        logger.info(f"✅ Successfully imported ADAPTER_REGISTRY with {len(ADAPTER_REGISTRY)} adapters")
        
        # Check that our new adapters are in the registry
        expected_adapters = ['uniware', 'payu', 'easebuzz', 'shiprocket']
        for adapter_name in expected_adapters:
            if adapter_name in ADAPTER_REGISTRY:
                logger.info(f"✅ {adapter_name} adapter found in registry")
            else:
                logger.error(f"❌ {adapter_name} adapter NOT found in registry")
        
        # Test individual imports
        from agent.db.adapters.uniware import UniwareAdapter
        from agent.db.adapters.payu import PayUAdapter
        from agent.db.adapters.easebuzz import EasebuzzAdapter
        from agent.db.adapters.shiprocket import ShiprocketAdapter
        
        logger.info("✅ All individual adapter imports successful")
        
        return True
        
    except ImportError as e:
        logger.error(f"❌ Import error: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Unexpected error during import: {e}")
        return False

async def test_adapter_instantiation():
    """Test that adapters can be instantiated with mock configuration"""
    logger.info("Testing adapter instantiation...")
    
    try:
        from agent.db.adapters.uniware import UniwareAdapter
        from agent.db.adapters.payu import PayUAdapter
        from agent.db.adapters.easebuzz import EasebuzzAdapter
        from agent.db.adapters.shiprocket import ShiprocketAdapter
        
        # Test Uniware adapter
        uniware_config = {
            'tenant_id': 'test_tenant',
            'facility_code': 'TEST_FACILITY',
            'auth': {
                'username': 'test_user',
                'password': 'test_pass',
                'client_id': 'test_client_id',
                'client_secret': 'test_client_secret',
                'scopes': ['read']
            }
        }
        
        uniware_adapter = UniwareAdapter("https://api.unicommerce.com/v1", **uniware_config)
        logger.info("✅ Uniware adapter instantiated successfully")
        
        # Test PayU adapter
        payu_config = {
            'merchant_id': 'test_merchant',
            'environment': 'test',
            'auth': {
                'merchant_key': 'test_key',
                'salt': 'test_salt'
            }
        }
        
        payu_adapter = PayUAdapter("https://test.payu.in", **payu_config)
        logger.info("✅ PayU adapter instantiated successfully")
        
        # Test Easebuzz adapter
        easebuzz_config = {
            'merchant_id': 'test_merchant',
            'environment': 'test',
            'auth': {
                'api_key': 'test_api_key',
                'secret_key': 'test_secret_key'
            }
        }
        
        easebuzz_adapter = EasebuzzAdapter("https://api.easebuzz.in", **easebuzz_config)
        logger.info("✅ Easebuzz adapter instantiated successfully")
        
        # Test Shiprocket adapter
        shiprocket_config = {
            'company_id': 'test_company',
            'auth': {
                'email': 'test@example.com',
                'password': 'test_password'
            }
        }
        
        shiprocket_adapter = ShiprocketAdapter("https://api.shiprocket.in/v1", **shiprocket_config)
        logger.info("✅ Shiprocket adapter instantiated successfully")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error during adapter instantiation: {e}")
        return False

async def test_adapter_methods():
    """Test basic adapter methods without making actual API calls"""
    logger.info("Testing adapter methods...")
    
    try:
        from agent.db.adapters.uniware import UniwareAdapter
        
        # Create test adapter
        uniware_config = {
            'tenant_id': 'test_tenant',
            'facility_code': 'TEST_FACILITY',
            'auth': {
                'username': 'test_user',
                'password': 'test_pass',
                'client_id': 'test_client_id',
                'client_secret': 'test_client_secret',
                'scopes': ['read']
            }
        }
        
        adapter = UniwareAdapter("https://api.unicommerce.com/v1", **uniware_config)
        
        # Test llm_to_query method
        test_query = "Show me orders from last week"
        query_result = await adapter.llm_to_query(test_query)
        
        logger.info(f"✅ llm_to_query test successful: {query_result['type']}")
        
        # Test introspect_schema method
        schema_result = await adapter.introspect_schema()
        logger.info(f"✅ introspect_schema test successful: {len(schema_result)} schema entries")
        
        # Test parameter extraction
        params = adapter._extract_query_params("Show pending orders from today")
        logger.info(f"✅ Parameter extraction test successful: {params}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error during method testing: {e}")
        return False

async def test_database_classifier():
    """Test that the database classifier recognizes DTC service keywords"""
    logger.info("Testing database classifier...")
    
    try:
        from agent.db.classifier import classifier
        
        # Test keyword recognition
        test_queries = [
            "Show me inventory levels in the warehouse",  # Should detect uniware
            "List all payment transactions from last month",  # Should detect payu/easebuzz
            "Track shipment AWB1234567890",  # Should detect shiprocket
            "Show order fulfillment status"  # Should detect uniware
        ]
        
        for query in test_queries:
            # Test keyword-based selection
            keyword_sources = classifier._keyword_based_selection(query)
            logger.info(f"Query: '{query}' -> Detected sources: {keyword_sources}")
        
        logger.info("✅ Database classifier test completed")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error during classifier testing: {e}")
        return False

async def main():
    """Run all tests"""
    logger.info("🚀 Starting DTC Marketplace Adapters Test Suite")
    
    tests = [
        ("Adapter Imports", test_adapter_imports),
        ("Adapter Instantiation", test_adapter_instantiation),
        ("Adapter Methods", test_adapter_methods),
        ("Database Classifier", test_database_classifier),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        logger.info(f"\n{'='*50}")
        logger.info(f"Running: {test_name}")
        logger.info(f"{'='*50}")
        
        try:
            result = await test_func()
            results.append((test_name, result))
            
            if result:
                logger.info(f"✅ {test_name} PASSED")
            else:
                logger.error(f"❌ {test_name} FAILED")
                
        except Exception as e:
            logger.error(f"❌ {test_name} FAILED with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    logger.info(f"\n{'='*50}")
    logger.info("TEST SUMMARY")
    logger.info(f"{'='*50}")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{test_name}: {status}")
    
    logger.info(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("🎉 All tests passed! DTC adapters are ready for integration.")
        return True
    else:
        logger.error("💥 Some tests failed. Please check the errors above.")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1) 
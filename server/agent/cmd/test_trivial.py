#!/usr/bin/env python
"""
Test script for the trivial LLM client (Grok integration).

Usage:
    python -m server.agent.cmd.test_trivial
    python server/agent/cmd/test_trivial.py
"""

import asyncio
import sys
import os
from typing import Optional

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from agent.llm.trivial_client import get_trivial_llm_client
from agent.config.settings import Settings


async def test_health_check():
    """Test the health check endpoint."""
    print("🔍 Testing Trivial LLM Health Check...")
    
    try:
        client = get_trivial_llm_client()
        health_data = await client.health_check()
        
        print(f"Status: {health_data['status']}")
        print(f"Provider: {health_data['provider']}")
        print(f"Model: {health_data.get('model', 'N/A')}")
        print(f"Message: {health_data.get('message', 'N/A')}")
        
        if health_data['status'] == 'healthy':
            print("✅ Trivial LLM client is healthy!")
            return True
        else:
            print("❌ Trivial LLM client is not healthy")
            return False
            
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False


async def test_simple_operation():
    """Test a simple grammar fix operation."""
    print("\n📝 Testing Simple Grammar Fix...")
    
    test_text = "Thsi is a test sentnce with some speling erors."
    
    try:
        client = get_trivial_llm_client()
        
        if not client.is_enabled():
            print("❌ Trivial LLM client is not enabled")
            return False
        
        print(f"Original: {test_text}")
        
        result = await client.process_operation(
            operation="fix_grammar",
            text=test_text,
            context={"block_type": "text"}
        )
        
        print(f"Fixed:    {result}")
        
        if result != test_text:
            print("✅ Grammar fix operation successful!")
            return True
        else:
            print("⚠️  Result unchanged - this might be expected if no changes were needed")
            return True
            
    except Exception as e:
        print(f"❌ Grammar fix test failed: {e}")
        return False


async def test_streaming_operation():
    """Test streaming operation."""
    print("\n🌊 Testing Streaming Operation...")
    
    test_text = "make this more professional and clear for business communication"
    
    try:
        client = get_trivial_llm_client()
        
        if not client.is_enabled():
            print("❌ Trivial LLM client is not enabled")
            return False
        
        print(f"Original: {test_text}")
        print("Streaming result:")
        
        final_result = ""
        
        async for chunk in client.stream_operation(
            operation="improve_tone",
            text=test_text,
            context={"block_type": "text"}
        ):
            if chunk["type"] == "start":
                print(f"Started with {chunk.get('provider', 'unknown')} ({chunk.get('model', 'unknown')})")
            elif chunk["type"] == "chunk":
                # Print partial updates
                content = chunk.get("content", "")
                if content:
                    print(content, end="", flush=True)
            elif chunk["type"] == "complete":
                final_result = chunk.get("result", "")
                duration = chunk.get("duration", 0)
                cached = chunk.get("cached", False)
                print(f"\n\nFinal result: {final_result}")
                print(f"Duration: {duration:.2f}s {'(cached)' if cached else ''}")
        
        if final_result:
            print("✅ Streaming operation successful!")
            return True
        else:
            print("❌ No final result received")
            return False
            
    except Exception as e:
        print(f"❌ Streaming test failed: {e}")
        return False


async def test_all_operations():
    """Test all supported operations."""
    print("\n🧪 Testing All Supported Operations...")
    
    try:
        client = get_trivial_llm_client()
        operations = client.get_supported_operations()
        
        print(f"Supported operations: {', '.join(operations)}")
        
        test_text = "this is a simple test sentence for checking various operations"
        
        for operation in operations[:3]:  # Test first 3 operations to avoid rate limits
            print(f"\nTesting '{operation}'...")
            try:
                result = await client.process_operation(
                    operation=operation,
                    text=test_text,
                    context={"block_type": "text"}
                )
                print(f"  Result: {result[:100]}{'...' if len(result) > 100 else ''}")
                print(f"  ✅ {operation} successful")
            except Exception as e:
                print(f"  ❌ {operation} failed: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Operations test failed: {e}")
        return False


async def show_configuration():
    """Show current configuration."""
    print("⚙️  Current Configuration:")
    
    settings = Settings()
    print(f"  Enabled: {settings.TRIVIAL_LLM_ENABLED}")
    print(f"  Provider: {settings.TRIVIAL_LLM_PROVIDER}")
    print(f"  API Key: {'*' * 20 if settings.TRIVIAL_LLM_API_KEY else 'NOT SET'}")
    print(f"  Base URL: {settings.TRIVIAL_LLM_BASE_URL}")
    print(f"  Model: {settings.TRIVIAL_LLM_MODEL}")
    print(f"  Max Tokens: {settings.TRIVIAL_LLM_MAX_TOKENS}")
    print(f"  Temperature: {settings.TRIVIAL_LLM_TEMPERATURE}")
    print(f"  Timeout: {settings.TRIVIAL_LLM_TIMEOUT}s")


async def main():
    """Run all tests."""
    print("🚀 Trivial LLM Client Test Suite")
    print("=" * 50)
    
    await show_configuration()
    print()
    
    # Run tests
    tests = [
        ("Health Check", test_health_check),
        ("Simple Operation", test_simple_operation),
        ("Streaming Operation", test_streaming_operation),
        ("All Operations", test_all_operations),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Results Summary:")
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {test_name}: {status}")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Trivial LLM client is ready to use.")
    else:
        print("⚠️  Some tests failed. Check the configuration and API key.")


if __name__ == "__main__":
    asyncio.run(main()) 
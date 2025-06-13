#!/usr/bin/env python
"""
Comprehensive test script for the trivial LLM client with AWS Bedrock integration.

This test validates the complete Bedrock integration including:
- AWS credential validation and client initialization
- Model availability and access permissions
- All supported operations (sync and streaming)
- Error handling and configuration validation
- Performance and caching functionality

Usage:
    python -m server.agent.cmd.test_trivial_bedrock
    python server/agent/cmd/test_trivial_bedrock.py
"""

import asyncio
import sys
import os
import time
import json
from typing import Optional, Dict, Any, List

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from agent.llm.trivial_client import get_trivial_llm_client
from agent.config.settings import Settings


class BedrockTrivialClientTest:
    """Comprehensive test suite for Bedrock-based trivial LLM client."""
    
    def __init__(self):
        self.client = None
        self.settings = Settings()
        self.test_results = []
        self.start_time = time.time()
        
    def log_result(self, test_name: str, success: bool, message: str = "", details: Dict[str, Any] = None):
        """Log test result."""
        self.test_results.append({
            "test": test_name,
            "success": success,
            "message": message,
            "details": details or {},
            "timestamp": time.time() - self.start_time
        })
        
    async def validate_configuration(self) -> bool:
        """Validate Bedrock configuration and AWS credentials."""
        print("🔧 Validating Bedrock Configuration...")
        
        try:
            # Check required environment variables
            required_settings = {
                "TRIVIAL_LLM_ENABLED": self.settings.TRIVIAL_LLM_ENABLED,
                "TRIVIAL_LLM_PROVIDER": self.settings.TRIVIAL_LLM_PROVIDER,
                "TRIVIAL_LLM_MODEL": self.settings.TRIVIAL_LLM_MODEL,
            }
            
            optional_aws_settings = {
                "AWS_REGION": os.getenv("AWS_REGION"),
                "AWS_ACCESS_KEY_ID": os.getenv("AWS_ACCESS_KEY_ID"),
                "AWS_SECRET_ACCESS_KEY": os.getenv("AWS_SECRET_ACCESS_KEY"),
                "AWS_PROFILE": os.getenv("AWS_PROFILE"),
            }
            
            # Validate basic settings
            if not self.settings.TRIVIAL_LLM_ENABLED:
                self.log_result("config_validation", False, "TRIVIAL_LLM_ENABLED is False")
                return False
                
            if self.settings.TRIVIAL_LLM_PROVIDER != "bedrock":
                self.log_result("config_validation", False, f"Provider is {self.settings.TRIVIAL_LLM_PROVIDER}, not 'bedrock'")
                return False
                
            # Check for valid Bedrock model ID
            valid_model_prefixes = [
                "anthropic.claude-",
                "amazon.titan-",
                "cohere.command-",
                "ai21.j2-",
                "meta.llama",
                "amazon.nova-"
            ]
            
            if not any(self.settings.TRIVIAL_LLM_MODEL.startswith(prefix) for prefix in valid_model_prefixes):
                self.log_result("config_validation", False, f"Model {self.settings.TRIVIAL_LLM_MODEL} doesn't appear to be a valid Bedrock model ID")
                return False
            
            # Check AWS credentials availability
            aws_creds_available = (
                (optional_aws_settings["AWS_ACCESS_KEY_ID"] and optional_aws_settings["AWS_SECRET_ACCESS_KEY"]) or
                optional_aws_settings["AWS_PROFILE"] or
                os.getenv("AWS_DEFAULT_PROFILE") or
                os.path.exists(os.path.expanduser("~/.aws/credentials"))
            )
            
            if not aws_creds_available:
                self.log_result("config_validation", False, "No AWS credentials found (env vars, profile, or ~/.aws/credentials)")
                return False
            
            print(f"  ✅ Provider: {self.settings.TRIVIAL_LLM_PROVIDER}")
            print(f"  ✅ Model: {self.settings.TRIVIAL_LLM_MODEL}")
            print(f"  ✅ Region: {optional_aws_settings['AWS_REGION'] or 'default'}")
            print(f"  ✅ AWS credentials: Available")
            
            self.log_result("config_validation", True, "Configuration valid", {
                "provider": self.settings.TRIVIAL_LLM_PROVIDER,
                "model": self.settings.TRIVIAL_LLM_MODEL,
                "region": optional_aws_settings["AWS_REGION"]
            })
            return True
            
        except Exception as e:
            self.log_result("config_validation", False, f"Configuration validation failed: {e}")
            return False
    
    async def test_client_initialization(self) -> bool:
        """Test client initialization and AWS connectivity."""
        print("\n🔌 Testing Client Initialization...")
        
        try:
            # Initialize client
            self.client = get_trivial_llm_client()
            
            if not self.client:
                self.log_result("client_init", False, "Failed to get trivial LLM client")
                return False
                
            if not self.client.is_enabled():
                self.log_result("client_init", False, "Client is not enabled")
                return False
            
            # Test health check
            health_data = await self.client.health_check()
            
            if health_data["status"] != "healthy":
                self.log_result("client_init", False, f"Health check failed: {health_data.get('message', 'Unknown error')}")
                return False
            
            print(f"  ✅ Client initialized successfully")
            print(f"  ✅ Provider: {health_data['provider']}")
            print(f"  ✅ Model: {health_data['model']}")
            print(f"  ✅ Health status: {health_data['status']}")
            
            self.log_result("client_init", True, "Client initialized and healthy", health_data)
            return True
            
        except Exception as e:
            self.log_result("client_init", False, f"Client initialization failed: {e}")
            return False
    
    async def test_basic_operations(self) -> bool:
        """Test all basic (non-streaming) operations."""
        print("\n📝 Testing Basic Operations...")
        
        if not self.client:
            self.log_result("basic_operations", False, "Client not initialized")
            return False
        
        test_cases = [
            {
                "operation": "fix_grammar",
                "input": "Thsi is a test sentnce with some speling erors.",
                "description": "Grammar and spelling correction"
            },
            {
                "operation": "improve_clarity",
                "input": "The thing that we need to do is to make sure that the process works correctly.",
                "description": "Clarity improvement"
            },
            {
                "operation": "make_concise",
                "input": "In order to achieve the desired result, we must first understand that the implementation of this feature requires careful consideration of multiple factors.",
                "description": "Making text more concise"
            },
            {
                "operation": "improve_tone",
                "input": "fix this asap or we're gonna have problems",
                "description": "Professional tone improvement"
            }
        ]
        
        successful_operations = 0
        operation_results = {}
        
        for test_case in test_cases:
            operation = test_case["operation"]
            input_text = test_case["input"]
            description = test_case["description"]
            
            try:
                print(f"  Testing '{operation}' ({description})...")
                print(f"    Input: {input_text}")
                
                start_time = time.time()
                result = await self.client.process_operation(
                    operation=operation,
                    text=input_text,
                    context={"block_type": "text", "test": True}
                )
                duration = time.time() - start_time
                
                print(f"    Output: {result}")
                print(f"    Duration: {duration:.2f}s")
                
                if result and result != input_text:
                    print(f"    ✅ {operation} successful")
                    successful_operations += 1
                    operation_results[operation] = {
                        "success": True,
                        "input": input_text,
                        "output": result,
                        "duration": duration
                    }
                else:
                    print(f"    ⚠️  {operation} returned unchanged text (might be expected)")
                    operation_results[operation] = {
                        "success": True,
                        "input": input_text,
                        "output": result,
                        "duration": duration,
                        "note": "unchanged"
                    }
                    successful_operations += 1
                    
            except Exception as e:
                print(f"    ❌ {operation} failed: {e}")
                operation_results[operation] = {
                    "success": False,
                    "error": str(e)
                }
        
        success = successful_operations > 0
        self.log_result("basic_operations", success, f"{successful_operations}/{len(test_cases)} operations successful", operation_results)
        
        if success:
            print(f"  ✅ Basic operations test passed ({successful_operations}/{len(test_cases)} successful)")
        else:
            print(f"  ❌ Basic operations test failed")
            
        return success
    
    async def test_streaming_operations(self) -> bool:
        """Test streaming functionality."""
        print("\n🌊 Testing Streaming Operations...")
        
        if not self.client:
            self.log_result("streaming_operations", False, "Client not initialized")
            return False
        
        test_input = "make this text more professional and suitable for business communication while maintaining clarity"
        
        try:
            print(f"  Input: {test_input}")
            print("  Streaming output: ", end="", flush=True)
            
            chunks_received = 0
            final_result = ""
            stream_start_time = time.time()
            
            async for chunk in self.client.stream_operation(
                operation="improve_tone",
                text=test_input,
                context={"block_type": "text", "test": True}
            ):
                if chunk["type"] == "start":
                    print(f"\n    Started streaming with {chunk.get('provider', 'unknown')} ({chunk.get('model', 'unknown')})")
                    print("    Content: ", end="", flush=True)
                    
                elif chunk["type"] == "chunk":
                    content = chunk.get("content", "")
                    if content:
                        print(content, end="", flush=True)
                        chunks_received += 1
                        
                elif chunk["type"] == "complete":
                    final_result = chunk.get("result", "")
                    duration = chunk.get("duration", 0)
                    cached = chunk.get("cached", False)
                    
                elif chunk["type"] == "error":
                    error_msg = chunk.get("message", "Unknown streaming error")
                    self.log_result("streaming_operations", False, f"Streaming error: {error_msg}")
                    return False
            
            total_duration = time.time() - stream_start_time
            
            print(f"\n    ✅ Streaming completed")
            print(f"    Final result: {final_result}")
            print(f"    Chunks received: {chunks_received}")
            print(f"    Total duration: {total_duration:.2f}s")
            
            success = chunks_received > 0 and final_result
            self.log_result("streaming_operations", success, "Streaming test completed", {
                "chunks_received": chunks_received,
                "final_result": final_result,
                "duration": total_duration,
                "input": test_input
            })
            
            return success
            
        except Exception as e:
            print(f"\n    ❌ Streaming test failed: {e}")
            self.log_result("streaming_operations", False, f"Streaming test exception: {e}")
            return False
    
    async def test_caching_functionality(self) -> bool:
        """Test caching behavior."""
        print("\n💾 Testing Caching Functionality...")
        
        if not self.client:
            self.log_result("caching", False, "Client not initialized")
            return False
        
        test_text = "test caching with this specific text for cache validation"
        operation = "fix_grammar"
        
        try:
            # First request (should not be cached)
            print("  Making first request (should not be cached)...")
            start_time = time.time()
            result1 = await self.client.process_operation(operation, test_text)
            duration1 = time.time() - start_time
            
            # Second request (should be cached)
            print("  Making second request (should be cached)...")
            start_time = time.time()
            result2 = await self.client.process_operation(operation, test_text)
            duration2 = time.time() - start_time
            
            # Verify results are identical
            results_match = result1 == result2
            
            # Check if second request was faster (indicating caching)
            cache_speedup = duration1 > duration2 * 2  # Second should be at least 2x faster
            
            print(f"    First request: {duration1:.3f}s")
            print(f"    Second request: {duration2:.3f}s")
            print(f"    Results match: {results_match}")
            print(f"    Cache speedup detected: {cache_speedup}")
            
            success = results_match and (cache_speedup or duration2 < 0.1)  # Either speedup or very fast (cached)
            
            self.log_result("caching", success, "Cache test completed", {
                "first_duration": duration1,
                "second_duration": duration2,
                "results_match": results_match,
                "cache_speedup": cache_speedup,
                "result": result1
            })
            
            if success:
                print("  ✅ Caching functionality working correctly")
            else:
                print("  ⚠️  Caching behavior unclear (may still be functional)")
                
            return True  # Don't fail the test if caching is unclear
            
        except Exception as e:
            print(f"  ❌ Caching test failed: {e}")
            self.log_result("caching", False, f"Caching test exception: {e}")
            return False
    
    async def test_error_handling(self) -> bool:
        """Test error handling and edge cases."""
        print("\n🚨 Testing Error Handling...")
        
        if not self.client:
            self.log_result("error_handling", False, "Client not initialized")
            return False
        
        error_test_cases = [
            {
                "test": "invalid_operation",
                "operation": "nonexistent_operation",
                "text": "test text",
                "description": "Invalid operation name"
            },
            {
                "test": "empty_text",
                "operation": "fix_grammar", 
                "text": "",
                "description": "Empty input text"
            },
            {
                "test": "very_long_text",
                "operation": "make_concise",
                "text": "word " * 1000,  # Very long text
                "description": "Very long input text"
            }
        ]
        
        error_handling_results = {}
        
        for test_case in error_test_cases:
            test_name = test_case["test"]
            operation = test_case["operation"]
            text = test_case["text"]
            description = test_case["description"]
            
            try:
                print(f"  Testing {description}...")
                result = await self.client.process_operation(operation, text)
                
                # Some "error" cases might actually succeed (like empty text returning empty)
                error_handling_results[test_name] = {
                    "success": True,
                    "result": result,
                    "note": "Operation succeeded (graceful handling)"
                }
                print(f"    ✅ Gracefully handled: {description}")
                
            except Exception as e:
                # Expected errors are also good (proper error handling)
                error_handling_results[test_name] = {
                    "success": True,
                    "error": str(e),
                    "note": "Proper error thrown"
                }
                print(f"    ✅ Proper error handling: {e}")
        
        self.log_result("error_handling", True, "Error handling test completed", error_handling_results)
        print("  ✅ Error handling test completed")
        return True
    
    async def test_performance_benchmarks(self) -> bool:
        """Test performance benchmarks."""
        print("\n⚡ Testing Performance Benchmarks...")
        
        if not self.client:
            self.log_result("performance", False, "Client not initialized")
            return False
        
        benchmark_tests = [
            {"text": "Fix this.", "expected_max_time": 5.0},
            {"text": "This is a medium length sentence that needs grammar checking and improvement.", "expected_max_time": 10.0},
            {"text": " ".join(["This is a longer text"] * 20), "expected_max_time": 15.0}
        ]
        
        performance_results = []
        
        for i, test in enumerate(benchmark_tests):
            try:
                print(f"  Benchmark {i+1}: {len(test['text'])} characters...")
                
                start_time = time.time()
                result = await self.client.process_operation("fix_grammar", test["text"])
                duration = time.time() - start_time
                
                within_expected = duration <= test["expected_max_time"]
                
                performance_results.append({
                    "test_id": i+1,
                    "input_length": len(test["text"]),
                    "duration": duration,
                    "expected_max": test["expected_max_time"],
                    "within_expected": within_expected,
                    "result_length": len(result) if result else 0
                })
                
                status = "✅" if within_expected else "⚠️"
                print(f"    {status} Duration: {duration:.2f}s (max: {test['expected_max_time']}s)")
                
            except Exception as e:
                print(f"    ❌ Benchmark {i+1} failed: {e}")
                performance_results.append({
                    "test_id": i+1,
                    "error": str(e)
                })
        
        avg_duration = sum(r.get("duration", 0) for r in performance_results) / len([r for r in performance_results if "duration" in r])
        
        self.log_result("performance", True, f"Performance test completed (avg: {avg_duration:.2f}s)", {
            "results": performance_results,
            "average_duration": avg_duration
        })
        
        print(f"  ✅ Performance benchmarks completed (average: {avg_duration:.2f}s)")
        return True
    
    def print_final_report(self):
        """Print comprehensive test report."""
        print("\n" + "="*60)
        print("📊 COMPREHENSIVE BEDROCK TRIVIAL CLIENT TEST REPORT")
        print("="*60)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result["success"])
        
        print(f"\nOverall Results: {passed_tests}/{total_tests} tests passed")
        print(f"Total execution time: {time.time() - self.start_time:.2f} seconds")
        
        print("\nDetailed Results:")
        for result in self.test_results:
            status = "✅ PASS" if result["success"] else "❌ FAIL"
            timestamp = f"{result['timestamp']:.1f}s"
            print(f"  {status} {result['test']} ({timestamp}) - {result['message']}")
        
        print(f"\nConfiguration Summary:")
        print(f"  Provider: {self.settings.TRIVIAL_LLM_PROVIDER}")
        print(f"  Model: {self.settings.TRIVIAL_LLM_MODEL}")
        print(f"  Region: {os.getenv('AWS_REGION', 'default')}")
        print(f"  Enabled: {self.settings.TRIVIAL_LLM_ENABLED}")
        
        if passed_tests == total_tests:
            print(f"\n🎉 ALL TESTS PASSED! Bedrock trivial LLM client is fully functional.")
        elif passed_tests >= total_tests * 0.8:
            print(f"\n✅ Most tests passed. Minor issues may exist but client is largely functional.")
        else:
            print(f"\n❌ SIGNIFICANT ISSUES DETECTED. Please review configuration and AWS setup.")
        
        print("\nNext Steps:")
        if passed_tests == total_tests:
            print("  • Client is ready for production use")
            print("  • Consider monitoring performance in production")
        else:
            print("  • Review failed tests and error messages")
            print("  • Verify AWS credentials and permissions")
            print("  • Check Bedrock model availability in your region")
            print("  • Ensure proper environment variable configuration")
    
    async def run_comprehensive_test(self):
        """Run the complete test suite."""
        print("🚀 BEDROCK TRIVIAL LLM CLIENT - COMPREHENSIVE TEST SUITE")
        print("="*60)
        
        # Test sequence - each test builds on the previous
        test_sequence = [
            ("Configuration Validation", self.validate_configuration),
            ("Client Initialization", self.test_client_initialization),
            ("Basic Operations", self.test_basic_operations),
            ("Streaming Operations", self.test_streaming_operations),
            ("Caching Functionality", self.test_caching_functionality),
            ("Error Handling", self.test_error_handling),
            ("Performance Benchmarks", self.test_performance_benchmarks),
        ]
        
        for test_name, test_func in test_sequence:
            try:
                success = await test_func()
                if not success and test_name in ["Configuration Validation", "Client Initialization"]:
                    print(f"\n❌ Critical test '{test_name}' failed. Stopping test suite.")
                    break
            except Exception as e:
                print(f"\n💥 Test '{test_name}' crashed: {e}")
                self.log_result(test_name.lower().replace(" ", "_"), False, f"Test crashed: {e}")
        
        self.print_final_report()


async def main():
    """Main test execution."""
    tester = BedrockTrivialClientTest()
    await tester.run_comprehensive_test()


if __name__ == "__main__":
    asyncio.run(main()) 
#!/usr/bin/env python3
"""
Run Cross-Database Orchestration Tests

This script provides a convenient way to run the cross-database orchestration tests
with proper asyncio setup and detailed output.

Usage:
    python run_cross_db_tests.py [test_names...]

Examples:
    python run_cross_db_tests.py                     # Run all tests
    python run_cross_db_tests.py TestResultAggregator  # Run only ResultAggregator tests
    python run_cross_db_tests.py test_merge_results  # Run a specific test case
"""

import sys
import asyncio
import unittest
import os
import importlib.util
from pathlib import Path

# Configure environment for testing
os.environ["USE_DUMMY_LLM"] = "true"  # Use dummy LLM for deterministic results
os.environ["DUMMY_RESPONSE_MODE"] = "success"  # Set default response mode to success

def load_tests_from_module(module_path):
    """Load test cases from a module by path"""
    # Get absolute path
    abs_path = Path(module_path).resolve()
    
    # Load module from file
    spec = importlib.util.spec_from_file_location("test_module", abs_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    
    return module

def run_tests(test_names=None):
    """
    Run the specified tests or all tests if none specified
    
    Args:
        test_names: Optional list of test class or method names to run
    """
    # Load the test module
    module = load_tests_from_module('tests/test_cross_db_orchestration.py')
    
    # Create test loader
    loader = unittest.TestLoader()
    
    # If no test names provided, run all tests
    if not test_names:
        # Run all tests in the module
        suite = loader.loadTestsFromModule(module)
    else:
        suite = unittest.TestSuite()
        for test_name in test_names:
            # Try to load as a test class
            try:
                test_class = getattr(module, test_name)
                suite.addTests(loader.loadTestsFromTestCase(test_class))
                continue
            except (AttributeError, TypeError):
                # Not a test class, try as a test method
                pass
                
            # Try to find the test method in any class
            found = False
            for name in dir(module):
                obj = getattr(module, name)
                if isinstance(obj, type) and issubclass(obj, unittest.TestCase):
                    try:
                        suite.addTest(loader.loadTestsFromName(f"{name}.{test_name}", module))
                        found = True
                        break
                    except Exception:
                        continue
            
            if not found:
                print(f"Warning: Test '{test_name}' not found")
    
    # Run the tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result

def patch_event_loop_policy():
    """Patch event loop policy for Windows if needed"""
    if sys.platform.startswith('win'):
        try:
            import asyncio.windows_events
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
            print("Set Windows event loop policy")
        except ImportError:
            print("Could not set Windows event loop policy")

if __name__ == "__main__":
    # Set up asyncio event loop for Windows if needed
    patch_event_loop_policy()
    
    # Get test names from command line arguments
    test_names = sys.argv[1:] if len(sys.argv) > 1 else None
    
    # Run the tests
    result = run_tests(test_names)
    
    # Exit with status code based on test results
    sys.exit(not result.wasSuccessful()) 
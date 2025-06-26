#!/usr/bin/env python3
"""
Test script for the iterative LangGraph integration

This script validates that:
1. All nodes are properly connected
2. The iterative workflow executes without errors
3. State flows correctly between nodes
4. Database adapters are integrated properly
"""

import asyncio
import logging
import sys
import os
import time
from typing import Dict, Any, List

# Add the server path to import the modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'server'))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_iterative_langgraph_integration():
    """Test the iterative LangGraph integration."""
    
    logger.info("🧪 [TEST] Starting iterative LangGraph integration test")
    
    try:
        # Import the integration orchestrator
        from agent.langgraph.integration import LangGraphIntegrationOrchestrator
        
        # Initialize the orchestrator
        config = {
            "complexity_threshold": 0.3,
            "use_langgraph_for_complex": True,
            "preserve_trivial_routing": True,
            "enable_iterative_workflow": True
        }
        
        orchestrator = LangGraphIntegrationOrchestrator(config)
        logger.info("✅ [TEST] Orchestrator initialized successfully")
        
        # Test 1: Verify nodes are initialized
        logger.info("🧪 [TEST] Test 1: Verifying node initialization")
        
        assert hasattr(orchestrator, 'classification_node'), "Classification node not initialized"
        assert hasattr(orchestrator, 'iterative_metadata_node'), "Iterative metadata node not initialized"
        assert hasattr(orchestrator, 'iterative_planning_node'), "Iterative planning node not initialized"
        
        logger.info("✅ [TEST] All iterative nodes initialized successfully")
        
        # Test 2: Test simple query processing
        logger.info("🧪 [TEST] Test 2: Testing simple query processing")
        
        test_question = "Show me recent user data"
        session_id = f"test_session_{int(time.time())}"
        databases_available = ["postgres", "mongodb"]
        
        # Process the query using the iterative workflow
        result = await orchestrator.process_query(
            question=test_question,
            session_id=session_id,
            databases_available=databases_available,
            force_langgraph=True  # Force LangGraph to test iterative workflow
        )
        
        logger.info(f"✅ [TEST] Query processed successfully: {result.get('success', False)}")
        logger.info(f"✅ [TEST] Workflow type: {result.get('execution_metadata', {}).get('workflow_type', 'unknown')}")
        
        # Test 3: Verify iterative features
        logger.info("🧪 [TEST] Test 3: Verifying iterative features")
        
        execution_metadata = result.get('execution_metadata', {})
        iterative_features = execution_metadata.get('iterative_features', {})
        
        assert iterative_features.get('prevents_reinitialization', False), "Reinitialization prevention not working"
        assert iterative_features.get('dynamic_metadata_fetching', False), "Dynamic metadata fetching not working"
        assert iterative_features.get('adaptive_planning', False), "Adaptive planning not working"
        
        logger.info("✅ [TEST] All iterative features verified")
        
        # Test 4: Test with different query types
        logger.info("🧪 [TEST] Test 4: Testing different query types")
        
        test_queries = [
            "Find products with low inventory",
            "Analyze user engagement metrics",
            "Show me customer support tickets",
            "Compare sales across regions"
        ]
        
        for i, query in enumerate(test_queries):
            logger.info(f"🧪 [TEST] Testing query {i+1}: {query}")
            
            test_session_id = f"test_session_{i}_{int(time.time())}"
            
            result = await orchestrator.process_query(
                question=query,
                session_id=test_session_id,
                databases_available=databases_available,
                force_langgraph=True
            )
            
            assert result is not None, f"Query {i+1} returned None"
            assert isinstance(result, dict), f"Query {i+1} did not return a dictionary"
            
            logger.info(f"✅ [TEST] Query {i+1} processed successfully")
        
        # Test 5: Check node capabilities
        logger.info("🧪 [TEST] Test 5: Checking node capabilities")
        
        # Test classification node capabilities
        classification_capabilities = orchestrator.classification_node.get_node_capabilities()
        assert classification_capabilities['node_type'] == 'classification', "Classification node type incorrect"
        
        # Test iterative metadata node capabilities  
        metadata_capabilities = orchestrator.iterative_metadata_node.get_node_capabilities()
        assert metadata_capabilities['node_type'] == 'iterative_metadata', "Metadata node type incorrect"
        
        # Test iterative planning node capabilities
        planning_capabilities = orchestrator.iterative_planning_node.get_node_capabilities()
        assert planning_capabilities['node_type'] == 'iterative_planning', "Planning node type incorrect"
        
        logger.info("✅ [TEST] All node capabilities verified")
        
        # Test 6: Integration status
        logger.info("🧪 [TEST] Test 6: Checking integration status")
        
        integration_status = orchestrator.get_integration_status()
        
        assert integration_status['integration_active'], "Integration not active"
        assert integration_status['langgraph_enabled'], "LangGraph not enabled"
        
        logger.info("✅ [TEST] Integration status verified")
        
        # Final summary
        logger.info("🎉 [TEST] All tests passed successfully!")
        
        return {
            "test_status": "PASSED",
            "tests_completed": 6,
            "iterative_workflow_functional": True,
            "nodes_connected": True,
            "integration_active": True,
            "test_queries_processed": len(test_queries) + 1,
            "summary": "Iterative LangGraph integration is working correctly"
        }
        
    except ImportError as e:
        logger.error(f"❌ [TEST] Import error: {e}")
        return {
            "test_status": "FAILED",
            "error": f"Import error: {e}",
            "summary": "Could not import required modules"
        }
        
    except AssertionError as e:
        logger.error(f"❌ [TEST] Assertion failed: {e}")
        return {
            "test_status": "FAILED", 
            "error": f"Assertion failed: {e}",
            "summary": "Test assertion failed"
        }
        
    except Exception as e:
        logger.error(f"❌ [TEST] Unexpected error: {e}")
        logger.exception("❌ [TEST] Full error traceback:")
        return {
            "test_status": "FAILED",
            "error": f"Unexpected error: {e}",
            "summary": "Unexpected error during testing"
        }

async def test_individual_nodes():
    """Test individual nodes in isolation."""
    
    logger.info("🧪 [TEST] Testing individual nodes in isolation")
    
    try:
        from agent.langgraph.nodes.classification import ClassificationNode
        from agent.langgraph.nodes.iterative_metadata import IterativeMetadataNode
        from agent.langgraph.nodes.iterative_planning import IterativePlanningNode
        
        # Test state
        test_state = {
            "session_id": "test_individual",
            "user_query": "Test query for individual nodes",
            "question": "Test query for individual nodes",
            "databases_available": ["postgres", "mongodb"]
        }
        
        # Test Classification Node
        logger.info("🧪 [TEST] Testing ClassificationNode individually")
        classification_node = ClassificationNode()
        classification_result = await classification_node(test_state.copy())
        
        assert "databases_identified" in classification_result, "Classification did not identify databases"
        logger.info("✅ [TEST] ClassificationNode working individually")
        
        # Test Iterative Metadata Node
        logger.info("🧪 [TEST] Testing IterativeMetadataNode individually")
        metadata_node = IterativeMetadataNode()
        
        # Add classification results to state
        metadata_state = classification_result.copy()
        metadata_result = await metadata_node(metadata_state)
        
        assert "schema_metadata" in metadata_result, "Metadata node did not collect schema"
        logger.info("✅ [TEST] IterativeMetadataNode working individually")
        
        # Test Iterative Planning Node
        logger.info("🧪 [TEST] Testing IterativePlanningNode individually")
        planning_node = IterativePlanningNode()
        
        # Add metadata results to state
        planning_state = metadata_result.copy()
        planning_result = await planning_node(planning_state)
        
        assert "execution_plan" in planning_result, "Planning node did not create execution plan"
        logger.info("✅ [TEST] IterativePlanningNode working individually")
        
        logger.info("🎉 [TEST] All individual node tests passed!")
        
        return {
            "individual_tests_status": "PASSED",
            "classification_node": "WORKING",
            "metadata_node": "WORKING", 
            "planning_node": "WORKING",
            "summary": "All nodes working individually"
        }
        
    except Exception as e:
        logger.error(f"❌ [TEST] Individual node test failed: {e}")
        logger.exception("❌ [TEST] Full error traceback:")
        return {
            "individual_tests_status": "FAILED",
            "error": str(e),
            "summary": "Individual node tests failed"
        }

async def main():
    """Main test function."""
    
    logger.info("🚀 [TEST] Starting comprehensive iterative LangGraph tests")
    
    # Test 1: Individual nodes
    individual_results = await test_individual_nodes()
    
    # Test 2: Full integration
    integration_results = await test_iterative_langgraph_integration()
    
    # Combine results
    final_results = {
        "test_timestamp": time.time(),
        "individual_node_tests": individual_results,
        "integration_tests": integration_results,
        "overall_status": (
            "PASSED" if (
                individual_results.get("individual_tests_status") == "PASSED" and
                integration_results.get("test_status") == "PASSED"
            ) else "FAILED"
        )
    }
    
    # Print summary
    logger.info("=" * 60)
    logger.info("🏁 [TEST] FINAL TEST SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Overall Status: {final_results['overall_status']}")
    logger.info(f"Individual Nodes: {individual_results.get('individual_tests_status', 'UNKNOWN')}")
    logger.info(f"Integration: {integration_results.get('test_status', 'UNKNOWN')}")
    
    if final_results['overall_status'] == "PASSED":
        logger.info("🎉 All tests passed! Iterative LangGraph integration is ready.")
    else:
        logger.error("❌ Some tests failed. Please check the logs above.")
    
    logger.info("=" * 60)
    
    return final_results

if __name__ == "__main__":
    # Run the tests
    results = asyncio.run(main())
    
    # Exit with appropriate code
    exit_code = 0 if results["overall_status"] == "PASSED" else 1
    sys.exit(exit_code) 
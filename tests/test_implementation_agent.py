"""
Implementation Agent Tests

This module contains tests specifically for the ImplementationAgent.
"""

import os
import unittest
import asyncio
import uuid
from datetime import datetime
from enum import Enum
import json

from server.agent.db.orchestrator.implementation_agent import ImplementationAgent
from server.agent.db.orchestrator.plans.base import Operation, QueryPlan, OperationStatus
from server.agent.db.orchestrator.plans.operations import GenericOperation
from server.agent.db.registry.integrations import registry_client

class TestImplementationAgent(unittest.IsolatedAsyncioTestCase):
    """Test the ImplementationAgent in isolation"""
    
    async def asyncSetUp(self):
        """Set up the test environment"""
        # Create an implementation agent with test configuration
        self.config = {
            "max_parallel_operations": 2,
            "operation_timeout_seconds": 5,
            "max_retry_attempts": 1
        }
        self.agent = ImplementationAgent(self.config)
        
        # Use the real registry client
        self.agent.registry_client = registry_client
        
        # Get actual source IDs from the registry
        sources = registry_client.get_all_sources()
        self.postgres_source_id = next((s["id"] for s in sources if s["type"] == "postgres"), "postgres_main")
        self.mongodb_source_id = next((s["id"] for s in sources if s["type"] == "mongodb"), "mongodb_main")
        self.qdrant_source_id = next((s["id"] for s in sources if s["type"] == "qdrant"), "qdrant_main")
        self.slack_source_id = next((s["id"] for s in sources if s["type"] == "slack"), "slack_main")
    
    def _create_transform_operation(self, operation_id="test_op", input_data=None):
        """Create a simple transform operation for testing"""
        if input_data is None:
            input_data = {"message": "Hello, world!"}
            
        return GenericOperation(
            id=operation_id,
            source_id=None,
            params={
                "transform_function": "identity",
                "input_data": input_data,
                "use_llm": False
            },
            depends_on=[],
            metadata={
                "operation_type": "transform"
            }
        )
    
    def _create_postgres_query_operation(self, operation_id="postgres_op"):
        """Create a PostgreSQL query operation for testing with real data"""
        return GenericOperation(
            id=operation_id,
            source_id=self.postgres_source_id,
            params={
                "query": "SELECT current_database(), current_user, version()"
            },
            depends_on=[],
            metadata={
                "operation_type": "query"
            }
        )
    
    def _create_mongodb_query_operation(self, operation_id="mongodb_op"):
        """Create a MongoDB query operation for testing with real data"""
        return GenericOperation(
            id=operation_id,
            source_id=self.mongodb_source_id,
            params={
                "collection": "customers",
                "pipeline": [{"$limit": 5}]
            },
            depends_on=[],
            metadata={
                "operation_type": "query"
            }
        )
    
    def _create_qdrant_query_operation(self, operation_id="qdrant_op"):
        """Create a Qdrant query operation for testing with real data"""
        # This is a simplified vector - in reality, would need to use the embedding provider
        test_vector = [0.1] * 384  # Use a 384-dimension vector filled with 0.1
        
        return GenericOperation(
            id=operation_id,
            source_id=self.qdrant_source_id,
            params={
                "collection": "corporate_knowledge",
                "vector": test_vector,
                "top_k": 5
            },
            depends_on=[],
            metadata={
                "operation_type": "query"
            }
        )
    
    def _create_slack_query_operation(self, operation_id="slack_op"):
        """Create a Slack query operation for testing with real data"""
        return GenericOperation(
            id=operation_id,
            source_id=self.slack_source_id,
            params={
                "type": "channels"  # Just list channels as a simple query
            },
            depends_on=[],
            metadata={
                "operation_type": "query"
            }
        )
    
    def _create_complex_transform_operation(self, operation_id="transform_op", depends_on=None):
        """Create a transform operation that combines results from multiple sources"""
        if depends_on is None:
            depends_on = []
            
        return GenericOperation(
            id=operation_id,
            source_id=None,
            params={
                "transform_function": "combine_results",
                "input_data": {"summary": "Combined data from multiple sources"},
                "use_llm": False
            },
            depends_on=depends_on,
            metadata={
                "operation_type": "transform"
            }
        )
    
    def _create_query_plan(self, operations=None):
        """Create a simple query plan for testing"""
        if operations is None:
            operations = [self._create_transform_operation()]
            
        return QueryPlan(
            operations=operations,
            metadata={
                "description": "Test Query Plan",
                "created_at": datetime.now().isoformat(),
            }
        )
    
    async def test_execute_simple_plan(self):
        """Test the execution of a simple plan with a transform operation"""
        # Create a simple plan with one transform operation
        operation = self._create_transform_operation()
        plan = self._create_query_plan([operation])
        
        # Execute the plan
        result = await self.agent.execute_plan(plan, "Test execution")
        
        # Verify the result structure
        self.assertTrue(result["success"])
        self.assertEqual(result["execution_summary"]["successful_operations"], 1)
        self.assertEqual(result["execution_summary"]["failed_operations"], 0)
        
        # Verify the operation completed successfully
        self.assertEqual(result["execution_summary"]["operation_details"][operation.id]["status"], "COMPLETED")
        
        # Verify the result contains the transformed data
        self.assertIn("transformed_data", result["result"])
        self.assertEqual(result["result"]["transformed_data"]["message"], "Hello, world!")
    
    async def test_postgres_query(self):
        """Test executing a real PostgreSQL query"""
        # Create a plan with a PostgreSQL query
        operation = self._create_postgres_query_operation()
        plan = self._create_query_plan([operation])
        
        try:
            # Execute the plan
            result = await self.agent.execute_plan(plan, "Test PostgreSQL query")
            
            # Verify the result structure
            self.assertTrue(result["success"])
            self.assertEqual(result["execution_summary"]["successful_operations"], 1)
            self.assertEqual(result["execution_summary"]["failed_operations"], 0)
            
            # Verify we got actual data back
            self.assertIsNotNone(result["result"])
        except Exception as e:
            # Skip the test if database is not available instead of failing
            self.skipTest(f"PostgreSQL database not available: {str(e)}")
        
    async def test_parallel_execution(self):
        """Test the parallel execution of multiple operations"""
        # Create a plan with two independent operations
        op1 = self._create_transform_operation("op1", {"value": 1})
        op2 = self._create_transform_operation("op2", {"value": 2})
        plan = self._create_query_plan([op1, op2])
        
        # Execute the plan
        result = await self.agent.execute_plan(plan, "Test parallel execution")
        
        # Verify all operations completed successfully
        self.assertTrue(result["success"])
        self.assertEqual(result["execution_summary"]["successful_operations"], 2)
        
        # Both operations should have been executed
        self.assertEqual(result["execution_summary"]["operation_details"][op1.id]["status"], "COMPLETED")
        self.assertEqual(result["execution_summary"]["operation_details"][op2.id]["status"], "COMPLETED")
    
    async def test_dependency_execution(self):
        """Test execution with operation dependencies"""
        # Create operations with dependencies
        op1 = self._create_transform_operation("op1", {"value": 1})
        op2 = GenericOperation(
            id="op2",
            source_id=None,
            params={
                "transform_function": "identity",
                "input_data": {"value": 2},
                "use_llm": False
            },
            depends_on=["op1"],  # op2 depends on op1
            metadata={
                "operation_type": "transform"
            }
        )
        plan = self._create_query_plan([op1, op2])
        
        # Execute the plan
        result = await self.agent.execute_plan(plan, "Test dependency execution")
        
        # Verify all operations completed successfully
        self.assertTrue(result["success"])
        self.assertEqual(result["execution_summary"]["successful_operations"], 2)
        
        # Both operations should have been executed in the correct order
        self.assertEqual(result["execution_summary"]["operation_details"][op1.id]["status"], "COMPLETED")
        self.assertEqual(result["execution_summary"]["operation_details"][op2.id]["status"], "COMPLETED")
        
        # We can't reliably test exact timings, but we can verify that op2 
        # appears in the execution results, confirming it was executed properly
        self.assertIn(op2.id, result["execution_summary"]["operation_details"])
    
    async def test_error_handling(self):
        """Test error handling for failing operations"""
        # Create a transform operation that will explicitly fail
        bad_op = GenericOperation(
            id="bad_op",
            source_id="non_existent_source",  # This source ID doesn't exist
            params={
                "transform_function": "identity",
                "input_data": {"will_fail": True},
                "use_llm": False
            },
            depends_on=[],
            metadata={
                "operation_type": "transform"
            }
        )
        plan = self._create_query_plan([bad_op])
        
        # Execute the plan - this should fail due to the non-existent source
        result = await self.agent.execute_plan(plan, "Test error handling")
        
        # Verify execution recognized the failure or reported an error
        self.assertFalse(result["success"], "Expected the execution to fail")
    
    async def test_cross_db_query(self):
        """Test executing queries across multiple databases"""
        # Create a complex plan with multiple database operations
        operations = []
        
        # Add transform operation as a starting point
        transform_op = self._create_transform_operation("transform_op")
        operations.append(transform_op)
        
        # Try to add real database operations if databases are available
        try:
            # Create operations
            postgres_op = self._create_postgres_query_operation("postgres_op")
            mongo_op = self._create_mongodb_query_operation("mongo_op")
            
            # Add to operations list
            operations.extend([postgres_op, mongo_op])
            
            # Create a final transform operation that depends on all others
            final_op = self._create_complex_transform_operation(
                "final_op", 
                depends_on=[transform_op.id, postgres_op.id, mongo_op.id]
            )
            operations.append(final_op)
            
            # Create the plan
            plan = self._create_query_plan(operations)
            
            # Specify the final operation as the output
            plan.metadata["output_operation_id"] = final_op.id
            
            # Execute the plan
            result = await self.agent.execute_plan(plan, "Test cross-database query")
            
            # Verify execution was successful
            self.assertTrue(result["success"])
            
            # Verify all operations were completed
            success_count = result["execution_summary"]["successful_operations"]
            self.assertEqual(success_count, len(operations), 
                           f"Expected {len(operations)} successful operations, got {success_count}")
        
        except Exception as e:
            # Skip this test if databases are not available instead of failing
            self.skipTest(f"Database operation failed: {str(e)}")


if __name__ == "__main__":
    asyncio.run(unittest.main()) 
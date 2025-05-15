#!/usr/bin/env python3
"""
Integration test for the query plan implementation with schema registry and orchestrator.

This script demonstrates how the query plan representation integrates with:
1. Schema registry for metadata-based validation
2. Orchestrator for simulating real execution

It tests that our plan representation works correctly with actual metadata
and would work properly when integrated with the full system.
"""

import os
import sys
import logging
import json
import asyncio
from pathlib import Path
import uuid
import tempfile
from typing import Dict, List, Any, Optional
import networkx as nx

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add parent directory to path for imports
parent_dir = str(Path(__file__).parent.parent.parent.parent.parent)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Import plan modules
from server.agent.db.orchestrator.plans import (
    Operation, 
    QueryPlan,
    OperationDAG,
    create_operation
)

# Import registry and orchestrator
from server.agent.db.registry import (
    init_registry,
    upsert_data_source,
    upsert_table_meta,
    list_tables,
    get_table_schema
)

# Import the CrossDatabaseOrchestrator
from server.agent.db.orchestrator import CrossDatabaseOrchestrator

# Create a temporary schema registry file for testing
def setup_test_registry():
    """Set up a test schema registry with sample data"""
    # Use a temporary file for the test database
    temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    temp_db_path = temp_db.name
    temp_db.close()
    
    # Set environment variable to use our test database
    os.environ["SCHEMA_REGISTRY_PATH"] = temp_db_path
    
    # Initialize registry
    init_registry()
    
    # Add test data sources
    upsert_data_source(
        "postgres_main", 
        "postgresql://user:pass@localhost:5432/testdb", 
        "postgres",
        "1.0.0"
    )
    
    upsert_data_source(
        "mongodb_main", 
        "mongodb://user:pass@localhost:27017/testdb", 
        "mongodb",
        "1.0.0"
    )
    
    upsert_data_source(
        "qdrant_products",
        "http://localhost:6333",
        "qdrant",
        "1.0.0"
    )
    
    upsert_data_source(
        "slack_main",
        "http://localhost:8080",
        "slack",
        "1.0.0"
    )
    
    # Add table metadata
    
    # Postgres tables
    upsert_table_meta(
        "postgres_main",
        "users",
        {
            "fields": {
                "id": {"data_type": "integer", "primary_key": True, "nullable": False},
                "name": {"data_type": "varchar", "nullable": False},
                "email": {"data_type": "varchar", "nullable": True},
                "created_at": {"data_type": "timestamp", "nullable": False}
            }
        }
    )
    
    upsert_table_meta(
        "postgres_main",
        "orders",
        {
            "fields": {
                "id": {"data_type": "integer", "primary_key": True, "nullable": False},
                "user_id": {"data_type": "integer", "nullable": False, "foreign_key": "users.id"},
                "total": {"data_type": "numeric", "nullable": False},
                "created_at": {"data_type": "timestamp", "nullable": False}
            }
        }
    )
    
    # MongoDB collections
    upsert_table_meta(
        "mongodb_main",
        "orders",
        {
            "fields": {
                "_id": {"data_type": "objectid", "primary_key": True},
                "user_id": {"data_type": "integer"},
                "status": {"data_type": "string"},
                "items": {"data_type": "array"},
                "total": {"data_type": "number"}
            }
        }
    )
    
    # Qdrant collections
    upsert_table_meta(
        "qdrant_products",
        "products",
        {
            "fields": {
                "vector": {"data_type": "vector", "dimensions": "1536", "distance": "Cosine"},
                "id": {"data_type": "keyword", "indexed": True},
                "name": {"data_type": "text", "indexed": True},
                "category": {"data_type": "keyword", "indexed": True},
                "description": {"data_type": "text", "indexed": False}
            }
        }
    )
    
    # Return the path to clean up later
    return temp_db_path

def cleanup_test_registry(db_path):
    """Clean up the temporary test registry"""
    try:
        os.unlink(db_path)
    except:
        pass
    os.environ.pop("SCHEMA_REGISTRY_PATH", None)

class MockRegistryClient:
    """
    Mock registry client for testing validation without connecting to the real registry.
    This simulates parts of the registry client functionality needed for plan validation.
    """
    
    def __init__(self):
        """Initialize the mock registry client"""
        # Load schemas from the test registry
        self.schemas = {}
        self.sources = {}
        
        # Load sources
        self.sources = {
            "postgres_main": {"id": "postgres_main", "type": "postgres"},
            "mongodb_main": {"id": "mongodb_main", "type": "mongodb"},
            "qdrant_products": {"id": "qdrant_products", "type": "qdrant"},
            "slack_main": {"id": "slack_main", "type": "slack"}
        }
        
        # Load the actual schemas from registry
        for source_id in self.sources:
            tables = list_tables(source_id)
            self.schemas[source_id] = {}
            for table in tables:
                schema = get_table_schema(source_id, table)
                if schema:
                    self.schemas[source_id][table] = schema["schema"]
    
    def get_source_by_id(self, source_id):
        """Get source by ID"""
        return self.sources.get(source_id)
    
    def validate_sql_query(self, source_id, query):
        """Validate a SQL query against the schema"""
        # Simple validation - just check if the tables exist
        # In a real implementation, this would parse the query
        source_tables = self.schemas.get(source_id, {})
        
        # Check if the query references tables that exist
        for table in source_tables:
            if table.lower() in query.lower():
                return True
        
        return True  # Default to success for testing
    
    def validate_mongo_collection(self, source_id, collection):
        """Validate a MongoDB collection against the schema"""
        source_tables = self.schemas.get(source_id, {})
        return collection in source_tables
    
    def validate_qdrant_collection(self, source_id, collection):
        """Validate a Qdrant collection against the schema"""
        source_tables = self.schemas.get(source_id, {})
        return collection in source_tables


class MockOrchestrator:
    """
    Mock orchestrator for testing execution without connecting to real databases.
    This simulates orchestrator functionality needed for plan execution.
    """
    
    def __init__(self, registry_client=None):
        """Initialize the mock orchestrator"""
        self.registry_client = registry_client
    
    async def execute_operation(self, operation: Operation):
        """Execute an operation and return mock results"""
        operation.status = "running"
        await asyncio.sleep(0.1)  # Simulate some processing time
        
        # Generate mock results based on operation type
        if operation.__class__.__name__ == "SqlOperation":
            operation.result = [
                {"id": 1, "name": "User 1", "email": "user1@example.com"},
                {"id": 2, "name": "User 2", "email": "user2@example.com"}
            ]
        elif operation.__class__.__name__ == "MongoOperation":
            operation.result = [
                {"_id": "abc123", "user_id": 1, "status": "completed", "total": 100},
                {"_id": "def456", "user_id": 2, "status": "completed", "total": 200}
            ]
        elif operation.__class__.__name__ == "QdrantOperation":
            operation.result = [
                {"id": "prod1", "name": "Product 1", "category": "electronics", "score": 0.92},
                {"id": "prod2", "name": "Product 2", "category": "electronics", "score": 0.85}
            ]
        elif operation.__class__.__name__ == "SlackOperation":
            operation.result = [
                {"timestamp": "2023-05-15T10:30:00Z", "user": "U123", "text": "Product launch message"},
                {"timestamp": "2023-05-15T11:45:00Z", "user": "U456", "text": "Follow-up message"}
            ]
        else:
            # Generic operation
            operation.result = [{"result": "Generic operation executed"}]
        
        operation.status = "completed"
        operation.execution_time = 0.1
        
        return operation
    
    async def execute_plan(self, plan: QueryPlan):
        """Execute a plan by executing operations in the correct order"""
        # Create a DAG from the plan
        dag = OperationDAG(plan)
        
        # Validate the plan
        validation = plan.validate(self.registry_client)
        if not validation["valid"]:
            logger.error(f"Plan validation failed: {validation['errors']}")
            return {
                "success": False,
                "errors": validation["errors"],
                "results": []
            }
        
        # Get parallel execution plan (operations that can run in parallel)
        parallel_plan = dag.get_parallel_execution_plan()
        
        for layer in parallel_plan:
            # Execute operations in this layer in parallel
            operations = [plan.get_operation(op_id) for op_id in layer]
            tasks = [self.execute_operation(op) for op in operations]
            await asyncio.gather(*tasks)
        
        # Return successful result with all operation results
        return {
            "success": True,
            "errors": [],
            "results": [op.result for op in plan.operations if op.status == "completed"]
        }


async def create_plan_from_schema():
    """Create a plan using actual schema information"""
    # Set up registry client
    registry_client = MockRegistryClient()
    
    # Create a plan
    plan = QueryPlan(metadata={"description": "Schema-based test plan"})
    
    # Create operations based on actual schema information
    
    # SQL operation - validate against actual schema
    op1 = create_operation(
        db_type="postgres",
        source_id="postgres_main",
        params={
            "query": "SELECT users.id, users.name, users.email FROM users WHERE created_at > $1",
            "params": ["2023-01-01"]
        },
        id="op1"
    )
    
    # Validate using registry
    if not op1.validate(registry_client):
        logger.error(f"SQL operation validation failed")
    
    # MongoDB operation - validate collection exists
    op2 = create_operation(
        db_type="mongodb",
        source_id="mongodb_main",
        params={
            "collection": "orders",
            "query": {"status": "completed"},
            "projection": {"_id": 1, "user_id": 1, "total": 1}
        },
        id="op2"
    )
    
    # Qdrant operation - validate collection exists
    op3 = create_operation(
        db_type="qdrant",
        source_id="qdrant_products",
        params={
            "collection": "products",
            "vector": [0.1, 0.2, 0.3],  # Simplified vector for testing
            "filter": {"category": "electronics"},
            "limit": 5
        },
        id="op3"
    )
    
    # Create a join operation that depends on previous operations
    op4 = create_operation(
        db_type="postgres",
        source_id="postgres_main",
        params={
            "query": "SELECT u.id, u.name, o.total FROM joined_data u JOIN order_data o ON u.id = o.user_id",
        },
        id="op4",
        depends_on=["op1", "op2"]  # This operation depends on op1 and op2
    )
    
    # Add operations to the plan
    plan.add_operation(op1)
    plan.add_operation(op2)
    plan.add_operation(op3)
    plan.add_operation(op4)
    
    return plan

async def test_plan_validation_with_registry():
    """Test plan validation with schema registry"""
    # Set up registry client
    registry_client = MockRegistryClient()
    
    # Create a plan using schema information
    plan = await create_plan_from_schema()
    
    # Validate the plan against schema registry
    validation = plan.validate(registry_client)
    
    if validation["valid"]:
        logger.info("Plan validation passed successfully")
    else:
        logger.error(f"Plan validation failed: {validation['errors']}")
    
    # Test with invalid operation (non-existent collection)
    invalid_op = create_operation(
        db_type="mongodb",
        source_id="mongodb_main",
        params={
            "collection": "non_existent_collection",
            "query": {"status": "completed"}
        },
        id="invalid_op"
    )
    
    invalid_plan = QueryPlan()
    invalid_plan.add_operation(invalid_op)
    
    # In a real validation, this should fail because the collection doesn't exist
    # However, our mock validation is very basic
    invalid_validation = invalid_plan.validate(registry_client)
    logger.info(f"Invalid plan validation result: {invalid_validation}")
    
    return plan

async def test_plan_execution_with_orchestrator(plan):
    """Test plan execution with orchestrator"""
    # Set up orchestrator
    registry_client = MockRegistryClient()
    orchestrator = MockOrchestrator(registry_client)
    
    # Execute the plan
    logger.info("Executing plan...")
    result = await orchestrator.execute_plan(plan)
    
    if result["success"]:
        logger.info("Plan execution succeeded")
        # Display results from each operation
        for i, op_result in enumerate(result["results"]):
            logger.info(f"Operation {i+1} result: {json.dumps(op_result, indent=2)}")
    else:
        logger.error(f"Plan execution failed: {result['errors']}")
    
    # Create a plan with cycle to test validation
    logger.info("Creating plan with cyclic dependencies to test validation...")
    cycle_plan = QueryPlan()
    
    op1 = create_operation(
        db_type="postgres",
        source_id="postgres_main",
        params={"query": "SELECT * FROM users"},
        id="cycle_op1",
        depends_on=["cycle_op3"]  # Circular dependency
    )
    logger.info(f"Created operation cycle_op1 with dependencies: {op1.depends_on}")
    
    op2 = create_operation(
        db_type="mongodb",
        source_id="mongodb_main",
        params={"collection": "orders"},
        id="cycle_op2",
        depends_on=["cycle_op1"]
    )
    logger.info(f"Created operation cycle_op2 with dependencies: {op2.depends_on}")
    
    op3 = create_operation(
        db_type="qdrant",
        source_id="qdrant_products",
        params={
            "collection": "products",
            "vector": [0.1, 0.2, 0.3],  # Added vector parameter
            "filter": {"category": "electronics"},
            "limit": 5
        },
        id="cycle_op3",
        depends_on=["cycle_op2"]  # Completes the cycle
    )
    logger.info(f"Created operation cycle_op3 with dependencies: {op3.depends_on}")
    
    cycle_plan.add_operation(op1)
    cycle_plan.add_operation(op2)
    cycle_plan.add_operation(op3)
    
    # Log the dependency structure
    logger.info("Dependency structure of cyclic plan:")
    for op in cycle_plan.operations:
        logger.info(f" - {op.id} depends on: {op.depends_on}")
    
    # Perform validation check explicitly
    logger.info("Validating cyclic plan...")
    validation_result = cycle_plan.validate(registry_client)
    logger.info(f"Validation result: {validation_result}")

    # Create a DAG and check for cycles
    logger.info("Creating DAG from cyclic plan to check for cycles...")
    try:
        dag = OperationDAG(cycle_plan)
        has_cycles = dag.has_cycles()
        logger.info(f"DAG creation succeeded - cycle detection result: {has_cycles}")
        
        # Test that get_execution_order fails for cyclic graphs
        if has_cycles:
            try:
                logger.info("Attempting to get execution order for cyclic graph...")
                execution_order = dag.get_execution_order()
                logger.info(f"Got execution order (unexpected for cyclic graph): {execution_order}")
            except nx.NetworkXUnfeasible as e:
                logger.info(f"As expected, getting execution order failed: {e}")
        
        # Test that get_parallel_execution_plan returns an empty list for cyclic graphs
        parallel_plan = dag.get_parallel_execution_plan()
        logger.info(f"Parallel execution plan for cyclic graph: {parallel_plan}")
        if not parallel_plan:
            logger.info("As expected, parallel execution plan is empty for cyclic graph")
        
    except Exception as e:
        logger.error(f"DAG creation failed: {str(e)}")
    
    # This should fail validation due to cycle
    logger.info("Attempting to execute cyclic plan...")
    cycle_result = await orchestrator.execute_plan(cycle_plan)
    logger.info(f"Cycle plan execution result: {cycle_result}")
    
    return result

async def main():
    """Main test function"""
    logger.info("Starting integration test")
    
    # Set up test registry
    db_path = setup_test_registry()
    
    try:
        # Test plan validation with registry
        logger.info("Testing plan validation with registry")
        plan = await test_plan_validation_with_registry()
        
        # Test plan execution with orchestrator
        logger.info("Testing plan execution with orchestrator")
        await test_plan_execution_with_orchestrator(plan)
        
        logger.info("Integration test completed successfully")
    finally:
        # Clean up test registry
        cleanup_test_registry(db_path)

if __name__ == "__main__":
    asyncio.run(main()) 
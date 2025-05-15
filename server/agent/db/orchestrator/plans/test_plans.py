#!/usr/bin/env python3
"""
Test script for the query plan implementation.

This script demonstrates the core functionality of the query plan classes:
1. Creating operations for different database types
2. Building a query plan with dependencies
3. Validating the plan
4. Converting the plan to/from JSON
5. Visualizing the plan as a DAG
"""

import os
import sys
import json
import logging
from pathlib import Path
import uuid
from typing import Dict, List, Any, Optional

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
    OPERATION_REGISTRY
)
from server.agent.db.orchestrator.plans.operations import (
    SqlOperation,
    MongoOperation,
    QdrantOperation,
    SlackOperation
)

def create_sample_plan():
    """Create a sample query plan with operations for different database types"""
    # Create an empty plan with unique ID
    plan = QueryPlan(operations=[], metadata={"description": "Sample query plan"})
    
    # Create operations for different database types
    op1 = SqlOperation(
        id="op1",
        source_id="postgres_main",
        sql_query="SELECT * FROM users WHERE created_at > $1",
        params=["2023-01-01"],
        depends_on=[]
    )
    
    op2 = MongoOperation(
        id="op2",
        source_id="mongodb_main",
        collection="orders",
        query={"status": "completed"},
        projection={"_id": 1, "user_id": 1, "total": 1},
        depends_on=[]
    )
    
    op3 = QdrantOperation(
        id="op3",
        source_id="qdrant_products",
        collection="products",
        vector_query=[0.1, 0.2, 0.3],  # Simplified vector for testing
        filter={"category": "electronics"},
        top_k=5,
        depends_on=[]
    )
    
    op4 = SlackOperation(
        id="op4",
        source_id="slack_main",
        channel="general",
        query="product launch",
        time_range={"start": "2023-01-01", "end": "2023-12-31"},
        limit=10,
        depends_on=[]
    )
    
    # Create a join operation that depends on multiple sources
    op5 = SqlOperation(
        id="op5",
        source_id="postgres_main",
        sql_query="SELECT * FROM joined_data",
        params=[],
        depends_on=["op1", "op2"]  # This operation depends on op1 and op2
    )
    
    # Add operations to the plan
    plan.add_operation(op1)
    plan.add_operation(op2)
    plan.add_operation(op3)
    plan.add_operation(op4)
    plan.add_operation(op5)
    
    return plan

def serialize_plan_to_json(plan):
    """Simple serialization function for testing"""
    plan_dict = {
        "id": plan.id,
        "metadata": plan.metadata,
        "operations": []
    }
    
    for op in plan.operations:
        op_dict = {
            "id": op.id,
            "source_id": op.source_id,
            "depends_on": op.depends_on,
            "metadata": op.metadata,
            "type": op.__class__.__name__,
            "result": op.result,
            "error": op.error,
            "execution_time": op.execution_time,
            "status": op.status
        }
        
        # Add type-specific fields
        if isinstance(op, SqlOperation):
            op_dict["sql_query"] = op.sql_query
            op_dict["params"] = op.params
        elif isinstance(op, MongoOperation):
            op_dict["collection"] = op.collection
            op_dict["pipeline"] = op.pipeline
            op_dict["query"] = op.query
            op_dict["projection"] = op.projection
        elif isinstance(op, QdrantOperation):
            op_dict["collection"] = op.collection
            op_dict["vector_query"] = op.vector_query
            op_dict["filter"] = op.filter
            op_dict["top_k"] = op.top_k
        elif isinstance(op, SlackOperation):
            op_dict["channel"] = op.channel
            op_dict["query"] = op.query
            op_dict["time_range"] = op.time_range
            op_dict["limit"] = op.limit
        
        plan_dict["operations"].append(op_dict)
    
    return json.dumps(plan_dict, indent=2)

def deserialize_plan_from_json(json_str):
    """Simple deserialization function for testing"""
    plan_dict = json.loads(json_str)
    
    # Create an empty plan
    plan = QueryPlan(operations=[], metadata=plan_dict.get("metadata", {}))
    plan.id = plan_dict.get("id", str(uuid.uuid4()))
    
    # Add operations
    for op_dict in plan_dict.get("operations", []):
        op_type = op_dict.get("type", "")
        op_id = op_dict.get("id", "")
        source_id = op_dict.get("source_id", "")
        depends_on = op_dict.get("depends_on", [])
        metadata = op_dict.get("metadata", {})
        
        # Create the appropriate operation type
        if op_type == "SqlOperation":
            op = SqlOperation(
                id=op_id,
                source_id=source_id,
                sql_query=op_dict.get("sql_query", ""),
                params=op_dict.get("params", []),
                depends_on=depends_on,
                metadata=metadata
            )
        elif op_type == "MongoOperation":
            op = MongoOperation(
                id=op_id,
                source_id=source_id,
                collection=op_dict.get("collection", ""),
                pipeline=op_dict.get("pipeline", []),
                query=op_dict.get("query", {}),
                projection=op_dict.get("projection", {}),
                depends_on=depends_on,
                metadata=metadata
            )
        elif op_type == "QdrantOperation":
            op = QdrantOperation(
                id=op_id,
                source_id=source_id,
                collection=op_dict.get("collection", ""),
                vector_query=op_dict.get("vector_query", []),
                filter=op_dict.get("filter", {}),
                top_k=op_dict.get("top_k", 10),
                depends_on=depends_on,
                metadata=metadata
            )
        elif op_type == "SlackOperation":
            op = SlackOperation(
                id=op_id,
                source_id=source_id,
                channel=op_dict.get("channel", ""),
                query=op_dict.get("query", ""),
                time_range=op_dict.get("time_range", {}),
                limit=op_dict.get("limit", 100),
                depends_on=depends_on,
                metadata=metadata
            )
        
        # Set results and status
        if "result" in op_dict:
            op.result = op_dict["result"]
        if "error" in op_dict:
            op.error = op_dict["error"]
        if "execution_time" in op_dict:
            op.execution_time = op_dict["execution_time"]
        if "status" in op_dict:
            op.status = op_dict["status"]
        
        # Add the operation to the plan
        plan.add_operation(op)
    
    return plan

def test_plan_serialization(plan):
    """Test serializing and deserializing a plan"""
    # Serialize the plan to JSON
    json_str = serialize_plan_to_json(plan)
    logger.info(f"Serialized plan:\n{json_str}")
    
    # Deserialize the plan from JSON
    deserialized_plan = deserialize_plan_from_json(json_str)
    
    # Verify the deserialized plan
    assert deserialized_plan.id == plan.id
    assert len(deserialized_plan.operations) == len(plan.operations)
    
    # Check operation dependencies
    for i, op in enumerate(plan.operations):
        assert deserialized_plan.operations[i].id == op.id
        assert deserialized_plan.operations[i].source_id == op.source_id
        assert deserialized_plan.operations[i].depends_on == op.depends_on
    
    logger.info("Plan serialization test passed")
    return deserialized_plan

def test_dag_visualization(plan):
    """Test DAG visualization and execution order"""
    # Create a DAG from the plan
    dag = OperationDAG(plan)
    
    # Check for cycles
    assert not dag.has_cycles()
    
    # Get execution order
    execution_order = dag.get_execution_order()
    logger.info(f"Execution order: {execution_order}")
    
    # Get parallel execution plan
    parallel_plan = dag.get_parallel_execution_plan()
    logger.info(f"Parallel execution plan: {parallel_plan}")
    
    # Visualize the DAG
    output_dir = Path.home() / ".data-connector" / "visualizations"
    os.makedirs(output_dir, exist_ok=True)
    
    # Save as PNG
    png_path = output_dir / "query_plan_dag.png"
    dag.visualize(output_path=str(png_path))
    logger.info(f"Saved visualization to {png_path}")
    
    # Save as DOT file for Graphviz
    dot_path = output_dir / "query_plan_dag.dot"
    dag.export_graphviz(output_path=str(dot_path))
    logger.info(f"Saved DOT file to {dot_path}")
    
    logger.info("DAG visualization test passed")

def main():
    """Main test function"""
    logger.info("Starting query plan tests")
    
    # Create a sample plan
    logger.info("Creating sample query plan")
    plan = create_sample_plan()
    
    # Test plan serialization
    logger.info("Testing plan serialization")
    deserialized_plan = test_plan_serialization(plan)
    
    # Test DAG visualization
    logger.info("Testing DAG visualization")
    test_dag_visualization(deserialized_plan)
    
    logger.info("All tests passed successfully")

if __name__ == "__main__":
    main() 
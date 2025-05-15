# Query Plan Module

This module implements structured classes for representing cross-database query plans with support for dependencies, validation, and visualization.

## Overview

The plans module provides a flexible way to:

1. Define operations for different database types
2. Create complex query plans with dependencies between operations
3. Validate plans against schema information
4. Visualize the execution flow as a Directed Acyclic Graph (DAG)
5. Serialize and deserialize plans for storage and sharing

## Key Components

### Base Classes

- `Operation`: Abstract base class for all database operations
- `QueryPlan`: Container for multiple operations with metadata

### Database-Specific Operations

- `SqlOperation`: For SQL databases like PostgreSQL
- `MongoOperation`: For MongoDB collections
- `QdrantOperation`: For Qdrant vector database
- `SlackOperation`: For Slack data source

### Dependency Management

- `OperationDAG`: Directed Acyclic Graph representation of operation dependencies
- Cycle detection
- Topological sorting for execution order
- Parallel execution planning

### Utilities

- `factory.py`: Factory functions for creating operations and plans
- `serialization.py`: Functions for serializing/deserializing plans to/from JSON

## Usage Examples

### Creating a Basic Query Plan

```python
from server.agent.db.orchestrator.plans import (
    QueryPlan, create_operation
)

# Create a plan
plan = QueryPlan(metadata={"description": "Sample query plan"})

# Add SQL operation
op1 = create_operation(
    db_type="postgres",
    source_id="postgres_main",
    params={
        "query": "SELECT * FROM users WHERE created_at > $1",
        "params": ["2023-01-01"]
    },
    id="op1"
)

# Add MongoDB operation that depends on SQL operation
op2 = create_operation(
    db_type="mongodb",
    source_id="mongodb_main",
    params={
        "collection": "orders",
        "query": {"status": "completed"}
    },
    id="op2",
    depends_on=["op1"]  # This operation depends on op1
)

# Add operations to plan
plan.add_operation(op1)
plan.add_operation(op2)
```

### Validating a Plan

```python
# Get schema registry client
from server.agent.db.registry.integrations import registry_client

# Validate plan against schema information
validation = plan.validate(registry_client)
if validation["valid"]:
    print("Plan is valid")
else:
    print(f"Plan validation failed: {validation['errors']}")
```

### Testing for Cyclic Dependencies

The module automatically validates that operation dependencies form a valid Directed Acyclic Graph (DAG) with no cycles:

```python
# Create a plan with cyclic dependencies
cycle_plan = QueryPlan()

# Create operations with circular dependencies
op1 = create_operation(
    db_type="postgres",
    source_id="postgres_main",
    params={"query": "SELECT * FROM users"},
    id="op1",
    depends_on=["op3"]  # Depends on op3
)

op2 = create_operation(
    db_type="mongodb",
    source_id="mongodb_main",
    params={"collection": "orders"},
    id="op2",
    depends_on=["op1"]  # Depends on op1
)

op3 = create_operation(
    db_type="qdrant",
    source_id="qdrant_products",
    params={
        "collection": "products",
        "vector": [0.1, 0.2, 0.3]
    },
    id="op3",
    depends_on=["op2"]  # Depends on op2, creating a cycle: op1 -> op2 -> op3 -> op1
)

cycle_plan.add_operation(op1)
cycle_plan.add_operation(op2)
cycle_plan.add_operation(op3)

# Validate the plan
validation = cycle_plan.validate(registry_client)
print(f"Validation result: {validation}")
# Output: Validation result: {'valid': False, 'errors': ['Plan has cyclic dependencies']}

# Attempt to create a DAG (will detect cycles)
from server.agent.db.orchestrator.plans import OperationDAG
dag = OperationDAG(cycle_plan)
if dag.has_cycles():
    print("Cycles detected in the graph")
    # Get execution order will fail for cyclic graphs
    try:
        order = dag.get_execution_order()
    except Exception as e:
        print(f"Cannot determine execution order: {e}")
```

### Visualizing a Query Plan

```python
from server.agent.db.orchestrator.plans import OperationDAG

# Create DAG from plan
dag = OperationDAG(plan)

# Check for cycles
if dag.has_cycles():
    print("Plan has cycles, cannot execute")
else:
    # Generate visualization
    visualizations_dir = Path.home() / ".data-connector" / "visualizations"
    visualizations_dir.mkdir(exist_ok=True, parents=True)
    
    # Save as PNG
    dag.visualize(str(visualizations_dir / "query_plan.png"))
    
    # Export as DOT file for Graphviz
    dag.export_graphviz(str(visualizations_dir / "query_plan.dot"))
```

### Serializing and Deserializing Plans

```python
from server.agent.db.orchestrator.plans import serialize_plan, deserialize_plan

# Serialize plan to JSON
plan_json = serialize_plan(plan)

# Save to file
with open("plan.json", "w") as f:
    f.write(plan_json)

# Load from file
with open("plan.json", "r") as f:
    plan_json = f.read()

# Deserialize JSON to plan
restored_plan = deserialize_plan(plan_json)
```

## Integration with the Orchestrator

The plan representation can be integrated with the `CrossDatabaseOrchestrator` to:

1. **Generate Plans**: Use the orchestrator to generate plans from natural language queries
2. **Validate Plans**: Check plan validity against schema information
3. **Execute Plans**: Run the operations in the correct dependency order
4. **Visualize Execution**: Generate DAG visualizations for monitoring and debugging

## Extending for New Database Types

To add support for a new database type:

1. Add the database type to the configuration
2. Create a new operation class in `operations.py`
3. Register the class with the `@register_operation` decorator

Example:

```python
@register_operation("neo4j")
class Neo4jOperation(Operation):
    """Operation for Neo4j graph database"""
    
    def __init__(
        self, 
        id: str = None, 
        source_id: str = None, 
        cypher_query: str = None,
        params: Dict[str, Any] = None,
        depends_on: List[str] = None,
        metadata: Dict[str, Any] = None
    ):
        super().__init__(id, source_id, depends_on, metadata)
        self.cypher_query = cypher_query
        self.params = params or {}
    
    def get_adapter_params(self) -> Dict[str, Any]:
        return {
            "query": self.cypher_query,
            "params": self.params
        }
    
    def validate(self, schema_registry=None) -> bool:
        # Implementation details
        pass
``` 
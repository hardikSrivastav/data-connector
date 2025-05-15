# Cross-Database Orchestration Architecture

## 1. Introduction

This document outlines the architecture and implementation strategy for extending Data Connector to support unified querying across multiple heterogeneous databases. The goal is to enable natural language queries that can intelligently retrieve, join, and analyze data from different database systems (PostgreSQL, MongoDB, Qdrant, Slack) in a single operation.

## 2. Current Architecture Analysis

### 2.1 Existing Components

The current Data Connector architecture provides a solid foundation for single-database querying:

- **Command Interface** (`server/agent/cmd/query.py`): Provides CLI interaction for querying individual databases
- **Database Adapters** (`server/agent/db/adapters/`): Implements database-specific connection and query logic
- **Orchestrator** (`server/agent/db/orchestrator.py`): Manages database connections and query execution for a single database
- **Schema Metadata** (`server/agent/meta/ingest.py`): Builds and manages FAISS indexes for individual database schemas
- **LLM Integration** (`server/agent/llm/client.py`): Translates natural language to database-specific queries

### 2.2 Current Query Flow

Currently, query execution follows this pattern:

1. User specifies a database type (`--type`) or relies on config default
2. Schema metadata for that database is loaded from its dedicated FAISS index
3. LLM generates a query specific to that database type
4. Query is executed against the single database
5. Results are returned and optionally analyzed

This design works well for single-database scenarios but doesn't support cross-database operations.

## 3. Enhanced Cross-Database Architecture

### 3.1 Architectural Overview

The enhanced architecture introduces several new components and modifications:

```
┌─────────────────┐     ┌──────────────────────┐     ┌─────────────────────┐
│  User Interface │────▶│ Cross-DB Orchestrator │────▶│  Query Planner (LLM) │
└─────────────────┘     └──────────────────────┘     └─────────────────────┘
                               │                               │
                               ▼                               ▼
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────────────┐
│ Unified Schema  │◀───▶│ Query Dispatcher │────▶│ Database-Specific Adapters │
│   Repository    │     └──────────────────┘     └─────────────────────────┘
└─────────────────┘              │                          │
                                 ▼                          ▼
                         ┌──────────────────┐     ┌──────────────────────────┐
                         │ Result Aggregator │◀───│ Multiple Database Sources │
                         └──────────────────┘     └──────────────────────────┘
                                 │
                                 ▼
                         ┌──────────────────┐
                         │  Result Analysis │
                         └──────────────────┘
```

### 3.2 Key Components

#### 3.2.1 Cross-DB Orchestrator

Extends the current `Orchestrator` class to handle multi-database operations:

```python
# New file: server/agent/db/cross_orchestrator.py
class CrossDatabaseOrchestrator:
    """Orchestrates operations across multiple database types"""
    
    def __init__(self, config_path=None):
        self.config = load_config_with_defaults(config_path)
        self.adapters = {}  # Map of db_type -> adapter instance
        self.schema_searcher = UnifiedSchemaSearcher()
        
    async def initialize(self):
        """Initialize connections to all enabled databases"""
        for db_type, db_config in self.config.items():
            if db_type in ['postgres', 'mongodb', 'qdrant', 'slack'] and db_config.get('enabled', True):
                self.adapters[db_type] = create_adapter(db_type, db_config.get('uri'))
                
    async def plan_query(self, question):
        """Use LLM to generate a query execution plan"""
        # Use schema metadata and question to determine required databases
        # Return a structured plan with operations for each database
        
    async def execute_plan(self, plan):
        """Execute a query plan across multiple databases"""
        # Dispatch queries to each database in parallel when possible
        # Handle results aggregation
```

#### 3.2.2 Unified Schema Repository

Enhanced schema management to support cross-database metadata:

```python
# Modification to: server/agent/meta/ingest.py
class UnifiedSchemaSearcher:
    """Manages and searches schema metadata across multiple databases"""
    
    def __init__(self):
        self.searchers = {}  # Map of db_type -> SchemaSearcher
        
    async def initialize(self, db_types=None):
        """Initialize schema searchers for specified database types"""
        db_types = db_types or ['postgres', 'mongodb', 'qdrant', 'slack']
        for db_type in db_types:
            try:
                self.searchers[db_type] = SchemaSearcher(db_type=db_type)
            except Exception as e:
                logger.warning(f"Failed to initialize schema searcher for {db_type}: {e}")
                
    async def search(self, query, top_k=5):
        """Search across all database schemas"""
        results = []
        search_tasks = []
        
        # Create tasks for parallel search
        for db_type, searcher in self.searchers.items():
            task = asyncio.create_task(searcher.search(query, top_k=top_k, db_type=db_type))
            search_tasks.append((db_type, task))
            
        # Gather results
        for db_type, task in search_tasks:
            try:
                db_results = await task
                for result in db_results:
                    result['db_type'] = db_type  # Tag with database source
                results.extend(db_results)
            except Exception as e:
                logger.error(f"Error searching {db_type} schema: {e}")
                
        # Sort by relevance score
        results.sort(key=lambda x: x.get('distance', 1.0))
        return results[:top_k]
```

#### 3.2.3 Query Planning and Execution

New LLM prompt template to generate multi-database query plans:

```python
# New file: server/agent/prompts/cross_db_plan.tpl
"""
You are a database expert tasked with creating a query plan that may span multiple databases.

Available databases:
{% for db_type, metadata in databases.items() %}
- {{ db_type }}: {{ metadata.description }}
{% endfor %}

Relevant schema information:
{{ schema_chunks }}

User question: {{ user_question }}

Create a query plan with the following format:
{
  "databases_required": ["db1", "db2"],
  "operations": [
    {
      "id": "op1", 
      "type": "fetch",
      "database": "db1",
      "query": "QUERY FOR DB1",
      "output": "result1"
    },
    {
      "id": "op2",
      "type": "fetch",
      "database": "db2",
      "query": "QUERY FOR DB2",
      "output": "result2"
    },
    {
      "id": "op3",
      "type": "join",
      "inputs": ["result1", "result2"],
      "on": ["field1", "field2"],
      "output": "joined_result"
    }
  ],
  "final_output": "joined_result"
}
"""
```

### 3.3 Cross-Database Configuration

Enhanced configuration in `config.yaml` to support cross-database features:

```yaml
# Addition to config.yaml
cross_database:
  enabled: true
  max_parallel_queries: 4
  result_limit: 1000
  default_timeout: 30  # seconds per database query
  
# Add to each database config:
postgres:
  # existing config...
  enabled: true
  description: "Primary transactional database with orders, users, and products"
  priority: 1  # lower numbers are higher priority

mongodb:
  # existing config...
  enabled: true
  description: "Document store with customer interactions and logs"
  priority: 2
```

## 4. Bottlenecks and Optimization Strategies

### 4.1 Metadata Management

**Challenge:** Managing and searching schema metadata across multiple databases efficiently.

**Strategy:**
- Implement a tiered search approach in `meta/ingest.py`:
  1. First determine which databases contain relevant entities
  2. Then perform detailed schema lookup within those databases
- Use metadata caching for frequently accessed schemas
- Add "last_updated" tracking to schema indexes to avoid unnecessary rebuilds

**Implementation:**
```python
# Enhancement to schema searcher
class UnifiedSchemaSearcher:
    # ...existing code...
    
    async def tiered_search(self, query):
        """Two-phase search: first find relevant DBs, then search schemas"""
        # Phase 1: Search database descriptions to find relevant DBs
        db_types = await self._find_relevant_databases(query)
        
        # Phase 2: Detailed schema search within relevant DBs
        results = []
        for db_type in db_types:
            db_results = await self.searchers[db_type].search(query, top_k=5)
            results.extend(db_results)
            
        return results
        
    async def _find_relevant_databases(self, query):
        """Find databases that might contain data for this query"""
        # Use LLM to analyze query and determine which DBs might be relevant
        # Return list of db_types in priority order
```

### 4.2 Query Generation and Execution

**Challenge:** Generating and executing optimized queries for multiple databases.

**Strategy:**
- Parallelize independent database queries with `asyncio.gather()`
- Implement smart database selection to avoid unnecessary queries
- Use a DAG (Directed Acyclic Graph) to represent query dependencies

**Implementation:**
```python
# In cross_orchestrator.py
async def execute_plan(self, plan):
    """Execute a query plan across multiple databases"""
    # Track operation outputs
    outputs = {}
    
    # Identify operations that can be executed in parallel
    operation_graph = self._build_operation_graph(plan['operations'])
    
    # Execute operations in dependency order
    for level in operation_graph:
        level_tasks = []
        
        # Create tasks for all operations at this level
        for op in level:
            task = asyncio.create_task(self._execute_operation(op, outputs))
            level_tasks.append((op['id'], task))
            
        # Wait for all operations at this level to complete
        for op_id, task in level_tasks:
            try:
                result = await task
                outputs[op_id] = result
            except Exception as e:
                logger.error(f"Operation {op_id} failed: {e}")
                raise
                
    # Return final output
    return outputs.get(plan['final_output'])
```

### 4.3 Result Aggregation

**Challenge:** Combining heterogeneous data formats from different database types.

**Strategy:**
- Standardize result format across adapters
- Implement type conversion for cross-database joins
- Support both early materialization (pull all data) and late materialization (push down joins where possible)

**Implementation:**
```python
# New file: server/agent/db/aggregator.py
class ResultAggregator:
    """Handles data aggregation operations across results from multiple databases"""
    
    def join(self, left_data, right_data, left_key, right_key):
        """Join two result sets on specified keys"""
        # Normalize data format if needed
        left_data = self._normalize_results(left_data)
        right_data = self._normalize_results(right_data)
        
        # Build lookup table for right data
        lookup = {}
        for item in right_data:
            key_value = item.get(right_key)
            if key_value not in lookup:
                lookup[key_value] = []
            lookup[key_value].append(item)
            
        # Perform join
        results = []
        for left_item in left_data:
            left_value = left_item.get(left_key)
            matching_right = lookup.get(left_value, [])
            
            if not matching_right:  # No match, outer join would include this
                continue
                
            # Create joined records
            for right_item in matching_right:
                joined = {**left_item}  # Copy left item
                # Add right item fields with prefix to avoid collisions
                for k, v in right_item.items():
                    if k != right_key:  # Avoid duplicate join key
                        joined[f"r_{k}"] = v
                results.append(joined)
                
        return results
```

## 5. Implementation Strategy

### 5.1 Phased Approach

1. **Phase 1: Unified Schema Layer**
   - Implement `UnifiedSchemaSearcher` class
   - Update schema indexing to tag with database source
   - Enhance config.yaml with cross-database settings

2. **Phase 2: Query Planning**
   - Create cross-database prompt templates
   - Implement LLM-based query planning in `CrossDatabaseOrchestrator`
   - Add DAG representation for execution plans

3. **Phase 3: Parallel Execution**
   - Implement parallel query execution
   - Create result transformation functions
   - Develop aggregation operations (join, union, etc.)

4. **Phase 4: Enhanced CLI and API**
   - Update `server/agent/cmd/query.py` with cross-database flag
   - Add API endpoints for cross-database operations
   - Implement progress tracking for long-running operations

### 5.2 Code Structure Updates

```
server/agent/
├── db/
│   ├── cross_orchestrator.py     # NEW: Cross-database orchestration
│   ├── aggregator.py             # NEW: Result aggregation logic
│   ├── dag.py                    # NEW: Dependency graph for operations
│   ├── query_plan.py             # NEW: Query plan representation
│   └── adapters/                 # EXISTING: Database-specific adapters
├── meta/
│   ├── unified_searcher.py       # NEW: Cross-database schema search
│   └── ingest.py                 # MODIFIED: Enhanced schema handling
├── prompts/
│   ├── cross_db_plan.tpl         # NEW: Cross-database planning template
│   └── cross_db_analyze.tpl      # NEW: Cross-database analysis template
└── cmd/
    └── query.py                  # MODIFIED: Add cross-database support
```

### 5.3 Testing Strategy

1. **Unit Tests**
   - Test each component in isolation (schema search, plan generation, etc.)
   - Mock database responses for predictable testing

2. **Integration Tests**
   - Test with multiple real database instances
   - Measure performance metrics and optimize

3. **Sample Queries**
   - Create test suite with representative cross-database queries
   - Validate results against expected output

## 6. Advanced Features

### 6.1 Data Federation Layer

For complex cases where simple query routing isn't sufficient, implement a data federation layer:

```python
# server/agent/db/federation.py
class DataFederationService:
    """Provides virtual unified view across multiple databases"""
    
    def __init__(self, cross_orchestrator):
        self.orchestrator = cross_orchestrator
        self.virtual_views = {}  # Maps virtual view names to source mappings
        
    def register_virtual_view(self, view_name, mappings):
        """Register a virtual view that spans multiple databases"""
        self.virtual_views[view_name] = mappings
        
    async def query_virtual_view(self, view_name, filters=None, projection=None):
        """Query a virtual view with optional filters and projections"""
        if view_name not in self.virtual_views:
            raise ValueError(f"Virtual view {view_name} not found")
            
        mapping = self.virtual_views[view_name]
        
        # Generate and execute query plan based on virtual view
        plan = self._generate_plan_from_mapping(mapping, filters, projection)
        return await self.orchestrator.execute_plan(plan)
```

### 6.2 Semantic Layer

Implement a semantic layer to abstract database details and provide business-meaningful entities:

```python
# server/agent/semantic/model.py
class SemanticModel:
    """Business-oriented semantic model over raw database schemas"""
    
    def __init__(self):
        self.entities = {}  # Business entities (Customer, Order, etc.)
        self.metrics = {}   # Business metrics (Revenue, Engagement, etc.)
        self.dimensions = {} # Business dimensions (Time, Geography, etc.)
        
    def register_entity(self, entity_name, db_mappings):
        """Register a business entity with its database mappings"""
        self.entities[entity_name] = {
            'db_mappings': db_mappings,
            'description': f"Business entity representing {entity_name}"
        }
```

### 6.3 Caching and Materialized Views

Implement caching for expensive cross-database operations:

```python
# server/agent/performance/cache.py
class QueryCache:
    """Cache for cross-database query results"""
    
    def __init__(self, max_size=100, ttl=3600):
        self.cache = {}  # Map of query_hash -> result
        self.max_size = max_size
        self.ttl = ttl
        
    async def get(self, query_plan):
        """Get cached result for query plan if available"""
        query_hash = self._hash_plan(query_plan)
        cached = self.cache.get(query_hash)
        
        if cached and time.time() - cached['timestamp'] < self.ttl:
            return cached['result']
            
        return None
        
    async def set(self, query_plan, result):
        """Cache result for query plan"""
        query_hash = self._hash_plan(query_plan)
        
        # Implement LRU eviction if needed
        if len(self.cache) >= self.max_size:
            self._evict_oldest()
            
        self.cache[query_hash] = {
            'result': result,
            'timestamp': time.time()
        }
```

## 7. Future Considerations

### 7.1 Real-time Data Updates

As the system evolves, consider adding real-time data update capabilities:

- Implement Change Data Capture (CDC) from database sources
- Create real-time materialized views for frequently joined data
- Support streaming aggregations for time-series data

### 7.2 Scaling and Performance

For larger deployments:

- Implement distributed execution coordinator
- Add worker nodes for parallel processing
- Consider specialized optimization for specific database types

### 7.3 Security and Access Control

Enhanced security features:

- Row-level security across databases
- Unified access control model
- Query auditing and governance

### 7.4 User Experience

Improvements to user interaction:

- Interactive query building with database recommendations
- Query cost estimation before execution
- Progressive result loading for long-running queries

## 8. Conclusion

This cross-database orchestration architecture builds upon the existing Data Connector framework to provide seamless querying across heterogeneous data sources. By implementing the components and strategies outlined in this document, the system will be able to:

1. Intelligently route queries to appropriate databases
2. Execute operations in parallel where possible
3. Join and aggregate data across different database types
4. Provide unified analysis on heterogeneous data

This approach leverages the strengths of your existing adapter pattern while adding new orchestration capabilities to deliver a powerful cross-database querying experience. 
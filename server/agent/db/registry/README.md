# Schema Registry

The Schema Registry is a centralized repository for storing and retrieving metadata about all data sources in the system. It provides a unified view of tables, collections, and their schemas across different database types (PostgreSQL, MongoDB, Qdrant, Slack, etc.).

## Features

- Single source of truth for all database schema metadata
- Support for multiple data sources (PostgreSQL, MongoDB, Qdrant, Slack)
- Schema versioning to track changes over time
- Business ontology mapping for semantic understanding
- SQLite-based for embedded, lightweight operation

## Usage

### Basic Operations

```python
from agent.db.registry import (
    init_registry, 
    list_data_sources, 
    get_table_schema
)

# Initialize registry
init_registry()

# List all data sources
sources = list_data_sources()
print(sources)

# Get schema for a specific table
schema = get_table_schema("postgres_main", "customers")
print(schema)
```

### Using the Client Interface

```python
from agent.db.registry.integrations import registry_client

# Get recommended data sources for a query
query = "Find all customers who made purchases last month"
sources = registry_client.get_recommended_sources_for_query(query)

# Get schema summary for these sources
summary = registry_client.get_schema_summary_for_sources(list(sources))
print(summary)
```

### Using the Database Classifier

```python
from agent.db.classifier import classifier

# Classify a question to determine which databases to query
question = "Find all customers who made purchases last month"
result = classifier.classify(question)

# The result contains the recommended sources, reasoning, and schema summary
print(f"Sources: {result['sources']}")
print(f"Reasoning: {result['reasoning']}")
print(f"Schema: {result['schemas']}")
```

## Introspection

The registry includes an introspection worker that automatically discovers and catalogs schema information from all connected data sources:

```bash
# Run the introspection
python -m agent.db.registry.run_introspection
```

Configuration for data sources comes from your `~/.data-connector/config.yaml` file.

## Schema Change Detection

The registry provides a schema watcher that can detect changes in your database schemas without constant polling:

```bash
# Run the schema watcher with default settings (checks every hour)
python -m agent.db.registry.schema_watcher

# Run with custom check interval (in seconds)
python -m agent.db.registry.schema_watcher --interval 1800  # 30 minutes

# Run a one-time check for schema changes
python -m agent.db.registry.schema_watcher --one-time
```

The watcher uses different methods for different database types:

1. **PostgreSQL** - Uses `LISTEN/NOTIFY` with event triggers where possible
2. **MongoDB** - Uses Change Streams (requires replica set)
3. **Qdrant** - Monitors vector collections and their configurations
4. **All databases** - Falls back to a fingerprinting approach that detects changes by comparing schema signatures

When a schema change is detected, the watcher automatically updates the registry for the affected database(s) only.

### Vector Database Support

The schema registry includes comprehensive support for Qdrant vector databases:

- **Collection metadata**: Tracks vector collection names, vector counts, and statuses
- **Vector configurations**: Monitors vector dimensions and distance metrics
- **Payload schemas**: Catalogs field names, data types, and indexing status
- **Automatic change detection**: Identifies when collections are added, removed, or modified

This enables intelligent query routing across both relational and vector databases, allowing applications to determine when to use vector similarity search versus traditional queries.

## Docker Support

When running in Docker, the schema registry data is persisted in a volume defined in `docker-compose.yml`. The registry automatically detects the Docker environment and uses the appropriate connection URIs.

## Testing

Run the test suite to verify functionality:

```bash
# Test the basic registry functions
python -m agent.db.registry.test_registry

# Test the client interface
python -m agent.db.registry.test_client

# Test the database classifier
python -m agent.db.classifier
```

### Cleaning Up Test Data

After running tests, you may want to remove test databases from the registry to keep only production data sources:

```bash
# Clean up test databases (those with IDs starting with 'test_')
python -m agent.db.registry.cleanup_test_dbs
```

## Integration

The Schema Registry is a key component of the Database Classification Module and Cross-DB Orchestrator. It provides the metadata needed to determine which databases to query for a given question and how to join data across multiple sources. 
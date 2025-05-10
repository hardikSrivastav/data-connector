# Schema Monitoring System

This module provides automatic monitoring and reindexing of database schema changes to ensure that the schema index used for natural language queries stays up-to-date with the actual database schema.

## Overview

The schema monitoring system addresses the challenge of keeping the schema index in sync with database changes. Without this system, when tables or views are added or modified in the database, the schema index would become outdated, leading to incomplete or incorrect query results.

The monitoring works by:

1. Creating a hash of the current database schema
2. Comparing it with the previously stored hash
3. Triggering reindexing when changes are detected
4. Tracking when checks are performed to avoid excessive checking

## Components

The system consists of these main components:

1. `SchemaMonitor` class - Core functionality for detecting schema changes
2. `ensure_schema_index_updated()` - Utility function for integration into application flows
3. `schema_watcher.py` - Standalone script for background monitoring

## Usage

### CLI Command

The `check-schema` command has been added to the Data Connector CLI:

```bash
# Check for schema changes (only reindexes if changes are detected)
python -m server.agent.cmd.query check-schema

# Force reindexing even if no changes are detected
python -m server.agent.cmd.query check-schema --force
```

### Automatic Checking

Schema changes are automatically checked during query execution, ensuring that queries always use up-to-date schema information without requiring manual intervention.

### Background Watcher

For production environments, use the schema watcher script to continuously monitor for changes:

```bash
# Run with default settings (check every 5 minutes)
python -m server.agent.performance.schema_watcher

# Run with custom interval (e.g., check every hour)
python -m server.agent.performance.schema_watcher --interval 3600

# Run once and exit
python -m server.agent.performance.schema_watcher --once
```

This script can be run as a systemd service, cron job, or Docker container to provide continuous monitoring.

## Configuration

The schema monitor uses several configurable parameters:

- `check_interval`: Time in seconds between checks (default: 3600 seconds / 1 hour)
- `SCHEMA_HASH_FILE`: Location where schema hash data is stored

## Integration

You can integrate schema monitoring into your own code with:

```python
from agent.performance import ensure_schema_index_updated

# Check and update if needed
updated, message = await ensure_schema_index_updated()

# Force update regardless of changes
updated, message = await ensure_schema_index_updated(force=True)
```

## Logging

The schema monitoring system logs all activities and errors to help with troubleshooting and monitoring.

The standalone watcher logs to:
- Standard output (console)
- A log file at `~/schema_watcher.log` 
# Schema Registry

A centralized, on‑premises Schema Registry provides a single source of truth for all data source metadata—tables, collections, JSON schemas, and business‑level ontologies—while remaining fully embedded and lightweight via SQLite. This document covers design, implementation, advanced features, and integration points.

---

## 1. Purpose & Benefits

* **Uniform Metadata**: Centralized storage of schema definitions for PostgreSQL, MongoDB, Qdrant, Slack, etc.
* **Schema Contracts**: JSON Schema or Protobuf definitions per table/collection ensure type safety.
* **Versioning & Change Management**: Semantic version tracking, change notifications, and auditability.
* **On‑Prem Compliance**: Fully self‑hosted, no external dependencies, can run embedded.

---

## 2. SQLite Implementation

### 2.1 Database Schema (registry\_schema.sql)

```sql
PRAGMA foreign_keys = ON;

-- Data sources metadata
CREATE TABLE IF NOT EXISTS data_sources (
  id         TEXT   PRIMARY KEY,   -- e.g., "postgres_users"
  uri        TEXT   NOT NULL,      -- connection string
  type       TEXT   NOT NULL,      -- "postgres", "mongo", "qdrant", etc.
  version    TEXT   NOT NULL,      -- semver, e.g. "1.0.0"
  updated_at INTEGER NOT NULL      -- Unix epoch millis
);

-- Tables/Collections metadata
CREATE TABLE IF NOT EXISTS table_meta (
  source_id   TEXT   NOT NULL,      -- FK -> data_sources.id
  table_name  TEXT   NOT NULL,      -- e.g., "customers"
  schema_json TEXT   NOT NULL,      -- JSON-stringified field definitions
  version     TEXT   NOT NULL,      -- semver for this table
  updated_at  INTEGER NOT NULL,     -- Unix epoch millis
  PRIMARY KEY (source_id, table_name),
  FOREIGN KEY (source_id) REFERENCES data_sources(id) ON DELETE CASCADE
);

-- Optional: Business ontology mapping
CREATE TABLE IF NOT EXISTS ontology_mapping (
  entity_name   TEXT   PRIMARY KEY,  -- e.g., "Customer"
  source_tables TEXT   NOT NULL     -- JSON array of ["source_id.table_name"]
);
```

### 2.2 Python Registry Module (registry.py)

```python
import sqlite3, json, time
from pathlib import Path

# Path to the embedded registry database
DB_PATH = Path(__file__).parent / "schema_registry.db"

def get_conn():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def init_registry():
    ddl = open(Path(__file__).parent / "registry_schema.sql").read()
    with get_conn() as c:
        c.executescript(ddl)

# Data source operations
def list_data_sources():
    with get_conn() as c:
        return [dict(row) for row in c.execute("SELECT * FROM data_sources")]

def upsert_data_source(id, uri, type, version):
    now = int(time.time() * 1000)
    with get_conn() as c:
        c.execute("""
            INSERT INTO data_sources (id, uri, type, version, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
              uri=excluded.uri,
              type=excluded.type,
              version=excluded.version,
              updated_at=excluded.updated_at
        """, (id, uri, type, version, now))

# Table metadata operations
def upsert_table_meta(source_id, table_name, schema_dict, version):
    now = int(time.time() * 1000)
    schema_json = json.dumps(schema_dict)
    with get_conn() as c:
        c.execute("""
            INSERT INTO table_meta (source_id, table_name, schema_json, version, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(source_id, table_name) DO UPDATE SET
              schema_json=excluded.schema_json,
              version=excluded.version,
              updated_at=excluded.updated_at
        """, (source_id, table_name, schema_json, version, now))

def get_table_schema(source_id, table_name):
    with get_conn() as c:
        row = c.execute(
            "SELECT schema_json FROM table_meta WHERE source_id=? AND table_name=?",
            (source_id, table_name)
        ).fetchone()
    return json.loads(row["schema_json"]) if row else None

def list_tables(source_id):
    with get_conn() as c:
        return [row["table_name"]
                for row in c.execute(
                    "SELECT table_name FROM table_meta WHERE source_id=?", (source_id,)
                )]
```

### 2.3 Introspection Worker (introspect.py)

```python
# Example for PostgreSQL; repeat for Mongo, Qdrant, etc.
from registry import upsert_data_source, upsert_table_meta
import your_postgres_adapter

def introspect_postgres(source_id, uri):
    # Register the source
    upsert_data_source(source_id, uri, "postgres", version="1.0.0")
    # Fetch and store schema
    schema = your_postgres_adapter.fetch_schema(uri)  # returns dict of {table: {col: type}}
    for table, cols in schema.items():
        upsert_table_meta(source_id, table, cols, version="1.0.0")

if __name__ == "__main__":
    introspect_postgres("postgres_users", "postgresql://...connection...")
```

### 2.4 Bootstrapping & Migration

* **First Run**: Call `init_registry()` at orchestrator startup to create tables.
* **Seeding**: Run `introspect.py` (or schedule periodically) to populate metadata.
* **Schema Evolution**: Introspection worker bumps `version` and `updated_at` on changes; applications subscribe to change events.
* **Future Swap**: Swap SQLite for Postgres by changing the connection string and ensuring identical schema—no client code changes required.

---

## 3. Advanced Features

### 3.1 Semantic Versioning & Change Notifications

* **TableMeta.version** uses semantic versioning:

  * MAJOR for breaking changes (dropped fields)
  * MINOR for additions (new optional fields)
  * PATCH for metadata-only edits
* Registry emits webhooks or Kafka events on schema changes for planners/doers to refresh caches.

### 3.2 Ontology & Business Glossary

* Use the `ontology_mapping` table to link domain entities (e.g., "Customer") to one or more physical tables.
* Planning Agent prompts reference ontological names; Implementation Agent resolves these to `source_id.table_name` via registry lookup.

### 3.3 Validation & Dry-Run Contracts

1. **Compile-Time Checks**: Planner’s output code is validated against `table_meta.schema_json` to ensure referenced fields exist and types match.
2. **Dry-Run Phase**: Doer issues `EXPLAIN` or `findOne(limit=0)` to verify syntax and permissions before live execution.
3. **Runtime Guards**: Adapters assert returned row types against registry contracts, logging mismatches.

### 3.4 Security & Access Control

* **Scoped Introspection Credentials**: Worker uses read‑only creds for schema discovery only.
* **Vault Integration**: Runtime credentials for Doer fetched from the same on‑prem Vault; registry stores only URIs and metadata.
* **Encryption**: `schema_registry.db` can live on encrypted volumes (e.g., LUKS, EBS encryption).

### 3.5 Deployment & CI/CD

* **Containerization**: Package registry (DDL, `registry.py`, introspection) in a Docker image or Helm chart.
* **High Availability**: For HA, run multiple orchestrator instances pointing to a shared SQLite on clustered storage—or migrate to Postgres if needed.
* **Testing**: Use Docker Compose to spin up the registry and sample DBs; run automated end‑to‑end tests on every commit.

---

## 4. Integration Points

* **Planning Agent**:

  * Calls `list_data_sources()` → obtains available sources.
  * Uses `list_tables()` & `get_table_schema()` to embed schema summaries in prompts.
  * Reads ontology mappings for semantic planning.

* **Implementation Agent**:

  * Before executing each snippet, checks target table presence and field contracts via registry.
  * Runs dry‑run validations and executes queries under timeouts and retries.

---

*End of schema registry spec.*

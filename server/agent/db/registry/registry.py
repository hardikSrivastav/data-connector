import sqlite3
import json
import time
import os
from pathlib import Path
from typing import Dict, List, Any, Optional, Union

# Path to the embedded registry database
# Use environment variable if set, otherwise use default path
DB_PATH = Path(os.environ.get(
    "SCHEMA_REGISTRY_PATH", 
    str(Path(__file__).parent / "schema_registry.db")
))

# Ensure the parent directory exists
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

SCHEMA_PATH = Path(__file__).parent / "schema.sql"

def get_conn():
    """Get a connection to the SQLite database with row factory enabled"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def init_registry():
    """Initialize the registry database with the schema"""
    if not SCHEMA_PATH.exists():
        raise FileNotFoundError(f"Schema file not found at {SCHEMA_PATH}")
        
    ddl = SCHEMA_PATH.read_text()
    with get_conn() as conn:
        conn.executescript(ddl)
    
    return True

# Data source operations
def list_data_sources() -> List[Dict[str, Any]]:
    """List all registered data sources"""
    with get_conn() as conn:
        return [dict(row) for row in conn.execute("SELECT * FROM data_sources")]

def get_data_source(source_id: str) -> Optional[Dict[str, Any]]:
    """Get a specific data source by ID"""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM data_sources WHERE id = ?", 
            (source_id,)
        ).fetchone()
    
    return dict(row) if row else None

def upsert_data_source(id: str, uri: str, type: str, version: str = "1.0.0") -> bool:
    """Add or update a data source in the registry"""
    now = int(time.time() * 1000)
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO data_sources (id, uri, type, version, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
              uri=excluded.uri,
              type=excluded.type,
              version=excluded.version,
              updated_at=excluded.updated_at
        """, (id, uri, type, version, now))
    
    return True

def delete_data_source(source_id: str) -> bool:
    """Delete a data source and its related table metadata (cascade)"""
    with get_conn() as conn:
        conn.execute("DELETE FROM data_sources WHERE id = ?", (source_id,))
    
    return True

# Table metadata operations
def list_tables(source_id: str) -> List[str]:
    """List all tables for a given data source"""
    with get_conn() as conn:
        return [row["table_name"]
                for row in conn.execute(
                    "SELECT table_name FROM table_meta WHERE source_id = ?", 
                    (source_id,)
                )]

def upsert_table_meta(
    source_id: str, 
    table_name: str, 
    schema_dict: Dict[str, Any], 
    version: str = "1.0.0"
) -> bool:
    """Add or update table metadata in the registry"""
    now = int(time.time() * 1000)
    schema_json = json.dumps(schema_dict)
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO table_meta (source_id, table_name, schema_json, version, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(source_id, table_name) DO UPDATE SET
              schema_json=excluded.schema_json,
              version=excluded.version,
              updated_at=excluded.updated_at
        """, (source_id, table_name, schema_json, version, now))
    
    return True

def get_table_schema(source_id: str, table_name: str) -> Optional[Dict[str, Any]]:
    """Get schema for a specific table"""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT schema_json, version, updated_at FROM table_meta WHERE source_id = ? AND table_name = ?",
            (source_id, table_name)
        ).fetchone()
    
    if row:
        result = {
            "schema": json.loads(row["schema_json"]),
            "version": row["version"],
            "updated_at": row["updated_at"]
        }
        return result
    return None

def delete_table_meta(source_id: str, table_name: str) -> bool:
    """Delete table metadata for a specific table"""
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM table_meta WHERE source_id = ? AND table_name = ?",
            (source_id, table_name)
        )
    
    return True

# Ontology operations
def get_ontology_mapping(entity_name: str) -> Optional[List[str]]:
    """Get source tables for a business entity"""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT source_tables FROM ontology_mapping WHERE entity_name = ?",
            (entity_name,)
        ).fetchone()
    
    return json.loads(row["source_tables"]) if row else None

def set_ontology_mapping(entity_name: str, source_tables: List[str]) -> bool:
    """Set or update ontology mapping for a business entity"""
    source_tables_json = json.dumps(source_tables)
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO ontology_mapping (entity_name, source_tables)
            VALUES (?, ?)
            ON CONFLICT(entity_name) DO UPDATE SET
              source_tables=excluded.source_tables
        """, (entity_name, source_tables_json))
    
    return True

def list_ontology_entities() -> List[Dict[str, Any]]:
    """List all business entities in the ontology"""
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM ontology_mapping").fetchall()
    
    return [{
        "entity_name": row["entity_name"],
        "source_tables": json.loads(row["source_tables"])
    } for row in rows]

# Search and utility functions
def search_tables_by_name(name_pattern: str) -> List[Dict[str, Any]]:
    """Search tables by name pattern"""
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT m.source_id, m.table_name, m.version, m.updated_at, d.type
            FROM table_meta m
            JOIN data_sources d ON m.source_id = d.id
            WHERE m.table_name LIKE ?
            ORDER BY m.source_id, m.table_name
        """, (f"%{name_pattern}%",)).fetchall()
    
    return [dict(row) for row in rows]

def search_schema_content(text_pattern: str) -> List[Dict[str, Any]]:
    """Search for text pattern in table schemas"""
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT m.source_id, m.table_name, m.version, m.updated_at, d.type
            FROM table_meta m
            JOIN data_sources d ON m.source_id = d.id
            WHERE m.schema_json LIKE ?
            ORDER BY m.source_id, m.table_name
        """, (f"%{text_pattern}%",)).fetchall()
    
    return [dict(row) for row in rows]

if __name__ == "__main__":
    # Initialize the registry when run directly
    init_registry()
    print(f"Schema registry initialized at {DB_PATH}") 
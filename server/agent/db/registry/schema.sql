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
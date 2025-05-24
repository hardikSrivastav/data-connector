import asyncpg
from typing import Dict, List, Any, Optional
from ..config.settings import Settings
from urllib.parse import urlparse
import logging

# Configure logging
logger = logging.getLogger(__name__)

async def fetch_schema(pool: asyncpg.Pool) -> Dict[str, Any]:
    """
    Fetch database schema metadata using asyncpg
    
    Args:
        pool: asyncpg connection pool
        
    Returns:
        Dictionary containing tables, columns, and relationships metadata
    """
    async with pool.acquire() as conn:
        # Get all tables in the public schema
        tables = await conn.fetch("""
            SELECT 
                table_name 
            FROM 
                information_schema.tables 
            WHERE 
                table_schema='public' 
                AND table_type='BASE TABLE'
            ORDER BY 
                table_name
        """)
        
        # Get all columns with their data types
        columns = await conn.fetch("""
            SELECT 
                table_name, 
                column_name, 
                data_type,
                column_default,
                is_nullable 
            FROM 
                information_schema.columns 
            WHERE 
                table_schema='public'
            ORDER BY 
                table_name, 
                ordinal_position
        """)
        
        # Get primary key constraints
        primary_keys = await conn.fetch("""
            SELECT
                tc.table_name,
                kc.column_name
            FROM
                information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kc ON
                    tc.constraint_name = kc.constraint_name AND
                    tc.table_schema = kc.table_schema
            WHERE
                tc.constraint_type = 'PRIMARY KEY' AND
                tc.table_schema = 'public'
            ORDER BY
                tc.table_name,
                kc.ordinal_position
        """)
        
        # Get foreign key relationships
        foreign_keys = await conn.fetch("""
            SELECT
                tc.table_name,
                kcu.column_name,
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name
            FROM
                information_schema.table_constraints AS tc
                JOIN information_schema.key_column_usage AS kcu ON
                    tc.constraint_name = kcu.constraint_name AND
                    tc.table_schema = kcu.table_schema
                JOIN information_schema.constraint_column_usage AS ccu ON
                    ccu.constraint_name = tc.constraint_name AND
                    ccu.table_schema = tc.table_schema
            WHERE
                tc.constraint_type = 'FOREIGN KEY' AND
                tc.table_schema = 'public'
            ORDER BY
                tc.table_name,
                kcu.ordinal_position
        """)
        
        # Get table row counts (approximate)
        row_counts = await conn.fetch("""
            SELECT
                relname as table_name,
                n_live_tup as row_count
            FROM
                pg_stat_user_tables
            ORDER BY
                relname
        """)
        
        # Bundle everything into a structured schema object
        return {
            "tables": [dict(t) for t in tables],
            "columns": [dict(c) for c in columns],
            "primary_keys": [dict(pk) for pk in primary_keys],
            "foreign_keys": [dict(fk) for fk in foreign_keys],
            "row_counts": [dict(rc) for rc in row_counts]
        }

async def format_schema_for_embedding(schema_data: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    Format the schema data into documents suitable for embedding
    
    Args:
        schema_data: Schema data from fetch_schema
        
    Returns:
        List of documents (dicts with 'id' and 'content' keys)
    """
    documents = []
    
    # Create a document for each table with its description
    table_columns = {}
    for col in schema_data["columns"]:
        if col["table_name"] not in table_columns:
            table_columns[col["table_name"]] = []
        table_columns[col["table_name"]].append(col)
    
    # Identify primary keys for each table
    table_pks = {}
    for pk in schema_data["primary_keys"]:
        if pk["table_name"] not in table_pks:
            table_pks[pk["table_name"]] = []
        table_pks[pk["table_name"]].append(pk["column_name"])
    
    # Identify foreign keys for each table
    table_fks = {}
    for fk in schema_data["foreign_keys"]:
        if fk["table_name"] not in table_fks:
            table_fks[fk["table_name"]] = []
        table_fks[fk["table_name"]].append(
            f"{fk['column_name']} -> {fk['foreign_table_name']}.{fk['foreign_column_name']}"
        )
    
    # Generate row counts lookup
    row_count_lookup = {rc["table_name"]: rc["row_count"] for rc in schema_data["row_counts"]}
    
    # Create a document for each table
    for table in schema_data["tables"]:
        table_name = table["table_name"]
        columns_info = table_columns.get(table_name, [])
        
        # Format column information
        cols_text = "\n".join([
            f"- {col['column_name']} ({col['data_type']})" +
            (", PRIMARY KEY" if table_pks.get(table_name) and col['column_name'] in table_pks[table_name] else "") +
            (", NOT NULL" if col['is_nullable'] == 'NO' else "")
            for col in columns_info
        ])
        
        # Format primary key information
        pks_text = ", ".join(table_pks.get(table_name, []))
        
        # Format foreign key information
        fks_text = "\n".join(table_fks.get(table_name, []))
        
        # Get approximate row count
        row_count = row_count_lookup.get(table_name, 0)
        
        # Create document content
        content = f"""
        TABLE: {table_name}
        APPROXIMATE ROW COUNT: {row_count}
        
        COLUMNS:
        {cols_text}
        
        PRIMARY KEY: {pks_text or 'None'}
        
        FOREIGN KEYS:
        {fks_text or 'None'}
        """
        
        # Add table document
        documents.append({
            "id": f"table:{table_name}",
            "content": content.strip()
        })
    
    return documents

async def create_connection_pool() -> asyncpg.Pool:
    """
    Create and return an asyncpg connection pool
    """
    settings = Settings()
    return await asyncpg.create_pool(
        dsn=settings.db_dsn,
        min_size=5,
        max_size=20
    )

async def get_schema_metadata(conn_uri: Optional[str] = None, db_type: Optional[str] = None, **kwargs) -> List[Dict[str, str]]:
    """
    Main function to get formatted schema metadata ready for embedding.
    Now database-agnostic, supporting all adapter types.
    
    Args:
        conn_uri: Optional connection URI. If None, uses the default from settings.
        db_type: Optional database type. If provided, overrides detection from URI.
        **kwargs: Additional adapter-specific parameters
        
    Returns:
        List of document dictionaries with 'id' and 'content' keys
    """
    settings = Settings()
    
    # Use provided URI or fall back to settings
    uri = conn_uri or settings.connection_uri
    
    # Determine database type from arguments, then URI if not provided
    if not db_type:
        parsed_uri = urlparse(uri)
        
        # For HTTP URIs, don't use the scheme as db_type
        if parsed_uri.scheme in ['http', 'https']:
            db_type = settings.DB_TYPE
        else:
            # Use scheme for other database URIs
            db_type = parsed_uri.scheme
    
    # Log which database we're introspecting
    logger.info(f"Introspecting schema for database type: {db_type}")
    
    if db_type in ["postgresql", "postgres"]:
        # Use existing PostgreSQL implementation for backward compatibility
        pool = await create_connection_pool()
        try:
            schema_data = await fetch_schema(pool)
            return await format_schema_for_embedding(schema_data)
        finally:
            await pool.close()
    else:
        # For all other database types, use the orchestrator
        from ..db.db_orchestrator import Orchestrator
        
        # Always pass the explicitly determined db_type to the orchestrator
        kwargs['db_type'] = db_type
        
        # Create orchestrator with the appropriate adapter
        orchestrator = Orchestrator(uri, **kwargs)
        
        # Use the adapter's introspect_schema method
        return await orchestrator.introspect_schema()

if __name__ == "__main__":
    import asyncio
    
    async def print_schema():
        documents = await get_schema_metadata()
        for doc in documents:
            print(f"\n=== {doc['id']} ===")
            print(doc['content'])
            print("\n" + "="*50)
    
    asyncio.run(print_schema())

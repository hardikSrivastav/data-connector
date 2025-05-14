#!/usr/bin/env python3
"""
Database migration script to create and update database schema.
Run this script manually after adding new models or columns.
"""
import os
import sys
import logging
from sqlalchemy import create_engine, text, inspect

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add the parent directory to path so we can import the module
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(os.path.dirname(current_dir))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from agent.mcp.config import settings

def get_db_url():
    """Get the database URL from settings"""
    return f"postgresql://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"

def table_exists(engine, table_name):
    """Check if a table exists in the database"""
    inspector = inspect(engine)
    return table_name in inspector.get_table_names()

def column_exists(engine, table_name, column_name):
    """Check if a column exists in a table"""
    inspector = inspect(engine)
    if not table_name in inspector.get_table_names():
        return False
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns

def run_migration():
    """Execute the database migrations"""
    engine = create_engine(get_db_url())
    
    # Add User and SlackWorkspace columns if they don't exist
    user_columns = [
        ("is_temporary", "BOOLEAN DEFAULT FALSE"),
        ("session_id", "VARCHAR(64) UNIQUE")
    ]
    
    workspace_columns = [
        ("user_token", "TEXT"),
        ("user_token_scope", "TEXT"),
        ("user_token_expires_at", "TIMESTAMP"),
        ("user_refresh_token", "TEXT")
    ]
    
    user_workspace_columns = [
        ("is_admin", "BOOLEAN DEFAULT FALSE"),
        ("scopes", "TEXT")
    ]
    
    # Apply column migrations
    with engine.connect() as conn:
        # User table columns
        for col_name, col_type in user_columns:
            if not column_exists(engine, "users", col_name):
                sql = f"""
                ALTER TABLE users 
                ADD COLUMN {col_name} {col_type};
                """
                logger.info(f"Adding column {col_name} to users table")
                conn.execute(text(sql))
                conn.commit()
        
        # SlackWorkspace table columns
        for col_name, col_type in workspace_columns:
            if not column_exists(engine, "slack_workspaces", col_name):
                sql = f"""
                ALTER TABLE slack_workspaces 
                ADD COLUMN {col_name} {col_type};
                """
                logger.info(f"Adding column {col_name} to slack_workspaces table")
                conn.execute(text(sql))
                conn.commit()
        
        # UserWorkspace table columns
        for col_name, col_type in user_workspace_columns:
            if not column_exists(engine, "user_workspaces", col_name):
                sql = f"""
                ALTER TABLE user_workspaces 
                ADD COLUMN {col_name} {col_type};
                """
                logger.info(f"Adding column {col_name} to user_workspaces table")
                conn.execute(text(sql))
                conn.commit()
    
    # Create new tables for message indexing if they don't exist
    with engine.connect() as conn:
        # SlackMessageIndex table
        if not table_exists(engine, "slack_message_indexes"):
            sql = """
            CREATE TABLE slack_message_indexes (
                id SERIAL PRIMARY KEY,
                workspace_id INTEGER REFERENCES slack_workspaces(id) UNIQUE,
                collection_name VARCHAR(255) NOT NULL,
                last_indexed_at TIMESTAMP,
                last_completed_at TIMESTAMP,
                is_indexing BOOLEAN DEFAULT FALSE,
                total_messages INTEGER DEFAULT 0,
                indexed_messages INTEGER DEFAULT 0,
                oldest_message_ts VARCHAR(255),
                newest_message_ts VARCHAR(255),
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),
                history_days INTEGER DEFAULT 30,
                update_frequency_hours INTEGER DEFAULT 6,
                embedding_model VARCHAR(255) DEFAULT 'all-MiniLM-L6-v2'
            );
            """
            logger.info("Creating slack_message_indexes table")
            conn.execute(text(sql))
            conn.commit()
        
        # IndexedChannel table
        if not table_exists(engine, "indexed_channels"):
            sql = """
            CREATE TABLE indexed_channels (
                id SERIAL PRIMARY KEY,
                index_id INTEGER REFERENCES slack_message_indexes(id),
                channel_id VARCHAR(255) NOT NULL,
                channel_name VARCHAR(255) NOT NULL,
                last_indexed_ts VARCHAR(255),
                message_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),
                UNIQUE (index_id, channel_id)
            );
            """
            logger.info("Creating indexed_channels table")
            conn.execute(text(sql))
            conn.commit()
    
    logger.info("Database migration completed successfully")

if __name__ == "__main__":
    logger.info("Starting database migration...")
    run_migration()
    logger.info("Migration completed!") 
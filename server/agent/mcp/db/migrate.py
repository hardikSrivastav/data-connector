#!/usr/bin/env python3
"""
Database migration script to add user token columns to the SlackWorkspace table,
and the is_temporary column to the User table.
Run this script manually after adding new columns to the models.
"""
import os
import sys
import logging
from sqlalchemy import create_engine, text

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

def run_migration():
    """Execute the migration to add the new columns"""
    engine = create_engine(get_db_url())
    
    # SQL statements to add the new columns if they don't exist
    sql_statements = [
        # Columns for SlackWorkspace
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                         WHERE table_name='slack_workspaces' AND column_name='user_token') THEN
                ALTER TABLE slack_workspaces ADD COLUMN user_token TEXT NULL;
            END IF;
        END
        $$;
        """,
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                         WHERE table_name='slack_workspaces' AND column_name='user_token_scope') THEN
                ALTER TABLE slack_workspaces ADD COLUMN user_token_scope TEXT NULL;
            END IF;
        END
        $$;
        """,
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                         WHERE table_name='slack_workspaces' AND column_name='user_token_expires_at') THEN
                ALTER TABLE slack_workspaces ADD COLUMN user_token_expires_at TIMESTAMP NULL;
            END IF;
        END
        $$;
        """,
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                         WHERE table_name='slack_workspaces' AND column_name='user_refresh_token') THEN
                ALTER TABLE slack_workspaces ADD COLUMN user_refresh_token TEXT NULL;
            END IF;
        END
        $$;
        """,
        
        # Column for User model - is_temporary
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                         WHERE table_name='users' AND column_name='is_temporary') THEN
                ALTER TABLE users ADD COLUMN is_temporary BOOLEAN DEFAULT FALSE;
            END IF;
        END
        $$;
        """,
        
        # Column for UserWorkspace model - is_admin
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                         WHERE table_name='user_workspaces' AND column_name='is_admin') THEN
                ALTER TABLE user_workspaces ADD COLUMN is_admin BOOLEAN DEFAULT FALSE;
            END IF;
        END
        $$;
        """
    ]
    
    with engine.connect() as conn:
        for sql in sql_statements:
            logger.info(f"Executing migration statement...")
            conn.execute(text(sql))
            conn.commit()
            logger.info(f"Migration statement executed successfully")
    
    logger.info("Database migration completed successfully")

if __name__ == "__main__":
    logger.info("Starting migration to add new columns...")
    run_migration()
    logger.info("Migration completed!") 
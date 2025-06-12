"""
Database Migration: Add User Ownership Columns
Phase 2 of User Isolation Implementation

This migration adds owner_id columns to workspaces, pages, and blocks tables
to support proper user data isolation.
"""

import os
import logging
from sqlalchemy import create_engine, text, MetaData, Table, Column, String, Index
from sqlalchemy.orm import sessionmaker
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://notion_user:notion_password@localhost:5432/notion_clone")

def run_migration():
    """Run the user ownership migration"""
    logger.info("🚀 Starting User Ownership Migration (Phase 2)")
    
    try:
        # Create engine and session
        engine = create_engine(DATABASE_URL, echo=True)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        logger.info("✅ Database connection established")
        
        # Step 1: Add owner_id columns
        logger.info("📝 Step 1: Adding owner_id columns...")
        
        # Add owner_id to workspaces table
        try:
            session.execute(text("""
                ALTER TABLE workspaces 
                ADD COLUMN IF NOT EXISTS owner_id VARCHAR(255)
            """))
            logger.info("✅ Added owner_id to workspaces table")
        except Exception as e:
            logger.warning(f"⚠️ workspaces.owner_id may already exist: {e}")
        
        # Add owner_id to pages table
        try:
            session.execute(text("""
                ALTER TABLE pages 
                ADD COLUMN IF NOT EXISTS owner_id VARCHAR(255)
            """))
            logger.info("✅ Added owner_id to pages table")
        except Exception as e:
            logger.warning(f"⚠️ pages.owner_id may already exist: {e}")
        
        # Add owner_id to blocks table
        try:
            session.execute(text("""
                ALTER TABLE blocks 
                ADD COLUMN IF NOT EXISTS owner_id VARCHAR(255)
            """))
            logger.info("✅ Added owner_id to blocks table")
        except Exception as e:
            logger.warning(f"⚠️ blocks.owner_id may already exist: {e}")
        
        session.commit()
        logger.info("✅ Step 1 completed: owner_id columns added")
        
        # Step 2: Migrate existing data
        logger.info("📝 Step 2: Migrating existing data...")
        
        # Get all existing workspaces with user-prefixed IDs
        existing_workspaces = session.execute(text("""
            SELECT id, name FROM workspaces WHERE owner_id IS NULL
        """)).fetchall()
        
        logger.info(f"Found {len(existing_workspaces)} workspaces to migrate")
        
        for workspace in existing_workspaces:
            workspace_id = workspace.id
            
            # Extract user_id from workspace_id if it follows our pattern
            if "_" in workspace_id:
                parts = workspace_id.split("_", 1)
                if parts[0].startswith("user_") or parts[0] == "dev":
                    extracted_user_id = parts[0]
                    original_workspace_id = parts[1]
                    
                    logger.info(f"Migrating workspace {workspace_id} → user: {extracted_user_id}")
                    
                    # Update workspace with owner_id
                    session.execute(text("""
                        UPDATE workspaces 
                        SET owner_id = :owner_id 
                        WHERE id = :workspace_id
                    """), {"owner_id": extracted_user_id, "workspace_id": workspace_id})
                    
                    # Update pages for this workspace
                    session.execute(text("""
                        UPDATE pages 
                        SET owner_id = :owner_id 
                        WHERE workspace_id = :workspace_id
                    """), {"owner_id": extracted_user_id, "workspace_id": workspace_id})
                    
                    # Update blocks for pages in this workspace
                    session.execute(text("""
                        UPDATE blocks 
                        SET owner_id = :owner_id 
                        WHERE page_id IN (
                            SELECT id FROM pages WHERE workspace_id = :workspace_id
                        )
                    """), {"owner_id": extracted_user_id, "workspace_id": workspace_id})
                    
                else:
                    # Handle non-user workspaces (assign to system user)
                    logger.info(f"Assigning workspace {workspace_id} to system user")
                    system_user = "system_admin"
                    
                    session.execute(text("""
                        UPDATE workspaces 
                        SET owner_id = :owner_id 
                        WHERE id = :workspace_id
                    """), {"owner_id": system_user, "workspace_id": workspace_id})
                    
                    session.execute(text("""
                        UPDATE pages 
                        SET owner_id = :owner_id 
                        WHERE workspace_id = :workspace_id
                    """), {"owner_id": system_user, "workspace_id": workspace_id})
                    
                    session.execute(text("""
                        UPDATE blocks 
                        SET owner_id = :owner_id 
                        WHERE page_id IN (
                            SELECT id FROM pages WHERE workspace_id = :workspace_id
                        )
                    """), {"owner_id": system_user, "workspace_id": workspace_id})
            else:
                # Original "main" workspace or other legacy data
                logger.info(f"Assigning legacy workspace {workspace_id} to system user")
                system_user = "system_admin"
                
                session.execute(text("""
                    UPDATE workspaces 
                    SET owner_id = :owner_id 
                    WHERE id = :workspace_id
                """), {"owner_id": system_user, "workspace_id": workspace_id})
                
                session.execute(text("""
                    UPDATE pages 
                    SET owner_id = :owner_id 
                    WHERE workspace_id = :workspace_id
                """), {"owner_id": system_user, "workspace_id": workspace_id})
                
                session.execute(text("""
                    UPDATE blocks 
                    SET owner_id = :owner_id 
                    WHERE page_id IN (
                        SELECT id FROM pages WHERE workspace_id = :workspace_id
                    )
                """), {"owner_id": system_user, "workspace_id": workspace_id})
        
        session.commit()
        logger.info("✅ Step 2 completed: existing data migrated")
        
        # Step 3: Add indexes for performance
        logger.info("📝 Step 3: Adding performance indexes...")
        
        try:
            session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_workspaces_owner_id ON workspaces(owner_id)
            """))
            logger.info("✅ Added index: workspaces.owner_id")
        except Exception as e:
            logger.warning(f"⚠️ Index may already exist: {e}")
        
        try:
            session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_pages_owner_id ON pages(owner_id)
            """))
            logger.info("✅ Added index: pages.owner_id")
        except Exception as e:
            logger.warning(f"⚠️ Index may already exist: {e}")
        
        try:
            session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_blocks_owner_id ON blocks(owner_id)
            """))
            logger.info("✅ Added index: blocks.owner_id")
        except Exception as e:
            logger.warning(f"⚠️ Index may already exist: {e}")
        
        session.commit()
        logger.info("✅ Step 3 completed: performance indexes added")
        
        # Step 4: Add NOT NULL constraints (optional, for future records)
        logger.info("📝 Step 4: Adding constraints...")
        
        # Check data integrity first
        null_workspaces = session.execute(text("""
            SELECT COUNT(*) FROM workspaces WHERE owner_id IS NULL
        """)).scalar()
        
        null_pages = session.execute(text("""
            SELECT COUNT(*) FROM pages WHERE owner_id IS NULL
        """)).scalar()
        
        null_blocks = session.execute(text("""
            SELECT COUNT(*) FROM blocks WHERE owner_id IS NULL
        """)).scalar()
        
        logger.info(f"Data integrity check: {null_workspaces} workspaces, {null_pages} pages, {null_blocks} blocks with NULL owner_id")
        
        if null_workspaces == 0 and null_pages == 0 and null_blocks == 0:
            logger.info("✅ All data has owner_id - constraints can be added later if needed")
        else:
            logger.warning("⚠️ Some records still have NULL owner_id - constraints not added")
        
        session.commit()
        session.close()
        
        logger.info("🎉 Migration completed successfully!")
        
        # Step 5: Verification
        logger.info("📝 Step 5: Verifying migration...")
        verify_migration()
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {str(e)}")
        if 'session' in locals():
            session.rollback()
            session.close()
        raise

def verify_migration():
    """Verify the migration was successful"""
    logger.info("🔍 Verifying migration results...")
    
    try:
        engine = create_engine(DATABASE_URL)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # Check column existence
        workspaces_columns = session.execute(text("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'workspaces' AND column_name = 'owner_id'
        """)).fetchall()
        
        pages_columns = session.execute(text("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'pages' AND column_name = 'owner_id'
        """)).fetchall()
        
        blocks_columns = session.execute(text("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'blocks' AND column_name = 'owner_id'
        """)).fetchall()
        
        logger.info(f"✅ owner_id columns exist: workspaces={len(workspaces_columns)}, pages={len(pages_columns)}, blocks={len(blocks_columns)}")
        
        # Check data distribution
        user_stats = session.execute(text("""
            SELECT owner_id, COUNT(*) as workspace_count 
            FROM workspaces 
            WHERE owner_id IS NOT NULL 
            GROUP BY owner_id
        """)).fetchall()
        
        logger.info("👥 User workspace distribution:")
        for user_id, count in user_stats:
            logger.info(f"   {user_id}: {count} workspaces")
        
        session.close()
        logger.info("✅ Migration verification completed")
        
    except Exception as e:
        logger.error(f"❌ Verification failed: {str(e)}")

def rollback_migration():
    """Rollback the migration if needed"""
    logger.info("🔄 Rolling back User Ownership Migration...")
    
    try:
        engine = create_engine(DATABASE_URL)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # Drop indexes
        session.execute(text("DROP INDEX IF EXISTS idx_workspaces_owner_id"))
        session.execute(text("DROP INDEX IF EXISTS idx_pages_owner_id"))
        session.execute(text("DROP INDEX IF EXISTS idx_blocks_owner_id"))
        
        # Drop columns
        session.execute(text("ALTER TABLE workspaces DROP COLUMN IF EXISTS owner_id"))
        session.execute(text("ALTER TABLE pages DROP COLUMN IF EXISTS owner_id"))
        session.execute(text("ALTER TABLE blocks DROP COLUMN IF EXISTS owner_id"))
        
        session.commit()
        session.close()
        
        logger.info("✅ Migration rollback completed")
        
    except Exception as e:
        logger.error(f"❌ Rollback failed: {str(e)}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "rollback":
        rollback_migration()
    elif len(sys.argv) > 1 and sys.argv[1] == "verify":
        verify_migration()
    else:
        run_migration() 
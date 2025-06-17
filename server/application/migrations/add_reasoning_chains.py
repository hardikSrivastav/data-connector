#!/usr/bin/env python3
"""
Smart Migration: Add Reasoning Chains Table

This migration adds the new reasoning_chains table for independent reasoning chain storage
without affecting any existing data or functionality.

Features:
- Non-destructive: Only adds new table, doesn't modify existing ones
- Idempotent: Can be run multiple times safely
- Preserves existing reasoning chain data in block properties
- Provides migration path for existing data
"""

import os
import sys
import logging
from datetime import datetime
from sqlalchemy import create_engine, text, inspect, Column, String, DateTime, Text, Float, Index, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

# Add the parent directory to the path to import settings
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

try:
    from config.settings import Settings
except ImportError:
    # Try alternative import path
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
    from server.agent.config.settings import Settings

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

Base = declarative_base()

class ReasoningChainDB(Base):
    """New reasoning chains table definition"""
    __tablename__ = "reasoning_chains"
    
    id = Column(String, primary_key=True)  # session_id from streaming
    workspace_id = Column(String, nullable=False)
    page_id = Column(String, nullable=False)
    block_id = Column(String, nullable=True)  # Optional link to block
    user_id = Column(String, nullable=False)  # User isolation
    original_query = Column(Text, nullable=False)
    status = Column(String, default='streaming')  # 'streaming', 'completed', 'failed', 'cancelled'
    progress = Column(Float, default=0.0)  # 0.0 to 1.0
    events = Column(JSONB, default=list)  # Array of reasoning events
    chain_metadata = Column(JSONB, default=dict)  # Session info, timing, classification, etc.
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_reasoning_chains_session_id', 'id'),
        Index('idx_reasoning_chains_workspace_id', 'workspace_id'),
        Index('idx_reasoning_chains_page_id', 'page_id'),
        Index('idx_reasoning_chains_block_id', 'block_id'),
        Index('idx_reasoning_chains_user_id', 'user_id'),
        Index('idx_reasoning_chains_status', 'status'),
        Index('idx_reasoning_chains_created_at', 'created_at'),
        Index('idx_reasoning_chains_user_page', 'user_id', 'page_id'),
    )

def check_table_exists(engine, table_name: str) -> bool:
    """Check if a table exists in the database"""
    inspector = inspect(engine)
    return table_name in inspector.get_table_names()

def check_column_exists(engine, table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table"""
    try:
        inspector = inspect(engine)
        columns = inspector.get_columns(table_name)
        return any(col['name'] == column_name for col in columns)
    except Exception:
        return False

def get_existing_reasoning_data(session: Session) -> list:
    """Extract existing reasoning chain data from block properties"""
    try:
        # Query blocks that have reasoning chain data in their properties
        result = session.execute(text("""
            SELECT 
                b.id as block_id,
                b.page_id,
                p.workspace_id,
                b.properties
            FROM blocks b
            JOIN pages p ON b.page_id = p.id
            WHERE b.properties::text LIKE '%reasoningChain%'
               OR b.properties::text LIKE '%reasoning_chain%'
        """))
        
        existing_data = []
        for row in result:
            try:
                properties = row.properties or {}
                
                # Check for reasoning chain data in various formats
                reasoning_chain = None
                if 'reasoningChain' in properties:
                    reasoning_chain = properties['reasoningChain']
                elif 'canvasData' in properties and 'reasoningChain' in properties['canvasData']:
                    reasoning_chain = properties['canvasData']['reasoningChain']
                
                if reasoning_chain:
                    existing_data.append({
                        'block_id': row.block_id,
                        'page_id': row.page_id,
                        'workspace_id': row.workspace_id,
                        'reasoning_chain': reasoning_chain,
                        'properties': properties
                    })
                    
            except Exception as e:
                logger.warning(f"Error processing block {row.block_id}: {e}")
                continue
        
        return existing_data
        
    except Exception as e:
        logger.error(f"Error extracting existing reasoning data: {e}")
        return []

def migrate_existing_data(session: Session, existing_data: list) -> int:
    """Migrate existing reasoning chain data to new table"""
    migrated_count = 0
    
    for data in existing_data:
        try:
            # Extract reasoning chain events
            reasoning_chain = data['reasoning_chain']
            if not reasoning_chain or not isinstance(reasoning_chain, list):
                continue
            
            # Generate a session ID for this historical data
            session_id = f"migrated_{data['block_id']}_{int(datetime.utcnow().timestamp())}"
            
            # Extract original query from events or properties
            original_query = "Historical query (migrated)"
            for event in reasoning_chain:
                if isinstance(event, dict) and 'metadata' in event:
                    if 'query' in event['metadata']:
                        original_query = event['metadata']['query']
                        break
            
            # Check if this data was already migrated
            existing = session.execute(text("""
                SELECT id FROM reasoning_chains 
                WHERE block_id = :block_id 
                AND original_query = :original_query
            """), {
                'block_id': data['block_id'],
                'original_query': original_query
            }).first()
            
            if existing:
                logger.info(f"Reasoning chain for block {data['block_id']} already migrated, skipping")
                continue
            
            # Insert migrated data
            session.execute(text("""
                INSERT INTO reasoning_chains (
                    id, workspace_id, page_id, block_id, user_id,
                    original_query, status, progress, events, chain_metadata,
                    created_at, updated_at, completed_at
                ) VALUES (
                    :id, :workspace_id, :page_id, :block_id, :user_id,
                    :original_query, :status, :progress, :events, :chain_metadata,
                    :created_at, :updated_at, :completed_at
                )
            """), {
                'id': session_id,
                'workspace_id': data['workspace_id'],
                'page_id': data['page_id'],
                'block_id': data['block_id'],
                'user_id': 'migrated_user',  # Default for historical data
                'original_query': original_query,
                'status': 'completed',  # Assume historical data is complete
                'progress': 1.0,
                'events': reasoning_chain,
                'chain_metadata': {
                    'migrated': True,
                    'migration_date': datetime.utcnow().isoformat(),
                    'source': 'block_properties'
                },
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow(),
                'completed_at': datetime.utcnow()
            })
            
            migrated_count += 1
            logger.info(f"Migrated reasoning chain for block {data['block_id']}")
            
        except Exception as e:
            logger.error(f"Error migrating data for block {data.get('block_id', 'unknown')}: {e}")
            continue
    
    return migrated_count

def run_migration():
    """Run the complete migration process"""
    logger.info("🚀 Starting Reasoning Chains Migration")
    logger.info("=" * 60)
    
    try:
        # Use the same database connection as the web application
        DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://notion_user:notion_password@localhost:5432/notion_clone")
        logger.info(f"Using database URL: {DATABASE_URL}")
        
        engine = create_engine(DATABASE_URL)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        
        logger.info(f"Connected to web application database")
        
        # Check if reasoning_chains table already exists
        if check_table_exists(engine, 'reasoning_chains'):
            logger.info("✅ reasoning_chains table already exists")
            
            # Check if we should migrate existing data
            with SessionLocal() as session:
                existing_count = session.execute(text("SELECT COUNT(*) FROM reasoning_chains")).scalar()
                logger.info(f"📊 Found {existing_count} existing reasoning chains in database")
                
                if existing_count == 0:
                    logger.info("🔄 No data in reasoning_chains table, checking for data to migrate...")
                    existing_data = get_existing_reasoning_data(session)
                    
                    if existing_data:
                        logger.info(f"📦 Found {len(existing_data)} blocks with reasoning chain data to migrate")
                        migrated_count = migrate_existing_data(session, existing_data)
                        session.commit()
                        logger.info(f"✅ Successfully migrated {migrated_count} reasoning chains")
                    else:
                        logger.info("📭 No existing reasoning chain data found to migrate")
                else:
                    logger.info("✅ reasoning_chains table already contains data, skipping migration")
        else:
            logger.info("🔨 Creating reasoning_chains table...")
            
            # Create the table
            ReasoningChainDB.__table__.create(engine)
            logger.info("✅ reasoning_chains table created successfully")
            
            # Migrate existing data
            with SessionLocal() as session:
                logger.info("🔄 Checking for existing reasoning chain data to migrate...")
                existing_data = get_existing_reasoning_data(session)
                
                if existing_data:
                    logger.info(f"📦 Found {len(existing_data)} blocks with reasoning chain data")
                    migrated_count = migrate_existing_data(session, existing_data)
                    session.commit()
                    logger.info(f"✅ Successfully migrated {migrated_count} reasoning chains")
                else:
                    logger.info("📭 No existing reasoning chain data found")
        
        # Verify the migration
        with SessionLocal() as session:
            total_chains = session.execute(text("SELECT COUNT(*) FROM reasoning_chains")).scalar()
            recent_chains = session.execute(text("""
                SELECT COUNT(*) FROM reasoning_chains 
                WHERE created_at > NOW() - INTERVAL '1 hour'
            """)).scalar()
            
            logger.info("=" * 60)
            logger.info("📊 MIGRATION SUMMARY")
            logger.info(f"   Total reasoning chains: {total_chains}")
            logger.info(f"   Recent chains (last hour): {recent_chains}")
            logger.info("=" * 60)
            logger.info("✅ Migration completed successfully!")
            logger.info("")
            logger.info("🎯 NEXT STEPS:")
            logger.info("   1. Restart the web server to pick up new storage endpoints")
            logger.info("   2. Restart the agent server to enable reasoning chain persistence")
            logger.info("   3. Test with a new query to verify reasoning chains are being saved")
            logger.info("")
            
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        logger.error("🔧 Troubleshooting:")
        logger.error("   1. Check database connection settings")
        logger.error("   2. Ensure database user has CREATE TABLE permissions")
        logger.error("   3. Verify PostgreSQL is running and accessible")
        raise

if __name__ == "__main__":
    run_migration() 
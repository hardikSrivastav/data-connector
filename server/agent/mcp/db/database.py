from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import logging
import os
import sys

# Handle imports both when run as a module and when imported directly
try:
    # Direct import when running as a module
    from agent.mcp.config import settings
except ImportError:
    # Relative import when imported from another module
    from ..config import settings

from .models import Base

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create database URL
DB_URL = f"postgresql://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"

# Create database engine
engine = create_engine(
    DB_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True  # Enables connection validation before usage
)

# Create database session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Initialize the database with tables"""
    try:
        # Import here to avoid circular imports
        from .models import Base
        
        # Create all tables if they don't exist
        Base.metadata.create_all(bind=engine)
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        raise


def get_db() -> Session:
    """Get a database session - to be used as a FastAPI dependency"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

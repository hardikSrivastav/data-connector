from sqlalchemy import create_engine, Column, String, DateTime, Text, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Session(Base):
    __tablename__ = "sessions"
    
    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, index=True)
    template_version = Column(String, nullable=False)
    template_hash = Column(String, nullable=False)
    status = Column(String, default="active")  # active, completed, failed
    session_metadata = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class EditHistory(Base):
    __tablename__ = "edit_history"
    
    id = Column(String, primary_key=True, index=True)
    session_id = Column(String, index=True)
    file_path = Column(String, nullable=False)
    placeholder = Column(String)
    old_value = Column(Text)
    new_value = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)

class TemplateVersion(Base):
    __tablename__ = "template_versions"
    
    version = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    hash = Column(String, nullable=False)
    schema = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)

def create_tables():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
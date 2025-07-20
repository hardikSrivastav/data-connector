from sqlalchemy import create_engine, Column, String, DateTime, Text, JSON, ForeignKey, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class DeploymentScenario(Base):
    __tablename__ = "deployment_scenarios"
    
    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    category = Column(String, nullable=False)  # basic, enterprise, development
    template_versions = Column(JSON, nullable=False)  # List of template versions
    dependencies = Column(JSON)  # Cross-file dependency rules
    variable_mappings = Column(JSON)  # Shared variables across templates
    created_at = Column(DateTime, default=datetime.utcnow)
    
class Session(Base):
    __tablename__ = "sessions"
    
    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, index=True)
    template_version = Column(String, nullable=False)  # Will store "scenario:ID" for scenarios
    template_hash = Column(String, nullable=False)     # Will store "scenario-hash" for scenarios
    status = Column(String, default="active")  # active, completed, failed
    session_metadata = Column(JSON)  # Will store scenario_id and other info for scenarios
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
class SessionTemplate(Base):
    __tablename__ = "session_templates"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, ForeignKey('sessions.id'), nullable=False)
    template_version = Column(String, nullable=False)
    template_hash = Column(String, nullable=False)
    status = Column(String, default="active")  # active, completed, failed
    variables = Column(JSON)  # Template-specific variables
    created_at = Column(DateTime, default=datetime.utcnow)

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
    category = Column(String)  # authentication, deployment, infrastructure, configuration
    format = Column(String)   # yaml, docker-compose, nginx, javascript, env
    created_at = Column(DateTime, default=datetime.utcnow)

def create_tables():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
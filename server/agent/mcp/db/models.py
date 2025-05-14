from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text, Table, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import datetime
import json

Base = declarative_base()


class User(Base):
    """User model for storing user information"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    name = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    
    # SSO information (optional)
    sso_provider = Column(String(50), nullable=True)
    sso_id = Column(String(255), nullable=True)
    
    # Flag for temporary users (used in session-based authentication)
    is_temporary = Column(Boolean, default=False)
    
    session_id = Column(String(64), nullable=True, unique=True)
    
    # Relationships
    workspaces = relationship("SlackWorkspace", secondary="user_workspaces", back_populates="users")


class SlackWorkspace(Base):
    """Slack workspace model"""
    __tablename__ = "slack_workspaces"
    
    id = Column(Integer, primary_key=True)
    team_id = Column(String(255), nullable=False, unique=True)
    team_name = Column(String(255), nullable=False)
    bot_user_id = Column(String(255), nullable=False)
    bot_token = Column(Text, nullable=False)  # Encrypted xoxb token
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    last_used = Column(DateTime, nullable=True)
    
    # User token for additional permissions
    user_token = Column(Text, nullable=True)  # Encrypted xoxp token
    user_token_scope = Column(Text, nullable=True)  # List of scopes granted to user token
    
    # For token rotation
    access_token_expires_at = Column(DateTime, nullable=True)
    refresh_token = Column(Text, nullable=True)
    
    # User token expiration (may be different than bot token)
    user_token_expires_at = Column(DateTime, nullable=True)
    user_refresh_token = Column(Text, nullable=True)
    
    # Relationships
    users = relationship("User", secondary="user_workspaces", back_populates="workspaces")
    indexing_status = relationship("SlackMessageIndex", uselist=False, back_populates="workspace")


class UserWorkspace(Base):
    """Association table for users and workspaces"""
    __tablename__ = "user_workspaces"
    
    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    workspace_id = Column(Integer, ForeignKey("slack_workspaces.id"), primary_key=True)
    added_at = Column(DateTime, default=datetime.datetime.utcnow)
    is_admin = Column(Boolean, default=False)
    
    # Store authorized scopes
    scopes = Column(Text, nullable=True)
    
    def get_scopes(self):
        """Get the list of authorized scopes"""
        if self.scopes:
            try:
                # Try to parse as JSON first
                return json.loads(self.scopes)
            except json.JSONDecodeError:
                # Fall back to comma-separated format
                return self.scopes.split(',')
        return []


class OAuthStateRecord(Base):
    """Database storage for OAuth state records"""
    __tablename__ = "oauth_states"
    
    id = Column(Integer, primary_key=True)
    state = Column(String(255), unique=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False)


class SessionRecord(Base):
    """Database storage for CLI sessions"""
    __tablename__ = "sessions"
    
    id = Column(Integer, primary_key=True)
    session_id = Column(String(255), unique=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    state = Column(String(255), nullable=True)  # Associated OAuth state
    completed = Column(Boolean, default=False)
    
    # JSON-serialized result data
    result_data = Column(Text, nullable=True)


# New models for Slack message indexing
class SlackMessageIndex(Base):
    __tablename__ = "slack_message_indexes"
    
    id = Column(Integer, primary_key=True)
    workspace_id = Column(Integer, ForeignKey("slack_workspaces.id"), unique=True)
    collection_name = Column(String(255), nullable=False)
    last_indexed_at = Column(DateTime, nullable=True)
    last_completed_at = Column(DateTime, nullable=True)
    is_indexing = Column(Boolean, default=False)
    total_messages = Column(Integer, default=0)
    indexed_messages = Column(Integer, default=0)
    oldest_message_ts = Column(String(255), nullable=True)
    newest_message_ts = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    # Index configuration
    history_days = Column(Integer, default=30)
    update_frequency_hours = Column(Integer, default=6)
    embedding_model = Column(String(255), default="all-MiniLM-L6-v2")
    
    # Relationship
    workspace = relationship("SlackWorkspace", back_populates="indexing_status")
    channels = relationship("IndexedChannel", back_populates="index")


class IndexedChannel(Base):
    __tablename__ = "indexed_channels"
    
    id = Column(Integer, primary_key=True)
    index_id = Column(Integer, ForeignKey("slack_message_indexes.id"))
    channel_id = Column(String(255), nullable=False)
    channel_name = Column(String(255), nullable=False)
    last_indexed_ts = Column(String(255), nullable=True)
    message_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    # Relationship
    index = relationship("SlackMessageIndex", back_populates="channels")
    
    class Meta:
        unique_together = (("index_id", "channel_id"),)

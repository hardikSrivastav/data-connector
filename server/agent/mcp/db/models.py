from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text, Table
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
    
    # Relationships
    workspaces = relationship("SlackWorkspace", secondary="user_workspaces", back_populates="users")


class SlackWorkspace(Base):
    """Slack workspace model"""
    __tablename__ = "slack_workspaces"
    
    id = Column(Integer, primary_key=True)
    team_id = Column(String(50), unique=True, nullable=False)
    team_name = Column(String(255), nullable=False)
    bot_user_id = Column(String(50), nullable=False)
    bot_token = Column(Text, nullable=False)  # Encrypted xoxb token
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    last_used = Column(DateTime, nullable=True)
    
    # For token rotation
    access_token_expires_at = Column(DateTime, nullable=True)
    refresh_token = Column(Text, nullable=True)
    
    # Relationships
    users = relationship("User", secondary="user_workspaces", back_populates="workspaces")


class UserWorkspace(Base):
    """Association table for users and workspaces"""
    __tablename__ = "user_workspaces"
    
    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    workspace_id = Column(Integer, ForeignKey("slack_workspaces.id"), primary_key=True)
    added_at = Column(DateTime, default=datetime.datetime.utcnow)
    is_admin = Column(Boolean, default=False)
    
    # Authorized scopes as JSON
    authorized_scopes = Column(Text, nullable=True)
    
    def get_scopes(self):
        """Get the list of authorized scopes"""
        if self.authorized_scopes:
            return json.loads(self.authorized_scopes)
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

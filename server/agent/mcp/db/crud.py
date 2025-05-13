from sqlalchemy.orm import Session
from sqlalchemy import update
from datetime import datetime, timedelta
import uuid
import json
import logging
from typing import List, Optional, Dict, Any

# Handle imports with fallbacks to accommodate both package and direct module execution
try:
    # Package-style import (when running as part of the agent package)
    from ..security import token_encryption, encrypt, decrypt
    from . import models
    from ..models.oauth import OAuthState
except (ImportError, ValueError):
    # Direct module import (when running the module directly)
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from agent.mcp.security import token_encryption, encrypt, decrypt
    from agent.mcp.db import models
    from agent.mcp.models.oauth import OAuthState

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# User operations
def get_user(db: Session, user_id: int) -> Optional[models.User]:
    """Get a user by ID"""
    return db.query(models.User).filter(models.User.id == user_id).first()


def get_user_by_email(db: Session, email: str) -> Optional[models.User]:
    """Get a user by email"""
    return db.query(models.User).filter(models.User.email == email).first()


def create_user(db: Session, email: str, name: Optional[str] = None) -> models.User:
    """Create a new user"""
    user = models.User(email=email, name=name)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_temporary_user(db: Session):
    """Create a temporary user for session-based OAuth flow"""
    # Generate a unique email for the temporary user
    temp_email = f"temp_{uuid.uuid4()}@example.com"
    
    # Create user with a prefix to identify temporary users
    user = models.User(
        email=temp_email,
        name="Temporary User",
        is_temporary=True,
        created_at=datetime.utcnow()
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info(f"Created temporary user with ID {user.id}")
    
    return user


# Workspace operations
def get_workspace(db: Session, workspace_id: int) -> Optional[models.SlackWorkspace]:
    """Get a workspace by ID"""
    return db.query(models.SlackWorkspace).filter(models.SlackWorkspace.id == workspace_id).first()


def get_workspace_by_team_id(db: Session, team_id: str) -> Optional[models.SlackWorkspace]:
    """Get a workspace by Slack team ID"""
    return db.query(models.SlackWorkspace).filter(models.SlackWorkspace.team_id == team_id).first()


def create_workspace(db: Session, workspace: models.SlackWorkspace) -> models.SlackWorkspace:
    """Create or update a workspace"""
    # Check if workspace already exists
    existing = get_workspace_by_team_id(db, workspace.team_id)
    if existing:
        # Update existing workspace
        existing.team_name = workspace.team_name
        existing.bot_user_id = workspace.bot_user_id
        # Encrypt bot token before storing
        existing.bot_token = token_encryption.encrypt_token(workspace.bot_token)
        
        # Update user token if provided
        if hasattr(workspace, 'user_token') and workspace.user_token:
            existing.user_token = token_encryption.encrypt_token(workspace.user_token)
            existing.user_token_scope = workspace.user_token_scope
        
        # Update refresh tokens if provided
        if hasattr(workspace, 'refresh_token') and workspace.refresh_token:
            existing.refresh_token = token_encryption.encrypt_token(workspace.refresh_token)
            existing.access_token_expires_at = workspace.access_token_expires_at
        
        existing.last_used = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        return existing
    
    # Create new workspace with encrypted tokens
    workspace.bot_token = token_encryption.encrypt_token(workspace.bot_token)
    
    # Encrypt user token if provided
    if hasattr(workspace, 'user_token') and workspace.user_token:
        workspace.user_token = token_encryption.encrypt_token(workspace.user_token)
    
    db.add(workspace)
    db.commit()
    db.refresh(workspace)
    return workspace


def get_user_workspaces(db: Session, user_id: int) -> List[models.SlackWorkspace]:
    """Get all workspaces for a user"""
    user = get_user(db, user_id)
    if not user:
        return []
    return user.workspaces


# User-Workspace operations
def get_user_workspace(db: Session, user_id: int, workspace_id: int) -> Optional[models.UserWorkspace]:
    """Get a user-workspace relationship"""
    return db.query(models.UserWorkspace).filter(
        models.UserWorkspace.user_id == user_id,
        models.UserWorkspace.workspace_id == workspace_id
    ).first()


def create_user_workspace(db: Session, user_id: int, workspace_id: int, scopes: List[str]) -> models.UserWorkspace:
    """Create a user-workspace relationship"""
    user_workspace = models.UserWorkspace(
        user_id=user_id,
        workspace_id=workspace_id,
        authorized_scopes=json.dumps(scopes)
    )
    db.add(user_workspace)
    db.commit()
    db.refresh(user_workspace)
    return user_workspace


# OAuth state operations
def create_oauth_state(db: Session, state_data: OAuthState) -> models.OAuthStateRecord:
    """Create an OAuth state record"""
    # Set expiry time if not provided
    if not state_data.expires_at:
        state_data.expires_at = datetime.utcnow() + timedelta(minutes=10)
    
    # Create record
    state_record = models.OAuthStateRecord(
        state=state_data.state,
        user_id=state_data.user_id,
        created_at=state_data.created_at,
        expires_at=state_data.expires_at,
    )
    db.add(state_record)
    db.commit()
    db.refresh(state_record)
    return state_record


def get_oauth_state(db: Session, state: str) -> Optional[models.OAuthStateRecord]:
    """Get an OAuth state record"""
    return db.query(models.OAuthStateRecord).filter(
        models.OAuthStateRecord.state == state,
        models.OAuthStateRecord.used == False,  # Only get unused states
        models.OAuthStateRecord.expires_at > datetime.utcnow()  # Only get non-expired states
    ).first()


def get_user_id_from_state(db: Session, state: str) -> Optional[int]:
    """Get the user ID associated with an OAuth state"""
    state_record = get_oauth_state(db, state)
    if not state_record:
        return None
    
    # Mark state as used
    state_record.used = True
    db.commit()
    
    return state_record.user_id


# Token operations
def get_workspace_token(db: Session, workspace_id: int) -> Optional[str]:
    """Get the decrypted bot token for a workspace"""
    workspace = get_workspace(db, workspace_id)
    if not workspace:
        return None
    
    try:
        # Decrypt bot token
        return decrypt(workspace.bot_token)
    except Exception as e:
        logger.error(f"Error decrypting bot token: {str(e)}")
        return None

def get_workspace_user_token(db: Session, workspace_id: int) -> Optional[str]:
    """Get the decrypted user token for a workspace if available"""
    workspace = get_workspace(db, workspace_id)
    if not workspace or not workspace.user_token:
        return None
    
    try:
        # Decrypt user token
        return decrypt(workspace.user_token)
    except Exception as e:
        logger.error(f"Error decrypting user token: {str(e)}")
        return None

def has_user_token(db: Session, workspace_id: int) -> bool:
    """Check if a workspace has a user token"""
    workspace = get_workspace(db, workspace_id)
    return workspace is not None and workspace.user_token is not None

def cleanup_temporary_users(db: Session, days: int = 1):
    """Clean up temporary users that are older than the specified number of days"""
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    # Find temporary users older than cutoff date
    temp_users = db.query(models.User).filter(
        models.User.is_temporary == True,
        models.User.created_at < cutoff_date
    ).all()
    
    # Log how many users will be deleted
    logger.info(f"Cleaning up {len(temp_users)} temporary users older than {days} days")
    
    # Delete the users
    for user in temp_users:
        db.delete(user)
    
    db.commit()
    return len(temp_users)

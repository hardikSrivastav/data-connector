from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import json
import logging
from typing import List, Optional, Dict, Any

from . import models
from ..security import token_encryption
from ..models.oauth import OAuthState

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
        # Encrypt token before storing
        existing.bot_token = token_encryption.encrypt_token(workspace.bot_token)
        existing.last_used = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        return existing
    
    # Create new workspace with encrypted token
    workspace.bot_token = token_encryption.encrypt_token(workspace.bot_token)
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
    """Get the decrypted token for a workspace"""
    workspace = get_workspace(db, workspace_id)
    if not workspace:
        return None
    
    try:
        # Decrypt token
        return token_encryption.decrypt_token(workspace.bot_token)
    except Exception as e:
        logger.error(f"Error decrypting token: {str(e)}")
        return None

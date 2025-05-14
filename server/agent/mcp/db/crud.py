from sqlalchemy.orm import Session
from sqlalchemy import update, func, desc, and_, or_
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


def get_user_by_session(db: Session, session_id: str) -> Optional[models.User]:
    """Get a user by session ID"""
    return db.query(models.User).filter(models.User.session_id == session_id).first()


def create_user(db: Session, email: str, name: Optional[str] = None, is_temporary: bool = False) -> models.User:
    """Create a new user"""
    user = models.User(email=email, name=name, is_temporary=is_temporary)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_user_session(db: Session, user_id: int, session_id: str) -> bool:
    """Update a user's session ID"""
    db.query(models.User).filter(models.User.id == user_id).update(
        {"session_id": session_id, "last_login": datetime.utcnow()}
    )
    db.commit()
    return True


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


def update_workspace_tokens(db: Session, workspace_id: int, user_token: str = None, 
                          user_refresh_token: str = None, 
                          expires_at: datetime = None,
                          scope: str = None) -> bool:
    """Update a workspace's user token information"""
    update_data = {"last_used": datetime.utcnow()}
    
    if user_token:
        update_data["user_token"] = token_encryption.encrypt_token(user_token)
    
    if user_refresh_token:
        update_data["user_refresh_token"] = token_encryption.encrypt_token(user_refresh_token)
    
    if expires_at:
        update_data["user_token_expires_at"] = expires_at
    
    if scope:
        update_data["user_token_scope"] = scope
    
    db.query(models.SlackWorkspace).filter(models.SlackWorkspace.id == workspace_id).update(update_data)
    db.commit()
    return True


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


def create_user_workspace(db: Session, user_id: int, workspace_id: int, scopes: List[str] = None, is_admin: bool = False) -> models.UserWorkspace:
    """Create a user-workspace relationship"""
    if scopes:
        scopes_json = json.dumps(scopes)
    else:
        scopes_json = None
        
    user_workspace = models.UserWorkspace(
        user_id=user_id,
        workspace_id=workspace_id,
        authorized_scopes=scopes_json,
        is_admin=is_admin
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
    """Get OAuth state by state value"""
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

# Message Indexing operations
def get_indexing_status(db: Session, workspace_id: int) -> Optional[models.SlackMessageIndex]:
    """Get indexing status for a workspace"""
    return db.query(models.SlackMessageIndex).filter(models.SlackMessageIndex.workspace_id == workspace_id).first()

def create_indexing_status(db: Session, workspace_id: int, collection_name: str,
                         history_days: int = 30, update_frequency_hours: int = 6) -> models.SlackMessageIndex:
    """Create indexing status for a workspace"""
    status = models.SlackMessageIndex(
        workspace_id=workspace_id,
        collection_name=collection_name,
        history_days=history_days,
        update_frequency_hours=update_frequency_hours
    )
    db.add(status)
    db.commit()
    db.refresh(status)
    return status

def update_indexing_status(db: Session, index_id: int, **kwargs) -> bool:
    """Update indexing status"""
    # Add updated_at time
    kwargs["updated_at"] = datetime.utcnow()
    
    db.query(models.SlackMessageIndex).filter(models.SlackMessageIndex.id == index_id).update(kwargs)
    db.commit()
    return True

def update_indexing_completed(db: Session, index_id: int, 
                            total_messages: int, indexed_messages: int,
                            oldest_ts: str = None, newest_ts: str = None) -> bool:
    """Update indexing status on completion"""
    now = datetime.utcnow()
    db.query(models.SlackMessageIndex).filter(models.SlackMessageIndex.id == index_id).update({
        "is_indexing": False,
        "last_completed_at": now,
        "last_indexed_at": now,
        "total_messages": total_messages,
        "indexed_messages": indexed_messages,
        "oldest_message_ts": oldest_ts,
        "newest_message_ts": newest_ts,
        "updated_at": now
    })
    db.commit()
    return True

def get_pending_indexing_workspaces(db: Session, max_results: int = 10) -> List[models.SlackMessageIndex]:
    """Get workspaces that need indexing"""
    now = datetime.utcnow()
    cutoff_time = now - timedelta(hours=1)
    
    return db.query(models.SlackMessageIndex).filter(
        # Not currently indexing or indexing for over an hour (stuck)
        or_(
            models.SlackMessageIndex.is_indexing == False,
            models.SlackMessageIndex.updated_at < cutoff_time
        ),
        # Either never indexed or last indexed more than update_frequency hours ago
        or_(
            models.SlackMessageIndex.last_indexed_at == None,
            and_(
                models.SlackMessageIndex.last_indexed_at < now - func.make_interval(0, 0, 0, 0, models.SlackMessageIndex.update_frequency_hours),
                # Don't retry too often on failures
                models.SlackMessageIndex.updated_at < now - timedelta(minutes=30)
            )
        )
    ).order_by(models.SlackMessageIndex.last_indexed_at.asc().nullsfirst()).limit(max_results).all()

# Channel Indexing operations
def get_indexed_channel(db: Session, index_id: int, channel_id: str) -> Optional[models.IndexedChannel]:
    """Get indexed channel info"""
    return db.query(models.IndexedChannel).filter(
        models.IndexedChannel.index_id == index_id,
        models.IndexedChannel.channel_id == channel_id
    ).first()

def get_indexed_channels(db: Session, index_id: int) -> List[models.IndexedChannel]:
    """Get all indexed channels for an index"""
    return db.query(models.IndexedChannel).filter(models.IndexedChannel.index_id == index_id).all()

def create_indexed_channel(db: Session, index_id: int, channel_id: str, 
                         channel_name: str) -> models.IndexedChannel:
    """Create or update indexed channel"""
    channel = get_indexed_channel(db, index_id, channel_id)
    if channel:
        channel.channel_name = channel_name
        channel.updated_at = datetime.utcnow()
    else:
        channel = models.IndexedChannel(
            index_id=index_id,
            channel_id=channel_id,
            channel_name=channel_name
        )
        db.add(channel)
    
    db.commit()
    db.refresh(channel)
    return channel

def update_indexed_channel(db: Session, index_id: int, channel_id: str, 
                         last_indexed_ts: str, message_count: int) -> bool:
    """Update indexed channel status"""
    db.query(models.IndexedChannel).filter(
        models.IndexedChannel.index_id == index_id,
        models.IndexedChannel.channel_id == channel_id
    ).update({
        "last_indexed_ts": last_indexed_ts,
        "message_count": message_count,
        "updated_at": datetime.utcnow()
    })
    db.commit()
    return True

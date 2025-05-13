from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
import secrets
import time
from typing import Optional, Dict
import json
import logging
from datetime import datetime, timedelta

# Handle imports with fallbacks to accommodate both package and direct module execution
try:
    # Package-style import (when running as part of the agent package)
    from ..db import crud, models
    from ..db.database import get_db
    from ..models.oauth import OAuthState, OAuthToken
    from ..security import create_jwt_token
    from ..config import settings
except (ImportError, ValueError):
    # Direct module import (when running the module directly)
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from agent.mcp.db import crud, models
    from agent.mcp.db.database import get_db
    from agent.mcp.models.oauth import OAuthState, OAuthToken
    from agent.mcp.security import create_jwt_token
    from agent.mcp.config import settings

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory session store (for demo purposes)
# In production, use Redis or database storage for sessions
active_sessions: Dict[str, Dict] = {}

def cleanup_expired_sessions():
    """Remove expired sessions from memory"""
    now = time.time()
    expired = [sid for sid, data in active_sessions.items() 
              if data.get("expires_at", 0) < now]
    
    for sid in expired:
        active_sessions.pop(sid, None)
    
    logger.info(f"Cleaned up {len(expired)} expired sessions")


@router.get("/slack/authorize")
async def slack_authorize(
    request: Request, 
    session: Optional[str] = None,
    user_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Start the OAuth flow by redirecting to Slack
    
    Support both session-based (new) and user_id-based (legacy) authentication
    """
    # Clean up expired sessions
    cleanup_expired_sessions()
    
    # Handle session-based flow (new)
    if session:
        logger.info(f"Using session-based authentication flow with session ID: {session}")
        
        # Create temporary user if session doesn't exist
        if session not in active_sessions:
            # Create a session with 30 min expiry
            active_sessions[session] = {
                "created_at": time.time(),
                "expires_at": time.time() + 1800,  # 30 minutes
                "state": None
            }
            logger.info(f"Created new session: {session}")
        
        # Create temporary user for the session
        temp_user = crud.create_temporary_user(db)
        temp_user_id = temp_user.id
        
        # Store the user_id in the session
        active_sessions[session]["user_id"] = temp_user_id
        logger.info(f"Associated session {session} with temporary user ID {temp_user_id}")
    
    # Handle legacy user_id-based flow
    elif user_id:
        logger.info(f"Using legacy user_id-based authentication flow with user ID: {user_id}")
        
        try:
            temp_user_id = int(user_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid user_id format")
        
        # Check if user exists
        user = crud.get_user(db, temp_user_id)
        if not user:
            # Create user if it doesn't exist (for legacy flow)
            user = crud.create_user(db, email=f"user_{temp_user_id}@example.com", name=f"User {temp_user_id}")
            temp_user_id = user.id
    else:
        # Neither session nor user_id provided
        raise HTTPException(status_code=400, detail="Either session or user_id parameter is required")
    
    # Generate state
    state = secrets.token_urlsafe(32)
    oauth_state = OAuthState(state=state, user_id=temp_user_id)
    crud.create_oauth_state(db, oauth_state)
    
    # Store state in session if using session-based flow
    if session:
        active_sessions[session]["state"] = state
    
    # Generate authorization URL with both user and bot scopes
    from slack_sdk.oauth import AuthorizeUrlGenerator
    
    # Combine both bot and user scopes
    user_scopes = settings.SLACK_USER_SCOPES
    
    authorize_url_generator = AuthorizeUrlGenerator(
        client_id=settings.SLACK_CLIENT_ID,
        scopes=settings.SLACK_BOT_SCOPES,
        user_scopes=user_scopes,  # Request user token scopes
        redirect_uri=f"{settings.API_BASE_URL}/api/auth/slack/callback"
    )
    
    url = authorize_url_generator.generate(state)
    logger.info(f"Redirecting to Slack authorization URL with user and bot scopes")
    return RedirectResponse(url)


@router.get("/slack/callback")
async def slack_callback(
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Handle the OAuth callback from Slack"""
    # Check for errors
    if error:
        logger.error(f"Slack OAuth error: {error}")
        return RedirectResponse(
            url=f"{settings.WEB_APP_URL}/slack/error?error={error}"
        )
    
    # Validate required parameters
    if not code or not state:
        logger.error("Missing code or state parameters")
        return RedirectResponse(
            url=f"{settings.WEB_APP_URL}/slack/error?error=missing_parameters"
        )
    
    # Get user_id from state
    user_id = crud.get_user_id_from_state(db, state)
    if not user_id:
        logger.error(f"Invalid or expired state: {state}")
        return RedirectResponse(
            url=f"{settings.WEB_APP_URL}/slack/error?error=invalid_state"
        )
    
    # Get user
    user = crud.get_user(db, user_id)
    if not user:
        logger.error(f"User not found: {user_id}")
        return RedirectResponse(
            url=f"{settings.WEB_APP_URL}/slack/error?error=user_not_found"
        )
    
    # Exchange code for token
    try:
        from slack_sdk.web import WebClient
        client = WebClient()
        response = client.oauth_v2_access(
            client_id=settings.SLACK_CLIENT_ID,
            client_secret=settings.SLACK_CLIENT_SECRET,
            code=code,
            redirect_uri=f"{settings.API_BASE_URL}/api/auth/slack/callback"
        )
        token_data = response.data
        logger.info(f"Successfully exchanged code for tokens")
    except Exception as e:
        logger.error(f"Error exchanging code: {str(e)}")
        return RedirectResponse(
            url=f"{settings.WEB_APP_URL}/slack/error?error=token_exchange_failed"
        )
    
    # Extract team info
    team_id = token_data["team"]["id"]
    team_name = token_data["team"]["name"]
    
    # Extract user token if available
    user_token = None
    user_token_scope = None
    if "authed_user" in token_data and "access_token" in token_data["authed_user"]:
        user_token = token_data["authed_user"]["access_token"]
        user_token_scope = token_data["authed_user"].get("scope", "")
        logger.info(f"Received user token with scopes: {user_token_scope}")
    
    # Create or update workspace
    workspace_data = {
        "team_id": team_id,
        "team_name": team_name,
        "bot_user_id": token_data["bot_user_id"],
        "bot_token": token_data["access_token"]
    }
    
    # Add user token data if available
    if user_token:
        workspace_data["user_token"] = user_token
        workspace_data["user_token_scope"] = user_token_scope
    
    workspace = models.SlackWorkspace(**workspace_data)
    workspace = crud.create_workspace(db, workspace)
    
    # Link user to workspace if not already linked
    user_workspace = crud.get_user_workspace(db, user_id, workspace.id)
    if not user_workspace:
        # Get both bot and user scopes
        bot_scopes = token_data.get("scope", "").split(",")
        user_scopes = user_token_scope.split(",") if user_token_scope else []
        all_scopes = list(set(bot_scopes + user_scopes))  # Combine and deduplicate
        
        crud.create_user_workspace(db, user_id, workspace.id, all_scopes)
    
    # Find the session associated with this state
    session_id = None
    for sid, session_data in active_sessions.items():
        if session_data.get("state") == state:
            session_id = sid
            # Update session with auth result
            active_sessions[sid]["auth_result"] = {
                "success": True,
                "user_id": user_id,
                "workspace_id": workspace.id,
                "team_id": team_id,
                "team_name": team_name
            }
            logger.info(f"Updated session {sid} with successful authentication result")
            break
    
    # Build success URL with appropriate parameters
    success_params = f"team={team_id}&workspace_id={workspace.id}"
    if user_token:
        success_params += "&user_token=true"  # Indicate that we have a user token
    
    # Add session_id if available - this allows the web app to display the session for CLI copy
    if session_id:
        success_params += f"&session_id={session_id}"
        
    return RedirectResponse(
        url=f"{settings.WEB_APP_URL}/slack/success?{success_params}"
    )


@router.get("/slack/workspaces/{user_id}")
async def get_user_workspaces(user_id: int, db: Session = Depends(get_db)):
    """Get all Slack workspaces for a user"""
    # Check if user exists
    user = crud.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get workspaces
    workspaces = crud.get_user_workspaces(db, user_id)
    
    # Get user-workspace associations to find admin status
    formatted_workspaces = []
    for ws in workspaces:
        # Get the association record
        user_workspace = db.query(models.UserWorkspace).filter(
            models.UserWorkspace.user_id == user_id,
            models.UserWorkspace.workspace_id == ws.id
        ).first()
        
        formatted_workspaces.append({
            "id": ws.id,
            "team_id": ws.team_id,
            "team_name": ws.team_name,
            "added_at": ws.created_at.isoformat(),
            "is_admin": user_workspace.is_admin if user_workspace else False
        })
    
    return formatted_workspaces


@router.get("/slack/check_session/{session_id}")
async def check_session(session_id: str):
    """
    Check if a session has completed authentication
    
    This endpoint is polled by the CLI tool to check if the user has completed 
    the browser-based OAuth flow.
    """
    # Clean up expired sessions
    cleanup_expired_sessions()
    
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found or expired")
    
    session_data = active_sessions[session_id]
    
    # Check if authentication is complete
    if "auth_result" in session_data:
        # Authentication is complete, return the result
        result = session_data["auth_result"]
        
        # If auth was successful, also return credentials the CLI needs
        if result.get("success", False):
            return {
                "status": "complete",
                "success": True,
                "user_id": result["user_id"],
                "workspace_id": result["workspace_id"],
                "team_name": result["team_name"]
            }
        else:
            return {
                "status": "complete",
                "success": False,
                "error": result.get("error", "Unknown error")
            }
    else:
        # Authentication is still pending
        return {
            "status": "pending",
            "expires_at": session_data["expires_at"]
        }

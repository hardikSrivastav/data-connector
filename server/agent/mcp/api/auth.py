from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
import secrets
from typing import Optional
import json
import logging

from ..db import crud, models
from ..db.database import get_db
from ..models.oauth import OAuthState, OAuthToken
from ..security import create_jwt_token
from ..config import settings

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/slack/authorize")
async def slack_authorize(request: Request, db: Session = Depends(get_db)):
    """Start the OAuth flow by redirecting to Slack"""
    # Get user from session or query parameter
    # In a real implementation, you'd get this from an authenticated session
    user_id = request.query_params.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized - user_id required")
    
    try:
        user_id = int(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user_id format")
    
    # Check if user exists
    user = crud.get_user(db, user_id)
    if not user:
        # Create user if it doesn't exist (for demo purposes)
        # In a real implementation, you'd expect the user to already exist
        user = crud.create_user(db, email=f"user_{user_id}@example.com", name=f"User {user_id}")
    
    # Generate state
    state = secrets.token_urlsafe(32)
    oauth_state = OAuthState(state=state, user_id=user.id)
    crud.create_oauth_state(db, oauth_state)
    
    # Generate authorization URL
    from slack_sdk.oauth import AuthorizeUrlGenerator
    
    authorize_url_generator = AuthorizeUrlGenerator(
        client_id=settings.SLACK_CLIENT_ID,
        scopes=settings.SLACK_SCOPES,
        #redirect_uri=f"{settings.API_BASE_URL}/api/auth/slack/callback"
        redirect_uri=f"https://6aec-2405-201-4011-b202-3089-406f-2549-df4f.ngrok-free.app/api/auth/slack/callback"
    )
    
    url = authorize_url_generator.generate(state)
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
            #redirect_uri=f"{settings.API_BASE_URL}/api/auth/slack/callback"
            redirect_uri=f"https://6aec-2405-201-4011-b202-3089-406f-2549-df4f.ngrok-free.app/api/auth/slack/callback"
        )
        token_data = response.data
    except Exception as e:
        logger.error(f"Error exchanging code: {str(e)}")
        return RedirectResponse(
            url=f"{settings.WEB_APP_URL}/slack/error?error=token_exchange_failed"
        )
    
    # Extract team info
    team_id = token_data["team"]["id"]
    team_name = token_data["team"]["name"]
    
    # Create or update workspace
    workspace = models.SlackWorkspace(
        team_id=team_id,
        team_name=team_name,
        bot_user_id=token_data["bot_user_id"],
        bot_token=token_data["access_token"]
    )
    workspace = crud.create_workspace(db, workspace)
    
    # Link user to workspace if not already linked
    user_workspace = crud.get_user_workspace(db, user_id, workspace.id)
    if not user_workspace:
        scopes = token_data.get("scope", "").split(",")
        crud.create_user_workspace(db, user_id, workspace.id, scopes)
    
    # Redirect to success page
    return RedirectResponse(
        url=f"{settings.WEB_APP_URL}/slack/success?team={team_id}&workspace_id={workspace.id}"
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
    
    # Format response
    return [
        {
            "id": ws.id,
            "team_id": ws.team_id,
            "team_name": ws.team_name,
            "added_at": ws.created_at.isoformat(),
            "is_admin": next(
                (uw.is_admin for uw in user.workspaces if uw.id == ws.id),
                False
            )
        }
        for ws in workspaces
    ]

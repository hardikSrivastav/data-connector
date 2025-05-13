from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any, Optional
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from pydantic import BaseModel
from sqlalchemy.orm import Session
import logging

from ..db.database import get_db
from ..db import crud
from ..security import verify_jwt_token, JWTData, create_jwt_token
from ..models.oauth import TokenRequest, TokenResponse
from ..models.workspace import SlackToolRequest, SlackToolResponse
from ..config import settings

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/invoke", response_model=SlackToolResponse)
async def invoke(
    request: SlackToolRequest,
    token_data: JWTData = Depends(verify_jwt_token),
    db: Session = Depends(get_db)
):
    """MCP invoke endpoint for Slack tools"""
    # Get workspace token from database
    workspace_token = crud.get_workspace_token(db, token_data.workspace_id)
    if not workspace_token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found or token is invalid"
        )
    
    # Create Slack client with the token
    slack = WebClient(token=workspace_token)
    
    try:
        if request.tool == "slack_list_channels":
            # List all channels in the workspace
            res = slack.conversations_list(limit=1000)
            channels = [{"id": c["id"], "name": c["name"]} for c in res["channels"]]
            logger.info(f"Retrieved {len(channels)} channels")
            return SlackToolResponse(result={"channels": channels})

        elif request.tool == "slack_get_channel_history":
            # Get message history from a channel
            channel_id = request.parameters.get("channel_id")
            if not channel_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Missing channel_id parameter"
                )
                
            limit = request.parameters.get("limit", 50)
            res = slack.conversations_history(channel=channel_id, limit=limit)
            logger.info(f"Retrieved {len(res['messages'])} messages from channel {channel_id}")
            return SlackToolResponse(result={"messages": res["messages"]})

        elif request.tool == "slack_get_thread_replies":
            # Get all replies in a thread
            channel_id = request.parameters.get("channel_id")
            thread_ts = request.parameters.get("thread_ts")
            
            if not channel_id or not thread_ts:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Missing required parameters: channel_id and thread_ts"
                )
                
            res = slack.conversations_replies(channel=channel_id, ts=thread_ts)
            logger.info(f"Retrieved {len(res['messages'])} replies in thread {thread_ts}")
            return SlackToolResponse(result={"replies": res["messages"]})
            
        elif request.tool == "slack_post_message":
            # Post a message to a channel
            channel_id = request.parameters.get("channel_id")
            text = request.parameters.get("text")
            
            if not channel_id or not text:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Missing required parameters: channel_id and text"
                )
            
            # Optional parameters
            message_params = {
                "channel": channel_id,
                "text": text
            }
            
            # Optional thread parameter
            thread_ts = request.parameters.get("thread_ts")
            if thread_ts:
                message_params["thread_ts"] = thread_ts
                
            res = slack.chat_postMessage(**message_params)
            logger.info(f"Posted message to channel {channel_id}")
            return SlackToolResponse(result={"message": res["message"]})

        elif request.tool == "slack_user_info":
            # Get user information
            user_id = request.parameters.get("user_id")
            if not user_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Missing user_id parameter"
                )
                
            res = slack.users_info(user=user_id)
            return SlackToolResponse(result={"user": res["user"]})

        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown tool: {request.tool}"
            )

    except SlackApiError as e:
        logger.error(f"Slack API error: {e.response['error']}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Slack API error: {e.response['error']}"
        )
    except Exception as e:
        logger.error(f"Error invoking Slack tool: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/token", response_model=TokenResponse)
async def generate_token(
    request: TokenRequest,
    db: Session = Depends(get_db)
):
    """Generate a JWT token for client use"""
    # Verify user has access to this workspace
    user_workspace = crud.get_user_workspace(db, request.user_id, request.workspace_id)
    if not user_workspace:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User does not have access to this workspace"
        )
    
    # Generate token
    from datetime import datetime, timedelta
    
    # Get token expiry time
    expiry = datetime.utcnow() + timedelta(hours=settings.TOKEN_EXPIRY_HOURS)
    
    # Create token
    token, expires_at = create_jwt_token(
        user_id=request.user_id,
        workspace_id=request.workspace_id,
        expiry=expiry
    )
    
    return TokenResponse(token=token, expires_at=expires_at)

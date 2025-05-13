from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any, Optional
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from pydantic import BaseModel
from sqlalchemy.orm import Session
import logging

# Handle imports with fallbacks to accommodate both package and direct module execution
try:
    # Package-style import (when running as part of the agent package)
    from ..db.database import get_db
    from ..db import crud
    from ..security import verify_jwt_token, JWTData, create_jwt_token
    from ..models.oauth import TokenRequest, TokenResponse
    from ..models.workspace import SlackToolRequest, SlackToolResponse
    from ..config import settings
except (ImportError, ValueError):
    # Direct module import (when running the module directly)
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from agent.mcp.db.database import get_db
    from agent.mcp.db import crud
    from agent.mcp.security import verify_jwt_token, JWTData, create_jwt_token
    from agent.mcp.models.oauth import TokenRequest, TokenResponse
    from agent.mcp.models.workspace import SlackToolRequest, SlackToolResponse
    from agent.mcp.config import settings

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
    
    # Check if user token is available - use it for read operations when possible
    user_token = None
    has_user_token = crud.has_user_token(db, token_data.workspace_id)
    if has_user_token:
        user_token = crud.get_workspace_user_token(db, token_data.workspace_id)
        logger.info("User token available for workspace - will use for read operations")
    
    # Determine which tools require read access to content (where user token helps)
    read_content_tools = [
        "slack_get_channel_history", 
        "slack_get_thread_replies"
    ]
    
    # Use user token for read operations if available, otherwise use bot token
    if user_token and request.tool in read_content_tools:
        logger.info(f"Using user token for {request.tool}")
        slack = WebClient(token=user_token)
    else:
        logger.info(f"Using bot token for {request.tool}")
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
            try:
                res = slack.conversations_history(channel=channel_id, limit=limit)
                logger.info(f"Retrieved {len(res['messages'])} messages from channel {channel_id}")
                return SlackToolResponse(result={"messages": res["messages"]})
            except SlackApiError as e:
                if e.response["error"] == "not_in_channel" and user_token:
                    # If bot isn't in channel but we have user token, we can still try to use it
                    logger.warning(f"Bot not in channel {channel_id}, falling back to user token")
                    user_slack = WebClient(token=user_token)
                    res = user_slack.conversations_history(channel=channel_id, limit=limit)
                    logger.info(f"Retrieved {len(res['messages'])} messages using user token")
                    return SlackToolResponse(result={"messages": res["messages"]})
                else:
                    # Re-raise the error if we can't handle it
                    raise

        elif request.tool == "slack_get_thread_replies":
            # Get all replies in a thread
            channel_id = request.parameters.get("channel_id")
            thread_ts = request.parameters.get("thread_ts")
            
            if not channel_id or not thread_ts:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Missing required parameters: channel_id and thread_ts"
                )
                
            try:
                res = slack.conversations_replies(channel=channel_id, ts=thread_ts)
                logger.info(f"Retrieved {len(res['messages'])} replies in thread {thread_ts}")
                return SlackToolResponse(result={"replies": res["messages"]})
            except SlackApiError as e:
                if e.response["error"] == "not_in_channel" and user_token:
                    # If bot isn't in channel but we have user token, we can still try to use it
                    logger.warning(f"Bot not in channel {channel_id}, falling back to user token")
                    user_slack = WebClient(token=user_token)
                    res = user_slack.conversations_replies(channel=channel_id, ts=thread_ts)
                    logger.info(f"Retrieved {len(res['messages'])} replies using user token")
                    return SlackToolResponse(result={"replies": res["messages"]})
                else:
                    # Re-raise the error if we can't handle it
                    raise
            
        elif request.tool == "slack_post_message":
            # Post a message to a channel - always use bot token
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

        elif request.tool == "slack_bot_info":
            # Get information about the bot/app without using auth_test or team_info
            # Just return basic info we can get from the token and available methods
            try:
                # Try to get bot's user ID from auth.test if available
                # This might fail if we don't have the right scope
                auth_info = {"bot_user_id": None, "bot_name": "Bot"}
                try:
                    auth_test_result = slack.auth_test()
                    auth_info = {
                        "bot_user_id": auth_test_result.get("user_id"),
                        "bot_name": auth_test_result.get("user")
                    }
                except SlackApiError:
                    # If auth.test fails, we'll just use placeholder values
                    logger.warning("Could not get bot info via auth.test - missing scope")
                
                # Return available info
                return SlackToolResponse(result={
                    "bot_info": {
                        "bot_user_id": auth_info["bot_user_id"],
                        "bot_name": auth_info["bot_name"],
                        # Skip team info since we don't have the scope
                        "note": "Limited information available due to scope restrictions"
                    }
                })
            except Exception as e:
                logger.error(f"Error getting bot info: {str(e)}")
                # Return minimal info
                return SlackToolResponse(result={
                    "bot_info": {
                        "note": "Could not retrieve bot info - please check scopes",
                        "error": str(e)
                    }
                })

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


@router.get("/channels/help_invite", response_model=Dict[str, Any])
async def help_invite_to_channels(
    workspace_id: int,
    db: Session = Depends(get_db)
):
    """Get a list of channels and invite commands to help users add the bot to their channels"""
    # Get the workspace
    workspace = crud.get_workspace(db, workspace_id)
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found"
        )
    
    # Get user token if available
    user_token = None
    if workspace.user_token:
        user_token = crud.get_workspace_user_token(db, workspace_id)
    
    # If no user token, we can't list all channels
    if not user_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User token not available - can't list all channels"
        )
    
    # Use user token to list all channels
    slack = WebClient(token=user_token)
    
    try:
        res = slack.conversations_list(limit=1000)
        channels = res["channels"]
        
        # Get bot info to show proper name in invite command
        bot_info = {"name": "your_bot"}
        try:
            bot_token = crud.get_workspace_token(db, workspace_id)
            bot_client = WebClient(token=bot_token)
            auth_test = bot_client.auth_test()
            bot_info["name"] = auth_test.get("user", "your_bot")
        except Exception as e:
            logger.warning(f"Could not get bot name: {str(e)}")
        
        # Format response with invite commands
        result = {
            "channels": [
                {
                    "id": channel["id"],
                    "name": channel["name"],
                    "invite_command": f"/invite @{bot_info['name']}"
                }
                for channel in channels
            ],
            "bot_name": bot_info["name"],
            "bulk_invite_instructions": "To invite the bot to a channel, use the /invite command in each channel.",
            "easy_setup": f"Just run /invite @{bot_info['name']} in the channels you want to analyze."
        }
        
        return result
        
    except SlackApiError as e:
        logger.error(f"Slack API error: {e.response['error']}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Slack API error: {e.response['error']}"
        )
    except Exception as e:
        logger.error(f"Error listing channels: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

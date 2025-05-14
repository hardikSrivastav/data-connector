from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict, Any, Optional, List
import logging
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError as SlackAPIError
from datetime import datetime, timedelta

from ..db import crud, models
from ..db.database import get_db
from ..models.workspace import SlackToolRequest, SlackToolResponse
from ..models.oauth import TokenRequest, TokenResponse
from ..security import verify_jwt_token, JWTData, decode_jwt_token, get_token, create_jwt_token, decrypt
from sqlalchemy.orm import Session

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

# Define API dependencies
security = HTTPBearer(auto_error=False)

def get_db_session() -> Session:
    """Get a database session"""
    return next(get_db())

def get_optional_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[JWTData]:
    """
    Get the JWT token data if available, but don't require it
    This allows endpoints to accept either token or direct credentials
    """
    if not credentials:
        return None
        
    try:
        token = credentials.credentials
        return decode_jwt_token(token)
    except Exception as e:
        logger.warning(f"Invalid token: {str(e)}")
        return None
        
def get_slack_client(workspace: models.SlackWorkspace) -> WebClient:
    """
    Get a Slack client for the workspace
    """
    if not workspace.bot_token:
        raise ValueError("Workspace has no bot token")
    
    # Decrypt token and create client
    try:
        token = decrypt(workspace.bot_token)
        
        # Debug log token (mask most of it)
        if token:
            masked_token = token[:10] + "..." + token[-5:] if len(token) > 15 else "***"
            logger.info(f"Using bot token: {masked_token}")
        else:
            logger.error("Decrypted token is None or empty")
            
        return WebClient(token=token)
    except Exception as e:
        logger.error(f"Error creating Slack client: {str(e)}")
        raise ValueError(f"Could not initialize Slack client: {str(e)}")
    
# Simple tool registry
class SlackToolRegistry:
    """Registry of Slack tools"""
    
    async def execute_tool(self, client: WebClient, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool with the given parameters"""
        tools = {
            "slack_list_channels": self._list_channels,
            "slack_get_channel_history": self._get_channel_history,
            "slack_get_thread_replies": self._get_thread_replies,
            "slack_post_message": self._post_message,
            "slack_user_info": self._get_user_info,
            "slack_bot_info": self._get_bot_info
        }
        
        if tool_name not in tools:
            raise ValueError(f"Unknown tool: {tool_name}")
            
        return await tools[tool_name](client, parameters)
    
    async def _list_channels(self, client: WebClient, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """List all channels in the workspace"""
        res = client.conversations_list(limit=1000)
        channels = [{"id": c["id"], "name": c["name"]} for c in res["channels"]]
        logger.info(f"Retrieved {len(channels)} channels")
        return {"channels": channels}
    
    async def _get_channel_history(self, client: WebClient, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Get message history from a channel"""
        channel_id = parameters.get("channel_id")
        if not channel_id:
            raise ValueError("Missing channel_id parameter")
            
        limit = parameters.get("limit", 50)
        res = client.conversations_history(channel=channel_id, limit=limit)
        logger.info(f"Retrieved {len(res['messages'])} messages from channel {channel_id}")
        return {"messages": res["messages"]}
    
    async def _get_thread_replies(self, client: WebClient, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Get all replies in a thread"""
        channel_id = parameters.get("channel_id")
        thread_ts = parameters.get("thread_ts")
        
        if not channel_id or not thread_ts:
            raise ValueError("Missing required parameters: channel_id and thread_ts")
            
        res = client.conversations_replies(channel=channel_id, ts=thread_ts)
        logger.info(f"Retrieved {len(res['messages'])} replies in thread {thread_ts}")
        return {"replies": res["messages"]}
    
    async def _post_message(self, client: WebClient, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Post a message to a channel"""
        channel_id = parameters.get("channel_id")
        text = parameters.get("text")
        
        if not channel_id or not text:
            raise ValueError("Missing required parameters: channel_id and text")
        
        # Optional parameters
        message_params = {
            "channel": channel_id,
            "text": text
        }
        
        # Optional thread parameter
        thread_ts = parameters.get("thread_ts")
        if thread_ts:
            message_params["thread_ts"] = thread_ts
            
        res = client.chat_postMessage(**message_params)
        logger.info(f"Posted message to channel {channel_id}")
        return {"message": res["message"]}

    async def _get_user_info(self, client: WebClient, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Get user information"""
        user_id = parameters.get("user_id")
        if not user_id:
            raise ValueError("Missing user_id parameter")
            
        res = client.users_info(user=user_id)
        return {"user": res["user"]}

    async def _get_bot_info(self, client: WebClient, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Get information about the bot/app"""
        try:
            # Try to get bot's user ID from auth.test
            auth_test_result = client.auth_test()
            return {
                "bot_info": {
                    "bot_user_id": auth_test_result.get("user_id"),
                    "bot_name": auth_test_result.get("user"),
                    "team_id": auth_test_result.get("team_id"),
                    "team_name": auth_test_result.get("team"),
                    "team_domain": auth_test_result.get("team_domain")
                }
            }
        except Exception as e:
            logger.error(f"Error getting bot info: {str(e)}")
            return {
                "bot_info": {
                    "note": "Could not retrieve bot info",
                    "error": str(e)
                }
            }

# Create a global instance
slack_tool_registry = SlackToolRegistry()

@router.post("/token")
async def get_api_token(
    request: TokenRequest,
    db: Session = Depends(get_db)
):
    """Get an API token"""
    try:
        # Get user and workspace
        user = crud.get_user(db, request.user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
            
        workspace = crud.get_workspace(db, request.workspace_id)
        if not workspace:
            raise HTTPException(status_code=404, detail="Workspace not found")
            
        # Check if user has access to workspace
        user_workspace = crud.get_user_workspace(db, request.user_id, request.workspace_id)
        if not user_workspace:
            raise HTTPException(status_code=403, detail="User does not have access to workspace")
            
        # Generate token
        expiry = datetime.utcnow() + timedelta(hours=24)  # Use settings if available
        token, expires_at = create_jwt_token(user.id, workspace.id, expiry)
        
        return TokenResponse(
            token=token,
            expires_at=expires_at
        )
    except Exception as e:
        logger.error(f"Error generating token: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/invoke")
async def invoke_tool(
    request: SlackToolRequest,
    token_data: Optional[JWTData] = Depends(get_optional_token)
):
    """
    Invoke a Slack tool
    
    This endpoint accepts either:
    1. JWT token in Authorization header (preferred)
    2. Direct credentials (user_id, workspace_id) in the request body
    """
    # Handle authentication
    user_id = None
    workspace_id = None
    
    # If we have token data, use it
    if token_data:
        user_id = token_data.user_id
        workspace_id = token_data.workspace_id
    # Otherwise check for direct credentials in the request
    elif hasattr(request, 'user_id') and hasattr(request, 'workspace_id'):
        user_id = request.user_id
        workspace_id = request.workspace_id
        
    # Ensure we have authentication
    if not user_id or not workspace_id:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Provide token or credentials."
        )
    
    try:
        # Check if workspace exists and has valid tokens
        workspace = crud.get_workspace(get_db_session(), workspace_id)
        if not workspace:
            raise HTTPException(status_code=404, detail="Workspace not found")
        
        # Check if user has access to workspace
        user_workspace = crud.get_user_workspace(get_db_session(), user_id, workspace_id)
        if not user_workspace:
            raise HTTPException(
                status_code=403, 
                detail="User does not have access to this workspace"
            )
        
        # Get client
        client = get_slack_client(workspace)
        
        # Execute the tool
        result = await slack_tool_registry.execute_tool(
            client=client,
            tool_name=request.tool,
            parameters=request.parameters
        )
        
        return SlackToolResponse(result=result)
        
    except SlackAPIError as e:
        logger.error(f"Slack API error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        logger.error(f"Value error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Error invoking tool: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


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
        
    except SlackAPIError as e:
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

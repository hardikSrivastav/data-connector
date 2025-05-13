import requests
import logging
from typing import Dict, List, Any, Optional
import json
from datetime import datetime, timedelta
from pydantic import BaseModel

from .models.workspace import SlackToolRequest, SlackToolResponse
from .models.oauth import TokenRequest, TokenResponse

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MCPClient:
    """Client for interacting with the Slack MCP Server"""
    
    def __init__(self, server_url: str):
        """Initialize the MCP client
        
        Args:
            server_url: URL of the MCP server (e.g., http://localhost:8000)
        """
        self.server_url = server_url.rstrip("/")
        self.token: Optional[str] = None
        self.token_expires_at: Optional[datetime] = None
        self.user_id: Optional[str] = None
        self.workspace_id: Optional[str] = None
        
    def _is_token_valid(self) -> bool:
        """Check if the current token is valid and not expired"""
        if not self.token or not self.token_expires_at:
            return False
        
        # Add a buffer time to avoid edge cases
        buffer_minutes = 5
        return datetime.utcnow() + timedelta(minutes=buffer_minutes) < self.token_expires_at
    
    def authenticate(self, user_id: str, workspace_id: str) -> bool:
        """Authenticate with the MCP server and get a token
        
        Args:
            user_id: User ID to authenticate with
            workspace_id: Workspace ID to authenticate for
            
        Returns:
            True if authentication was successful, False otherwise
        """
        self.user_id = user_id
        self.workspace_id = workspace_id
        
        if self._is_token_valid():
            logger.info("Using existing valid token")
            return True
        
        try:
            # Request a new token
            response = requests.post(
                f"{self.server_url}/api/tools/token",
                json={"user_id": user_id, "workspace_id": workspace_id}
            )
            
            if response.status_code == 200:
                token_data = response.json()
                self.token = token_data["token"]
                # Parse the expiry date
                if "expires_at" in token_data:
                    self.token_expires_at = datetime.fromisoformat(token_data["expires_at"].replace("Z", "+00:00"))
                logger.info(f"Successfully authenticated for user {user_id} and workspace {workspace_id}")
                return True
            else:
                logger.error(f"Authentication failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            return False
    
    def invoke_tool(self, tool: str, parameters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Invoke a Slack tool through the MCP server
        
        Args:
            tool: Name of the tool to invoke (e.g., slack_list_channels)
            parameters: Parameters for the tool
            
        Returns:
            The tool response data
            
        Raises:
            Exception: If authentication fails or tool invocation fails
        """
        if not self._is_token_valid():
            if not self.user_id or not self.workspace_id:
                raise Exception("Not authenticated. Call authenticate() first.")
            
            if not self.authenticate(self.user_id, self.workspace_id):
                raise Exception("Authentication failed")
        
        # Create the tool request
        request_data = SlackToolRequest(
            tool=tool,
            parameters=parameters or {}
        ).dict()
        
        # Make the request
        try:
            response = requests.post(
                f"{self.server_url}/api/tools/invoke",
                json=request_data,
                headers={"Authorization": f"Bearer {self.token}"}
            )
            
            if response.status_code == 200:
                return response.json()["result"]
            else:
                error_msg = f"Tool invocation failed: {response.status_code} - {response.text}"
                logger.error(error_msg)
                raise Exception(error_msg)
                
        except Exception as e:
            logger.error(f"Tool invocation error: {str(e)}")
            raise
    
    def list_channels(self) -> List[Dict[str, str]]:
        """List all channels in the Slack workspace
        
        Returns:
            List of channels with their ID and name
        """
        result = self.invoke_tool("slack_list_channels")
        return result.get("channels", [])
    
    def get_channel_history(self, channel_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get message history from a channel
        
        Args:
            channel_id: Channel ID to get history from
            limit: Maximum number of messages to retrieve
            
        Returns:
            List of messages in the channel
        """
        result = self.invoke_tool(
            "slack_get_channel_history", 
            {"channel_id": channel_id, "limit": limit}
        )
        return result.get("messages", [])
    
    def get_thread_replies(self, channel_id: str, thread_ts: str) -> List[Dict[str, Any]]:
        """Get all replies in a thread
        
        Args:
            channel_id: Channel ID containing the thread
            thread_ts: Thread timestamp identifier
            
        Returns:
            List of messages in the thread
        """
        result = self.invoke_tool(
            "slack_get_thread_replies", 
            {"channel_id": channel_id, "thread_ts": thread_ts}
        )
        return result.get("replies", [])
    
    def post_message(self, channel_id: str, text: str, thread_ts: str = None) -> Dict[str, Any]:
        """Post a message to a channel
        
        Args:
            channel_id: Channel ID to post to
            text: Message text
            thread_ts: Optional thread timestamp to reply to
            
        Returns:
            Information about the posted message
        """
        params = {"channel_id": channel_id, "text": text}
        if thread_ts:
            params["thread_ts"] = thread_ts
            
        result = self.invoke_tool("slack_post_message", params)
        return result.get("message", {})
    
    def get_user_info(self, user_id: str) -> Dict[str, Any]:
        """Get information about a Slack user
        
        Args:
            user_id: Slack user ID
            
        Returns:
            User information
        """
        result = self.invoke_tool("slack_user_info", {"user_id": user_id})
        return result.get("user", {})

import requests
import logging
from typing import Dict, List, Any, Optional
import json
from datetime import datetime, timedelta
from pydantic import BaseModel
import time

from .models.workspace import SlackToolRequest, SlackToolResponse
from .models.oauth import TokenRequest, TokenResponse

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MCPClient:
    """
    Client for the MCP API
    
    This client provides functionality to authenticate and invoke Slack tools
    through the MCP API.
    """
    
    def __init__(self, base_url: str):
        """
        Initialize the client
        
        Args:
            base_url: Base URL of the MCP API
        """
        self.base_url = base_url.rstrip("/")
        
        # Validate the URL format
        if not self.base_url.startswith(("http://", "https://")):
            logger.warning(f"Base URL '{self.base_url}' doesn't have http:// or https:// prefix")
            # Try to add https by default
            self.base_url = f"https://{self.base_url}"
            logger.info(f"Using modified base URL: {self.base_url}")
            
        logger.info(f"Initialized MCP client with base URL: {self.base_url}")
        
        self.token = None
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
        """
        Authenticate with the MCP API
        
        Args:
            user_id: User ID
            workspace_id: Workspace ID
            
        Returns:
            True if authentication was successful, False otherwise
        """
        try:
            logger.info(f"Authenticating with user_id={user_id}, workspace_id={workspace_id}")
            url = f"{self.base_url}/api/tools/token"
            
            data = {
                "user_id": int(user_id),
                "workspace_id": int(workspace_id)
            }
            
            # Add retry logic with increased timeout
            max_retries = 3
            timeout_seconds = 30  # Increase timeout from 10 to 30 seconds
            
            for attempt in range(max_retries):
                try:
                    logger.info(f"Authentication attempt {attempt+1}/{max_retries} to {url}")
                    response = requests.post(url, json=data, timeout=timeout_seconds)
                    
                    if response.status_code == 200:
                        result = response.json()
                        self.token = result.get("token")
                        # Parse the expiry date
                        if "expires_at" in result:
                            self.token_expires_at = datetime.fromisoformat(result["expires_at"].replace("Z", "+00:00"))
                        logger.info("Authentication successful")
                        self.user_id = user_id
                        self.workspace_id = workspace_id
                        return True
                    else:
                        logger.error(f"Authentication failed: {response.status_code} - {response.text}")
                        # If got a response but failed, no need to retry
                        return False
                except requests.Timeout:
                    logger.warning(f"Authentication timeout on attempt {attempt+1}/{max_retries}")
                    if attempt == max_retries - 1:
                        logger.error(f"Authentication timed out after {max_retries} attempts")
                        return False
                except requests.ConnectionError as ce:
                    logger.warning(f"Connection error on attempt {attempt+1}/{max_retries}: {str(ce)}")
                    if attempt == max_retries - 1:
                        logger.error(f"Failed to connect after {max_retries} attempts")
                        return False
                
                # Wait before retrying (exponential backoff)
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # 1, 2, 4 seconds
                    logger.info(f"Waiting {wait_time} seconds before retry")
                    time.sleep(wait_time)
                
        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            return False
    
    def invoke_tool(self, tool: str, parameters: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Invoke a tool through the MCP API
        
        Args:
            tool: Name of the tool to invoke
            parameters: Parameters for the tool
            
        Returns:
            Response from the tool
            
        Raises:
            ValueError: If not authenticated or tool invocation fails
        """
        # Allow credential-based auth without token
        if not self.token and not (self.user_id and self.workspace_id):
            raise ValueError("Not authenticated. Call authenticate() first or set user_id and workspace_id directly")
            
        try:
            url = f"{self.base_url}/api/tools/invoke"
            
            data = {
                "tool": tool,
                "parameters": parameters or {}
            }
            
            headers = {}
            
            # If we have a token, use it
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"
            # Otherwise use direct credential auth
            elif self.user_id and self.workspace_id:
                # Add credentials directly to the request
                data["user_id"] = int(self.user_id)
                data["workspace_id"] = int(self.workspace_id)
                logger.info(f"Using direct credential auth with user_id={self.user_id}, workspace_id={self.workspace_id}")
            
            logger.info(f"Invoking tool {tool}")
            response = requests.post(url, json=data, headers=headers, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                return result.get("result", {})
            else:
                error_msg = f"Tool invocation failed: {response.status_code} - {response.text}"
                logger.error(error_msg)
                raise ValueError(error_msg)
                
        except requests.RequestException as e:
            error_msg = f"Request error: {str(e)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        except Exception as e:
            error_msg = f"Tool invocation error: {str(e)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
    
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

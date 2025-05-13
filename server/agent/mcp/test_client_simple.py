#!/usr/bin/env python3
"""
Simple test client for the MCP server.
This version avoids complex import dependencies.
"""

import requests
import logging
import time
from datetime import datetime, timedelta

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SimpleClient:
    """Simplified client for the MCP server"""
    
    def __init__(self, server_url: str):
        """Initialize the MCP client"""
        self.server_url = server_url.rstrip("/")
        self.token = None
        self.token_expires_at = None
        self.user_id = None
        self.workspace_id = None
    
    def authenticate(self, user_id: str, workspace_id: str) -> bool:
        """Authenticate with the MCP server and get a token"""
        self.user_id = user_id
        self.workspace_id = workspace_id
        
        try:
            # Request a new token
            response = requests.post(
                f"{self.server_url}/api/tools/token",
                json={"user_id": int(user_id), "workspace_id": int(workspace_id)}
            )
            
            if response.status_code == 200:
                token_data = response.json()
                self.token = token_data["token"]
                # Parse the expiry date if available
                if "expires_at" in token_data:
                    self.token_expires_at = datetime.fromtimestamp(token_data["expires_at"])
                return True
            else:
                logger.error(f"Authentication failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            return False
    
    def invoke_tool(self, tool: str, parameters: dict = None) -> dict:
        """Invoke a Slack tool through the MCP server"""
        if not self.token:
            raise Exception("Not authenticated. Call authenticate() first.")
        
        # Create the tool request
        request_data = {
            "tool": tool,
            "parameters": parameters or {}
        }
        
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
    
    def list_channels(self) -> list:
        """List all channels in the Slack workspace"""
        result = self.invoke_tool("slack_list_channels")
        return result.get("channels", [])
    
    def get_channel_history(self, channel_id: str, limit: int = 50) -> list:
        """Get message history from a channel"""
        result = self.invoke_tool(
            "slack_get_channel_history", 
            {"channel_id": channel_id, "limit": limit}
        )
        return result.get("messages", [])
    
    def post_message(self, channel_id: str, text: str, thread_ts: str = None) -> dict:
        """Post a message to a channel"""
        params = {"channel_id": channel_id, "text": text}
        if thread_ts:
            params["thread_ts"] = thread_ts
            
        result = self.invoke_tool("slack_post_message", params)
        return result.get("message", {})
    
    def get_user_info(self, user_id: str) -> dict:
        """Get information about a Slack user"""
        result = self.invoke_tool("slack_user_info", {"user_id": user_id})
        return result.get("user", {})


def main():
    """Main test function"""
    import sys
    
    # Get command line arguments
    user_id = "1"
    workspace_id = "1"
    
    if len(sys.argv) > 1:
        user_id = sys.argv[1]
    if len(sys.argv) > 2:
        workspace_id = sys.argv[2]
    
    print(f"Testing with user_id={user_id} and workspace_id={workspace_id}")
    
    # Initialize client
    client = SimpleClient("http://localhost:8500")
    print("MCP Client initialized")

    # Authenticate
    try:
        print("Authenticating...")
        success = client.authenticate(user_id, workspace_id)
        print(f"Authentication successful: {success}")
        
        if not success:
            print("Authentication failed, exiting.")
            return
    except Exception as e:
        print(f"Error during authentication: {e}")
        return

    # Test listing channels
    try:
        print("\nFetching channels...")
        channels = client.list_channels()
        print(f"Found {len(channels)} channels")
        for channel in channels[:3]:  # Print first 3 channels
            print(f" - {channel['name']} ({channel['id']})")
    except Exception as e:
        print(f"Error listing channels: {e}")
        channels = []  # Set empty channels to avoid error in next step

    # Test posting a message if we have channels
    if channels:
        try:
            channel_id = channels[0]['id']  # Use first channel
            message = "Test message from MCP client"
            print(f"\nPosting message to channel {channel_id}: '{message}'")
            result = client.post_message(channel_id, message)
            print(f"Message posted: {result.get('ts')}")
        except Exception as e:
            print(f"Error posting message: {e}")
    else:
        print("\nNo channels available to post messages")

    print("\nTest completed")


if __name__ == "__main__":
    main() 
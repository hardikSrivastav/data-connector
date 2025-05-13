#!/usr/bin/env python3
"""
Simple test client for the MCP server.
This version avoids complex import dependencies.
"""

import requests
import logging
import time
import secrets
import webbrowser
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

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
        self.credentials_file = os.path.join(str(Path.home()), ".data-connector", "slack_credentials.json")
    
    def authenticate(self, user_id: str = None, workspace_id: str = None) -> bool:
        """
        Authenticate with the MCP server and get a token
        
        Args:
            user_id: Optional user ID (if not provided, use stored credentials or session auth)
            workspace_id: Optional workspace ID
            
        Returns:
            True if authentication successful
        """
        # If explicit IDs are provided, use them
        if user_id and workspace_id:
            self.user_id = user_id
            self.workspace_id = workspace_id
            logger.info(f"Using provided user_id={user_id} and workspace_id={workspace_id}")
            return self._request_token()
            
        # Try to load from stored credentials
        if self._load_credentials():
            logger.info(f"Using stored credentials for user_id={self.user_id}")
            return self._request_token()
            
        # No stored credentials, initiate session-based auth
        logger.info("No credentials found. Starting session-based authentication...")
        return self._session_based_auth()
    
    def _request_token(self) -> bool:
        """Request a token using user_id and workspace_id"""
        try:
            # Request a new token
            response = requests.post(
                f"{self.server_url}/api/tools/token",
                json={"user_id": int(self.user_id), "workspace_id": int(self.workspace_id)}
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
    
    def _load_credentials(self) -> bool:
        """Load stored credentials if available"""
        try:
            if not os.path.exists(self.credentials_file):
                return False
                
            with open(self.credentials_file, 'r') as f:
                credentials = json.load(f)
                
            # Check if credentials contain required fields
            if 'user_id' not in credentials or not credentials.get('workspaces'):
                logger.warning("Incomplete credentials file")
                return False
                
            self.user_id = credentials['user_id']
            
            # Find default workspace or use the first one
            default_workspace = None
            for ws in credentials.get('workspaces', []):
                if ws.get('is_default'):
                    default_workspace = ws
                    break
            
            # If no default, use the first one
            if not default_workspace and credentials.get('workspaces'):
                default_workspace = credentials['workspaces'][0]
                
            if not default_workspace:
                logger.warning("No workspaces found in credentials")
                return False
                
            self.workspace_id = default_workspace['id']
            logger.info(f"Loaded credentials for user_id={self.user_id}, workspace={default_workspace.get('name', 'Unknown')}")
            return True
                
        except Exception as e:
            logger.error(f"Error loading credentials: {str(e)}")
            return False
    
    def _save_credentials(self) -> bool:
        """Save credentials to file"""
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(self.credentials_file), exist_ok=True)
            
            # Get workspace name from server if available
            workspace_name = "Unknown Workspace"
            try:
                workspaces = self.get_user_workspaces()
                for ws in workspaces:
                    if str(ws.get('id')) == str(self.workspace_id):
                        workspace_name = ws.get('team_name', workspace_name)
                        break
            except Exception:
                pass
            
            # Create credentials object
            credentials = {
                'user_id': self.user_id,
                'workspaces': [
                    {
                        'id': self.workspace_id,
                        'name': workspace_name,
                        'is_default': True
                    }
                ]
            }
            
            # Write to file
            with open(self.credentials_file, 'w') as f:
                json.dump(credentials, f, indent=2)
                
            logger.info(f"Saved credentials to {self.credentials_file}")
            return True
                
        except Exception as e:
            logger.error(f"Error saving credentials: {str(e)}")
            return False
    
    def _session_based_auth(self) -> bool:
        """
        Perform session-based authentication
        
        This flow:
        1. Generates a session ID
        2. Opens browser to authorization URL
        3. Polls server until authentication completes
        4. Saves credentials
        
        Returns:
            True if authentication successful
        """
        # Generate a session ID
        session_id = secrets.token_urlsafe(16)
        logger.info(f"Generated session ID: {session_id}")
        
        # Create authorization URL
        auth_url = f"{self.server_url}/api/auth/slack/authorize?session={session_id}"
        
        # Open browser
        print("\n" + "="*60)
        print(f"Opening browser for Slack authentication...")
        print(f"If your browser doesn't open automatically, please visit:")
        print(f"\n{auth_url}\n")
        print("="*60 + "\n")
        
        try:
            webbrowser.open(auth_url)
        except Exception as e:
            logger.error(f"Failed to open browser: {str(e)}")
            print(f"Please manually visit the URL above to complete authentication")
        
        # Poll for completion
        print("Waiting for authentication to complete in browser...")
        
        max_attempts = 60  # 5 minutes
        for attempt in range(max_attempts):
            time.sleep(5)  # Poll every 5 seconds
            
            try:
                response = requests.get(f"{self.server_url}/api/auth/slack/check_session/{session_id}")
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Check if auth is complete
                    if data.get('status') == 'complete':
                        if data.get('success'):
                            print("\nAuthentication successful!")
                            
                            # Save credentials
                            self.user_id = data.get('user_id')
                            self.workspace_id = data.get('workspace_id')
                            
                            logger.info(f"Authenticated as user_id={self.user_id}, workspace_id={self.workspace_id}")
                            
                            # Request token
                            if self._request_token():
                                # Save credentials for future use
                                self._save_credentials()
                                return True
                        else:
                            print(f"\nAuthentication failed: {data.get('error', 'Unknown error')}")
                            return False
                else:
                    # Only show error after a few attempts
                    if attempt > 5:
                        print(f"Polling error ({response.status_code}), still waiting...")
            
            except Exception as e:
                if attempt > 5:
                    print(f"Error polling for auth completion: {str(e)}")
        
        print("\nAuthentication timed out after 5 minutes")
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
    
    def get_bot_info(self) -> dict:
        """Get information about the bot/app"""
        result = self.invoke_tool("slack_bot_info", {})
        return result.get("bot_info", {})
    
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
    
    def get_user_workspaces(self) -> list:
        """Get all workspaces for the current user"""
        if not self.user_id:
            raise Exception("Not authenticated. Call authenticate() first.")
            
        try:
            response = requests.get(
                f"{self.server_url}/api/auth/slack/workspaces/{self.user_id}"
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get workspaces: {response.status_code} - {response.text}")
                return []
        except Exception as e:
            logger.error(f"Error getting workspaces: {str(e)}")
            return []


def main():
    """Main test function"""
    import sys
    
    # Get command line arguments
    user_id = None
    workspace_id = None
    server_url = "http://localhost:8500"
    
    # Parse arguments
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--user" and i+1 < len(args):
            user_id = args[i+1]
            i += 2
        elif args[i] == "--workspace" and i+1 < len(args):
            workspace_id = args[i+1]
            i += 2
        elif args[i] == "--server" and i+1 < len(args):
            server_url = args[i+1]
            i += 2
        else:
            i += 1
    
    # Initialize client
    client = SimpleClient(server_url)
    print(f"MCP Client initialized with server URL: {server_url}")

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

    # Get bot information
    try:
        print("\nGetting bot information...")
        bot_info = client.get_bot_info()
        print(f"Bot Name: {bot_info.get('bot_name', 'Unknown')}")
        print(f"Bot User ID: {bot_info.get('bot_user_id', 'Unknown')}")
        print(f"Team Name: {bot_info.get('team_name', 'Unknown')}")
        print(f"Team Domain: {bot_info.get('team_domain', 'Unknown')}")
        print(f"\nTo invite the bot to a channel, use: /invite @{bot_info.get('bot_name', 'YourBotName')}")
    except Exception as e:
        print(f"Error getting bot info: {e}")

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
    
    # Specifically test a channel where the bot is not a member (new-channel)
    new_channel_id = None
    for channel in channels:
        if channel['name'] == 'new-channel':
            new_channel_id = channel['id']
            break
    
    if new_channel_id:
        print(f"\n=== TESTING NON-MEMBER CHANNEL ACCESS ===")
        print(f"Testing access to 'new-channel' ({new_channel_id}) where bot is not a member")
        try:
            messages = client.get_channel_history(new_channel_id, limit=5)
            print(f"SUCCESS! Retrieved {len(messages)} messages from non-member channel")
            
            # Display messages to confirm we got real data
            for msg in messages:
                user_id = msg.get('user', 'UNKNOWN')
                text = msg.get('text', 'NO TEXT')
                ts = msg.get('ts', 'NO TIMESTAMP')
                print(f" - User {user_id}: {text} (at {ts})")
                
            print("This demonstrates our user token implementation is working correctly!")
            print("We can access channels without inviting the bot to each one.")
        except Exception as e:
            print(f"FAILED: Cannot access non-member channel: {e}")
            if "not_in_channel" in str(e):
                print("The user token fallback did not work. Check if user token is correctly stored and used.")
            else:
                print(f"Unexpected error: {e}")
    else:
        print("\nCould not find 'new-channel' to test non-member access")
    
    # Test getting channel history for any channel
    if channels:
        for channel in channels[:2]:  # Try first two channels
            channel_id = channel['id']
            channel_name = channel['name']
            try:
                print(f"\nGetting history for channel {channel_name} ({channel_id})...")
                messages = client.get_channel_history(channel_id, limit=5)
                print(f"Retrieved {len(messages)} messages")
                
                # Store unique user IDs for later lookup
                user_ids = set()
                
                for msg in messages:
                    # Print message info
                    user_id = msg.get('user', 'UNKNOWN')
                    user_ids.add(user_id)
                    text = msg.get('text', 'NO TEXT')
                    ts = msg.get('ts', 'NO TIMESTAMP')
                    print(f" - User {user_id}: {text} (at {ts})")
                
                # Print full details of the first message to check structure
                if messages:
                    print("\nFull structure of first message:")
                    print(json.dumps(messages[0], indent=2))
                    
                # Try to lookup user info
                print("\nLooking up user info:")
                for uid in user_ids:
                    if uid != 'UNKNOWN':
                        try:
                            user_info = client.get_user_info(uid)
                            real_name = user_info.get('real_name', 'Unknown')
                            display_name = user_info.get('profile', {}).get('display_name', 'No display name')
                            print(f" - User ID: {uid}, Real name: {real_name}, Display name: {display_name}")
                        except Exception as e:
                            print(f" - Error getting info for user {uid}: {e}")
                
                # Successfully got messages from this channel, no need to try others
                break
                            
            except Exception as e:
                if "not_in_channel" in str(e):
                    print(f"ERROR: Bot is not a member of channel '{channel_name}'")
                    print("To fix this, invite the bot to the channel using: /invite @YourBotName")
                    print("Trying next channel...")
                else:
                    print(f"Error getting channel history: {e}")

    print("\nTest completed")


if __name__ == "__main__":
    main() 
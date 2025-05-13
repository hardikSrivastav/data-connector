#!/usr/bin/env python3

import sys
import os
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    # Make sure current directory is in path
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir not in sys.path:
        sys.path.append(current_dir)
        print(f"Added {current_dir} to Python path")
    
    # Import the client directly
    from client import MCPClient
    
    # Get command line arguments
    user_id = "1"
    workspace_id = "1"
    
    if len(sys.argv) > 1:
        user_id = sys.argv[1]
    if len(sys.argv) > 2:
        workspace_id = sys.argv[2]
    
    print(f"Testing with user_id={user_id} and workspace_id={workspace_id}")
    
    # Initialize client
    client = MCPClient("http://localhost:8500")
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

    # Test getting user info
    try:
        print("\nFetching user info...")
        # Try to get a user ID from a channel message if available
        user_to_fetch = None
        if channels and len(channels) > 0:
            try:
                # Get history of first channel
                channel_id = channels[0]['id']
                messages = client.get_channel_history(channel_id, limit=10)
                for msg in messages:
                    if msg.get('user'):
                        user_to_fetch = msg['user']
                        break
            except Exception:
                pass
        
        if user_to_fetch:
            user_info = client.get_user_info(user_to_fetch)
            print(f"User info: {user_info.get('name')} ({user_info.get('id')})")
        else:
            print("No user ID found to fetch user info")
    except Exception as e:
        print(f"Error getting user info: {e}")

    print("\nTest completed")

if __name__ == "__main__":
    main() 
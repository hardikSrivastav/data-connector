#!/usr/bin/env python3

import os
import sys
from typing import Dict, List, Any
import json
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# Add the parent directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.mcp.db.database import SessionLocal
from agent.mcp.db import crud, models
from agent.mcp.security import token_encryption


def get_user_slack_data(user_id: int = 1) -> Dict[str, Any]:
    """
    Retrieve Slack data for a specific user and prepare it as context
    for a model.
    """
    # Create DB session
    db = SessionLocal()
    try:
        # Get user data
        user = crud.get_user(db, user_id)
        if not user:
            print(f"User with ID {user_id} not found")
            return {}
        
        print(f"Found user: {user.name} ({user.email})")
        
        # Get user's workspaces
        workspaces = crud.get_user_workspaces(db, user_id)
        if not workspaces:
            print(f"No workspaces found for user {user_id}")
            return {}
        
        context_data = {}
        
        for workspace in workspaces:
            print(f"Processing workspace: {workspace.team_name} ({workspace.team_id})")
            
            # Get decrypted token
            bot_token = crud.get_workspace_token(db, workspace.id)
            if not bot_token:
                print(f"Could not retrieve token for workspace {workspace.team_name}")
                continue
            
            # Initialize Slack client
            slack_client = WebClient(token=bot_token)
            
            try:
                # Get workspace info
                workspace_info = slack_client.team_info()
                print(f"Connected to Slack workspace: {workspace_info['team']['name']}")
                
                # Get channels
                channels_response = slack_client.conversations_list(types="public_channel")
                channels = channels_response.get("channels", [])
                print(f"Found {len(channels)} public channels")
                
                # Get some recent messages from a channel (first channel found)
                channel_context = []
                if channels:
                    first_channel = channels[0]
                    channel_id = first_channel["id"]
                    channel_name = first_channel["name"]
                    
                    print(f"Fetching messages from channel #{channel_name}")
                    
                    messages_response = slack_client.conversations_history(
                        channel=channel_id,
                        limit=10
                    )
                    messages = messages_response.get("messages", [])
                    
                    # Get user info for message authors
                    user_cache = {}
                    for msg in messages:
                        if msg.get("user") and msg.get("user") not in user_cache:
                            try:
                                user_info = slack_client.users_info(user=msg["user"])
                                user_cache[msg["user"]] = user_info["user"]["real_name"]
                            except SlackApiError:
                                user_cache[msg["user"]] = "Unknown User"
                    
                    # Format messages with user names
                    for msg in messages:
                        user_id = msg.get("user", "UNKNOWN")
                        user_name = user_cache.get(user_id, "Unknown User")
                        text = msg.get("text", "")
                        
                        channel_context.append({
                            "user": user_name,
                            "text": text,
                            "timestamp": msg.get("ts")
                        })
                
                # Build context data
                context_data[workspace.team_id] = {
                    "workspace_name": workspace.team_name,
                    "channels": [{"id": c["id"], "name": c["name"]} for c in channels],
                    "sample_channel": {
                        "name": channel_name if channels else "",
                        "messages": channel_context
                    }
                }
                
            except SlackApiError as e:
                print(f"Slack API error: {e}")
                continue
        
        return context_data
            
    finally:
        db.close()


def main():
    """Main function to run the test"""
    # Get slack data for default user (ID 1)
    slack_data = get_user_slack_data()
    
    if not slack_data:
        print("Could not retrieve any Slack data")
        return
    
    # Print the formatted context data that could be passed to a model
    print("\n--- Slack Context Data (Sample) ---\n")
    formatted_data = json.dumps(slack_data, indent=2)
    print(formatted_data)
    
    print("\nThis data can be passed as context to your model")


if __name__ == "__main__":
    main() 
"""
Slack Adapter for querying Slack data through MCP server
"""
import json
import logging
import os
import requests
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Union

from .base import DBAdapter

# Configure logging
logger = logging.getLogger(__name__)

class SlackAdapter(DBAdapter):
    """
    Adapter for querying Slack data via the MCP server
    
    This adapter uses a separate microservice (MCP server) to handle
    Slack API access and authentication.
    """
    
    def __init__(self, connection_uri: str, **kwargs):
        """
        Initialize Slack adapter with MCP server URL
        
        Args:
            connection_uri: URL of the MCP server
            **kwargs: Additional arguments
                cache_dir: Optional directory to cache schema data
        """
        # Use a default value if connection_uri is empty
        if not connection_uri:
            connection_uri = "http://localhost:8500"
            
        self.mcp_url = connection_uri.rstrip("/")
        self.credentials_file = os.path.join(str(Path.home()), 
                                          ".data-connector", 
                                          "slack_credentials.json")
        self.history_days = kwargs.get("history_days", 30)  # Default to 30 days
        self.user_id = None
        self.workspace_id = None
        self.token = None
        self.token_expires_at = None
        self.cache_dir = kwargs.get("cache_dir")
        
        # Load credentials if available
        self._load_credentials()
        
    def _load_credentials(self) -> bool:
        """Load stored credentials if available"""
        try:
            if not os.path.exists(self.credentials_file):
                logger.warning(f"Credentials file not found: {self.credentials_file}")
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
    
    async def _ensure_token(self) -> bool:
        """Ensure we have a valid token for API access"""
        # Check if token exists and is still valid
        if self.token and self.token_expires_at:
            expiry = datetime.fromtimestamp(self.token_expires_at)
            if expiry > datetime.now() + timedelta(minutes=5):
                return True
                
        # Request a new token
        if not self.user_id or not self.workspace_id:
            logger.error("Cannot request token: missing user_id or workspace_id")
            return False
            
        try:
            response = requests.post(
                f"{self.mcp_url}/api/tools/token",
                json={"user_id": int(self.user_id), "workspace_id": int(self.workspace_id)}
            )
            
            if response.status_code == 200:
                token_data = response.json()
                self.token = token_data["token"]
                self.token_expires_at = token_data.get("expires_at")
                logger.info("Successfully obtained new token")
                return True
            else:
                logger.error(f"Failed to get token: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error getting token: {str(e)}")
            return False

    async def _invoke_tool(self, tool: str, parameters: dict = None) -> dict:
        """
        Invoke a Slack tool through the MCP server
        
        Args:
            tool: Name of the tool to invoke
            parameters: Parameters for the tool
            
        Returns:
            Response data from the tool
        """
        if not await self._ensure_token():
            raise Exception("Authentication failed. Please run 'data-connector slack auth'")
        
        # Create the tool request
        request_data = {
            "tool": tool,
            "parameters": parameters or {}
        }
        
        # Make the request
        try:
            response = requests.post(
                f"{self.mcp_url}/api/tools/invoke",
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
    
    async def is_connected(self) -> bool:
        """
        Check if the connection to Slack is working
        
        Returns:
            True if connection is successful, False otherwise
        """
        try:
            # Try to get bot info as a simple connection test
            await self._invoke_tool("slack_bot_info")
            return True
        except Exception as e:
            logger.error(f"Connection test failed: {str(e)}")
            return False

    async def test_connection(self) -> bool:
        """
        Test the database connection.
        
        Returns:
            True if connection successful, False otherwise
        """
        return await self.is_connected()
            
    async def execute(self, query: Any) -> List[Dict]:
        """
        Execute the database query and return results.
        
        Args:
            query: Slack query specification (as returned by llm_to_query)
            
        Returns:
            List of dictionaries representing the query results
        """
        return await self.execute_query(query)
    
    async def llm_to_query(self, nl_prompt: str, **kwargs) -> Any:
        """
        Convert natural language prompt into a Slack query format.
        
        Args:
            nl_prompt: Natural language question or instruction
            **kwargs: Additional parameters (schema_chunks, etc.)
            
        Returns:
            A Slack query specification (JSON object)
        """
        from agent.llm.client import get_llm_client
        
        # Get LLM client
        llm = get_llm_client()
        
        # Get schema chunks if provided
        schema_chunks = kwargs.get("schema_chunks", [])
        
        # Create context from schema chunks
        schema_context = "\n\n".join([chunk.get("content", "") for chunk in schema_chunks])
        
        # Render prompt template for Slack
        prompt = llm.render_template("slack_query.tpl", 
                                 schema_context=schema_context, 
                                 query=nl_prompt)
        
        # Generate query
        response = await llm.generate_text(prompt)
        
        # Parse response as JSON
        try:
            # Try to extract JSON if embedded in markdown
            if "```json" in response:
                json_text = response.split("```json")[1].split("```")[0].strip()
                query_spec = json.loads(json_text)
            else:
                # Otherwise try to parse the whole response
                query_spec = json.loads(response)
                
            return query_spec
        except Exception as e:
            logger.error(f"Error parsing LLM response as JSON: {str(e)}")
            # Fallback to simple channel listing if parsing fails
            return {"type": "channels"}
    
    async def execute_query(self, query: str, params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Execute a query against Slack data
        
        Args:
            query: The query specification as JSON string
            params: Additional parameters for the query
            
        Returns:
            List of resulting records
        """
        try:
            # Parse the query
            if isinstance(query, str):
                query_spec = json.loads(query)
            else:
                query_spec = query
                
            query_type = query_spec.get("type", "channels")
            
            if query_type == "channels":
                # List channels
                result = await self._invoke_tool("slack_list_channels")
                return result.get("channels", [])
                
            elif query_type == "messages":
                # Get channel messages
                channel_id = query_spec.get("channel_id")
                limit = query_spec.get("limit", 50)
                
                if not channel_id:
                    raise ValueError("Missing channel_id in query")
                    
                result = await self._invoke_tool(
                    "slack_get_channel_history", 
                    {"channel_id": channel_id, "limit": limit}
                )
                return result.get("messages", [])
                
            elif query_type == "thread":
                # Get thread replies
                channel_id = query_spec.get("channel_id")
                thread_ts = query_spec.get("thread_ts")
                
                if not channel_id or not thread_ts:
                    raise ValueError("Missing channel_id or thread_ts in query")
                    
                result = await self._invoke_tool(
                    "slack_get_thread_replies", 
                    {"channel_id": channel_id, "thread_ts": thread_ts}
                )
                return result.get("replies", [])
                
            elif query_type == "user":
                # Get user info
                user_id = query_spec.get("user_id")
                
                if not user_id:
                    raise ValueError("Missing user_id in query")
                    
                result = await self._invoke_tool(
                    "slack_user_info", 
                    {"user_id": user_id}
                )
                return [result.get("user", {})]
                
            elif query_type == "bot":
                # Get bot info
                result = await self._invoke_tool("slack_bot_info")
                return [result.get("bot_info", {})]
                
            else:
                raise ValueError(f"Unknown query type: {query_type}")
                
        except Exception as e:
            logger.error(f"Error executing Slack query: {str(e)}")
            raise
    
    async def introspect_schema(self) -> List[Dict[str, str]]:
        """
        Introspect the Slack workspace to generate schema metadata
        
        Returns:
            List of schema metadata documents ready for embedding
        """
        try:
            if not await self._ensure_token():
                raise Exception("Authentication failed")
                
            documents = []
            
            # 1. Get team/workspace info
            bot_info = await self._invoke_tool("slack_bot_info")
            team_info = bot_info.get("bot_info", {})
            
            team_doc = {
                "id": "slack:workspace",
                "content": f"""
                WORKSPACE: {team_info.get('team_name', 'Unknown')}
                DOMAIN: {team_info.get('team_domain', 'unknown')}
                BOT: {team_info.get('bot_name', 'Unknown')}
                
                This is a Slack workspace containing channels, users, and messages.
                You can query message history, thread replies, and user information.
                """
            }
            documents.append(team_doc)
            
            # 2. Get channels
            channels_result = await self._invoke_tool("slack_list_channels")
            channels = channels_result.get("channels", [])
            
            channels_doc = {
                "id": "slack:channels",
                "content": f"""
                CHANNELS LIST:
                The workspace contains {len(channels)} channels.
                
                Available channels:
                {', '.join([f"#{c['name']} ({c['id']})" for c in channels[:20]])}
                {'...' if len(channels) > 20 else ''}
                
                You can query messages in these channels using the channel ID.
                """
            }
            documents.append(channels_doc)
            
            # 3. Add metadata for each channel
            for idx, channel in enumerate(channels[:10]):  # Limit to 10 channels to avoid overloading
                try:
                    # Get channel history to understand activity
                    messages = await self._invoke_tool(
                        "slack_get_channel_history", 
                        {"channel_id": channel["id"], "limit": 10}
                    )
                    
                    # Extract user IDs from messages to understand participation
                    user_ids = set()
                    for msg in messages.get("messages", []):
                        if "user" in msg:
                            user_ids.add(msg["user"])
                    
                    channel_doc = {
                        "id": f"slack:channel:{channel['id']}",
                        "content": f"""
                        CHANNEL: #{channel['name']} ({channel['id']})
                        PARTICIPANTS: {len(user_ids)} unique users recently active
                        RECENT MESSAGES: {len(messages.get('messages', []))} in the last few days
                        
                        This is a Slack channel where users exchange messages.
                        You can query message history for this channel using its ID: {channel['id']}
                        """
                    }
                    documents.append(channel_doc)
                except Exception as e:
                    logger.warning(f"Could not get details for channel {channel['name']}: {e}")
            
            # 4. Add a document about querying capabilities
            query_doc = {
                "id": "slack:query_capabilities",
                "content": f"""
                SLACK QUERY CAPABILITIES:
                
                You can query Slack data in several ways:
                
                1. Get list of all channels in the workspace
                2. Get message history from a specific channel (using channel ID)
                3. Get thread replies (using channel ID and thread timestamp)
                4. Get user information (using user ID)
                5. Get bot/workspace information
                
                The data is from the last {self.history_days} days of conversation history.
                """
            }
            documents.append(query_doc)
            
            return documents
                
        except Exception as e:
            logger.error(f"Error introspecting Slack schema: {str(e)}")
            raise

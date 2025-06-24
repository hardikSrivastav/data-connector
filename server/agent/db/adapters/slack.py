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
                user_id: User ID for authentication
                workspace_id: Workspace ID for authentication
        """
        # Use a default value if connection_uri is empty
        if not connection_uri:
            connection_uri = "http://localhost:8500"
            
        self.mcp_url = connection_uri.rstrip("/")
        self.credentials_file = os.path.join(str(Path.home()), 
                                          ".data-connector", 
                                          "slack_credentials.json")
        self.history_days = kwargs.get("history_days", 30)  # Default to 30 days
        self.user_id = kwargs.get("user_id")
        self.workspace_id = kwargs.get("workspace_id")
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
    
    async def _semantic_search(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        """
        Perform semantic search on Slack messages
        
        Args:
            query: Natural language query
            **kwargs: Additional parameters
                channels: List of channel IDs to search in
                date_from: Start date (ISO format)
                date_to: End date (ISO format)
                users: List of user IDs
                limit: Maximum number of results (default 20)
                
        Returns:
            List of message results
        """
        if not await self._ensure_token():
            raise Exception("Authentication failed. Please run 'data-connector slack auth'")
        
        # Prepare search parameters
        search_params = {
            "workspace_id": int(self.workspace_id),
            "query": query,
            "limit": kwargs.get("limit", 20)
        }
        
        # Add optional filters
        if "channels" in kwargs:
            search_params["channels"] = kwargs["channels"]
            
        if "date_from" in kwargs:
            search_params["date_from"] = kwargs["date_from"]
            
        if "date_to" in kwargs:
            search_params["date_to"] = kwargs["date_to"]
            
        if "users" in kwargs:
            search_params["users"] = kwargs["users"]
        
        # Make the request
        try:
            response = requests.post(
                f"{self.mcp_url}/api/indexing/search",
                json=search_params,
                headers={"Authorization": f"Bearer {self.token}"}
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get("messages", [])
            else:
                error_msg = f"Semantic search failed: {response.status_code} - {response.text}"
                logger.error(error_msg)
                raise Exception(error_msg)
                
        except Exception as e:
            logger.error(f"Semantic search error: {str(e)}")
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
    
    async def _convert_query_format(self, query: Any) -> Any:
        """
        Convert different query formats to Slack-compatible format.
        Handles string queries from LangGraph by converting them to Slack query specifications.
        
        Args:
            query: Query in various formats (string, dict)
            
        Returns:
            Query in Slack format
        """
        if isinstance(query, dict):
            # Already in proper format, return as-is
            return query
        
        elif isinstance(query, str):
            # Convert string query to Slack format
            logger.info(f"💬 Slack Query Conversion: Converting string query to Slack API format")
            
            try:
                # Use the existing llm_to_query method to convert string to Slack format
                slack_query = await self.llm_to_query(query)
                
                logger.info(f"💬 Slack Query Conversion: \"{query}\" → {slack_query.get('type', 'unknown')} query")
                return slack_query
                
            except Exception as e:
                logger.error(f"Error converting string query to Slack format: {e}")
                # Check if it looks like a semantic search query
                semantic_keywords = ["find", "search", "messages about", "conversations", "discussions"]
                is_semantic = any(keyword in query.lower() for keyword in semantic_keywords)
                
                if is_semantic:
                    # Fallback to semantic search
                    fallback_query = {
                        "type": "semantic_search",
                        "query": query,
                        "limit": 20,
                        "error": f"Fallback to semantic search due to conversion error: {str(e)}",
                        "original_query": query
                    }
                else:
                    # Fallback to channel listing
                    fallback_query = {
                        "type": "channels",
                        "error": f"Fallback to channel listing due to conversion error: {str(e)}",
                        "original_query": query
                    }
                
                return fallback_query
        
        else:
            # Unknown format, try to handle gracefully
            logger.warning(f"Unknown query format: {type(query)}")
            return {
                "type": "channels",
                "error": f"Unsupported query format: {type(query)}",
                "original_query": str(query)
            }
            
    async def execute(self, query: Any) -> List[Dict]:
        """
        Execute the database query and return results.
        
        Args:
            query: Slack query specification (as returned by llm_to_query)
            
        Returns:
            List of dictionaries representing the query results
        """
        # Convert query format if needed (handles string queries from LangGraph)
        query = await self._convert_query_format(query)
        
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
        
        # Check if this is likely a semantic search query
        is_semantic_search = False
        semantic_search_keywords = [
            "find messages about", "search for", "messages containing", 
            "find conversations", "look for messages", "search messages",
            "find discussions", "relevant messages", "where people talked about"
        ]
        
        for keyword in semantic_search_keywords:
            if keyword.lower() in nl_prompt.lower():
                is_semantic_search = True
                break
        
        if is_semantic_search:
            # Use special template for semantic search
            prompt = llm.render_template("slack_semantic_query.tpl", 
                                      schema_context=schema_context, 
                                      query=nl_prompt)
        else:
            # Use standard template for API-based queries
            prompt = llm.render_template("slack_query.tpl", 
                                      schema_context=schema_context, 
                                      query=nl_prompt)
        
        # Generate query using orchestrate_analysis which can handle JSON responses
        response_data = await llm.orchestrate_analysis(prompt, db_type="slack")
        
        # Extract the response text from the orchestration result
        if isinstance(response_data, dict) and 'analysis' in response_data:
            response = response_data['analysis']
        elif isinstance(response_data, dict) and 'result' in response_data:
            response = response_data['result']
        else:
            response = str(response_data)
        
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
            # Check if this looks like a search query
            if any(keyword in query.lower() for keyword in ["budget planning", "search", "find", "like", "where"]):
                # Extract search terms from the query
                search_terms = "budget planning"  # Default search term
                if "like" in query.lower():
                    # Try to extract the search term from LIKE clause
                    import re
                    like_match = re.search(r"like\\s+['\"]%?([^'\"]+)%?['\"]", query.lower())
                    if like_match:
                        search_terms = like_match.group(1)
                
                logger.info(f"💬 Slack Query Conversion: Converting to semantic search for: {search_terms}")
                return {
                    "type": "semantic_search",
                    "query": search_terms,
                    "limit": 20
                }
            
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
                # Try to parse as JSON
                try:
                    query_spec = json.loads(query)
                except json.JSONDecodeError:
                    # It's not JSON, treat as a semantic search query
                    return await self._semantic_search(query, **(params or {}))
            else:
                query_spec = query
            
            # Check for semantic search type
            query_type = query_spec.get("type", "channels")
            
            if query_type == "semantic_search":
                # Handle semantic search
                search_params = {
                    "query": query_spec.get("query", ""),
                    "limit": query_spec.get("limit", 20)
                }
                
                # Add filters if present
                if "channels" in query_spec:
                    search_params["channels"] = query_spec["channels"]
                
                if "date_from" in query_spec:
                    search_params["date_from"] = query_spec["date_from"]
                
                if "date_to" in query_spec:
                    search_params["date_to"] = query_spec["date_to"]
                
                if "users" in query_spec:
                    search_params["users"] = query_spec["users"]
                
                return await self._semantic_search(**search_params)
                
            elif query_type == "channels":
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
                6. Perform semantic search across messages (e.g. "search for messages about X")
                
                The data is from the last {self.history_days} days of conversation history.
                Semantic search allows finding relevant messages by topic or content.
                """
            }
            documents.append(query_doc)
            
            # 5. Add semantic search capabilities
            search_doc = {
                "id": "slack:semantic_search",
                "content": f"""
                SEMANTIC SEARCH:
                
                You can search for messages semantically by using the semantic_search query type.
                This allows finding messages based on their meaning, not just exact keywords.
                
                Example query:
                {{
                  "type": "semantic_search",
                  "query": "discussion about annual budget planning",
                  "limit": 20,
                  "channels": ["C0123456789"],  # Optional channel filter
                  "date_from": "2023-01-01",    # Optional date filter
                  "date_to": "2023-12-31",      # Optional date filter
                  "users": ["U0123456789"]      # Optional user filter
                }}
                
                Or you can simply pass the natural language query directly to the execute_query method.
                """
            }
            documents.append(search_doc)
            
            return documents
                
        except Exception as e:
            logger.error(f"Error introspecting Slack schema: {str(e)}")
            raise
    
    # Additional Slack-specific tools for the registry
    
    async def analyze_channel_activity(self, channel_ids: List[str] = None, days: int = 30) -> Dict[str, Any]:
        """
        Analyze channel activity and engagement metrics.
        
        Args:
            channel_ids: Optional list of specific channel IDs to analyze
            days: Number of days to analyze (default 30)
            
        Returns:
            Channel activity analysis results
        """
        logger.info(f"Analyzing channel activity for {len(channel_ids) if channel_ids else 'all'} channels over {days} days")
        
        try:
            # Get all channels if none specified
            if not channel_ids:
                channels_result = await self._invoke_tool("slack_list_channels")
                channels = channels_result.get("channels", [])
                channel_ids = [c["id"] for c in channels[:10]]  # Limit to 10 for performance
            
            channel_activity = {}
            total_messages = 0
            total_users = set()
            
            for channel_id in channel_ids:
                try:
                    # Get channel info
                    channels_result = await self._invoke_tool("slack_list_channels")
                    channels = channels_result.get("channels", [])
                    channel_info = next((c for c in channels if c["id"] == channel_id), {"name": "unknown"})
                    
                    # Get recent messages
                    messages_result = await self._invoke_tool(
                        "slack_get_channel_history",
                        {"channel_id": channel_id, "limit": 100}
                    )
                    messages = messages_result.get("messages", [])
                    
                    # Analyze messages
                    channel_users = set()
                    message_count = len(messages)
                    thread_count = 0
                    
                    for msg in messages:
                        if "user" in msg:
                            channel_users.add(msg["user"])
                            total_users.add(msg["user"])
                        
                        if "thread_ts" in msg and msg["thread_ts"] != msg.get("ts"):
                            thread_count += 1
                    
                    total_messages += message_count
                    
                    channel_activity[channel_id] = {
                        "channel_id": channel_id,
                        "channel_name": channel_info.get("name", "unknown"),
                        "message_count": message_count,
                        "unique_users": len(channel_users),
                        "thread_count": thread_count,
                        "messages_per_user": message_count / len(channel_users) if channel_users else 0,
                        "thread_ratio": thread_count / message_count if message_count > 0 else 0,
                        "activity_score": self._calculate_activity_score(message_count, len(channel_users), thread_count)
                    }
                    
                except Exception as e:
                    logger.warning(f"Could not analyze channel {channel_id}: {e}")
                    channel_activity[channel_id] = {
                        "channel_id": channel_id,
                        "error": str(e)
                    }
            
            # Generate insights and recommendations
            active_channels = [c for c in channel_activity.values() if "error" not in c and c["message_count"] > 0]
            most_active = sorted(active_channels, key=lambda x: x["activity_score"], reverse=True)[:5]
            
            analysis_result = {
                "analysis_period_days": days,
                "channels_analyzed": len(channel_ids),
                "total_messages": total_messages,
                "total_unique_users": len(total_users),
                "channel_details": list(channel_activity.values()),
                "most_active_channels": most_active,
                "recommendations": self._generate_channel_activity_recommendations(active_channels),
                "summary": {
                    "avg_messages_per_channel": total_messages / len(active_channels) if active_channels else 0,
                    "avg_users_per_channel": len(total_users) / len(active_channels) if active_channels else 0,
                    "channels_with_activity": len(active_channels)
                }
            }
            
            logger.info(f"Channel activity analysis completed: {total_messages} messages across {len(active_channels)} active channels")
            return analysis_result
            
        except Exception as e:
            logger.error(f"Failed to analyze channel activity: {e}")
            raise
    
    def _calculate_activity_score(self, message_count: int, user_count: int, thread_count: int) -> float:
        """Calculate a channel activity score based on multiple factors."""
        if message_count == 0:
            return 0.0
        
        # Weight factors: messages (40%), user diversity (30%), threads (30%)
        message_score = min(message_count / 100, 1.0) * 40  # Normalize to 100 messages = max
        user_score = min(user_count / 20, 1.0) * 30  # Normalize to 20 users = max
        thread_score = min(thread_count / 20, 1.0) * 30  # Normalize to 20 threads = max
        
        return message_score + user_score + thread_score
    
    def _generate_channel_activity_recommendations(self, channels: List[Dict]) -> List[str]:
        """Generate recommendations based on channel activity analysis."""
        recommendations = []
        
        try:
            # Find inactive channels
            inactive_channels = [c for c in channels if c["message_count"] == 0]
            if inactive_channels:
                recommendations.append(f"{len(inactive_channels)} channels have no recent activity - consider archiving or promoting")
            
            # Find channels with low engagement
            low_engagement = [c for c in channels if c["message_count"] > 0 and c["unique_users"] <= 2]
            if low_engagement:
                recommendations.append(f"{len(low_engagement)} channels have low user engagement - consider promoting to broader audience")
            
            # Find channels with high thread usage
            high_threads = [c for c in channels if c["thread_ratio"] > 0.5]
            if high_threads:
                recommendations.append(f"{len(high_threads)} channels have high thread usage - good sign of detailed discussions")
            
            # Find monologue channels
            monologues = [c for c in channels if c["messages_per_user"] > 10]
            if monologues:
                recommendations.append(f"{len(monologues)} channels dominated by few users - encourage broader participation")
                
        except Exception as e:
            logger.warning(f"Failed to generate channel activity recommendations: {e}")
        
        return recommendations
    
    async def optimize_message_search(self, search_query: str, optimization_params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Optimize message search performance and provide search suggestions.
        
        Args:
            search_query: The search query to optimize
            optimization_params: Optional parameters for optimization
            
        Returns:
            Search optimization results and suggestions
        """
        logger.info(f"Optimizing message search for query: {search_query}")
        
        try:
            # Default optimization parameters
            if not optimization_params:
                optimization_params = {
                    "limit": 20,
                    "include_channels": True,
                    "include_users": True,
                    "include_date_filters": True
                }
            
            # Analyze the search query
            query_analysis = {
                "original_query": search_query,
                "query_length": len(search_query),
                "word_count": len(search_query.split()),
                "has_date_references": any(date_word in search_query.lower() for date_word in ["today", "yesterday", "last week", "last month"]),
                "has_user_references": "@" in search_query,
                "has_channel_references": "#" in search_query
            }
            
            # Generate optimized search suggestions
            search_suggestions = []
            
            # Basic semantic search
            basic_search = {
                "type": "semantic_search",
                "query": search_query,
                "limit": optimization_params.get("limit", 20)
            }
            search_suggestions.append(("basic_semantic", basic_search))
            
            # Add channel filters if available
            if optimization_params.get("include_channels", True):
                channels_result = await self._invoke_tool("slack_list_channels")
                channels = channels_result.get("channels", [])
                
                # Find channels that might be relevant
                relevant_channels = []
                for channel in channels[:5]:  # Check top 5 channels
                    channel_name = channel.get("name", "").lower()
                    if any(word in channel_name for word in search_query.lower().split()):
                        relevant_channels.append(channel["id"])
                
                if relevant_channels:
                    channel_filtered_search = basic_search.copy()
                    channel_filtered_search["channels"] = relevant_channels
                    search_suggestions.append(("channel_filtered", channel_filtered_search))
            
            # Add date filters if query has temporal references
            if query_analysis["has_date_references"]:
                from datetime import datetime, timedelta
                
                time_filtered_search = basic_search.copy()
                
                if "today" in search_query.lower():
                    time_filtered_search["date_from"] = datetime.now().date().isoformat()
                elif "yesterday" in search_query.lower():
                    yesterday = datetime.now().date() - timedelta(days=1)
                    time_filtered_search["date_from"] = yesterday.isoformat()
                    time_filtered_search["date_to"] = yesterday.isoformat()
                elif "last week" in search_query.lower():
                    week_ago = datetime.now().date() - timedelta(days=7)
                    time_filtered_search["date_from"] = week_ago.isoformat()
                
                search_suggestions.append(("time_filtered", time_filtered_search))
            
            # Test search performance
            performance_results = []
            for search_name, search_params in search_suggestions:
                try:
                    start_time = time.time()
                    results = await self._semantic_search(**search_params)
                    end_time = time.time()
                    
                    performance_results.append({
                        "search_type": search_name,
                        "execution_time_ms": int((end_time - start_time) * 1000),
                        "result_count": len(results),
                        "search_params": search_params
                    })
                except Exception as e:
                    performance_results.append({
                        "search_type": search_name,
                        "error": str(e),
                        "search_params": search_params
                    })
            
            # Generate optimization recommendations
            optimization_recommendations = self._generate_search_optimization_recommendations(
                query_analysis, performance_results
            )
            
            optimization_result = {
                "query_analysis": query_analysis,
                "search_suggestions": search_suggestions,
                "performance_results": performance_results,
                "best_performing_search": self._find_best_search(performance_results),
                "optimization_recommendations": optimization_recommendations,
                "estimated_improvement": self._calculate_search_improvement(performance_results)
            }
            
            logger.info(f"Message search optimization completed with {len(search_suggestions)} suggestions")
            return optimization_result
            
        except Exception as e:
            logger.error(f"Failed to optimize message search: {e}")
            raise
    
    def _generate_search_optimization_recommendations(self, query_analysis: Dict, performance_results: List[Dict]) -> List[str]:
        """Generate search optimization recommendations."""
        recommendations = []
        
        try:
            # Check query complexity
            if query_analysis["word_count"] > 10:
                recommendations.append("Consider simplifying the search query for better performance")
            
            if query_analysis["query_length"] > 100:
                recommendations.append("Very long search query may impact performance")
            
            # Check performance results
            successful_searches = [r for r in performance_results if "error" not in r]
            if successful_searches:
                avg_time = sum(r["execution_time_ms"] for r in successful_searches) / len(successful_searches)
                if avg_time > 2000:
                    recommendations.append("Search queries are taking longer than 2 seconds - consider adding filters")
            
            # Check result counts
            high_result_searches = [r for r in successful_searches if r.get("result_count", 0) > 50]
            if high_result_searches:
                recommendations.append("Some searches return many results - consider adding date or channel filters")
            
        except Exception as e:
            logger.warning(f"Failed to generate search optimization recommendations: {e}")
        
        return recommendations
    
    def _find_best_search(self, performance_results: List[Dict]) -> Optional[Dict]:
        """Find the best performing search based on speed and result quality."""
        successful_searches = [r for r in performance_results if "error" not in r and r.get("result_count", 0) > 0]
        
        if not successful_searches:
            return None
        
        # Score based on speed (lower is better) and result count (moderate is better)
        def score_search(search):
            time_score = 1000 / max(search["execution_time_ms"], 100)  # Faster = better
            result_score = min(search.get("result_count", 0), 20) / 20  # Sweet spot around 20 results
            return time_score * 0.6 + result_score * 0.4
        
        return max(successful_searches, key=score_search)
    
    def _calculate_search_improvement(self, performance_results: List[Dict]) -> float:
        """Calculate estimated improvement percentage from optimization."""
        successful_searches = [r for r in performance_results if "error" not in r]
        
        if len(successful_searches) < 2:
            return 0.0
        
        times = [r["execution_time_ms"] for r in successful_searches]
        fastest = min(times)
        slowest = max(times)
        
        if slowest > 0:
            improvement = ((slowest - fastest) / slowest) * 100
            return improvement
        
        return 0.0
    
    async def get_workspace_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive statistics for the Slack workspace.
        
        Returns:
            Workspace statistics and metadata
        """
        logger.info("Getting comprehensive Slack workspace statistics")
        
        try:
            # Get workspace info
            bot_info = await self._invoke_tool("slack_bot_info")
            workspace_info = bot_info.get("bot_info", {})
            
            # Get channels
            channels_result = await self._invoke_tool("slack_list_channels")
            channels = channels_result.get("channels", [])
            
            # Analyze channels
            total_channels = len(channels)
            public_channels = len([c for c in channels if not c.get("is_private", False)])
            private_channels = total_channels - public_channels
            
            # Sample recent activity from a few channels
            sample_channels = channels[:5]  # Sample first 5 channels
            total_sampled_messages = 0
            unique_users = set()
            
            for channel in sample_channels:
                try:
                    messages_result = await self._invoke_tool(
                        "slack_get_channel_history",
                        {"channel_id": channel["id"], "limit": 50}
                    )
                    messages = messages_result.get("messages", [])
                    total_sampled_messages += len(messages)
                    
                    for msg in messages:
                        if "user" in msg:
                            unique_users.add(msg["user"])
                            
                except Exception as e:
                    logger.warning(f"Could not sample channel {channel.get('name')}: {e}")
            
            # Estimate workspace activity
            estimated_total_messages = (total_sampled_messages / len(sample_channels)) * total_channels if sample_channels else 0
            
            statistics = {
                "workspace_info": {
                    "team_name": workspace_info.get("team_name", "Unknown"),
                    "team_domain": workspace_info.get("team_domain", "unknown"),
                    "bot_name": workspace_info.get("bot_name", "Unknown")
                },
                "channel_statistics": {
                    "total_channels": total_channels,
                    "public_channels": public_channels,
                    "private_channels": private_channels,
                    "sampled_channels": len(sample_channels)
                },
                "activity_estimates": {
                    "sampled_messages": total_sampled_messages,
                    "estimated_total_messages": int(estimated_total_messages),
                    "unique_users_in_sample": len(unique_users),
                    "avg_messages_per_channel": total_sampled_messages / len(sample_channels) if sample_channels else 0
                },
                "data_coverage": {
                    "history_days": self.history_days,
                    "channel_sample_size": len(sample_channels),
                    "sampling_ratio": len(sample_channels) / total_channels if total_channels > 0 else 0
                },
                "recommendations": self._generate_workspace_recommendations(
                    total_channels, public_channels, total_sampled_messages, len(unique_users)
                )
            }
            
            logger.info(f"Workspace statistics completed: {total_channels} channels, {len(unique_users)} users sampled")
            return statistics
            
        except Exception as e:
            logger.error(f"Failed to get workspace statistics: {e}")
            raise
    
    def _generate_workspace_recommendations(
        self, 
        total_channels: int, 
        public_channels: int, 
        sampled_messages: int, 
        unique_users: int
    ) -> List[str]:
        """Generate recommendations based on workspace analysis."""
        recommendations = []
        
        try:
            # Channel recommendations
            if total_channels > 50:
                recommendations.append("Large number of channels - consider organizing with channel naming conventions")
            
            private_ratio = (total_channels - public_channels) / total_channels if total_channels > 0 else 0
            if private_ratio > 0.5:
                recommendations.append("High ratio of private channels - consider making some public for better collaboration")
            
            # Activity recommendations
            if sampled_messages == 0:
                recommendations.append("No recent message activity detected - verify bot permissions and workspace engagement")
            elif sampled_messages < 10:
                recommendations.append("Low message activity - consider promoting workspace engagement")
            
            # User engagement recommendations
            if unique_users < 5:
                recommendations.append("Limited user engagement detected - consider onboarding more team members")
            
        except Exception as e:
            logger.warning(f"Failed to generate workspace recommendations: {e}")
        
        return recommendations

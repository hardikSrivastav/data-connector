import asyncio
import logging
import time
import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple, Set
from sqlalchemy.orm import Session
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, CollectionStatus
from slack_sdk import WebClient

from ..db.database import get_db
from ..db import crud, models
from ..qdrant_client import get_qdrant_client, store_message_embeddings, delete_old_messages
from ..config import settings
from ..security import decrypt

# Configure logging
logger = logging.getLogger(__name__)

class MessageIndexer:
    """Class for indexing Slack messages in Qdrant"""
    
    def __init__(self, workspace_id: int):
        """
        Initialize the indexer
        
        Args:
            workspace_id: ID of the workspace to index
        """
        self.workspace_id = workspace_id
        
        # Get workspace from database first to validate
        self.db = next(get_db())
        self.workspace = crud.get_workspace(self.db, workspace_id)
        if not self.workspace:
            raise ValueError(f"Workspace {workspace_id} not found")
            
        if not self.workspace.bot_token:
            raise ValueError(f"Workspace {workspace_id} has no bot token")
        
        # Get Qdrant client
        try:
            self.qdrant_client = get_qdrant_client()
            logger.info(f"Connected to Qdrant for workspace {workspace_id}")
        except Exception as e:
            logger.error(f"Failed to connect to Qdrant: {str(e)}")
            raise ValueError(f"Failed to connect to Qdrant: {str(e)}")
        
        # Initialize embedding model
        try:
            self.embedding_model = SentenceTransformer(settings.DEFAULT_EMBEDDING_MODEL)
            logger.info(f"Initialized embedding model: {settings.DEFAULT_EMBEDDING_MODEL}")
        except Exception as e:
            logger.error(f"Failed to initialize embedding model: {str(e)}")
            raise ValueError(f"Failed to initialize embedding model: {str(e)}")
        
        # Get or create indexing status
        self.index_status = crud.get_indexing_status(self.db, workspace_id)
        if not self.index_status:
            collection_name = f"slack_messages_{self.workspace.team_id}"
            self.index_status = crud.create_indexing_status(
                self.db, 
                workspace_id=workspace_id, 
                collection_name=collection_name,
                history_days=settings.DEFAULT_HISTORY_DAYS,
                update_frequency_hours=settings.DEFAULT_UPDATE_FREQUENCY
            )
            logger.info(f"Created new indexing status for workspace {workspace_id} with collection {collection_name}")
        else:
            logger.info(f"Found existing indexing status for workspace {workspace_id} with collection {self.index_status.collection_name}")
        
        # Ensure collection exists
        self._ensure_collection_exists()
        
        # Initialize Slack client directly
        self.slack_client = self._get_slack_client()
    
    def _get_slack_client(self) -> WebClient:
        """Create a Slack client for the workspace"""
        if not self.workspace.bot_token:
            raise ValueError("Workspace has no bot token")
        
        # Decrypt token and create client
        try:
            token = decrypt(self.workspace.bot_token)
            
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
    
    def _ensure_collection_exists(self):
        """Ensure the Qdrant collection exists"""
        collection_name = self.index_status.collection_name
        try:
            # Check if collection exists
            collections = self.qdrant_client.get_collections().collections
            collection_names = [c.name for c in collections]
            
            if collection_name in collection_names:
                logger.info(f"Collection {collection_name} already exists")
                return
            
            # Create collection
            logger.info(f"Creating collection {collection_name}")
            vector_size = 384  # Default for all-MiniLM-L6-v2
            
            self.qdrant_client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=vector_size,
                    distance=Distance.COSINE
                )
            )
            
            # Wait for collection to be ready
            max_retries = 5
            for i in range(max_retries):
                try:
                    collection_info = self.qdrant_client.get_collection(collection_name)
                    if collection_info.status == CollectionStatus.GREEN:
                        logger.info(f"Collection {collection_name} created and ready")
                        return
                except Exception as e:
                    logger.warning(f"Collection not ready yet (attempt {i+1}/{max_retries}): {str(e)}")
                
                time.sleep(1)
            
            logger.error(f"Failed to verify collection {collection_name} is ready after {max_retries} attempts")
        except Exception as e:
            logger.error(f"Error creating collection {collection_name}: {str(e)}")
            raise ValueError(f"Failed to create collection: {str(e)}")
    
    async def authenticate(self) -> bool:
        """Check if Slack client is authenticated correctly"""
        try:
            # Test authentication by making a simple API call
            auth_test = self.slack_client.auth_test()
            if auth_test and auth_test["ok"]:
                logger.info(f"Successfully authenticated with Slack as {auth_test.get('user')} for team {auth_test.get('team')}")
                return True
            return False
        except Exception as e:
            logger.error(f"Authentication failed: {str(e)}")
            return False
    
    async def process_channels(self, force_full: bool = False) -> Tuple[int, int]:
        """
        Process all channels in the workspace
        
        Args:
            force_full: If True, reindex all messages within history_days
        
        Returns:
            Tuple of (total_messages, indexed_messages)
        """
        if not await self.authenticate():
            logger.error(f"Failed to authenticate for workspace {self.workspace_id}")
            return 0, 0
        
        # Get all channels directly using Slack API
        try:
            response = self.slack_client.conversations_list(limit=1000)
            channels = [{"id": c["id"], "name": c["name"]} for c in response["channels"]]
            logger.info(f"Found {len(channels)} channels in workspace {self.workspace.team_name}")
            for channel in channels:
                logger.debug(f"Channel found: #{channel['name']} ({channel['id']})")
        except Exception as e:
            logger.error(f"Failed to list channels: {str(e)}")
            return 0, 0
        
        # Calculate the cutoff date for history
        cutoff_date = datetime.utcnow() - timedelta(days=self.index_status.history_days)
        cutoff_ts = cutoff_date.timestamp()
        logger.info(f"Using cutoff date {cutoff_date.isoformat()} (timestamp: {cutoff_ts})")
        
        # Track overall stats
        total_messages = 0
        indexed_messages = 0
        oldest_ts = None
        newest_ts = None
        
        # Process each channel
        for channel in channels:
            channel_id = channel["id"]
            channel_name = channel["name"]
            
            # Get or create channel indexing status
            indexed_channel = crud.get_indexed_channel(self.db, self.index_status.id, channel_id)
            if not indexed_channel:
                indexed_channel = crud.create_indexed_channel(
                    self.db,
                    index_id=self.index_status.id,
                    channel_id=channel_id,
                    channel_name=channel_name
                )
            
            # Get messages to index
            last_indexed_ts = None if force_full else indexed_channel.last_indexed_ts
            if last_indexed_ts:
                logger.info(f"Channel #{channel_name}: Only fetching messages newer than {datetime.fromtimestamp(float(last_indexed_ts)).isoformat()}")
            else:
                logger.info(f"Channel #{channel_name}: Fetching all messages within history days")
            
            try:
                # Process this channel
                channel_total, channel_indexed, channel_oldest, channel_newest = await self.process_channel(
                    channel_id=channel_id,
                    channel_name=channel_name,
                    cutoff_ts=cutoff_ts,
                    last_indexed_ts=last_indexed_ts
                )
                
                # Update stats
                total_messages += channel_total
                indexed_messages += channel_indexed
                
                # Track oldest/newest message timestamps
                if channel_oldest and (not oldest_ts or float(channel_oldest) < float(oldest_ts)):
                    oldest_ts = channel_oldest
                
                if channel_newest and (not newest_ts or float(channel_newest) > float(newest_ts)):
                    newest_ts = channel_newest
                
                # Update success in DB
                if channel_indexed > 0 and channel_newest:
                    crud.update_indexed_channel(
                        self.db,
                        index_id=self.index_status.id,
                        channel_id=channel_id,
                        last_indexed_ts=channel_newest,
                        message_count=indexed_channel.message_count + channel_indexed
                    )
            
            except Exception as e:
                logger.error(f"Error processing channel {channel_name}: {str(e)}")
                # Continue with next channel
        
        # Prune old messages
        try:
            deleted = delete_old_messages(
                self.qdrant_client, 
                self.index_status.collection_name, 
                cutoff_ts
            )
            logger.info(f"Deleted {deleted} messages older than {cutoff_date.isoformat()}")
        except Exception as e:
            logger.error(f"Error pruning old messages: {str(e)}")
        
        # Update indexing status
        crud.update_indexing_completed(
            self.db,
            index_id=self.index_status.id,
            total_messages=self.index_status.total_messages + total_messages,
            indexed_messages=indexed_messages,
            oldest_ts=oldest_ts,
            newest_ts=newest_ts
        )
        
        return total_messages, indexed_messages
    
    async def process_channel(
        self, 
        channel_id: str, 
        channel_name: str,
        cutoff_ts: float,
        last_indexed_ts: Optional[str] = None
    ) -> Tuple[int, int, Optional[str], Optional[str]]:
        """
        Process messages from a single channel
        
        Args:
            channel_id: Slack channel ID
            channel_name: Slack channel name
            cutoff_ts: Timestamp to cutoff older messages
            last_indexed_ts: Optional timestamp of last indexed message
        
        Returns:
            Tuple of (total_messages, indexed_messages, oldest_ts, newest_ts)
        """
        logger.info(f"Processing channel #{channel_name} ({channel_id})")
        
        # Initialize tracking
        all_messages = []
        oldest_ts = None
        newest_ts = None
        has_more = True
        cursor = None
        
        # Retrieve messages in batches
        while has_more:
            try:
                # Prepare parameters for Slack API
                params = {
                    "channel": channel_id,
                    "limit": 100  # Slack API limit
                }
                
                if cursor:
                    params["cursor"] = cursor
                
                # If we're only getting new messages, add oldest timestamp
                if last_indexed_ts:
                    params["oldest"] = last_indexed_ts
                
                # Get messages directly using Slack API
                logger.debug(f"Requesting messages from channel #{channel_name} with params: {params}")
                response = self.slack_client.conversations_history(**params)
                messages = response.get("messages", [])
                logger.info(f"Retrieved {len(messages)} messages from channel #{channel_name}")
                
                # Process pagination
                cursor = response.get("response_metadata", {}).get("next_cursor")
                has_more = bool(cursor)
                
                # Add messages to our list
                if messages:
                    # Filter out messages older than cutoff
                    filtered_messages = []
                    skipped_cutoff = 0
                    for msg in messages:
                        if "ts" in msg and float(msg["ts"]) >= cutoff_ts:
                            filtered_messages.append(msg)
                        else:
                            skipped_cutoff += 1
                    
                    if skipped_cutoff > 0:
                        logger.info(f"Skipped {skipped_cutoff} messages older than cutoff date {datetime.fromtimestamp(cutoff_ts).isoformat()}")
                    
                    all_messages.extend(filtered_messages)
                    
                    # Track timestamp range
                    for msg in filtered_messages:
                        if "ts" in msg:
                            if not oldest_ts or float(msg["ts"]) < float(oldest_ts):
                                oldest_ts = msg["ts"]
                            if not newest_ts or float(msg["ts"]) > float(newest_ts):
                                newest_ts = msg["ts"]
                
                # Don't hammer the API
                await asyncio.sleep(0.5)
                
                # Limit to reasonable number of messages per channel to avoid overloading
                if len(all_messages) >= 1000:
                    logger.info(f"Reached 1000 message limit for channel {channel_name}")
                    break
            
            except Exception as e:
                logger.error(f"Error retrieving messages for channel {channel_name}: {str(e)}")
                break
        
        # Return early if no messages
        if not all_messages:
            logger.info(f"No new messages found in channel {channel_name}")
            return 0, 0, oldest_ts, newest_ts
        
        logger.info(f"Retrieved {len(all_messages)} messages from channel {channel_name}")
        
        # Debug message contents
        for i, msg in enumerate(all_messages[:5]):  # Log first 5 messages as samples
            log_msg = {
                "ts": msg.get("ts"),
                "has_text": "text" in msg and bool(msg["text"]),
                "text_length": len(msg.get("text", "")) if "text" in msg else 0,
                "has_attachments": "attachments" in msg and bool(msg["attachments"]),
                "has_files": "files" in msg and bool(msg["files"]),
                "has_thread_ts": "thread_ts" in msg
            }
            logger.debug(f"Message sample {i+1}: {json.dumps(log_msg)}")
        
        # Process and index the messages
        try:
            indexed_count = await self.index_messages(all_messages, channel_id, channel_name)
            logger.info(f"Indexed {indexed_count}/{len(all_messages)} messages from channel #{channel_name}")
            if indexed_count < len(all_messages):
                logger.info(f"Skipped {len(all_messages) - indexed_count} messages in channel #{channel_name}")
            return len(all_messages), indexed_count, oldest_ts, newest_ts
        except Exception as e:
            logger.error(f"Error indexing messages for channel {channel_name}: {str(e)}")
            return len(all_messages), 0, oldest_ts, newest_ts
    
    async def index_messages(self, messages: List[Dict[str, Any]], channel_id: str, channel_name: str) -> int:
        """
        Generate embeddings and index messages
        
        Args:
            messages: List of Slack messages
            channel_id: Slack channel ID
            channel_name: Slack channel name
        
        Returns:
            Number of messages indexed
        """
        if not messages:
            return 0
        
        # Extract text from messages
        texts = []
        payloads = []
        skipped_messages = 0
        skipped_reasons = {
            "no_text": 0,
            "empty_text": 0
        }
        
        for msg in messages:
            # Skip messages without text
            if "text" not in msg:
                skipped_messages += 1
                skipped_reasons["no_text"] += 1
                logger.debug(f"Skipping message {msg.get('ts')}: No text field. Keys: {list(msg.keys())}")
                continue
                
            if not msg["text"]:
                skipped_messages += 1
                skipped_reasons["empty_text"] += 1
                logger.debug(f"Skipping message {msg.get('ts')}: Empty text. Type: {type(msg['text'])}")
                continue
            
            # Create text for embedding
            text = msg["text"]
            
            # Add attachments if any
            if "attachments" in msg and msg["attachments"]:
                for attachment in msg["attachments"]:
                    if "text" in attachment and attachment["text"]:
                        text += f"\n{attachment['text']}"
            
            # Create payload
            payload = {
                "ts": float(msg["ts"]),
                "text": msg["text"],
                "user_id": msg.get("user", ""),
                "channel_id": channel_id,
                "channel_name": channel_name,
                "has_attachments": "attachments" in msg and bool(msg["attachments"]),
                "has_files": "files" in msg and bool(msg["files"]),
                # TODO: Add timestamp as datetime for readability
                "datetime": datetime.fromtimestamp(float(msg["ts"])).isoformat(),
            }
            
            # Keep track of original message data
            payload["original_msg"] = {
                key: value for key, value in msg.items()
                if key in ["user", "ts", "thread_ts", "reply_count", "reactions"]
            }
            
            texts.append(text)
            payloads.append(payload)
        
        if skipped_messages > 0:
            logger.info(f"Skipped {skipped_messages} messages from channel {channel_name} during preprocessing")
            logger.info(f"Skip reasons: {json.dumps(skipped_reasons)}")
        
        logger.info(f"Preparing to index {len(texts)} messages with valid text from channel {channel_name}")
        
        # Generate embeddings in batches
        batch_size = settings.EMBEDDING_BATCH_SIZE
        total_indexed = 0
        
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            batch_payloads = payloads[i:i + batch_size]
            
            # Generate embeddings
            try:
                logger.debug(f"Generating embeddings for batch {i//batch_size+1} with {len(batch_texts)} messages")
                batch_embeddings = self.embedding_model.encode(batch_texts).tolist()
                
                # Store in Qdrant
                stored = store_message_embeddings(
                    self.qdrant_client,
                    self.index_status.collection_name,
                    batch_embeddings,
                    batch_payloads
                )
                
                total_indexed += stored
                logger.info(f"Indexed {stored} messages in batch ({i}-{i+len(batch_texts)})")
                
            except Exception as e:
                logger.error(f"Error indexing batch {i//batch_size}: {str(e)}")
                # Continue with next batch
        
        return total_indexed

async def process_workspace(workspace_id: int, force_full: bool = False):
    """
    Process a workspace's messages for indexing
    
    Args:
        workspace_id: ID of the workspace to process
        force_full: If True, reindex all messages within history days
    """
    logger.info(f"Starting indexing for workspace {workspace_id}")
    start_time = time.time()
    
    try:
        # Create indexer
        indexer = MessageIndexer(workspace_id)
        
        # Try to authenticate
        if not await indexer.authenticate():
            error_msg = f"Authentication failed for workspace {workspace_id}. Please check:"
            error_msg += "\n1. The bot token in the database for workspace ID {workspace_id}"
            error_msg += "\n2. Network connectivity to the Slack API"
            logger.error(error_msg)
            
            # Update indexing status to show it's no longer running
            db = next(get_db())
            status = crud.get_indexing_status(db, workspace_id)
            if status:
                crud.update_indexing_status(db, status.id, is_indexing=False)
                
            return {
                "success": False,
                "error": "Authentication failed",
                "details": error_msg
            }
        
        # Process channels
        total_messages, indexed_messages = await indexer.process_channels(force_full=force_full)
        
        # Record metrics
        elapsed_time = time.time() - start_time
        logger.info(f"Completed indexing for workspace {workspace_id}")
        logger.info(f"Processed {total_messages} messages, indexed {indexed_messages}")
        logger.info(f"Elapsed time: {elapsed_time:.2f} seconds")
        
        return {
            "success": True,
            "total_messages": total_messages,
            "indexed_messages": indexed_messages,
            "elapsed_time": elapsed_time
        }
    
    except Exception as e:
        logger.error(f"Error processing workspace {workspace_id}: {str(e)}")
        
        # Update indexing status to show it's no longer running
        db = next(get_db())
        status = crud.get_indexing_status(db, workspace_id)
        if status:
            crud.update_indexing_status(db, status.id, is_indexing=False)
        
        return {
            "success": False,
            "error": str(e)
        }

async def run_scheduled_indexing():
    """
    Run scheduled indexing for workspaces that need updates
    
    This should be called periodically by a scheduler
    """
    logger.info("Starting scheduled indexing")
    
    # Get workspaces that need indexing
    db = next(get_db())
    pending_workspaces = crud.get_pending_indexing_workspaces(db, max_results=5)
    
    if not pending_workspaces:
        logger.info("No workspaces need indexing")
        return
    
    logger.info(f"Found {len(pending_workspaces)} workspaces to index")
    
    # Process each workspace
    for index_status in pending_workspaces:
        # Mark as indexing
        crud.update_indexing_status(db, index_status.id, is_indexing=True)
        
        # Process in background
        asyncio.create_task(process_workspace(index_status.workspace_id))
        
        # Wait a bit between workspaces to avoid overloading
        await asyncio.sleep(5) 
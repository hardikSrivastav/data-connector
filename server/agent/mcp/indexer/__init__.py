import logging
from typing import Dict, Any, List, Optional

from ..db.database import get_db
from ..db import crud
from ..models.indexing import IndexingStatus

# Configure logging
logger = logging.getLogger(__name__)

# Import functions from processor
from .processor import process_workspace, run_scheduled_indexing

async def start_indexing(workspace_id: int, force_full: bool = False) -> Dict[str, Any]:
    """
    High-level function to start indexing for a workspace
    
    Args:
        workspace_id: ID of the workspace to index
        force_full: If True, reindex all messages
        
    Returns:
        Dictionary with status information
    """
    logger.info(f"Starting indexing for workspace {workspace_id}")
    
    # Validate workspace exists
    db = next(get_db())
    workspace = crud.get_workspace(db, workspace_id)
    if not workspace:
        logger.error(f"Workspace {workspace_id} not found")
        return {
            "success": False,
            "error": f"Workspace {workspace_id} not found"
        }
    
    # Validate workspace has tokens
    if not workspace.bot_token:
        logger.error(f"Workspace {workspace_id} has no bot token")
        return {
            "success": False,
            "error": f"Workspace has no bot token"
        }
    
    # Start the indexing process in the background
    try:
        # Create a background task
        import asyncio
        asyncio.create_task(process_workspace(workspace_id, force_full))
        
        # Return success right away
        return {
            "success": True,
            "status": "started",
            "message": "Indexing has started for workspace"
        }
    except Exception as e:
        logger.exception(f"Error starting indexing: {str(e)}")
        
        # Make sure indexing status is updated
        status = crud.get_indexing_status(db, workspace_id)
        if status:
            crud.update_indexing_status(db, status.id, is_indexing=False)
        
        return {
            "success": False,
            "error": str(e)
        } 
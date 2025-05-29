from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
import json

router = APIRouter(prefix="/api", tags=["storage"])

# Pydantic models for request/response
class Block(BaseModel):
    id: str
    type: str
    content: str
    order: int = 0  # Position within the page
    pageId: Optional[str] = None
    updatedAt: Optional[datetime] = None

class Page(BaseModel):
    id: str
    title: str
    icon: Optional[str] = None
    blocks: List[Block]
    createdAt: datetime
    updatedAt: datetime

class Workspace(BaseModel):
    id: str
    name: str
    pages: List[Page]

class Change(BaseModel):
    id: str
    type: str  # 'create', 'update', 'delete'
    entity: str  # 'workspace', 'page', 'block'
    entityId: str
    data: Any
    timestamp: datetime
    userId: str

class SyncRequest(BaseModel):
    changes: List[Change]
    lastSync: Optional[datetime] = None

class SyncResponse(BaseModel):
    changes: List[Any] = []
    conflicts: List[Any] = []
    lastSync: datetime

# In-memory storage for demo purposes
# In production, this would connect to your database
storage = {
    "workspaces": {},
    "pages": {},
    "blocks": {},
    "changes": []
}

@router.get("/workspaces/{workspace_id}", response_model=Workspace)
async def get_workspace(workspace_id: str):
    """Get workspace by ID"""
    workspace = storage["workspaces"].get(workspace_id)
    if not workspace:
        # Create default workspace
        workspace = {
            "id": workspace_id,
            "name": "My Workspace",
            "pages": []
        }
        storage["workspaces"][workspace_id] = workspace
    
    # Get all pages that belong to this workspace (for now, all pages)
    workspace_pages = []
    for page_id, page_data in storage["pages"].items():
        # Add blocks to the page
        page_blocks = []
        for block_id, block_data in storage["blocks"].items():
            if block_data.get("pageId") == page_id:
                page_blocks.append(block_data)
        
        # Sort blocks by order field to preserve content sequence
        page_blocks.sort(key=lambda x: x.get("order", 0))
        
        page_with_blocks = {**page_data, "blocks": page_blocks}
        workspace_pages.append(page_with_blocks)
    
    # Sort pages by creation date or some other order
    workspace_pages.sort(key=lambda x: x.get("createdAt", ""))
    
    # Update workspace with current pages
    workspace["pages"] = workspace_pages
    storage["workspaces"][workspace_id] = workspace
    
    return Workspace(**workspace)

@router.post("/workspaces/{workspace_id}", response_model=Workspace)
async def save_workspace(workspace_id: str, workspace: Workspace):
    """Save workspace"""
    workspace_dict = workspace.dict()
    storage["workspaces"][workspace_id] = workspace_dict
    
    # Also save individual pages for easier access
    for page in workspace.pages:
        storage["pages"][page.id] = page.dict()
        
        # Clean up old blocks for this page first
        blocks_to_remove = []
        for block_id, block_data in storage["blocks"].items():
            if block_data.get("pageId") == page.id:
                blocks_to_remove.append(block_id)
        
        # Remove old blocks
        for block_id in blocks_to_remove:
            del storage["blocks"][block_id]
        
        # Save current blocks (only the ones that should exist)
        for block in page.blocks:
            block_dict = block.dict()
            block_dict["pageId"] = page.id
            storage["blocks"][block.id] = block_dict
    
    return workspace

@router.get("/pages/{page_id}", response_model=Page)
async def get_page(page_id: str):
    """Get page by ID"""
    page = storage["pages"].get(page_id)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    
    return Page(**page)

@router.post("/pages", response_model=Page)
async def save_page(page: Page):
    """Save page"""
    page_dict = page.dict()
    storage["pages"][page.id] = page_dict
    
    # Clean up old blocks for this page first
    blocks_to_remove = []
    for block_id, block_data in storage["blocks"].items():
        if block_data.get("pageId") == page.id:
            blocks_to_remove.append(block_id)
    
    # Remove old blocks
    for block_id in blocks_to_remove:
        del storage["blocks"][block_id]
    
    # Save current blocks (only the ones that should exist)
    for block in page.blocks:
        block_dict = block.dict()
        block_dict["pageId"] = page.id
        storage["blocks"][block.id] = block_dict
    
    return page

@router.post("/blocks", response_model=Block)
async def save_block(block: Block):
    """Save block"""
    block_dict = block.dict()
    storage["blocks"][block.id] = block_dict
    return block

@router.post("/sync", response_model=SyncResponse)
async def sync_changes(sync_request: SyncRequest):
    """Sync changes from client"""
    print(f"Received sync request with {len(sync_request.changes)} changes")
    
    # Process each change
    for change in sync_request.changes:
        print(f"Processing change: {change.type} {change.entity} {change.entityId}")
        
        # Store the change for audit log
        storage["changes"].append(change.dict())
        
        # Apply the change to storage
        if change.entity == "page":
            if change.type in ["create", "update"]:
                storage["pages"][change.entityId] = change.data
            elif change.type == "delete":
                if change.entityId in storage["pages"]:
                    del storage["pages"][change.entityId]
                # Also delete all blocks belonging to this page
                blocks_to_remove = []
                for block_id, block_data in storage["blocks"].items():
                    if block_data.get("pageId") == change.entityId:
                        blocks_to_remove.append(block_id)
                for block_id in blocks_to_remove:
                    del storage["blocks"][block_id]
        elif change.entity == "block":
            if change.type in ["create", "update"]:
                storage["blocks"][change.entityId] = change.data
            elif change.type == "delete":
                if change.entityId in storage["blocks"]:
                    del storage["blocks"][change.entityId]
        elif change.entity == "workspace":
            if change.type in ["create", "update"]:
                storage["workspaces"][change.entityId] = change.data
            elif change.type == "delete":
                if change.entityId in storage["workspaces"]:
                    del storage["workspaces"][change.entityId]
    
    # Return sync response
    return SyncResponse(
        changes=[],  # No server-side changes for now
        conflicts=[], # No conflicts for now
        lastSync=datetime.now()
    )

@router.get("/storage/stats")
async def get_storage_stats():
    """Get storage statistics for debugging"""
    return {
        "workspaces": len(storage["workspaces"]),
        "pages": len(storage["pages"]),
        "blocks": len(storage["blocks"]),
        "changes": len(storage["changes"])
    }

@router.delete("/storage/reset")
async def reset_storage():
    """Reset all storage (for development)"""
    storage["workspaces"].clear()
    storage["pages"].clear()
    storage["blocks"].clear()
    storage["changes"].clear()
    return {"message": "Storage reset successfully"}

@router.get("/storage/debug")
async def debug_storage():
    """Debug endpoint to see raw storage contents"""
    return {
        "workspaces": storage["workspaces"],
        "pages": storage["pages"],
        "blocks": storage["blocks"],
        "recent_changes": storage["changes"][-5:] if storage["changes"] else []
    } 
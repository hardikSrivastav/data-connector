from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
import json
import os
from sqlalchemy import create_engine, Column, String, DateTime, Text, Integer, JSON, Index, ForeignKey, Boolean, LargeBinary
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid

router = APIRouter(prefix="/api", tags=["storage"])

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://notion_user:notion_password@localhost:5432/notion_clone")

try:
    engine = create_engine(DATABASE_URL, echo=True)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base = declarative_base()
except Exception as e:
    print(f"Database connection error: {e}")
    print("Make sure PostgreSQL is running and the database exists")
    raise

# SQLAlchemy Models
class WorkspaceDB(Base):
    __tablename__ = "workspaces"
    
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    extra_data = Column(JSONB, default={})  # For future extensibility
    
    # Relationships
    pages = relationship("PageDB", back_populates="workspace", cascade="all, delete-orphan")
    changes = relationship("ChangeDB", back_populates="workspace")
    canvas_threads = relationship("CanvasThreadDB", back_populates="workspace", cascade="all, delete-orphan")

class PageDB(Base):
    __tablename__ = "pages"
    
    id = Column(String, primary_key=True)
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False)
    title = Column(String, nullable=False)
    icon = Column(String, nullable=True)  # Emoji icon
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    extra_data = Column(JSONB, default={})  # For future properties
    
    # Relationships
    workspace = relationship("WorkspaceDB", back_populates="pages")
    blocks = relationship("BlockDB", back_populates="page", cascade="all, delete-orphan", order_by="BlockDB.order")
    changes = relationship("ChangeDB", back_populates="page")
    canvas_threads = relationship("CanvasThreadDB", back_populates="page", cascade="all, delete-orphan")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_pages_workspace_id', 'workspace_id'),
        Index('idx_pages_updated_at', 'updated_at'),
    )

class BlockDB(Base):
    __tablename__ = "blocks"
    
    id = Column(String, primary_key=True)
    page_id = Column(String, ForeignKey("pages.id"), nullable=False)
    type = Column(String, nullable=False)  # text, heading1, bullet, canvas, etc.
    content = Column(Text, nullable=False, default="")
    order = Column(Integer, nullable=False, default=0)
    properties = Column(JSONB, default={})  # Bold, italic, color, canvas-specific properties, etc.
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    page = relationship("PageDB", back_populates="blocks")
    changes = relationship("ChangeDB", back_populates="block")
    canvas_thread = relationship("CanvasThreadDB", back_populates="block", uselist=False)
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_blocks_page_id', 'page_id'),
        Index('idx_blocks_page_order', 'page_id', 'order'),
        Index('idx_blocks_updated_at', 'updated_at'),
        Index('idx_blocks_type', 'type'),
    )

class ChangeDB(Base):
    __tablename__ = "changes"
    
    id = Column(String, primary_key=True)  # Will be set explicitly from frontend or auto-generated
    type = Column(String, nullable=False)  # create, update, delete
    entity = Column(String, nullable=False)  # workspace, page, block, canvas_thread, analysis_commit
    entity_id = Column(String, nullable=False)
    user_id = Column(String, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    data = Column(JSONB, nullable=True)  # The actual change data
    extra_data = Column(JSONB, default={})  # Client info, conflict resolution, etc.
    
    # Foreign key relationships (nullable for flexibility)
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=True)
    page_id = Column(String, ForeignKey("pages.id"), nullable=True)
    block_id = Column(String, ForeignKey("blocks.id"), nullable=True)
    
    # Relationships
    workspace = relationship("WorkspaceDB", back_populates="changes")
    page = relationship("PageDB", back_populates="changes")
    block = relationship("BlockDB", back_populates="changes")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_changes_entity', 'entity', 'entity_id'),
        Index('idx_changes_timestamp', 'timestamp'),
        Index('idx_changes_user_timestamp', 'user_id', 'timestamp'),
    )

# Canvas-related models for data analysis functionality
class CanvasThreadDB(Base):
    __tablename__ = "canvas_threads"
    
    id = Column(String, primary_key=True)
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False)
    page_id = Column(String, ForeignKey("pages.id"), nullable=False)
    block_id = Column(String, ForeignKey("blocks.id"), nullable=False)
    name = Column(String, nullable=False)
    status = Column(String, default='idle')  # 'idle', 'running', 'completed', 'failed'
    query_text = Column(Text, nullable=True)
    complexity_level = Column(String, default='quick')  # 'quick', 'deep', 'custom'
    auto_generated_name = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    workspace = relationship("WorkspaceDB", back_populates="canvas_threads")
    page = relationship("PageDB", back_populates="canvas_threads")
    block = relationship("BlockDB", back_populates="canvas_thread")
    commits = relationship("AnalysisCommitDB", back_populates="thread", cascade="all, delete-orphan", order_by="AnalysisCommitDB.created_at")
    progress_logs = relationship("ProgressLogDB", back_populates="thread", cascade="all, delete-orphan", order_by="ProgressLogDB.timestamp")
    cache_entries = relationship("CanvasCacheDB", back_populates="thread", cascade="all, delete-orphan")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_canvas_threads_workspace_id', 'workspace_id'),
        Index('idx_canvas_threads_page_id', 'page_id'),
        Index('idx_canvas_threads_block_id', 'block_id'),
        Index('idx_canvas_threads_status', 'status'),
        Index('idx_canvas_threads_updated_at', 'updated_at'),
    )

class AnalysisCommitDB(Base):
    __tablename__ = "analysis_commits"
    
    id = Column(String, primary_key=True)
    thread_id = Column(String, ForeignKey("canvas_threads.id"), nullable=False)
    commit_message = Column(String, nullable=False)
    query_text = Column(Text, nullable=True)
    result_data = Column(JSONB, nullable=True)
    analysis_summary = Column(Text, nullable=True)
    preview_data = Column(JSONB, nullable=True)  # For thumbnail generation
    performance_metrics = Column(JSONB, nullable=True)  # Query time, row count, etc.
    parent_commit = Column(String, ForeignKey("analysis_commits.id"), nullable=True)
    is_head = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    thread = relationship("CanvasThreadDB", back_populates="commits")
    parent = relationship("AnalysisCommitDB", remote_side=[id], backref="children")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_analysis_commits_thread_id', 'thread_id'),
        Index('idx_analysis_commits_is_head', 'is_head'),
        Index('idx_analysis_commits_created_at', 'created_at'),
        Index('idx_analysis_commits_parent', 'parent_commit'),
    )

class ProgressLogDB(Base):
    __tablename__ = "progress_logs"
    
    id = Column(String, primary_key=True)
    thread_id = Column(String, ForeignKey("canvas_threads.id"), nullable=False)
    message = Column(Text, nullable=False)
    step_type = Column(String, nullable=True)  # 'query', 'processing', 'analysis', 'error'
    category = Column(String, default='user-friendly')  # 'technical', 'user-friendly', 'error'
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    thread = relationship("CanvasThreadDB", back_populates="progress_logs")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_progress_logs_thread_id', 'thread_id'),
        Index('idx_progress_logs_timestamp', 'timestamp'),
        Index('idx_progress_logs_step_type', 'step_type'),
        Index('idx_progress_logs_category', 'category'),
    )

class CanvasCacheDB(Base):
    __tablename__ = "canvas_cache"
    
    id = Column(String, primary_key=True)
    thread_id = Column(String, ForeignKey("canvas_threads.id"), nullable=False)
    cache_key = Column(String, nullable=False)
    cache_data = Column(LargeBinary, nullable=True)  # Cached thumbnail images
    cache_type = Column(String, nullable=True)  # 'thumbnail', 'preview_data'
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    thread = relationship("CanvasThreadDB", back_populates="cache_entries")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_canvas_cache_thread_id', 'thread_id'),
        Index('idx_canvas_cache_key', 'cache_key'),
        Index('idx_canvas_cache_type', 'cache_type'),
        Index('idx_canvas_cache_expires_at', 'expires_at'),
    )

# Create tables
Base.metadata.create_all(bind=engine)

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Pydantic models for API (unchanged)
class Block(BaseModel):
    id: str
    type: str
    content: str
    order: int = 0
    properties: Optional[Dict[str, Any]] = {}
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
    type: str
    entity: str
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

# Canvas-related Pydantic models for API
class ProgressLog(BaseModel):
    id: str
    threadId: str
    message: str
    stepType: Optional[str] = None
    category: str = 'user-friendly'
    timestamp: datetime

class AnalysisCommit(BaseModel):
    id: str
    threadId: str
    commitMessage: str
    queryText: Optional[str] = None
    resultData: Optional[Dict[str, Any]] = None
    analysisSummary: Optional[str] = None
    previewData: Optional[Dict[str, Any]] = None
    performanceMetrics: Optional[Dict[str, Any]] = None
    parentCommit: Optional[str] = None
    isHead: bool = False
    createdAt: datetime

class CanvasThread(BaseModel):
    id: str
    workspaceId: str
    pageId: str
    blockId: str
    name: str
    status: str = 'idle'
    queryText: Optional[str] = None
    complexityLevel: str = 'quick'
    autoGeneratedName: bool = True
    createdAt: datetime
    updatedAt: datetime
    # Related data
    commits: List[AnalysisCommit] = []
    progressLogs: List[ProgressLog] = []

class CanvasCache(BaseModel):
    id: str
    threadId: str
    cacheKey: str
    cacheType: Optional[str] = None
    expiresAt: Optional[datetime] = None
    createdAt: datetime

# Extended Block model to support canvas properties
class CanvasBlockProperties(BaseModel):
    threadId: Optional[str] = None
    isExpanded: bool = False
    previewData: Optional[Dict[str, Any]] = None
    currentCommit: Optional[str] = None
    status: str = 'idle'
    scrollPosition: Optional[int] = None
    viewState: Optional[Dict[str, Any]] = None

# API request/response models
class CreateCanvasRequest(BaseModel):
    blockId: str
    query: str
    complexityLevel: str = 'quick'

class UpdateCanvasRequest(BaseModel):
    threadId: str
    query: str
    commitMessage: Optional[str] = None

class CanvasQueryResponse(BaseModel):
    threadId: str
    commitId: str
    status: str
    message: str

# Helper functions to convert between DB and Pydantic models
def db_workspace_to_pydantic(db_workspace: WorkspaceDB) -> Workspace:
    """Convert SQLAlchemy workspace to Pydantic model"""
    pages = []
    for db_page in db_workspace.pages:
        blocks = []
        for db_block in db_page.blocks:
            block = Block(
                id=db_block.id,
                type=db_block.type,
                content=db_block.content,
                order=db_block.order,
                properties=db_block.properties or {},
                pageId=db_block.page_id,
                updatedAt=db_block.updated_at
            )
            blocks.append(block)
        
        page = Page(
            id=db_page.id,
            title=db_page.title,
            icon=db_page.icon,
            blocks=blocks,
            createdAt=db_page.created_at,
            updatedAt=db_page.updated_at
        )
        pages.append(page)
    
    return Workspace(
        id=db_workspace.id,
        name=db_workspace.name,
        pages=pages
    )

def pydantic_workspace_to_db(workspace: Workspace, db: Session) -> WorkspaceDB:
    """Convert Pydantic workspace to SQLAlchemy model"""
    # Get or create workspace
    db_workspace = db.query(WorkspaceDB).filter(WorkspaceDB.id == workspace.id).first()
    if not db_workspace:
        db_workspace = WorkspaceDB(
            id=workspace.id,
            name=workspace.name
        )
        db.add(db_workspace)
    else:
        db_workspace.name = workspace.name
        db_workspace.updated_at = datetime.utcnow()
    
    return db_workspace

@router.get("/workspaces/{workspace_id}", response_model=Workspace)
async def get_workspace(workspace_id: str, db: Session = Depends(get_db)):
    """Get workspace by ID"""
    db_workspace = db.query(WorkspaceDB).filter(WorkspaceDB.id == workspace_id).first()
    
    if not db_workspace:
        # Create default workspace
        db_workspace = WorkspaceDB(
            id=workspace_id,
            name="My Workspace"
        )
        db.add(db_workspace)
        db.commit()
        db.refresh(db_workspace)
    
    return db_workspace_to_pydantic(db_workspace)

@router.post("/workspaces/{workspace_id}", response_model=Workspace)
async def save_workspace(workspace_id: str, workspace: Workspace, db: Session = Depends(get_db)):
    """Save workspace"""
    db_workspace = pydantic_workspace_to_db(workspace, db)
    
    # Clear existing pages and blocks for this workspace to avoid duplicates
    existing_pages = db.query(PageDB).filter(PageDB.workspace_id == workspace_id).all()
    for page in existing_pages:
        db.delete(page)  # Cascade will delete blocks too
    
    # Add new pages and blocks
    for page_data in workspace.pages:
        db_page = PageDB(
            id=page_data.id,
            workspace_id=workspace_id,
            title=page_data.title,
            icon=page_data.icon,
            created_at=page_data.createdAt,
            updated_at=page_data.updatedAt
        )
        db.add(db_page)
        
        # Add blocks for this page
        for block_data in page_data.blocks:
            db_block = BlockDB(
                id=block_data.id,
                page_id=page_data.id,
                type=block_data.type,
                content=block_data.content,
                order=block_data.order,
                properties=block_data.properties or {}
            )
            db.add(db_block)
    
    db.commit()
    db.refresh(db_workspace)
    return db_workspace_to_pydantic(db_workspace)

@router.get("/pages/{page_id}", response_model=Page)
async def get_page(page_id: str, db: Session = Depends(get_db)):
    """Get page by ID"""
    db_page = db.query(PageDB).filter(PageDB.id == page_id).first()
    if not db_page:
        raise HTTPException(status_code=404, detail="Page not found")
    
    # Convert to Pydantic
    blocks = []
    for db_block in db_page.blocks:
        block = Block(
            id=db_block.id,
            type=db_block.type,
            content=db_block.content,
            order=db_block.order,
            properties=db_block.properties or {},
            pageId=db_block.page_id,
            updatedAt=db_block.updated_at
        )
        blocks.append(block)
    
    return Page(
        id=db_page.id,
        title=db_page.title,
        icon=db_page.icon,
        blocks=blocks,
        createdAt=db_page.created_at,
        updatedAt=db_page.updated_at
    )

@router.post("/pages", response_model=Page)
async def save_page(page: Page, db: Session = Depends(get_db)):
    """Save page"""
    # Get or create page
    db_page = db.query(PageDB).filter(PageDB.id == page.id).first()
    if not db_page:
        # Need to find workspace for this page (assuming main workspace for now)
        workspace_id = "main"  # You might want to pass this in the request
        db_page = PageDB(
            id=page.id,
            workspace_id=workspace_id,
            title=page.title,
            icon=page.icon,
            created_at=page.createdAt,
            updated_at=page.updatedAt
        )
        db.add(db_page)
    else:
        db_page.title = page.title
        db_page.icon = page.icon
        db_page.updated_at = page.updatedAt
    
    # Clear existing blocks and add new ones
    existing_blocks = db.query(BlockDB).filter(BlockDB.page_id == page.id).all()
    for block in existing_blocks:
        db.delete(block)
    
    # Add current blocks
    for block_data in page.blocks:
        db_block = BlockDB(
            id=block_data.id,
            page_id=page.id,
            type=block_data.type,
            content=block_data.content,
            order=block_data.order,
            properties=block_data.properties or {}
        )
        db.add(db_block)
    
    db.commit()
    db.refresh(db_page)
    
    # Return the saved page
    return await get_page(page.id, db)

@router.post("/blocks", response_model=Block)
async def save_block(block: Block, db: Session = Depends(get_db)):
    """Save block"""
    db_block = db.query(BlockDB).filter(BlockDB.id == block.id).first()
    
    if not db_block:
        db_block = BlockDB(
            id=block.id,
            page_id=block.pageId,
            type=block.type,
            content=block.content,
            order=block.order,
            properties=block.properties or {}
        )
        db.add(db_block)
    else:
        db_block.type = block.type
        db_block.content = block.content
        db_block.order = block.order
        db_block.properties = block.properties or {}
        db_block.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(db_block)
    
    return Block(
        id=db_block.id,
        type=db_block.type,
        content=db_block.content,
        order=db_block.order,
        properties=db_block.properties or {},
        pageId=db_block.page_id,
        updatedAt=db_block.updated_at
    )

@router.post("/sync", response_model=SyncResponse)
async def sync_changes(sync_request: SyncRequest, db: Session = Depends(get_db)):
    """Sync changes from client"""
    print(f"🔄 Received sync request with {len(sync_request.changes)} changes")
    
    # Process each change
    for change in sync_request.changes:
        print(f"📝 Processing change: {change.type} {change.entity} {change.entityId}")
        
        # Check if this change already exists to avoid duplicates
        existing_change = db.query(ChangeDB).filter(ChangeDB.id == change.id).first()
        if existing_change:
            print(f"⚠️  Change {change.id} already exists, skipping...")
            continue
        
        # Store the change for audit log
        try:
            # For deletion changes, don't store them in the database to avoid foreign key constraint violations
            # Just process the deletion directly
            if change.type == "delete":
                print(f"🗑️  Processing deletion directly without storing change record: {change.entity} {change.entityId}")
            else:
                # Store non-deletion changes normally
                db_change = ChangeDB(
                    id=change.id,
                    type=change.type,
                    entity=change.entity,
                    entity_id=change.entityId,
                    user_id=change.userId,
                    timestamp=change.timestamp,
                    data=change.data,
                    workspace_id="main" if change.entity == "workspace" else None,
                    page_id=change.entityId if change.entity == "page" else None,
                    block_id=change.entityId if change.entity == "block" else None
                )
                db.add(db_change)
            
            # Apply the change to storage
            if change.entity == "page":
                if change.type in ["create", "update"]:
                    db_page = db.query(PageDB).filter(PageDB.id == change.entityId).first()
                    if db_page:
                        # Update existing page
                        if 'title' in change.data:
                            db_page.title = change.data['title']
                        if 'icon' in change.data:
                            db_page.icon = change.data['icon']
                        db_page.updated_at = datetime.utcnow()
                    else:
                        # Create new page
                        db_page = PageDB(
                            id=change.entityId,
                            workspace_id="main",  # Default workspace
                            title=change.data.get('title', 'Untitled'),
                            icon=change.data.get('icon'),
                            created_at=change.data.get('createdAt', datetime.utcnow()),
                            updated_at=datetime.utcnow()
                        )
                        db.add(db_page)
                elif change.type == "delete":
                    db_page = db.query(PageDB).filter(PageDB.id == change.entityId).first()
                    if db_page:
                        db.delete(db_page)  # Cascade will delete blocks too
                        
            elif change.entity == "block":
                if change.type in ["create", "update"]:
                    db_block = db.query(BlockDB).filter(BlockDB.id == change.entityId).first()
                    if db_block:
                        # Update existing block
                        if 'content' in change.data:
                            db_block.content = change.data['content']
                        if 'type' in change.data:
                            db_block.type = change.data['type']
                        if 'order' in change.data:
                            db_block.order = change.data['order']
                        if 'properties' in change.data:
                            db_block.properties = change.data['properties']
                        db_block.updated_at = datetime.utcnow()
                    else:
                        # Create new block
                        db_block = BlockDB(
                            id=change.entityId,
                            page_id=change.data.get('pageId'),
                            type=change.data.get('type', 'text'),
                            content=change.data.get('content', ''),
                            order=change.data.get('order', 0),
                            properties=change.data.get('properties', {})
                        )
                        db.add(db_block)
                elif change.type == "delete":
                    print(f"🗑️  Deleting block: {change.entityId}")
                    db_block = db.query(BlockDB).filter(BlockDB.id == change.entityId).first()
                    if db_block:
                        print(f"✅ Found block to delete: {db_block.id}")
                        db.delete(db_block)
                        print(f"🗑️  Block {change.entityId} marked for deletion")
                    else:
                        print(f"❌ Block {change.entityId} not found in database")
                        
            elif change.entity == "workspace":
                if change.type in ["create", "update"]:
                    db_workspace = db.query(WorkspaceDB).filter(WorkspaceDB.id == change.entityId).first()
                    if db_workspace:
                        if 'name' in change.data:
                            db_workspace.name = change.data['name']
                        db_workspace.updated_at = datetime.utcnow()
                    else:
                        db_workspace = WorkspaceDB(
                            id=change.entityId,
                            name=change.data.get('name', 'My Workspace')
                        )
                        db.add(db_workspace)
                elif change.type == "delete":
                    db_workspace = db.query(WorkspaceDB).filter(WorkspaceDB.id == change.entityId).first()
                    if db_workspace:
                        db.delete(db_workspace)  # Cascade will delete pages and blocks
                        
        except Exception as e:
            print(f"Error processing change {change.id}: {str(e)}")
            # Continue with other changes even if one fails
            continue
    
    try:
        db.commit()
        print("✅ Successfully committed all changes")
    except Exception as e:
        print(f"❌ Error committing changes: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database commit failed: {str(e)}")
    
    # Return sync response
    return SyncResponse(
        changes=[],  # No server-side changes for now
        conflicts=[], # No conflicts for now
        lastSync=datetime.utcnow()
    )

@router.get("/storage/stats")
async def get_storage_stats(db: Session = Depends(get_db)):
    """Get storage statistics for debugging"""
    workspace_count = db.query(WorkspaceDB).count()
    page_count = db.query(PageDB).count()
    block_count = db.query(BlockDB).count()
    change_count = db.query(ChangeDB).count()
    
    return {
        "workspaces": workspace_count,
        "pages": page_count,
        "blocks": block_count,
        "changes": change_count
    }

@router.delete("/storage/reset")
async def reset_storage(db: Session = Depends(get_db)):
    """Reset all storage (for development)"""
    db.query(ChangeDB).delete()
    db.query(BlockDB).delete()
    db.query(PageDB).delete()
    db.query(WorkspaceDB).delete()
    db.commit()
    return {"message": "Storage reset successfully"}

@router.get("/storage/debug")
async def debug_storage(db: Session = Depends(get_db)):
    """Debug endpoint to see raw storage contents"""
    workspaces = db.query(WorkspaceDB).all()
    pages = db.query(PageDB).all()
    blocks = db.query(BlockDB).all()
    recent_changes = db.query(ChangeDB).order_by(ChangeDB.timestamp.desc()).limit(5).all()
    
    # Canvas stats for debugging
    canvas_threads = db.query(CanvasThreadDB).count()
    analysis_commits = db.query(AnalysisCommitDB).count()
    progress_logs = db.query(ProgressLogDB).count()
    
    return {
        "workspaces": [{"id": w.id, "name": w.name} for w in workspaces],
        "pages": [{"id": p.id, "title": p.title, "icon": p.icon} for p in pages],
        "blocks": [{"id": b.id, "type": b.type, "content": b.content[:50]} for b in blocks],
        "recent_changes": [{"id": c.id, "type": c.type, "entity": c.entity} for c in recent_changes],
        "canvas_system": {
            "threads": canvas_threads,
            "commits": analysis_commits,
            "progress_logs": progress_logs
        }
    } 
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
from fastapi.security import HTTPBearer
from fastapi import Request
import logging

router = APIRouter(prefix="/api", tags=["storage"])

# Set up logging
logger = logging.getLogger(__name__)

# Add security scheme
security = HTTPBearer(auto_error=False)

# Authentication dependency
async def get_current_user_from_request(request: Request) -> str:
    """
    Extract current user from session cookie or return development user
    
    In production, this would validate the session cookie.
    For now, we'll extract from cookie or default to dev user.
    """
    try:
        # Try to get session cookie
        session_cookie = request.cookies.get('ceneca_session')
        
        if session_cookie:
            # For immediate security, we'll use the session ID as user ID
            user_id = f"user_{hash(session_cookie) % 10000}"
            return user_id
        else:
            # Development fallback
            return "dev_user_12345"
            
    except Exception as e:
        # Fallback to development user
        return "dev_user_12345"

# Helper function to create user-specific workspace ID
def get_user_workspace_id(user_id: str, workspace_id: str = "main") -> str:
    """Create user-specific workspace ID to ensure isolation"""
    return f"{user_id}_{workspace_id}"

# Helper function to extract original workspace ID
def extract_workspace_id(user_workspace_id: str) -> str:
    """Extract original workspace ID from user-specific ID"""
    if "_" in user_workspace_id:
        return user_workspace_id.split("_", 1)[1]
    return user_workspace_id

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
    owner_id = Column(String, nullable=True)  # User ownership - nullable for migration
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
    owner_id = Column(String, nullable=True)  # User ownership - nullable for migration
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
    owner_id = Column(String, nullable=True)  # User ownership - nullable for migration
    type = Column(String, nullable=False)  # text, heading1, bullet, canvas, etc.
    content = Column(Text, nullable=False, default="")
    order = Column(Integer, nullable=False, default=0)
    indent_level = Column(Integer, nullable=False, default=0)  # For nested lists
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

class UserPreferencesDB(Base):
    __tablename__ = "user_preferences"
    
    user_id = Column(String, primary_key=True)  # User ID as primary key
    preferences = Column(JSONB, nullable=False, default={})  # Store all preferences as JSON
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_user_preferences_user_id', 'user_id'),
        Index('idx_user_preferences_updated_at', 'updated_at'),
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
    indentLevel: Optional[int] = 0  # For nested lists (0 = no indent, 1 = first level, etc.)
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

# Add after the existing Pydantic models (around line 400, after CanvasCache)

class UserPreferences(BaseModel):
    userId: str
    enableNotifications: bool = True
    autoSaveQueries: bool = True
    defaultAnalyzeMode: bool = False
    pollInterval: int = 30
    enableLiveUpdates: bool = True
    showAdvancedSettings: bool = False
    theme: str = 'system'  # 'light', 'dark', 'system'
    createdAt: datetime
    updatedAt: datetime

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
                indentLevel=db_block.indent_level,
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
async def get_workspace(
    workspace_id: str, 
    request: Request,
    db: Session = Depends(get_db)
):
    """Get workspace by ID - with user authentication using owner_id"""
    # Get current user
    current_user = await get_current_user_from_request(request)
    logger.info(f"🔐 get_workspace: user={current_user}, requested_workspace={workspace_id}")
    
    # Query workspace by ID and owner
    db_workspace = db.query(WorkspaceDB).filter(
        WorkspaceDB.id == workspace_id,
        WorkspaceDB.owner_id == current_user
    ).first()
    
    if not db_workspace:
        # Try legacy user-prefixed workspace ID for backward compatibility
        user_workspace_id = get_user_workspace_id(current_user, workspace_id)
        db_workspace = db.query(WorkspaceDB).filter(WorkspaceDB.id == user_workspace_id).first()
        
        if not db_workspace:
            # Create default workspace for this user with user-specific ID
            logger.info(f"🔐 Creating new workspace for user {current_user}: {user_workspace_id}")
            db_workspace = WorkspaceDB(
                id=user_workspace_id,  # Use user-specific ID to avoid conflicts
                owner_id=current_user,
                name="My Workspace"
            )
            db.add(db_workspace)
            db.commit()
            db.refresh(db_workspace)
        else:
            # Found legacy workspace, ensure it has owner_id set
            logger.info(f"🔄 Migrating legacy workspace {user_workspace_id} to new schema")
            if not db_workspace.owner_id:
                db_workspace.owner_id = current_user
                db.commit()
                db.refresh(db_workspace)
    
    logger.info(f"🔐 Returning workspace for user {current_user}: {len(db_workspace.pages)} pages")
    
    # Convert to Pydantic and return clean workspace_id to client
    response = db_workspace_to_pydantic(db_workspace)
    response.id = workspace_id  # Use original clean ID for client
    return response

@router.post("/workspaces/{workspace_id}", response_model=Workspace)
async def save_workspace(
    workspace_id: str, 
    workspace: Workspace, 
    request: Request,
    db: Session = Depends(get_db)
):
    """Save workspace - with user authentication"""
    # Get current user
    current_user = await get_current_user_from_request(request)
    logger.info(f"🔐 save_workspace: user={current_user}, workspace={workspace_id}")
    
    # Create user-specific workspace ID
    user_workspace_id = get_user_workspace_id(current_user, workspace_id)
    
    # Update workspace object to use user-specific ID internally
    workspace.id = user_workspace_id
    db_workspace = pydantic_workspace_to_db(workspace, db)
    
    # Clear existing pages and blocks for this user's workspace only
    existing_pages = db.query(PageDB).filter(PageDB.workspace_id == user_workspace_id).all()
    for page in existing_pages:
        db.delete(page)  # Cascade will delete blocks too
    
    # Add new pages and blocks
    for page_data in workspace.pages:
        db_page = PageDB(
            id=page_data.id,
            workspace_id=user_workspace_id,  # Use user-specific workspace ID
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
                indent_level=block_data.indentLevel or 0,
                properties=block_data.properties or {}
            )
            db.add(db_block)
    
    db.commit()
    db.refresh(db_workspace)
    
    # Return workspace with original ID for client
    response = db_workspace_to_pydantic(db_workspace)
    response.id = workspace_id
    logger.info(f"🔐 Saved workspace for user {current_user}: {len(response.pages)} pages")
    return response

@router.get("/pages/{page_id}", response_model=Page)
async def get_page(page_id: str, request: Request, db: Session = Depends(get_db)):
    """Get page by ID - with user authentication using owner_id"""
    # Get current user
    current_user = await get_current_user_from_request(request)
    logger.info(f"🔐 get_page: user={current_user}, page={page_id}")
    
    # Find page and verify ownership
    db_page = db.query(PageDB).filter(
        PageDB.id == page_id,
        PageDB.owner_id == current_user
    ).first()
    
    if not db_page:
        # Check legacy approach for backward compatibility
        db_page = db.query(PageDB).filter(PageDB.id == page_id).first()
        if db_page and db_page.workspace_id.startswith(current_user):
            # Migrate legacy page to new schema
            logger.info(f"🔄 Migrating legacy page {page_id} to use owner_id")
            db_page.owner_id = current_user
            db.commit()
            db.refresh(db_page)
        else:
            logger.warning(f"🔐 User {current_user} attempted to access page {page_id} - not found or not owned")
            raise HTTPException(status_code=404, detail="Page not found")
    
    # Convert to Pydantic
    blocks = []
    for db_block in db_page.blocks:
        block = Block(
            id=db_block.id,
            type=db_block.type,
            content=db_block.content,
            order=db_block.order,
            indentLevel=db_block.indent_level,
            properties=db_block.properties or {},
            pageId=db_block.page_id,
            updatedAt=db_block.updated_at
        )
        blocks.append(block)
    
    logger.info(f"🔐 Returning page for user {current_user}: {len(blocks)} blocks")
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
            indent_level=block_data.indentLevel or 0,
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
            indent_level=block.indentLevel or 0,
            properties=block.properties or {}
        )
        db.add(db_block)
    else:
        db_block.type = block.type
        db_block.content = block.content
        db_block.order = block.order
        db_block.indent_level = block.indentLevel or 0
        db_block.properties = block.properties or {}
        db_block.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(db_block)
    
    return Block(
        id=db_block.id,
        type=db_block.type,
        content=db_block.content,
        order=db_block.order,
        indentLevel=db_block.indent_level,
        properties=db_block.properties or {},
        pageId=db_block.page_id,
        updatedAt=db_block.updated_at
    )

@router.post("/sync", response_model=SyncResponse)
async def sync_changes(sync_request: SyncRequest, request: Request, db: Session = Depends(get_db)):
    """Sync changes from client - with user authentication"""
    # Get current user
    current_user = await get_current_user_from_request(request)
    logger.info(f"🔄 Received sync request from user {current_user} with {len(sync_request.changes)} changes")
    
    # Process each change
    for change in sync_request.changes:
        # Debug canvas-specific changes
        if change.entity == "block" and change.data and isinstance(change.data, dict):
            properties = change.data.get('properties', {})
            if properties.get('isCanvasPage') == True:
                print(f"🎨 CANVAS BLOCK DETECTED: {change.entityId}")
                print(f"🎨 Canvas properties keys: {list(properties.keys())}")
                if 'canvasData' in properties:
                    canvas_data = properties['canvasData']
                    print(f"🎨 Canvas data keys: {list(canvas_data.keys()) if isinstance(canvas_data, dict) else 'Not a dict'}")
        
        # Check if this change already exists to avoid duplicates
        existing_change = db.query(ChangeDB).filter(ChangeDB.id == change.id).first()
        if existing_change:
            continue
        
        # Store the change for audit log
        try:
            # Apply the change to storage FIRST, then optionally store the change record
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
                        # Create new page for this user
                        db_page = PageDB(
                            id=change.entityId,
                            workspace_id="main",  # Use clean workspace ID
                            owner_id=current_user,  # Set ownership properly
                            title=change.data.get('title', 'Untitled'),
                            icon=change.data.get('icon'),
                            created_at=change.data.get('createdAt', datetime.utcnow()),
                            updated_at=datetime.utcnow()
                        )
                        db.add(db_page)
                elif change.type == "delete":
                    print(f"🗑️  Deleting page: {change.entityId}")
                    db_page = db.query(PageDB).filter(PageDB.id == change.entityId).first()
                    if db_page:
                        print(f"✅ Found page to delete: {db_page.id}")
                        db.delete(db_page)  # Cascade will delete blocks too
                        print(f"🗑️  Page {change.entityId} marked for deletion")
                    else:
                        print(f"❌ Page {change.entityId} not found in database")
                        
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
                        if 'indentLevel' in change.data:
                            db_block.indent_level = change.data['indentLevel'] or 0
                        if 'properties' in change.data:
                            db_block.properties = change.data['properties']
                        db_block.updated_at = datetime.utcnow()
                    else:
                        # Create new block
                        db_block = BlockDB(
                            id=change.entityId,
                            page_id=change.data.get('pageId'),
                            owner_id=current_user,  # Set ownership properly
                            type=change.data.get('type', 'text'),
                            content=change.data.get('content', ''),
                            order=change.data.get('order', 0),
                            indent_level=change.data.get('indentLevel', 0),
                            properties=change.data.get('properties', {})
                        )
                        db.add(db_block)
                elif change.type == "delete":
                    print(f"🗑️  Deleting block: {change.entityId}")
                    
                    # First check if this is a canvas block with special cleanup needed
                    db_block = db.query(BlockDB).filter(BlockDB.id == change.entityId).first()
                    if db_block:
                        print(f"✅ Found block to delete: {db_block.id} (type: {db_block.type})")
                        
                        # Special handling for canvas blocks
                        if db_block.type == 'canvas':
                            print(f"🎨 Canvas block detected - performing cleanup")
                            
                            # Clean up any associated canvas threads
                            canvas_thread = db.query(CanvasThreadDB).filter(CanvasThreadDB.block_id == change.entityId).first()
                            if canvas_thread:
                                print(f"🧹 Cleaning up canvas thread: {canvas_thread.id}")
                                db.delete(canvas_thread)  # Cascade will handle commits, logs, cache
                        
                        # Delete the block
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
                    print(f"🗑️  Deleting workspace: {change.entityId}")
                    db_workspace = db.query(WorkspaceDB).filter(WorkspaceDB.id == change.entityId).first()
                    if db_workspace:
                        print(f"✅ Found workspace to delete: {db_workspace.id}")
                        db.delete(db_workspace)  # Cascade will delete pages and blocks
                        print(f"🗑️  Workspace {change.entityId} marked for deletion")
                    else:
                        print(f"❌ Workspace {change.entityId} not found in database")
            
            # Now store the change record for audit (except for deletions to avoid foreign key issues)
            if change.type != "delete":
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
            else:
                # For deletion changes, store a simplified record without foreign key references
                db_change = ChangeDB(
                    id=change.id,
                    type=change.type,
                    entity=change.entity,
                    entity_id=change.entityId,
                    user_id=change.userId,
                    timestamp=change.timestamp,
                    data={"deleted": True},  # Simple data for deleted entities
                    # No foreign key references for deleted entities
                    workspace_id=None,
                    page_id=None,
                    block_id=None
                )
                db.add(db_change)
                        
        except Exception as e:
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

@router.get("/storage/canvas-debug")
async def debug_canvas_storage(db: Session = Depends(get_db)):
    """Debug endpoint specifically for canvas blocks and their properties"""
    # Get all blocks with properties
    blocks_with_properties = db.query(BlockDB).filter(
        BlockDB.properties != None,
        BlockDB.properties != {}
    ).all()
    
    # Get all blocks for detailed inspection
    all_blocks = db.query(BlockDB).all()
    detailed_blocks = []
    
    for block in all_blocks:
        block_info = {
            "id": block.id,
            "page_id": block.page_id,
            "type": block.type,
            "content": block.content[:50],
            "order": block.order,
            "has_properties": block.properties is not None and block.properties != {},
            "raw_properties": block.properties,  # Show the full properties object
            "created_at": block.created_at.isoformat(),
            "updated_at": block.updated_at.isoformat()
        }
        
        # Analyze properties if they exist
        if block.properties and isinstance(block.properties, dict):
            block_info.update({
                "properties_keys": list(block.properties.keys()),
                "is_canvas_page": block.properties.get('isCanvasPage'),
                "has_canvas_data": 'canvasData' in block.properties,
                "canvas_data_keys": list(block.properties['canvasData'].keys()) if 'canvasData' in block.properties and isinstance(block.properties['canvasData'], dict) else []
            })
        
        detailed_blocks.append(block_info)
    
    # Get canvas-specific blocks
    canvas_blocks = []
    for block in blocks_with_properties:
        if block.properties and isinstance(block.properties, dict):
            if block.properties.get('isCanvasPage') == True:
                canvas_blocks.append({
                    "id": block.id,
                    "page_id": block.page_id,
                    "type": block.type,
                    "content": block.content[:100],
                    "properties_keys": list(block.properties.keys()),
                    "is_canvas_page": block.properties.get('isCanvasPage'),
                    "has_canvas_data": 'canvasData' in block.properties,
                    "canvas_data_keys": list(block.properties['canvasData'].keys()) if 'canvasData' in block.properties and isinstance(block.properties['canvasData'], dict) else [],
                    "created_at": block.created_at.isoformat(),
                    "updated_at": block.updated_at.isoformat()
                })
    
    # Get all pages that might contain canvas blocks
    pages_with_canvas = []
    for page in db.query(PageDB).all():
        page_canvas_blocks = [b for b in page.blocks if b.properties and b.properties.get('isCanvasPage') == True]
        if page_canvas_blocks:
            pages_with_canvas.append({
                "id": page.id,
                "title": page.title,
                "canvas_blocks_count": len(page_canvas_blocks),
                "canvas_block_ids": [b.id for b in page_canvas_blocks]
            })
    
    return {
        "summary": {
            "total_blocks": len(all_blocks),
            "blocks_with_properties": len(blocks_with_properties),
            "canvas_blocks_count": len(canvas_blocks),
            "pages_with_canvas": len(pages_with_canvas)
        },
        "all_blocks": detailed_blocks,
        "canvas_blocks": canvas_blocks,
        "pages_with_canvas": pages_with_canvas,
        "block_types_summary": {block.type: len([b for b in all_blocks if b.type == block.type]) for block in all_blocks}
    }

@router.get("/auth/status")
async def get_auth_status(request: Request):
    """Get current authentication status for debugging"""
    try:
        current_user = await get_current_user_from_request(request)
        session_cookie = request.cookies.get('ceneca_session')
        
        return {
            "authenticated": True,
            "user_id": current_user,
            "has_session_cookie": session_cookie is not None,
            "session_preview": session_cookie[:8] + "..." if session_cookie else None,
            "user_workspace_id": get_user_workspace_id(current_user, "main"),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {
            "authenticated": False,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

@router.get("/users/preferences", response_model=UserPreferences)
async def get_user_preferences(
    request: Request,
    db: Session = Depends(get_db)
):
    """Get user preferences"""
    current_user = await get_current_user_from_request(request)
    logger.info(f"🔐 get_user_preferences: user={current_user}")
    
    # Get user preferences from database
    db_prefs = db.query(UserPreferencesDB).filter(UserPreferencesDB.user_id == current_user).first()
    
    if not db_prefs:
        # Create default preferences for new user
        default_prefs = {
            "enableNotifications": True,
            "autoSaveQueries": True,
            "defaultAnalyzeMode": False,
            "pollInterval": 30,
            "enableLiveUpdates": True,
            "showAdvancedSettings": False,
            "theme": "system"
        }
        
        db_prefs = UserPreferencesDB(
            user_id=current_user,
            preferences=default_prefs
        )
        db.add(db_prefs)
        db.commit()
        db.refresh(db_prefs)
        logger.info(f"🔐 Created default preferences for user {current_user}")
    
    # Convert to Pydantic model
    prefs_data = db_prefs.preferences
    return UserPreferences(
        userId=current_user,
        enableNotifications=prefs_data.get("enableNotifications", True),
        autoSaveQueries=prefs_data.get("autoSaveQueries", True),
        defaultAnalyzeMode=prefs_data.get("defaultAnalyzeMode", False),
        pollInterval=prefs_data.get("pollInterval", 30),
        enableLiveUpdates=prefs_data.get("enableLiveUpdates", True),
        showAdvancedSettings=prefs_data.get("showAdvancedSettings", False),
        theme=prefs_data.get("theme", "system"),
        createdAt=db_prefs.created_at,
        updatedAt=db_prefs.updated_at
    )

@router.post("/users/preferences", response_model=UserPreferences)
async def save_user_preferences(
    preferences: UserPreferences,
    request: Request,
    db: Session = Depends(get_db)
):
    """Save user preferences"""
    current_user = await get_current_user_from_request(request)
    logger.info(f"🔐 save_user_preferences: user={current_user}")
    
    # Get or create user preferences
    db_prefs = db.query(UserPreferencesDB).filter(UserPreferencesDB.user_id == current_user).first()
    
    # Convert Pydantic model to dict for storage
    prefs_dict = {
        "enableNotifications": preferences.enableNotifications,
        "autoSaveQueries": preferences.autoSaveQueries,
        "defaultAnalyzeMode": preferences.defaultAnalyzeMode,
        "pollInterval": preferences.pollInterval,
        "enableLiveUpdates": preferences.enableLiveUpdates,
        "showAdvancedSettings": preferences.showAdvancedSettings,
        "theme": preferences.theme
    }
    
    if not db_prefs:
        # Create new preferences
        db_prefs = UserPreferencesDB(
            user_id=current_user,
            preferences=prefs_dict
        )
        db.add(db_prefs)
        logger.info(f"🔐 Created new preferences for user {current_user}")
    else:
        # Update existing preferences
        db_prefs.preferences = prefs_dict
        db_prefs.updated_at = datetime.utcnow()
        logger.info(f"🔐 Updated preferences for user {current_user}")
    
    db.commit()
    db.refresh(db_prefs)
    
    # Return updated preferences
    return UserPreferences(
        userId=current_user,
        enableNotifications=prefs_dict["enableNotifications"],
        autoSaveQueries=prefs_dict["autoSaveQueries"],
        defaultAnalyzeMode=prefs_dict["defaultAnalyzeMode"],
        pollInterval=prefs_dict["pollInterval"],
        enableLiveUpdates=prefs_dict["enableLiveUpdates"],
        showAdvancedSettings=prefs_dict["showAdvancedSettings"],
        theme=prefs_dict["theme"],
        createdAt=db_prefs.created_at,
        updatedAt=db_prefs.updated_at
    )

@router.patch("/users/preferences")
async def update_user_preference(
    preference_key: str,
    preference_value: Any,
    request: Request,
    db: Session = Depends(get_db)
):
    """Update a single user preference"""
    current_user = await get_current_user_from_request(request)
    logger.info(f"🔐 update_user_preference: user={current_user}, key={preference_key}, value={preference_value}")
    
    # Get user preferences
    db_prefs = db.query(UserPreferencesDB).filter(UserPreferencesDB.user_id == current_user).first()
    
    if not db_prefs:
        # Create with default preferences
        default_prefs = {
            "enableNotifications": True,
            "autoSaveQueries": True,
            "defaultAnalyzeMode": False,
            "pollInterval": 30,
            "enableLiveUpdates": True,
            "showAdvancedSettings": False,
            "theme": "system"
        }
        db_prefs = UserPreferencesDB(
            user_id=current_user,
            preferences=default_prefs
        )
        db.add(db_prefs)
    
    # Update the specific preference
    current_prefs = db_prefs.preferences.copy()
    current_prefs[preference_key] = preference_value
    db_prefs.preferences = current_prefs
    db_prefs.updated_at = datetime.utcnow()
    
    db.commit()
    
    return {
        "success": True,
        "message": f"Updated {preference_key} preference",
        "updated_preference": {preference_key: preference_value}
    } 
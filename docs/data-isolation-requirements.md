# Data Isolation Requirements

## Current State
- Authentication works and saves user data in sessions
- NO data isolation - all users see the same workspace/pages/blocks
- Security vulnerability: any authenticated user can access any data

## Required Changes

### 1. Database Schema Updates

```python
# Add user ownership to core models
class WorkspaceDB(Base):
    __tablename__ = "workspaces"
    
    id = Column(String, primary_key=True)
    owner_id = Column(String, nullable=False)  # ADD THIS
    name = Column(String, nullable=False)
    # ... rest of fields

class PageDB(Base):
    __tablename__ = "pages"
    
    id = Column(String, primary_key=True)
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False)
    owner_id = Column(String, nullable=False)  # ADD THIS
    # ... rest of fields

class BlockDB(Base):
    __tablename__ = "blocks"
    
    id = Column(String, primary_key=True)
    page_id = Column(String, ForeignKey("pages.id"), nullable=False)
    owner_id = Column(String, nullable=False)  # ADD THIS
    # ... rest of fields
```

### 2. API Endpoint Security

```python
@router.get("/workspaces/{workspace_id}", response_model=Workspace)
async def get_workspace(
    workspace_id: str, 
    db: Session = Depends(get_db),
    current_user: SessionData = Depends(get_current_user)  # ADD AUTH
):
    # Filter by user ownership
    db_workspace = db.query(WorkspaceDB).filter(
        WorkspaceDB.id == workspace_id,
        WorkspaceDB.owner_id == current_user.user_id  # ADD FILTER
    ).first()
    
    if not db_workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
```

### 3. User-Specific Workspace Creation

```python
@router.post("/workspaces", response_model=Workspace)
async def create_user_workspace(
    workspace: CreateWorkspaceRequest,
    db: Session = Depends(get_db),
    current_user: SessionData = Depends(get_current_user)
):
    # Create workspace owned by current user
    db_workspace = WorkspaceDB(
        id=workspace.id or str(uuid.uuid4()),
        owner_id=current_user.user_id,  # Set ownership
        name=workspace.name
    )
    db.add(db_workspace)
    db.commit()
```

### 4. Migration Strategy

1. Add `owner_id` columns to existing tables
2. Create migration script to assign existing data to a default user
3. Update all API endpoints to filter by user
4. Add user authentication middleware to all routes

### 5. Sharing/Collaboration (Future)

For team workspaces, consider adding:
- `WorkspacePermissionDB` table for sharing
- Role-based access (owner, editor, viewer)
- Team/organization models

## Security Benefits

- ✅ Users only see their own workspaces/pages
- ✅ Prevent unauthorized data access
- ✅ Audit trail with proper user attribution
- ✅ Foundation for future collaboration features

## Implementation Priority

1. **High**: Add authentication middleware to all routes
2. **High**: Add user filtering to get/list endpoints  
3. **Medium**: Update database schema with migrations
4. **Medium**: Update frontend to handle user-specific data
5. **Low**: Add sharing/collaboration features 
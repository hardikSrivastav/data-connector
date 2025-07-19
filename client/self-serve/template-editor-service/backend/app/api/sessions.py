from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import uuid

from app.database.database import get_db, Session as SessionModel, EditHistory
from app.models.schemas import SessionCreate, SessionResponse, EditHistoryResponse, WorkspaceResponse
from app.services.workspace_manager import WorkspaceManager
from app.services.template_manager import TemplateManager

router = APIRouter()

@router.post("/", response_model=SessionResponse)
async def create_session(
    session_data: SessionCreate,
    db: Session = Depends(get_db)
):
    """Create a new editing session with isolated workspace"""
    try:
        # Generate session ID
        session_id = str(uuid.uuid4())
        
        # Get template manager
        template_manager = TemplateManager()
        template_info = template_manager.get_template_info(session_data.template_version)
        
        if not template_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Template version {session_data.template_version} not found"
            )
        
        # Create workspace
        workspace_manager = WorkspaceManager()
        await workspace_manager.create_workspace(session_id, session_data.template_version)
        
        # Create session in database
        db_session = SessionModel(
            id=session_id,
            user_id=session_data.user_id,
            template_version=session_data.template_version,
            template_hash=template_info["hash"],
            status="active",
            session_metadata=session_data.project_context or {}
        )
        
        db.add(db_session)
        db.commit()
        db.refresh(db_session)
        
        return SessionResponse(
            id=db_session.id,
            user_id=db_session.user_id,
            template_version=db_session.template_version,
            template_hash=db_session.template_hash,
            status=db_session.status,
            metadata=db_session.session_metadata,
            created_at=db_session.created_at,
            updated_at=db_session.updated_at
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create session: {str(e)}"
        )

@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str, db: Session = Depends(get_db)):
    """Get session details"""
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    return SessionResponse(
        id=session.id,
        user_id=session.user_id,
        template_version=session.template_version,
        template_hash=session.template_hash,
        status=session.status,
        metadata=session.session_metadata,
        created_at=session.created_at,
        updated_at=session.updated_at
    )

@router.get("/{session_id}/workspace", response_model=WorkspaceResponse)
async def get_workspace(session_id: str, db: Session = Depends(get_db)):
    """Get workspace files and metadata"""
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    workspace_manager = WorkspaceManager()
    workspace_data = await workspace_manager.get_workspace_files(session_id)
    
    return WorkspaceResponse(
        session_id=session_id,
        files=workspace_data["files"],
        metadata=workspace_data["metadata"]
    )

@router.get("/{session_id}/history", response_model=List[EditHistoryResponse])
async def get_edit_history(session_id: str, db: Session = Depends(get_db)):
    """Get edit history for a session"""
    history = db.query(EditHistory).filter(
        EditHistory.session_id == session_id
    ).order_by(EditHistory.timestamp.desc()).all()
    
    return [
        EditHistoryResponse(
            id=edit.id,
            session_id=edit.session_id,
            file_path=edit.file_path,
            placeholder=edit.placeholder,
            old_value=edit.old_value,
            new_value=edit.new_value,
            timestamp=edit.timestamp
        )
        for edit in history
    ]

@router.delete("/{session_id}")
async def delete_session(session_id: str, db: Session = Depends(get_db)):
    """Delete session and clean up workspace"""
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    try:
        # Clean up workspace
        workspace_manager = WorkspaceManager()
        await workspace_manager.cleanup_workspace(session_id)
        
        # Delete from database
        db.delete(session)
        db.commit()
        
        return {"message": "Session deleted successfully"}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete session: {str(e)}"
        )
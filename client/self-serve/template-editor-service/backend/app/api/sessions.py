from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import uuid

from app.database.database import get_db, Session as SessionModel, EditHistory
from app.models.schemas import SessionCreate, SessionResponse, EditHistoryResponse, WorkspaceResponse, SessionTemplateResponse
from app.services.workspace_manager import WorkspaceManager
from app.services.template_manager import TemplateManager
from app.services.scenario_manager import ScenarioManager

router = APIRouter()

@router.post("/", response_model=SessionResponse)
async def create_session(
    session_data: SessionCreate,
    db: Session = Depends(get_db)
):
    """Create a new editing session with isolated workspace - supports both scenarios and individual templates"""
    try:
        # Generate session ID
        session_id = str(uuid.uuid4())
        
        template_manager = TemplateManager()
        scenario_manager = ScenarioManager()
        workspace_manager = WorkspaceManager()
        
        # Handle scenario-based session
        if session_data.scenario_id:
            scenario = scenario_manager.get_scenario_by_id(session_data.scenario_id)
            if not scenario:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Deployment scenario {session_data.scenario_id} not found"
                )
            
            # Create multi-template workspace
            await workspace_manager.create_scenario_workspace(
                session_id, 
                session_data.scenario_id,
                scenario["template_versions"],
                session_data.variables or {}
            )
            
            # Create session in database (store scenario info in metadata for backwards compatibility)
            db_session = SessionModel(
                id=session_id,
                user_id=session_data.user_id,
                template_version=f"scenario:{session_data.scenario_id}",  # Backwards compatibility
                template_hash="scenario-hash",  # Backwards compatibility
                status="active",
                session_metadata={
                    "type": "scenario",
                    "scenario_id": session_data.scenario_id,
                    "scenario_name": scenario["name"],
                    "template_count": len(scenario["template_versions"]),
                    "variables": session_data.variables or {},
                    **(session_data.project_context or {})
                }
            )
            
            # Store template information in session metadata
            template_info_list = []
            for template_version in scenario["template_versions"]:
                template_info = template_manager.get_template_info(template_version)
                if template_info:
                    template_info_list.append({
                        "template_version": template_version,
                        "template_hash": template_info["hash"],
                        "template_name": template_info["name"],
                        "category": template_info.get("category"),
                        "format": template_info.get("format")
                    })
            
            # Update session metadata with template information
            session_metadata = db_session.session_metadata.copy()
            session_metadata["templates"] = template_info_list
            db_session.session_metadata = session_metadata
            
            db.add(db_session)
            
            db.commit()
            db.refresh(db_session)
            
            return SessionResponse(
                id=db_session.id,
                user_id=db_session.user_id,
                scenario_id=session_data.scenario_id,
                template_version=db_session.template_version,
                template_hash=db_session.template_hash,
                status=db_session.status,
                metadata=db_session.session_metadata,
                created_at=db_session.created_at,
                updated_at=db_session.updated_at
            )
            
        # Handle single template session (backwards compatibility)
        elif session_data.template_version:
            template_info = template_manager.get_template_info(session_data.template_version)
            
            if not template_info:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Template version {session_data.template_version} not found"
                )
            
            # Create single-template workspace
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
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either scenario_id or template_version must be provided"
            )
        
    except HTTPException:
        db.rollback()
        raise
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
    
    # Extract scenario_id from metadata if it's a scenario session
    scenario_id = None
    if session.session_metadata and session.session_metadata.get("type") == "scenario":
        scenario_id = session.session_metadata.get("scenario_id")
    
    return SessionResponse(
        id=session.id,
        user_id=session.user_id,
        scenario_id=scenario_id,
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

@router.get("/{session_id}/templates", response_model=List[SessionTemplateResponse])
async def get_session_templates(session_id: str, db: Session = Depends(get_db)):
    """Get all templates associated with a session (for scenario-based sessions)"""
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    # For scenario-based sessions, return templates from metadata
    if session.session_metadata and session.session_metadata.get("type") == "scenario":
        templates = session.session_metadata.get("templates", [])
        
        return [
            SessionTemplateResponse(
                id=idx,
                session_id=session_id,
                template_version=template["template_version"],
                template_hash=template["template_hash"],
                status="active",
                variables=session.session_metadata.get("variables", {}),
                created_at=session.created_at
            )
            for idx, template in enumerate(templates)
        ]
    
    # For single-template sessions, return the main template
    elif session.template_version:
        return [
            SessionTemplateResponse(
                id=0,  # Legacy sessions don't have session_template records
                session_id=session_id,
                template_version=session.template_version,
                template_hash=session.template_hash,
                status=session.status,
                variables={},
                created_at=session.created_at
            )
        ]
    
    return []
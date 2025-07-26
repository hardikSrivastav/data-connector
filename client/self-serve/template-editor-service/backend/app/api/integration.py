from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
import uuid
import os
import requests
from typing import Dict, Any

from app.database.database import get_db, Session
from app.models.schemas import (
    SessionHandoffRequest, 
    SessionHandoffResponse, 
    SessionCreate,
    SessionResponse,
    DeploymentCompleteNotification
)
from app.services.workspace_manager import WorkspaceManager
from app.services.scenario_manager import ScenarioManager

router = APIRouter()

@router.post("/handoff", response_model=SessionHandoffResponse)
async def create_session_handoff(
    request: SessionHandoffRequest,
    db: Session = Depends(get_db)
):
    """Create a session for main app integration and return editor URL"""
    try:
        # Map deployment type to scenario
        scenario_mapping = {
            "basic": "ceneca-basic-deployment",
            "enterprise": "ceneca-enterprise-deployment", 
            "custom": None  # Let user choose
        }
        
        scenario_id = scenario_mapping.get(request.deployment_type)
        
        # Create session data
        session_data = SessionCreate(
            user_id=request.user_id,
            scenario_id=scenario_id,
            project_context=request.context,
            variables=request.requirements,
            callback_url=request.callback_url
        )
        
        # Generate session ID
        session_id = str(uuid.uuid4())
        
        # Initialize managers
        workspace_manager = WorkspaceManager()
        scenario_manager = ScenarioManager()
        
        # Create workspace based on deployment type
        if scenario_id:
            scenario = scenario_manager.get_scenario_by_id(scenario_id)
            if scenario:
                await workspace_manager.create_scenario_workspace(
                    session_id, 
                    scenario_id,
                    scenario["template_versions"],
                    request.requirements
                )
            else:
                # Fallback to basic template
                await workspace_manager.create_workspace(session_id, "ceneca-config-v1.0.0")
        else:
            # Custom deployment - let user choose in editor
            await workspace_manager.create_workspace(session_id, "ceneca-config-v1.0.0")
        
        # Store session in database
        db_session = Session(
            id=session_id,
            user_id=request.user_id,
            template_version=scenario_id or "custom",
            template_hash="integration-session",
            status="active",
            session_metadata={
                "type": "integration",
                "deployment_type": request.deployment_type,
                "callback_url": request.callback_url,
                "requirements": request.requirements,
                "context": request.context or {}
            }
        )
        
        db.add(db_session)
        db.commit()
        db.refresh(db_session)
        
        # Generate editor URL (will be subdomain in production)
        base_url = os.getenv("TEMPLATE_EDITOR_BASE_URL", "http://localhost:8500")
        editor_url = f"{base_url}?session_id={session_id}&integration=true"
        
        return SessionHandoffResponse(
            session_id=session_id,
            editor_url=editor_url,
            success=True,
            message="Session created successfully"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create integration session: {str(e)}"
        )

@router.post("/complete/{session_id}")
async def mark_deployment_complete(
    session_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Mark deployment as complete and notify main app"""
    session = db.query(Session).filter(Session.id == session_id).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    # Update session status
    session.status = "completed"
    db.commit()
    
    # Prepare callback data
    workspace_manager = WorkspaceManager()
    workspace_data = await workspace_manager.get_workspace_files(session_id)
    
    callback_data = DeploymentCompleteNotification(
        session_id=session_id,
        user_id=session.user_id,
        status="completed",
        generated_files=workspace_data["files"],
        metadata=session.session_metadata,
        download_url=f"{os.getenv('TEMPLATE_EDITOR_BASE_URL', 'http://localhost:8501')}/api/sessions/{session_id}/download"
    )
    
    # Send callback to main app in background
    if session.session_metadata and session.session_metadata.get("callback_url"):
        background_tasks.add_task(
            send_completion_callback,
            session.session_metadata["callback_url"],
            callback_data.dict()
        )
    
    return {"message": "Deployment marked as complete", "session_id": session_id}

async def send_completion_callback(callback_url: str, data: Dict[str, Any]):
    """Send deployment completion notification to main app"""
    try:
        response = requests.post(
            callback_url,
            json=data,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        response.raise_for_status()
        print(f"Successfully sent callback to {callback_url}")
    except Exception as e:
        print(f"Failed to send callback to {callback_url}: {e}")
        # Could implement retry logic here

@router.get("/status/{session_id}")
async def get_integration_status(
    session_id: str,
    db: Session = Depends(get_db)
):
    """Get integration session status for main app polling"""
    session = db.query(Session).filter(Session.id == session_id).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    return {
        "session_id": session_id,
        "user_id": session.user_id,
        "status": session.status,
        "deployment_type": session.session_metadata.get("deployment_type"),
        "created_at": session.created_at,
        "updated_at": session.updated_at
    }
from fastapi import APIRouter, HTTPException, status
from typing import List

from app.models.schemas import TemplateVersionResponse
from app.services.template_manager import TemplateManager

router = APIRouter()

@router.get("/", response_model=List[TemplateVersionResponse])
async def list_templates():
    """List all available template versions"""
    template_manager = TemplateManager()
    templates = template_manager.list_templates()
    
    return [
        TemplateVersionResponse(
            version=template["version"],
            name=template["name"],
            description=template.get("description"),
            hash=template["hash"],
            schema=template.get("schema"),
            created_at=template["created_at"]
        )
        for template in templates
    ]

@router.get("/{version}", response_model=TemplateVersionResponse)
async def get_template(version: str):
    """Get specific template version details"""
    template_manager = TemplateManager()
    template = template_manager.get_template_info(version)
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template version {version} not found"
        )
    
    return TemplateVersionResponse(
        version=template["version"],
        name=template["name"],
        description=template.get("description"),
        hash=template["hash"],
        schema=template.get("schema"),
        created_at=template["created_at"]
    )

@router.get("/{version}/files")
async def get_template_files(version: str):
    """Get template files content (read-only)"""
    template_manager = TemplateManager()
    files = template_manager.get_template_files(version)
    
    if not files:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template version {version} not found"
        )
    
    return {
        "version": version,
        "files": files
    }
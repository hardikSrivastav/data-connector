from fastapi import APIRouter, HTTPException, status, Query
from typing import List, Optional
from pydantic import BaseModel

from app.models.schemas import (
    TemplateVersionResponse, 
    TemplateValidationRequest, 
    TemplateValidationResponse,
    TemplateCategoriesResponse,
    TemplateSchemaResponse
)
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
            created_at=template["created_at"],
            category=template.get("category"),
            format=template.get("format")
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

@router.get("/categories", response_model=TemplateCategoriesResponse)
async def get_template_categories():
    """Get list of all template categories"""
    template_manager = TemplateManager()
    categories = template_manager.get_template_categories()
    
    return TemplateCategoriesResponse(categories=categories)

@router.get("/by-category", response_model=List[TemplateVersionResponse])
async def list_templates_by_category(category: Optional[str] = Query(None, description="Filter templates by category")):
    """List templates filtered by category"""
    template_manager = TemplateManager()
    templates = template_manager.list_templates_by_category(category)
    
    return [
        TemplateVersionResponse(
            version=template["version"],
            name=template["name"],
            description=template.get("description"),
            hash=template["hash"],
            schema=template.get("schema"),
            created_at=template["created_at"],
            category=template.get("category"),
            format=template.get("format")
        )
        for template in templates
    ]

@router.post("/validate", response_model=TemplateValidationResponse)
async def validate_template_syntax(request: TemplateValidationRequest):
    """Validate template syntax based on format type"""
    template_manager = TemplateManager()
    result = template_manager.validate_template_syntax(request.content, request.format_type)
    
    return TemplateValidationResponse(**result)

@router.get("/{version}/schema", response_model=TemplateSchemaResponse)
async def get_template_schema(version: str):
    """Get template validation schema"""
    template_manager = TemplateManager()
    schema = template_manager.get_template_schema(version)
    
    if not schema:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schema for template version {version} not found"
        )
    
    return TemplateSchemaResponse(version=version, schema=schema)
from fastapi import APIRouter, HTTPException, status
from typing import List, Optional
from app.models.schemas import (
    DeploymentScenario,
    ScenarioValidationRequest,
    ScenarioValidationResponse,
    TemplateSchemaResponse
)
from app.services.scenario_manager import ScenarioManager

router = APIRouter()

@router.get("/", response_model=List[DeploymentScenario])
async def list_scenarios():
    """List all available deployment scenarios"""
    scenario_manager = ScenarioManager()
    scenarios = scenario_manager.get_scenarios()
    
    return [
        DeploymentScenario(**scenario)
        for scenario in scenarios
    ]

@router.get("/categories")
async def get_scenario_categories():
    """Get list of all scenario categories"""
    scenario_manager = ScenarioManager()
    categories = scenario_manager.get_scenario_categories()
    
    return {"categories": categories}

@router.get("/by-category", response_model=List[DeploymentScenario])
async def list_scenarios_by_category(category: Optional[str] = None):
    """List scenarios filtered by category"""
    scenario_manager = ScenarioManager()
    
    if category:
        scenarios = scenario_manager.get_scenarios_by_category(category)
    else:
        scenarios = scenario_manager.get_scenarios()
    
    return [
        DeploymentScenario(**scenario)
        for scenario in scenarios
    ]

@router.get("/{scenario_id}", response_model=DeploymentScenario)
async def get_scenario(scenario_id: str):
    """Get specific deployment scenario details"""
    scenario_manager = ScenarioManager()
    scenario = scenario_manager.get_scenario_by_id(scenario_id)
    
    if not scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deployment scenario {scenario_id} not found"
        )
    
    return DeploymentScenario(**scenario)

@router.get("/{scenario_id}/schema", response_model=TemplateSchemaResponse)
async def get_scenario_schema(scenario_id: str):
    """Get combined variable schema for all templates in a scenario"""
    scenario_manager = ScenarioManager()
    schema = scenario_manager.get_scenario_variable_schema(scenario_id)
    
    if not schema:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schema for scenario {scenario_id} not found"
        )
    
    return TemplateSchemaResponse(version=scenario_id, template_schema=schema)

@router.post("/validate", response_model=ScenarioValidationResponse)
async def validate_scenario(request: ScenarioValidationRequest):
    """Validate scenario variables and dependencies"""
    scenario_manager = ScenarioManager()
    result = scenario_manager.validate_scenario_dependencies(
        request.scenario_id, 
        request.variables
    )
    
    return ScenarioValidationResponse(**result)
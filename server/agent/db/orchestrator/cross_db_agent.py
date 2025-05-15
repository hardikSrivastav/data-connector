"""
Cross-Database Agent

This module provides a unified interface for the cross-database orchestration system,
integrating the planning and implementation agents.
"""

import logging
import asyncio
from typing import Dict, List, Any, Optional

from .planning_agent import PlanningAgent
from .implementation_agent import ImplementationAgent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CrossDatabaseAgent:
    """
    Unified agent for cross-database orchestration.
    
    This agent combines the planning and implementation agents to provide
    a complete solution for cross-database queries.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the cross-database agent.
        
        Args:
            config: Optional configuration dictionary with settings for both
                   planning and implementation agents
        """
        self.config = config or {}
        
        # Create planning and implementation agents
        planning_config = self.config.get("planning", {})
        implementation_config = self.config.get("implementation", {})
        
        self.planning_agent = PlanningAgent(planning_config)
        self.implementation_agent = ImplementationAgent(implementation_config)
    
    async def execute_query(
        self, 
        question: str,
        optimize_plan: bool = False,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Execute a cross-database query from a natural language question.
        
        This method handles the end-to-end process of:
        1. Planning: Analyzing the question and creating a query plan
        2. Implementation: Executing the plan and aggregating results
        
        Args:
            question: Natural language question from the user
            optimize_plan: Whether to optimize the plan before execution
            dry_run: Whether to perform a dry run without actual execution
            
        Returns:
            Query results with execution details
        """
        logger.info(f"Processing cross-database query: {question}")
        
        # Step 1: Generate a query plan
        query_plan, validation_result = await self.planning_agent.create_plan(
            question, optimize=optimize_plan
        )
        
        # Check if plan is valid
        if not validation_result.get("valid", False):
            logger.warning(f"Query plan validation failed: {validation_result.get('errors', [])}")
            return {
                "success": False,
                "error": "Failed to create a valid query plan",
                "validation_errors": validation_result.get("errors", []),
                "query_plan": query_plan.to_dict() if hasattr(query_plan, "to_dict") else query_plan
            }
        
        # Step 2: Execute the plan
        if dry_run:
            logger.info("Performing dry run (validation only)")
            execution_result = {
                "success": True,
                "dry_run": True,
                "message": "Plan validation successful",
                "query_plan": query_plan.to_dict() if hasattr(query_plan, "to_dict") else query_plan
            }
        else:
            logger.info("Executing query plan")
            execution_result = await self.implementation_agent.execute_plan(
                query_plan, question, dry_run=False
            )
        
        # Return combined results
        return {
            "question": question,
            "plan": query_plan.to_dict() if hasattr(query_plan, "to_dict") else query_plan,
            "validation": validation_result,
            "execution": execution_result
        }
    
    async def close(self):
        """Close all connections and clean up resources"""
        await self.implementation_agent.close() 
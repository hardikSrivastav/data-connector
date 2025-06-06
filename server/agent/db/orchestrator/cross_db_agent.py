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

# Set up dedicated logging for cross-database execution
def setup_cross_db_logger():
    """Set up a dedicated logger for cross-database execution with file output"""
    cross_db_logger = logging.getLogger('cross_db_execution')
    cross_db_logger.setLevel(logging.INFO)
    
    # Remove any existing handlers to avoid duplicates
    cross_db_logger.handlers.clear()
    
    # Create file handler for cross-database logs
    file_handler = logging.FileHandler('cross_db_execution.log', mode='a')  # Append mode
    file_handler.setLevel(logging.INFO)
    
    # Create console handler as well
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # Add handlers to logger
    cross_db_logger.addHandler(file_handler)
    cross_db_logger.addHandler(console_handler)
    
    # Prevent propagation to root logger to avoid SQLAlchemy noise
    cross_db_logger.propagate = False
    
    return cross_db_logger

# Get or create the dedicated logger
cross_db_logger = setup_cross_db_logger()

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
        cross_db_logger.info(f"🎯 CrossDatabaseAgent.execute_query called")
        cross_db_logger.info(f"🎯 Question: '{question}'")
        cross_db_logger.info(f"🎯 Parameters: optimize_plan={optimize_plan}, dry_run={dry_run}")
        
        try:
            # Step 1: Generate a query plan
            cross_db_logger.info(f"📋 Step 1: Generating query plan using planning_agent")
            query_plan, validation_result = await self.planning_agent.create_plan(
                question, optimize=optimize_plan
            )
            
            cross_db_logger.info(f"📋 Query plan generated")
            cross_db_logger.info(f"📋 Query plan type: {type(query_plan)}")
            cross_db_logger.info(f"📋 Validation result: {validation_result}")
        
            # Check if plan is valid
            if not validation_result.get("valid", False):
                cross_db_logger.warning(f"❌ Query plan validation failed: {validation_result.get('errors', [])}")
                return {
                    "success": False,
                    "error": "Failed to create a valid query plan",
                    "validation_errors": validation_result.get("errors", []),
                    "query_plan": query_plan.to_dict() if hasattr(query_plan, "to_dict") else query_plan
                }
        
            cross_db_logger.info(f"✅ Query plan validation successful")
            
            # Step 2: Execute the plan
            if dry_run:
                cross_db_logger.info("🏃 Performing dry run (validation only)")
                execution_result = {
                    "success": True,
                    "dry_run": True,
                    "message": "Plan validation successful",
                    "query_plan": query_plan.to_dict() if hasattr(query_plan, "to_dict") else query_plan
                }
            else:
                cross_db_logger.info("🚀 Step 2: Executing query plan using implementation_agent")
                execution_result = await self.implementation_agent.execute_plan(
                    query_plan, question, dry_run=False
                )
                
                cross_db_logger.info(f"📊 Execution result received from implementation_agent")
                cross_db_logger.info(f"📊 Execution result type: {type(execution_result)}")
                cross_db_logger.info(f"📊 Execution result keys: {list(execution_result.keys()) if isinstance(execution_result, dict) else 'Not a dict'}")
                
                if isinstance(execution_result, dict):
                    cross_db_logger.info(f"📊 Execution result success: {execution_result.get('success', 'KEY_NOT_FOUND')}")
                    if "result" in execution_result:
                        cross_db_logger.info(f"📊 Execution result has 'result' field")
                        result_field = execution_result["result"]
                        cross_db_logger.info(f"📊 Result field type: {type(result_field)}")
                        cross_db_logger.info(f"📊 Result field keys: {list(result_field.keys()) if isinstance(result_field, dict) else 'Not a dict'}")
                    else:
                        cross_db_logger.warning(f"⚠️ No 'result' field in execution_result")
        
            # Return combined results
            cross_db_logger.info(f"🔧 Building combined result structure")
            combined_result = {
                "question": question,
                "plan": query_plan.to_dict() if hasattr(query_plan, "to_dict") else query_plan,
                "validation": validation_result,
                "execution": execution_result
            }
            
            cross_db_logger.info(f"🔧 Combined result structure built")
            cross_db_logger.info(f"🔧 Combined result keys: {list(combined_result.keys())}")
            
            # Determine overall success
            overall_success = validation_result.get("valid", False) and (
                dry_run or execution_result.get("success", False)
            )
            combined_result["success"] = overall_success
            
            cross_db_logger.info(f"🔧 Overall success: {overall_success}")
            cross_db_logger.info(f"✅ CrossDatabaseAgent.execute_query completed successfully")
            
            return combined_result
            
        except Exception as e:
            cross_db_logger.error(f"❌ Error in CrossDatabaseAgent.execute_query: {str(e)}")
            cross_db_logger.error(f"❌ Exception type: {type(e)}")
            import traceback
            cross_db_logger.error(f"❌ Traceback: {traceback.format_exc()}")
            
            return {
                "success": False,
                "error": f"CrossDatabaseAgent execution failed: {str(e)}",
                "question": question
            }
    
    async def close(self):
        """Close all connections and clean up resources"""
        await self.implementation_agent.close() 
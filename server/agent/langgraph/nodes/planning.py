"""
Planning Node for LangGraph Integration

Converts the existing PlanningAgent into a LangGraph-compatible node while preserving
all existing functionality and adding enhanced streaming capabilities.
"""

import logging
import json
import time
from typing import Dict, List, Any, Optional, AsyncIterator

from ..state import LangGraphState
from ..streaming import StreamingNodeBase
from ...db.orchestrator.planning_agent import PlanningAgent
from ...db.orchestrator.plans.factory import create_plan_from_dict
from ...llm.client import get_llm_client, get_classification_client

logger = logging.getLogger(__name__)

class PlanningNode(StreamingNodeBase):
    """
    LangGraph node that wraps the existing PlanningAgent for plan generation.
    
    Features:
    - Preserves all existing planning logic
    - Adds streaming progress updates
    - Integrates with LangGraph state management
    - Supports enhanced error handling and retries
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("planning")
        self.planning_agent = PlanningAgent(config)
        self.llm_client = get_llm_client()
        self.classification_client = get_classification_client()
        
        logger.info("Initialized PlanningNode with LangGraph integration")
    
    async def stream(
        self,
        state: LangGraphState,
        **kwargs
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Execute planning with streaming progress updates.
        
        Args:
            state: Current LangGraph state
            **kwargs: Additional execution parameters
            
        Yields:
            Streaming chunks with planning progress
        """
        question = state["question"]
        session_id = state["session_id"]
        
        try:
            # Step 1: Database Classification
            yield self.create_progress_chunk(
                10.0,
                "Classifying relevant databases",
                {"current_step": 1, "total_steps": 5}
            )
            
            start_time = time.time()
            
            # Use existing classification logic
            db_types = await self.planning_agent._classify_databases(question)
            
            classification_time = time.time() - start_time
            
            yield self.create_progress_chunk(
                25.0,
                "Database classification complete",
                {
                    "databases_identified": db_types,
                    "performance_metrics": {
                        "classification_time": classification_time
                    }
                },
                {"classified_databases": db_types, "time_taken": classification_time}
            )
            
            # Step 2: Schema Information Retrieval
            yield self.create_progress_chunk(
                40.0,
                "Retrieving schema information",
                {"current_step": 2}
            )
            
            start_time = time.time()
            
            # Use existing schema retrieval logic
            schema_info = await self.planning_agent._get_schema_info(db_types, question)
            
            schema_time = time.time() - start_time
            
            yield self.create_progress_chunk(
                60.0,
                "Schema information retrieved",
                {
                    "schema_metadata": {
                        "total_tables": len(schema_info),
                        "databases_queried": len(db_types)
                    }
                },
                {
                    "schema_items_count": len(schema_info),
                    "time_taken": schema_time
                }
            )
            
            # Step 3: Plan Generation
            yield self.create_progress_chunk(
                75.0,
                "Generating execution plan",
                {"current_step": 3}
            )
            
            start_time = time.time()
            
            # Use existing plan generation logic
            plan_dict = await self.planning_agent._generate_plan(question, db_types, schema_info)
            
            plan_time = time.time() - start_time
            
            yield self.create_progress_chunk(
                90.0,
                "Plan generation complete",
                {
                    "execution_plan": plan_dict,
                    "current_step": 4
                },
                {
                    "operations_count": len(plan_dict.get("operations", [])),
                    "time_taken": plan_time
                }
            )
            
            # Step 4: Plan Validation (Optional)
            yield self.create_progress_chunk(
                95.0,
                "Validating execution plan",
                {"current_step": 5}
            )
            
            start_time = time.time()
            
            # Use existing validation logic
            query_plan = create_plan_from_dict(plan_dict)
            validation_result = await self.planning_agent._validate_plan(query_plan, question)
            
            validation_time = time.time() - start_time
            
            # Final result
            yield self.create_result_chunk(
                {
                    "plan": plan_dict,
                    "validation": validation_result,
                    "databases_used": db_types,
                    "schema_info": schema_info
                },
                {
                    "execution_plan": plan_dict,
                    "databases_identified": db_types,
                    "schema_metadata": {
                        "schema_info": schema_info,
                        "validation_result": validation_result
                    },
                    "current_step": 5,
                    "total_steps": 5,
                    "performance_metrics": {
                        "total_planning_time": classification_time + schema_time + plan_time + validation_time,
                        "classification_time": classification_time,
                        "schema_time": schema_time,
                        "plan_time": plan_time,
                        "validation_time": validation_time
                    }
                },
                is_final=True
            )
            
        except Exception as e:
            logger.error(f"Error in planning node: {e}")
            yield self.create_result_chunk(
                {"error": str(e), "node": "planning"},
                {
                    "error_history": [{
                        "timestamp": time.time(),
                        "error": str(e),
                        "node": "planning"
                    }]
                },
                is_final=True
            )
            raise
    
    async def __call__(
        self,
        state: LangGraphState,
        **kwargs
    ) -> LangGraphState:
        """
        Execute planning and update state.
        
        Args:
            state: Current LangGraph state
            **kwargs: Additional execution parameters
            
        Returns:
            Updated LangGraph state
        """
        # Collect all streaming results
        final_result = None
        async for chunk in self.stream(state, **kwargs):
            if chunk.get("is_final") and chunk.get("type") == "result":
                final_result = chunk["result_data"]
            
            # Apply state updates
            if "state_update" in chunk:
                state.update(chunk["state_update"])
        
        # Ensure we have a result
        if final_result is None:
            # Fallback to direct execution if streaming failed
            logger.warning("Streaming failed, falling back to direct execution")
            final_result = await self._execute_direct(state)
        
        # Update final state
        if "error" not in final_result:
            state["execution_plan"] = final_result.get("plan", {})
            state["databases_identified"] = final_result.get("databases_used", [])
            state["schema_metadata"] = final_result.get("schema_info", {})
        
        return state
    
    async def _execute_direct(self, state: LangGraphState) -> Dict[str, Any]:
        """Direct execution fallback without streaming."""
        try:
            question = state["question"]
            
            # Execute planning steps directly
            db_types = await self.planning_agent._classify_databases(question)
            schema_info = await self.planning_agent._get_schema_info(db_types, question)
            plan_dict = await self.planning_agent._generate_plan(question, db_types, schema_info)
            query_plan = create_plan_from_dict(plan_dict)
            validation_result = await self.planning_agent._validate_plan(query_plan, question)
            
            return {
                "plan": plan_dict,
                "validation": validation_result,
                "databases_used": db_types,
                "schema_info": schema_info
            }
            
        except Exception as e:
            logger.error(f"Direct execution failed: {e}")
            return {"error": str(e), "node": "planning"}
    
    async def create_simple_plan(
        self,
        question: str,
        db_types: List[str],
        override_schema: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a simplified plan for specific database types.
        
        Args:
            question: User's question
            db_types: List of database types to use
            override_schema: Optional schema information to use instead of fetching
            
        Returns:
            Generated plan dictionary
        """
        schema_info = override_schema
        if schema_info is None:
            schema_info = await self.planning_agent._get_schema_info(db_types, question)
        
        return await self.planning_agent._generate_plan(question, db_types, schema_info)
    
    async def validate_external_plan(
        self,
        plan_dict: Dict[str, Any],
        question: str = "External plan validation"
    ) -> Dict[str, Any]:
        """
        Validate an externally provided plan.
        
        Args:
            plan_dict: Plan to validate
            question: Context question for validation
            
        Returns:
            Validation result
        """
        query_plan = create_plan_from_dict(plan_dict)
        return await self.planning_agent._validate_plan(query_plan, question)
    
    def get_planning_capabilities(self) -> Dict[str, Any]:
        """Get information about planning capabilities."""
        return {
            "supported_databases": ["postgres", "mongodb", "qdrant", "slack", "shopify"],
            "max_operations_per_plan": 50,
            "supports_cross_database_joins": True,
            "supports_validation": True,
            "supports_optimization": True,
            "streaming_enabled": True
        } 
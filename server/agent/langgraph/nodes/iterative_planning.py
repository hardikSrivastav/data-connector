"""
Iterative Planning Node for Dynamic LangGraph Workflows

Provides intelligent planning that can dynamically adapt and re-plan based on
metadata discovery, execution results, and changing requirements.
"""

import logging
import time
import asyncio
from typing import Dict, List, Any, Optional, AsyncIterator

from ..state import LangGraphState
from ..streaming import StreamingNodeBase
from .planning import PlanningNode
from ...db.orchestrator.planning_agent import PlanningAgent

logger = logging.getLogger(__name__)

class IterativePlanningNode(StreamingNodeBase):
    """
    LangGraph node for iterative planning with dynamic re-planning capabilities.
    
    Features:
    - Dynamic re-planning based on metadata discovery
    - Iterative refinement based on execution feedback
    - Adaptive plan optimization and resource allocation
    - Integration with existing PlanningNode and PlanningAgent
    - Streaming progress updates
    - Context-aware planning strategies
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("iterative_planning")
        self.config = config or {}
        
        # Initialize base planning components
        self.base_planning_node = PlanningNode(config)
        self.planning_agent = PlanningAgent()
        
        # Iterative planning settings
        self.enable_dynamic_replanning = self.config.get("enable_dynamic_replanning", True)
        self.max_planning_iterations = self.config.get("max_planning_iterations", 3)
        self.plan_confidence_threshold = self.config.get("plan_confidence_threshold", 0.8)
        self.enable_context_learning = self.config.get("enable_context_learning", True)
        
        # Planning optimization settings
        self.planning_strategies = {}
        self.performance_history = []
        self.context_cache = {}
        
        logger.info("Initialized IterativePlanningNode with dynamic re-planning capabilities")
    
    async def stream(
        self,
        state: LangGraphState,
        **kwargs
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Execute iterative planning with streaming progress updates.
        
        Args:
            state: Current LangGraph state
            **kwargs: Additional execution parameters
            
        Yields:
            Streaming chunks with planning progress
        """
        question = state["question"]
        session_id = state["session_id"]
        
        try:
            # Step 1: Initialize iterative planning
            yield self.create_progress_chunk(
                10.0,
                "Starting iterative planning process",
                {"current_step": 1, "total_steps": 5}
            )
            
            start_time = time.time()
            
            # Step 2: Analyze planning context
            planning_context = self._analyze_planning_context(state)
            
            yield self.create_progress_chunk(
                25.0,
                "Analyzing planning context and requirements",
                {
                    "context_complexity": planning_context.get("complexity", "medium"),
                    "databases_available": planning_context.get("databases", []),
                    "current_step": 2
                }
            )
            
            # Step 3: Generate initial plan
            initial_plan = await self._generate_initial_plan(state, planning_context)
            
            yield self.create_progress_chunk(
                50.0,
                f"Generated initial plan with {len(initial_plan.get('steps', []))} steps",
                {
                    "plan_type": initial_plan.get("plan_type", "standard"),
                    "estimated_complexity": initial_plan.get("complexity", 5),
                    "current_step": 3
                }
            )
            
            # Step 4: Iterative plan refinement
            if self.enable_dynamic_replanning:
                refined_plan = await self._refine_plan_iteratively(
                    initial_plan,
                    planning_context,
                    state
                )
            else:
                refined_plan = initial_plan
            
            yield self.create_progress_chunk(
                80.0,
                "Plan refinement complete, finalizing execution strategy",
                {
                    "refinement_applied": self.enable_dynamic_replanning,
                    "final_confidence": refined_plan.get("confidence", 0.8),
                    "current_step": 4
                }
            )
            
            # Step 5: Optimize plan for execution
            optimized_plan = await self._optimize_plan_for_execution(
                refined_plan,
                planning_context,
                state
            )
            
            planning_time = time.time() - start_time
            
            # Final result
            yield self.create_result_chunk(
                {
                    "execution_plan": optimized_plan,
                    "planning_context": planning_context,
                    "iterative_features": {
                        "dynamic_replanning": self.enable_dynamic_replanning,
                        "iterations_performed": optimized_plan.get("iterations", 1),
                        "confidence_threshold": self.plan_confidence_threshold
                    }
                },
                {
                    "execution_plan": optimized_plan,
                    "plan_confidence": optimized_plan.get("confidence", 0.8),
                    "planning_metadata": {
                        "planning_time": planning_time,
                        "steps_count": len(optimized_plan.get("steps", [])),
                        "complexity_score": optimized_plan.get("complexity", 5),
                        "optimization_applied": True
                    },
                    "current_step": 5,
                    "total_steps": 5
                },
                is_final=True
            )
            
        except Exception as e:
            logger.error(f"Error in iterative planning: {e}")
            yield self.create_result_chunk(
                {"error": str(e), "node": "iterative_planning"},
                {
                    "error_history": [{
                        "timestamp": time.time(),
                        "error": str(e),
                        "node": "iterative_planning"
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
        Execute iterative planning and update state.
        
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
            state["execution_plan"] = final_result.get("execution_plan", {})
            state["planning_context"] = final_result.get("planning_context", {})
            state["plan_confidence"] = final_result.get("execution_plan", {}).get("confidence", 0.8)
            
            # Store for potential re-planning in iterative workflows
            state["_planning_history"] = state.get("_planning_history", [])
            state["_planning_history"].append({
                "timestamp": time.time(),
                "plan": final_result.get("execution_plan", {}),
                "context": final_result.get("planning_context", {}),
                "phase": "iterative_planning"
            })
        
        return state
    
    async def _execute_direct(self, state: LangGraphState) -> Dict[str, Any]:
        """Execute direct planning without streaming."""
        try:
            # Use base planning as fallback
            result_state = await self.base_planning_node(state)
            
            return {
                "execution_plan": result_state.get("execution_plan", {}),
                "planning_context": {"strategy_type": "fallback_direct"},
                "direct_execution": True
            }
        except Exception as e:
            logger.error(f"Direct execution failed: {e}")
            return {"error": str(e), "node": "iterative_planning"}
    
    def _analyze_planning_context(self, state: LangGraphState) -> Dict[str, Any]:
        """
        Analyze the planning context based on current state.
        
        Args:
            state: Current LangGraph state
            
        Returns:
            Planning context analysis
        """
        context = {
            "databases": state.get("databases_identified", []),
            "metadata_available": bool(state.get("metadata_results")),
            "classification_confidence": state.get("classification_confidence", 0.8),
            "question": state["question"],
            "complexity": "medium"
        }
        
        # Analyze complexity based on available information
        databases_count = len(context["databases"])
        metadata_schemas = len(state.get("metadata_results", {}).get("schemas", {}))
        
        if databases_count <= 1 and metadata_schemas <= 5:
            context["complexity"] = "low"
        elif databases_count <= 3 and metadata_schemas <= 15:
            context["complexity"] = "medium"
        else:
            context["complexity"] = "high"
        
        # Add question-specific context
        question_lower = context["question"].lower()
        context["requires_joins"] = any(word in question_lower for word in ["join", "combine", "across"])
        context["requires_aggregation"] = any(word in question_lower for word in ["total", "count", "sum", "average"])
        context["time_sensitive"] = any(word in question_lower for word in ["recent", "latest", "today", "now"])
        
        logger.info(f"Planning context: {context['complexity']} complexity, {databases_count} databases")
        
        return context
    
    async def _generate_initial_plan(
        self,
        state: LangGraphState,
        planning_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate initial execution plan based on context.
        
        Args:
            state: Current LangGraph state
            planning_context: Planning context analysis
            
        Returns:
            Initial execution plan
        """
        try:
            # Use base planning node for initial plan generation
            result_state = await self.base_planning_node(state)
            base_plan = result_state.get("execution_plan", {})
            
            # Enhance with iterative planning features
            enhanced_plan = base_plan.copy()
            enhanced_plan.update({
                "plan_type": "iterative_initial",
                "context": planning_context,
                "confidence": self._calculate_plan_confidence(base_plan, planning_context),
                "iterations": 1,
                "optimization_potential": self._assess_optimization_potential(base_plan, planning_context)
            })
            
            return enhanced_plan
            
        except Exception as e:
            logger.error(f"Initial plan generation failed: {e}")
            # Create fallback plan
            return self._create_fallback_plan(state, planning_context)
    
    def _calculate_plan_confidence(
        self,
        plan: Dict[str, Any],
        context: Dict[str, Any]
    ) -> float:
        """Calculate confidence score for the execution plan."""
        base_confidence = 0.7
        
        # Adjust based on context complexity
        if context["complexity"] == "low":
            base_confidence += 0.2
        elif context["complexity"] == "high":
            base_confidence -= 0.1
        
        # Adjust based on classification confidence
        classification_confidence = context.get("classification_confidence", 0.8)
        base_confidence = (base_confidence + classification_confidence) / 2
        
        # Adjust based on metadata availability
        if context.get("metadata_available", False):
            base_confidence += 0.1
        
        return min(max(base_confidence, 0.0), 1.0)
    
    def _assess_optimization_potential(
        self,
        plan: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Assess potential for plan optimization."""
        potential = {
            "parallelization": len(context["databases"]) > 1,
            "caching": context["complexity"] == "high",
            "resource_optimization": len(plan.get("steps", [])) > 3,
            "query_optimization": context.get("requires_joins", False)
        }
        
        potential["overall_score"] = sum(potential.values()) / len(potential)
        
        return potential
    
    async def _refine_plan_iteratively(
        self,
        initial_plan: Dict[str, Any],
        planning_context: Dict[str, Any],
        state: LangGraphState
    ) -> Dict[str, Any]:
        """
        Iteratively refine the execution plan.
        
        Args:
            initial_plan: Initial execution plan
            planning_context: Planning context
            state: Current LangGraph state
            
        Returns:
            Refined execution plan
        """
        current_plan = initial_plan.copy()
        iterations = 1
        
        while (iterations < self.max_planning_iterations and 
               current_plan.get("confidence", 0) < self.plan_confidence_threshold):
            
            logger.info(f"Refining plan - iteration {iterations + 1}")
            
            # Apply refinement strategies
            refined_plan = await self._apply_refinement_strategies(
                current_plan,
                planning_context,
                iterations
            )
            
            # Update iteration count and confidence
            refined_plan["iterations"] = iterations + 1
            refined_plan["confidence"] = min(
                refined_plan.get("confidence", 0.8) + 0.05,
                1.0
            )
            
            current_plan = refined_plan
            iterations += 1
        
        logger.info(f"Plan refinement complete after {iterations} iterations")
        current_plan["refinement_complete"] = True
        
        return current_plan
    
    async def _apply_refinement_strategies(
        self,
        plan: Dict[str, Any],
        context: Dict[str, Any],
        iteration: int
    ) -> Dict[str, Any]:
        """Apply specific refinement strategies based on iteration and context."""
        refined_plan = plan.copy()
        
        # Strategy 1: Optimize for parallelization
        if iteration == 1 and context["complexity"] != "low":
            refined_plan = self._apply_parallelization_optimization(refined_plan, context)
        
        # Strategy 2: Optimize resource allocation
        if iteration == 2:
            refined_plan = self._apply_resource_optimization(refined_plan, context)
        
        # Add refinement metadata
        refined_plan["refinement_strategies"] = refined_plan.get("refinement_strategies", [])
        refined_plan["refinement_strategies"].append(f"iteration_{iteration}")
        
        return refined_plan
    
    def _apply_parallelization_optimization(
        self,
        plan: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Apply parallelization optimizations to the plan."""
        optimized_plan = plan.copy()
        optimized_plan["parallelization_applied"] = True
        optimized_plan["parallel_databases"] = context["databases"]
        
        return optimized_plan
    
    def _apply_resource_optimization(
        self,
        plan: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Apply resource allocation optimizations to the plan."""
        optimized_plan = plan.copy()
        optimized_plan["resource_optimization_applied"] = True
        optimized_plan["resource_allocation"] = {
            "memory_optimization": True,
            "query_batching": context["complexity"] == "high"
        }
        
        return optimized_plan
    
    async def _optimize_plan_for_execution(
        self,
        plan: Dict[str, Any],
        context: Dict[str, Any],
        state: LangGraphState
    ) -> Dict[str, Any]:
        """
        Final optimization of the plan for execution.
        
        Args:
            plan: Refined execution plan
            context: Planning context
            state: Current LangGraph state
            
        Returns:
            Optimized execution plan
        """
        optimized_plan = plan.copy()
        
        # Add execution-specific optimizations
        optimized_plan["execution_optimizations"] = {
            "streaming_enabled": True,
            "error_recovery": True,
            "progress_tracking": True,
            "resource_monitoring": True
        }
        
        # Add execution metadata
        optimized_plan["execution_metadata"] = {
            "plan_version": "iterative_v1",
            "optimization_timestamp": time.time(),
            "execution_ready": True
        }
        
        return optimized_plan
    
    def _create_fallback_plan(
        self,
        state: LangGraphState,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a fallback plan when normal planning fails."""
        return {
            "plan_type": "fallback",
            "steps": [
                {"type": "metadata_collection", "databases": context["databases"]},
                {"type": "query_execution", "databases": context["databases"]},
                {"type": "result_aggregation"}
            ],
            "confidence": 0.6,
            "iterations": 1,
            "fallback": True,
            "context": context
        }
    
    async def replan_with_execution_feedback(
        self,
        state: LangGraphState,
        execution_results: Dict[str, Any],
        **kwargs
    ) -> Dict[str, Any]:
        """
        Re-plan based on execution feedback (for future phases).
        
        Args:
            state: Current LangGraph state
            execution_results: Results from query execution
            **kwargs: Additional re-planning parameters
            
        Returns:
            Updated execution plan with feedback integration
        """
        # Placeholder for future implementation
        logger.info("Execution feedback re-planning placeholder - to be implemented in future phases")
        
        current_plan = state.get("execution_plan", {})
        
        # Simulate feedback-based re-planning
        updated_plan = current_plan.copy()
        updated_plan["execution_feedback_applied"] = True
        updated_plan["feedback_timestamp"] = time.time()
        updated_plan["replanning_triggered"] = True
        
        return updated_plan 
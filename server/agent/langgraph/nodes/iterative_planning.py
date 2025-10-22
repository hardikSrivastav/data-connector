"""
Iterative Planning Node for Enhanced LangGraph Workflows

This node implements dynamic planning that adapts based on iterative metadata collection results.
"""

import logging
import time
from typing import Dict, List, Any, Optional, AsyncIterator

from ..streaming import StreamingNodeBase
from ..state import LangGraphState

logger = logging.getLogger(__name__)

class IterativePlanningNode(StreamingNodeBase):
    """
    Planning node that adapts based on iterative metadata collection results.
    
    Features:
    - Dynamic plan adjustment based on available metadata
    - Integration with iterative metadata results
    - Comprehensive logging for each planning step
    - Re-planning capabilities when new metadata becomes available
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("iterative_planning")
        
        self.config = config or {}
        
        # Planning cache to avoid redundant planning
        self.planning_cache: Dict[str, Dict[str, Any]] = {}
        
        # Plan adaptation history
        self.adaptation_history: Dict[str, List[Dict[str, Any]]] = {}
        
        logger.info("📋 [ITERATIVE_PLANNING] Initialized IterativePlanningNode")
    
    async def stream(self, state: LangGraphState, **kwargs) -> AsyncIterator[Dict[str, Any]]:
        """
        Streaming execution with dynamic planning based on metadata results.
        """
        session_id = state.get("session_id", "unknown")
        user_query = state.get("user_query", state.get("question", ""))
        schema_metadata = state.get("schema_metadata", {})
        available_tables = state.get("available_tables", [])
        
        logger.info(f"📋 [ITERATIVE_PLANNING] Starting planning for session: {session_id}")
        logger.info(f"📋 [ITERATIVE_PLANNING] Query: {user_query}")
        logger.info(f"📋 [ITERATIVE_PLANNING] Available tables: {len(available_tables)}")
        
        try:
            # Step 1: Analyze available metadata
            yield self.create_progress_chunk(
                20.0, "Analyzing available metadata for planning",
                {"current_step": 1, "total_steps": 4}
            )
            
            metadata_analysis = await self._analyze_metadata_for_planning(
                schema_metadata, available_tables, user_query
            )
            
            # Step 2: Generate execution plan
            yield self.create_progress_chunk(
                50.0, "Generating execution plan",
                {"current_step": 2, "metadata_analysis": metadata_analysis}
            )
            
            execution_plan = await self._generate_execution_plan(
                user_query, metadata_analysis, session_id
            )
            
            # Step 3: Optimize plan
            yield self.create_progress_chunk(
                75.0, "Optimizing execution plan",
                {"current_step": 3}
            )
            
            optimized_plan = await self._optimize_plan(execution_plan, metadata_analysis)
            
            # Step 4: Finalize plan
            yield self.create_progress_chunk(
                90.0, "Finalizing execution plan",
                {"current_step": 4}
            )
            
            final_plan = await self._finalize_plan(optimized_plan, session_id)
            
            # Cache the plan
            self._cache_plan(session_id, user_query, final_plan)
            
            # Final result
            yield self.create_result_chunk(
                final_plan,
                {
                    "execution_plan_ready": True,
                    "planning_completed": True
                },
                is_final=True
            )
            
            logger.info(f"📋 [ITERATIVE_PLANNING] Completed planning for session: {session_id}")
            
        except Exception as e:
            logger.error(f"📋 [ITERATIVE_PLANNING] Planning failed: {e}")
            logger.exception("📋 [ITERATIVE_PLANNING] Full error traceback:")
            
            yield self.create_result_chunk(
                {"error": str(e), "planning_failed": True},
                {"execution_plan": {}, "plan_steps": []},
                is_final=True
            )
    
    async def _analyze_metadata_for_planning(
        self, schema_metadata: Dict[str, Any], available_tables: List[Dict], user_query: str
    ) -> Dict[str, Any]:
        """Analyze available metadata to inform planning decisions."""
        logger.info("📋 [ITERATIVE_PLANNING] Analyzing metadata for planning")
        
        return {
            "metadata_quality": "good" if schema_metadata else "limited",
            "table_count": len(available_tables),
            "databases_involved": len(set(table.get("database_type", "unknown") for table in available_tables)),
            "query_complexity": self._assess_query_complexity(user_query),
            "key_tables": [table.get("name") for table in available_tables if self._is_key_table(table, user_query)]
        }
    
    async def _generate_execution_plan(
        self, user_query: str, metadata_analysis: Dict[str, Any], session_id: str
    ) -> Dict[str, Any]:
        """Generate initial execution plan."""
        logger.info("📋 [ITERATIVE_PLANNING] Generating execution plan")
        
        plan = {
            "plan_id": f"plan_{session_id}_{int(time.time())}",
            "query": user_query,
            "execution_strategy": "sequential",
            "steps": [],
            "estimated_time": 0
        }
        
        # Determine strategy based on metadata
        if metadata_analysis["databases_involved"] > 1:
            plan["execution_strategy"] = "cross_database"
            plan["steps"].append({
                "step": 1,
                "operation": "cross_database_query",
                "description": "Execute query across multiple databases",
                "estimated_time": 30
            })
        else:
            plan["execution_strategy"] = "simple"
            plan["steps"].append({
                "step": 1,
                "operation": "single_database_query", 
                "description": "Execute query on single database",
                "estimated_time": 15
            })
        
        plan["steps"].append({
            "step": 2,
            "operation": "result_processing",
            "description": "Process and format results",
            "estimated_time": 5
        })
        
        plan["estimated_time"] = sum(step["estimated_time"] for step in plan["steps"])
        return plan
    
    async def _optimize_plan(self, plan: Dict[str, Any], metadata_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Optimize the plan based on metadata insights."""
        logger.info("📋 [ITERATIVE_PLANNING] Optimizing execution plan")
        
        optimized_plan = plan.copy()
        
        # Apply optimizations based on metadata
        if metadata_analysis["key_tables"]:
            # Add key table preprocessing
            key_step = {
                "step": 0.5,
                "operation": "key_table_preprocessing",
                "description": f"Preprocess key tables: {', '.join(metadata_analysis['key_tables'][:3])}",
                "estimated_time": 3
            }
            optimized_plan["steps"].insert(0, key_step)
        
        # Recalculate timing
        optimized_plan["estimated_time"] = sum(step["estimated_time"] for step in optimized_plan["steps"])
        optimized_plan["optimizations_applied"] = ["key_table_preprocessing"] if metadata_analysis["key_tables"] else []
        
        return optimized_plan
    
    async def _finalize_plan(self, plan: Dict[str, Any], session_id: str) -> Dict[str, Any]:
        """Finalize the execution plan."""
        logger.info("📋 [ITERATIVE_PLANNING] Finalizing execution plan")
        
        final_plan = plan.copy()
        final_plan.update({
            "session_id": session_id,
            "created_at": time.time(),
            "status": "ready",
            "execution_metadata": {
                "can_execute": True,
                "estimated_success_rate": 0.9,
                "timeout_settings": {
                    "step_timeout": 60,
                    "total_timeout": plan.get("estimated_time", 30) * 2
                }
            }
        })
        
        return final_plan
    
    def _assess_query_complexity(self, query: str) -> str:
        """Assess query complexity."""
        complexity_indicators = {
            "high": ["join", "aggregate", "group by", "union"],
            "medium": ["where", "order by", "count", "sum"],
            "low": ["select", "show", "describe"]
        }
        
        query_lower = query.lower()
        for level, indicators in complexity_indicators.items():
            if any(indicator in query_lower for indicator in indicators):
                return level
        return "low"
    
    def _is_key_table(self, table: Dict[str, Any], query: str) -> bool:
        """Determine if table is key for the query."""
        table_name = table.get("name", "").lower()
        query_lower = query.lower()
        
        if table_name in query_lower:
            return True
        
        key_patterns = ["user", "customer", "order", "product", "main"]
        return any(pattern in table_name for pattern in key_patterns)
    
    def _cache_plan(self, session_id: str, query: str, plan: Dict[str, Any]):
        """Cache the plan for reuse."""
        cache_key = f"{session_id}_{hash(query)}"
        self.planning_cache[cache_key] = plan
        logger.info(f"📋 [ITERATIVE_PLANNING] Cached plan for session {session_id}")
    
    async def adapt_plan(
        self,
        session_id: str,
        current_plan: Dict[str, Any],
        new_metadata: Dict[str, Any],
        execution_feedback: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Adapt an existing plan based on new metadata or execution feedback.
        """
        logger.info(f"📋 [ITERATIVE_PLANNING] Adapting plan for session {session_id}")
        
        # Track adaptation history
        if session_id not in self.adaptation_history:
            self.adaptation_history[session_id] = []
        
        adaptation_record = {
            "timestamp": time.time(),
            "trigger": "metadata_update" if new_metadata else "execution_feedback",
            "changes_made": []
        }
        
        adapted_plan = current_plan.copy()
        
        # Update plan version
        adapted_plan["adaptive_planning"]["plan_version"] += 1
        
        # Apply adaptations based on new metadata
        if new_metadata:
            # Add new tables to consideration
            new_tables = new_metadata.get("available_tables", [])
            if new_tables:
                adaptation_record["changes_made"].append(f"Added {len(new_tables)} new tables")
                
                # Re-optimize with new metadata
                metadata_analysis = await self._analyze_metadata_for_planning(
                    new_metadata,
                    new_tables,
                    adapted_plan["query"]
                )
                
                adapted_plan = await self._optimize_plan(
                    adapted_plan,
                    metadata_analysis
                )
        
        # Apply adaptations based on execution feedback
        if execution_feedback:
            if execution_feedback.get("performance_issues"):
                adaptation_record["changes_made"].append("Adjusted for performance issues")
                # Increase timeouts
                adapted_plan["execution_metadata"]["timeout_settings"]["step_timeout"] *= 1.5
            
            if execution_feedback.get("connection_failures"):
                adaptation_record["changes_made"].append("Added connection retry logic")
                # Add retry steps
                adapted_plan["execution_metadata"]["retry_strategy"] = "aggressive"
        
        # Record adaptation
        self.adaptation_history[session_id].append(adaptation_record)
        adapted_plan["adaptive_planning"]["adaptation_history"] = self.adaptation_history[session_id]
        
        logger.info(f"📋 [ITERATIVE_PLANNING] Plan adapted: {len(adaptation_record['changes_made'])} changes made")
        
        return adapted_plan
    
    async def __call__(self, state: LangGraphState, **kwargs) -> LangGraphState:
        """Non-streaming execution of iterative planning."""
        logger.info("📋 [ITERATIVE_PLANNING] Starting non-streaming planning")
        
        final_plan = None
        final_state_update = {}
        
        async for chunk in self.stream(state, **kwargs):
            # Apply any state updates
            if "state_update" in chunk:
                final_state_update.update(chunk["state_update"])
            
            # Get the final plan
            if chunk.get("is_final", False) and chunk.get("type") == "result":
                final_plan = chunk.get("result_data")
        
        # Update state with planning results
        if final_plan and not final_plan.get("planning_failed"):
            state["execution_plan"] = final_plan
            state["planning_completed"] = True
            state["planning_metadata"] = {
                "strategy": final_plan.get("execution_strategy", "unknown"),
                "steps": len(final_plan.get("steps", [])),
                "estimated_time": final_plan.get("estimated_time", 0)
            }
        else:
            # Planning failed or no plan generated
            state["execution_plan"] = {}
            state["planning_completed"] = False
            state["planning_error"] = final_plan.get("error") if final_plan else "No plan generated"
        
        # Apply any additional state updates
        state.update(final_state_update)
        
        logger.info("📋 [ITERATIVE_PLANNING] Non-streaming planning completed")
        return state
    
    def get_node_capabilities(self) -> Dict[str, Any]:
        """Get capabilities and status of this planning node."""
        return {
            "node_type": "iterative_planning",
            "features": [
                "dynamic_plan_adaptation",
                "metadata_aware_planning",
                "cross_database_optimization",
                "performance_estimation",
                "plan_validation",
                "adaptive_re_planning"
            ],
            "planning_strategies": ["simple", "parallel", "cross_database"],
            "active_plans": len(self.planning_cache),
            "adaptation_sessions": len(self.adaptation_history)
        } 
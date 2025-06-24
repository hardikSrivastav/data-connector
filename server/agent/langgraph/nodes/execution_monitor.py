"""
Execution Monitor Node for Iterative LangGraph Workflows

Monitors execution progress and collects feedback for iterative refinement
of classification, metadata collection, and planning.
"""

import logging
import time
import asyncio
from typing import Dict, List, Any, Optional, AsyncIterator

from ..state import LangGraphState
from ..streaming import StreamingNodeBase

logger = logging.getLogger(__name__)

class ExecutionMonitorNode(StreamingNodeBase):
    """
    LangGraph node for execution monitoring with feedback collection.
    
    Features:
    - Real-time execution monitoring
    - Performance metrics collection
    - Error tracking and analysis
    - Feedback generation for iterative refinement
    - Integration with existing execution nodes
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("execution_monitor")
        self.config = config or {}
        
        # Monitoring settings
        self.enable_performance_tracking = self.config.get("enable_performance_tracking", True)
        self.collect_execution_feedback = self.config.get("collect_execution_feedback", True)
        self.error_analysis_enabled = self.config.get("error_analysis_enabled", True)
        
        # Metrics storage
        self.execution_metrics = {}
        self.feedback_history = []
        self.error_patterns = {}
        
        logger.info("Initialized ExecutionMonitorNode with feedback collection")
    
    async def stream(
        self,
        state: LangGraphState,
        **kwargs
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Monitor execution and collect feedback with streaming updates.
        
        Args:
            state: Current LangGraph state
            **kwargs: Additional monitoring parameters
            
        Yields:
            Streaming chunks with monitoring progress
        """
        session_id = state["session_id"]
        
        try:
            yield self.create_progress_chunk(
                10.0,
                "Starting execution monitoring",
                {"current_step": 1, "total_steps": 3}
            )
            
            start_time = time.time()
            
            # Step 1: Collect execution metrics
            execution_metrics = self._collect_execution_metrics(state)
            
            yield self.create_progress_chunk(
                40.0,
                "Analyzing execution performance",
                {
                    "metrics_collected": len(execution_metrics),
                    "current_step": 2
                }
            )
            
            # Step 2: Generate feedback for iterative improvement
            feedback = self._generate_iterative_feedback(state, execution_metrics)
            
            yield self.create_progress_chunk(
                70.0,
                "Generating improvement feedback",
                {
                    "feedback_items": len(feedback.get("recommendations", [])),
                    "current_step": 3
                }
            )
            
            # Final result
            monitoring_time = time.time() - start_time
            
            yield self.create_result_chunk(
                {
                    "execution_metrics": execution_metrics,
                    "iterative_feedback": feedback,
                    "monitoring_summary": {
                        "monitoring_time": monitoring_time,
                        "feedback_generated": bool(feedback.get("recommendations")),
                        "performance_analysis": execution_metrics.get("performance_summary", {})
                    }
                },
                {
                    "execution_monitored": True,
                    "feedback_available": bool(feedback.get("recommendations")),
                    "monitoring_metadata": {
                        "total_time": monitoring_time,
                        "metrics_count": len(execution_metrics),
                        "recommendations_count": len(feedback.get("recommendations", []))
                    }
                },
                is_final=True
            )
            
        except Exception as e:
            logger.error(f"Error in execution monitoring: {e}")
            yield self.create_result_chunk(
                {"error": str(e), "node": "execution_monitor"},
                {"error_timestamp": time.time()},
                is_final=True
            )
            raise
    
    async def __call__(
        self,
        state: LangGraphState,
        **kwargs
    ) -> LangGraphState:
        """
        Execute monitoring and update state with feedback.
        
        Args:
            state: Current LangGraph state
            **kwargs: Additional monitoring parameters
            
        Returns:
            Updated LangGraph state
        """
        # Collect all streaming results
        final_result = None
        async for chunk in self.stream(state, **kwargs):
            if chunk.get("is_final") and chunk.get("type") == "result":
                final_result = chunk["result_data"]
            
            if "state_update" in chunk:
                state.update(chunk["state_update"])
        
        # Update state with monitoring results
        if final_result and "error" not in final_result:
            state["execution_metrics"] = final_result.get("execution_metrics", {})
            state["iterative_feedback"] = final_result.get("iterative_feedback", {})
            
            # Store feedback for future iterations
            state["_execution_feedback_history"] = state.get("_execution_feedback_history", [])
            state["_execution_feedback_history"].append({
                "timestamp": time.time(),
                "feedback": final_result.get("iterative_feedback", {}),
                "metrics": final_result.get("execution_metrics", {}),
                "phase": "execution_monitoring"
            })
        
        return state
    
    def _collect_execution_metrics(self, state: LangGraphState) -> Dict[str, Any]:
        """Collect metrics from the current execution state."""
        metrics = {
            "classification_metrics": self._extract_classification_metrics(state),
            "metadata_metrics": self._extract_metadata_metrics(state),
            "planning_metrics": self._extract_planning_metrics(state),
            "performance_summary": {}
        }
        
        # Calculate overall performance summary
        metrics["performance_summary"] = {
            "classification_confidence": state.get("classification_confidence", 0.8),
            "metadata_confidence": state.get("metadata_confidence", 0.8),
            "plan_confidence": state.get("plan_confidence", 0.8),
            "overall_confidence": self._calculate_overall_confidence(state)
        }
        
        return metrics
    
    def _extract_classification_metrics(self, state: LangGraphState) -> Dict[str, Any]:
        """Extract classification-related metrics."""
        classification_result = state.get("classification_result", {})
        
        return {
            "databases_identified": len(state.get("databases_identified", [])),
            "confidence": state.get("classification_confidence", 0.8),
            "reasoning_quality": len(classification_result.get("reasoning", "")),
            "classification_time": classification_result.get("time_taken", 0)
        }
    
    def _extract_metadata_metrics(self, state: LangGraphState) -> Dict[str, Any]:
        """Extract metadata collection metrics."""
        metadata_results = state.get("metadata_results", {})
        
        return {
            "schemas_collected": len(metadata_results.get("schemas", {})),
            "confidence": state.get("metadata_confidence", 0.8),
            "collection_strategy": state.get("collection_strategy", {}).get("strategy_type", "unknown"),
            "collection_efficiency": state.get("collection_strategy", {}).get("efficiency_score", 0.8)
        }
    
    def _extract_planning_metrics(self, state: LangGraphState) -> Dict[str, Any]:
        """Extract planning-related metrics."""
        execution_plan = state.get("execution_plan", {})
        
        return {
            "plan_steps": len(execution_plan.get("steps", [])),
            "confidence": state.get("plan_confidence", 0.8),
            "complexity": execution_plan.get("complexity", 5),
            "iterations": execution_plan.get("iterations", 1),
            "optimization_applied": execution_plan.get("refinement_complete", False)
        }
    
    def _calculate_overall_confidence(self, state: LangGraphState) -> float:
        """Calculate overall confidence score across all phases."""
        classification_conf = state.get("classification_confidence", 0.8)
        metadata_conf = state.get("metadata_confidence", 0.8)
        plan_conf = state.get("plan_confidence", 0.8)
        
        return (classification_conf + metadata_conf + plan_conf) / 3
    
    def _generate_iterative_feedback(
        self,
        state: LangGraphState,
        execution_metrics: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate feedback for iterative improvement."""
        feedback = {
            "recommendations": [],
            "improvement_areas": [],
            "confidence_analysis": {},
            "next_iteration_suggestions": []
        }
        
        overall_confidence = execution_metrics["performance_summary"]["overall_confidence"]
        
        # Generate confidence-based recommendations
        if overall_confidence < 0.7:
            feedback["recommendations"].append({
                "area": "overall_confidence",
                "priority": "high",
                "suggestion": "Consider re-classification with additional context",
                "confidence_threshold": 0.7,
                "current_confidence": overall_confidence
            })
        
        # Classification feedback
        classification_conf = state.get("classification_confidence", 0.8)
        if classification_conf < 0.8:
            feedback["recommendations"].append({
                "area": "classification",
                "priority": "medium",
                "suggestion": "Refine database classification with execution context",
                "current_confidence": classification_conf
            })
        
        # Metadata feedback
        metadata_conf = state.get("metadata_confidence", 0.8)
        if metadata_conf < 0.8:
            feedback["recommendations"].append({
                "area": "metadata",
                "priority": "medium",
                "suggestion": "Enhance metadata collection with targeted queries",
                "current_confidence": metadata_conf
            })
        
        # Planning feedback
        plan_conf = state.get("plan_confidence", 0.8)
        if plan_conf < 0.8:
            feedback["recommendations"].append({
                "area": "planning",
                "priority": "medium",
                "suggestion": "Apply additional planning optimizations",
                "current_confidence": plan_conf
            })
        
        # Generate improvement areas
        feedback["improvement_areas"] = self._identify_improvement_areas(execution_metrics)
        
        # Confidence analysis
        feedback["confidence_analysis"] = {
            "classification": classification_conf,
            "metadata": metadata_conf,
            "planning": plan_conf,
            "overall": overall_confidence,
            "threshold_met": overall_confidence >= 0.8
        }
        
        # Next iteration suggestions (placeholder for future phases)
        feedback["next_iteration_suggestions"] = [
            "Apply execution feedback to refine classification",
            "Use performance metrics to optimize metadata collection",
            "Leverage results to improve planning strategies"
        ]
        
        return feedback
    
    def _identify_improvement_areas(self, execution_metrics: Dict[str, Any]) -> List[str]:
        """Identify specific areas that need improvement."""
        areas = []
        
        performance = execution_metrics["performance_summary"]
        
        if performance["classification_confidence"] < 0.8:
            areas.append("database_classification")
        
        if performance["metadata_confidence"] < 0.8:
            areas.append("metadata_collection")
        
        if performance["plan_confidence"] < 0.8:
            areas.append("execution_planning")
        
        if performance["overall_confidence"] < 0.7:
            areas.append("overall_workflow")
        
        return areas
    
    async def collect_execution_feedback(
        self,
        state: LangGraphState,
        execution_results: Dict[str, Any],
        **kwargs
    ) -> Dict[str, Any]:
        """
        Collect feedback from actual execution results (for future phases).
        
        Args:
            state: Current LangGraph state
            execution_results: Actual execution results
            **kwargs: Additional feedback parameters
            
        Returns:
            Collected feedback for iterative improvement
        """
        # Placeholder for future implementation
        logger.info("Execution results feedback collection - to be implemented in future phases")
        
        feedback = {
            "execution_success": execution_results.get("success", False),
            "performance_feedback": {
                "execution_time": execution_results.get("execution_time", 0),
                "result_quality": execution_results.get("result_quality", "unknown"),
                "error_rate": execution_results.get("error_count", 0)
            },
            "improvement_recommendations": [
                "Use actual execution results to refine classification accuracy",
                "Apply performance data to optimize metadata collection strategies",
                "Leverage success/failure patterns to improve planning decisions"
            ],
            "future_phase_data": True
        }
        
        return feedback 
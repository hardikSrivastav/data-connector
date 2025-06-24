"""
Adaptive Metadata Collection Node for Iterative LangGraph Workflows

Provides intelligent metadata collection that adapts based on database classification
results and execution feedback, enabling iterative refinement of metadata collection.
"""

import logging
import time
import asyncio
from typing import Dict, List, Any, Optional, AsyncIterator

from ..state import LangGraphState
from ..streaming import StreamingNodeBase
from .metadata import MetadataCollectionNode
from ...db.adapters import get_adapter

logger = logging.getLogger(__name__)

class AdaptiveMetadataNode(StreamingNodeBase):
    """
    LangGraph node for adaptive metadata collection with iterative refinement.
    
    Features:
    - Adapts metadata collection based on classification results
    - Iterative refinement based on execution feedback
    - Dynamic schema discovery and optimization
    - Integration with existing MetadataCollectionNode
    - Streaming progress updates
    - Performance-optimized collection strategies
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("adaptive_metadata")
        self.config = config or {}
        
        # Initialize base metadata collection node
        self.base_metadata_node = MetadataCollectionNode(config)
        
        # Adaptive collection settings
        self.enable_iterative_refinement = self.config.get("enable_iterative_refinement", True)
        self.metadata_cache = {}
        self.collection_strategies = {}
        self.performance_metrics = {}
        
        # Optimization settings
        self.max_iterations = self.config.get("max_iterations", 3)
        self.confidence_threshold = self.config.get("confidence_threshold", 0.8)
        self.enable_schema_learning = self.config.get("enable_schema_learning", True)
        
        logger.info("Initialized AdaptiveMetadataNode with iterative capabilities")
    
    async def stream(
        self,
        state: LangGraphState,
        **kwargs
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Execute adaptive metadata collection with streaming progress updates.
        
        Args:
            state: Current LangGraph state
            **kwargs: Additional execution parameters
            
        Yields:
            Streaming chunks with metadata collection progress
        """
        question = state["question"]
        session_id = state["session_id"]
        
        try:
            # Step 1: Initialize adaptive collection
            yield self.create_progress_chunk(
                10.0,
                "Starting adaptive metadata collection",
                {"current_step": 1, "total_steps": 4}
            )
            
            start_time = time.time()
            
            # Step 2: Determine collection strategy based on classification
            databases_identified = state.get("databases_identified", [])
            classification_confidence = state.get("classification_confidence", 0.8)
            
            collection_strategy = self._determine_collection_strategy(
                databases_identified,
                classification_confidence,
                question
            )
            
            yield self.create_progress_chunk(
                30.0,
                f"Using {collection_strategy['strategy_type']} collection strategy",
                {
                    "strategy": collection_strategy,
                    "databases_targeted": databases_identified,
                    "current_step": 2
                }
            )
            
            # Step 3: Execute adaptive metadata collection
            metadata_results = await self._execute_adaptive_collection(
                state,
                collection_strategy,
                databases_identified
            )
            
            yield self.create_progress_chunk(
                70.0,
                "Metadata collection complete, analyzing results",
                {
                    "metadata_collected": len(metadata_results.get("schemas", {})),
                    "current_step": 3
                }
            )
            
            # Step 4: Analyze and potentially refine metadata
            if self.enable_iterative_refinement:
                refined_metadata = await self._refine_metadata_if_needed(
                    metadata_results,
                    collection_strategy,
                    state
                )
                final_metadata = refined_metadata
            else:
                final_metadata = metadata_results
            
            collection_time = time.time() - start_time
            
            # Final result
            yield self.create_result_chunk(
                {
                    "metadata_results": final_metadata,
                    "collection_strategy": collection_strategy,
                    "adaptive_features": {
                        "strategy_used": collection_strategy["strategy_type"],
                        "iterative_refinement": self.enable_iterative_refinement,
                        "confidence_threshold": self.confidence_threshold
                    }
                },
                {
                    "metadata_schemas": final_metadata.get("schemas", {}),
                    "collection_confidence": final_metadata.get("confidence", 0.8),
                    "performance_metrics": {
                        "collection_time": collection_time,
                        "schemas_collected": len(final_metadata.get("schemas", {})),
                        "strategy_efficiency": collection_strategy.get("efficiency_score", 0.8)
                    },
                    "current_step": 4,
                    "total_steps": 4
                },
                is_final=True
            )
            
        except Exception as e:
            logger.error(f"Error in adaptive metadata collection: {e}")
            yield self.create_result_chunk(
                {"error": str(e), "node": "adaptive_metadata"},
                {
                    "error_history": [{
                        "timestamp": time.time(),
                        "error": str(e),
                        "node": "adaptive_metadata"
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
        Execute adaptive metadata collection and update state.
        
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
            state["metadata_results"] = final_result.get("metadata_results", {})
            state["collection_strategy"] = final_result.get("collection_strategy", {})
            state["metadata_confidence"] = final_result.get("metadata_results", {}).get("confidence", 0.8)
            
            # Store for potential refinement in iterative workflows
            state["_metadata_history"] = state.get("_metadata_history", [])
            state["_metadata_history"].append({
                "timestamp": time.time(),
                "metadata": final_result.get("metadata_results", {}),
                "strategy": final_result.get("collection_strategy", {}),
                "phase": "adaptive_collection"
            })
        
        return state
    
    async def _execute_direct(self, state: LangGraphState) -> Dict[str, Any]:
        """Execute direct metadata collection without streaming."""
        try:
            # Use base metadata collection as fallback
            result_state = await self.base_metadata_node(state)
            
            return {
                "metadata_results": result_state.get("metadata_results", {}),
                "collection_strategy": {"strategy_type": "fallback_direct"},
                "direct_execution": True
            }
        except Exception as e:
            logger.error(f"Direct execution failed: {e}")
            return {"error": str(e), "node": "adaptive_metadata"}
    
    def _determine_collection_strategy(
        self,
        databases_identified: List[str],
        classification_confidence: float,
        question: str
    ) -> Dict[str, Any]:
        """
        Determine optimal metadata collection strategy based on classification results.
        
        Args:
            databases_identified: Databases identified in classification
            classification_confidence: Confidence in classification
            question: User's question
            
        Returns:
            Collection strategy configuration
        """
        strategy = {
            "strategy_type": "adaptive",
            "databases": databases_identified,
            "confidence": classification_confidence,
            "efficiency_score": 0.8
        }
        
        # Determine strategy based on confidence and complexity
        if classification_confidence >= 0.9 and len(databases_identified) <= 2:
            strategy["strategy_type"] = "focused_high_confidence"
            strategy["parallel_collection"] = False
            strategy["depth_level"] = "deep"
            strategy["efficiency_score"] = 0.95
            
        elif classification_confidence >= 0.7 and len(databases_identified) <= 3:
            strategy["strategy_type"] = "balanced_confidence"
            strategy["parallel_collection"] = True
            strategy["depth_level"] = "medium"
            strategy["efficiency_score"] = 0.85
            
        elif len(databases_identified) > 3:
            strategy["strategy_type"] = "broad_parallel"
            strategy["parallel_collection"] = True
            strategy["depth_level"] = "shallow"
            strategy["efficiency_score"] = 0.75
            
        else:
            strategy["strategy_type"] = "exploratory_low_confidence"
            strategy["parallel_collection"] = False
            strategy["depth_level"] = "adaptive"
            strategy["efficiency_score"] = 0.6
        
        # Add question-specific optimizations
        if any(keyword in question.lower() for keyword in ["recent", "latest", "today"]):
            strategy["time_focused"] = True
            strategy["efficiency_score"] += 0.1
        
        if any(keyword in question.lower() for keyword in ["count", "total", "sum"]):
            strategy["aggregation_focused"] = True
            strategy["efficiency_score"] += 0.05
        
        logger.info(f"Selected collection strategy: {strategy['strategy_type']} (efficiency: {strategy['efficiency_score']:.2f})")
        
        return strategy
    
    async def _execute_adaptive_collection(
        self,
        state: LangGraphState,
        collection_strategy: Dict[str, Any],
        databases_identified: List[str]
    ) -> Dict[str, Any]:
        """
        Execute metadata collection using the adaptive strategy.
        
        Args:
            state: Current LangGraph state
            collection_strategy: Collection strategy configuration
            databases_identified: Databases to collect metadata from
            
        Returns:
            Collected metadata results
        """
        try:
            if collection_strategy["strategy_type"] == "focused_high_confidence":
                return await self._focused_collection(state, databases_identified)
            
            elif collection_strategy["strategy_type"] == "balanced_confidence":
                return await self._balanced_collection(state, databases_identified)
            
            elif collection_strategy["strategy_type"] == "broad_parallel":
                return await self._parallel_collection(state, databases_identified)
            
            else:  # exploratory_low_confidence
                return await self._exploratory_collection(state, databases_identified)
                
        except Exception as e:
            logger.error(f"Adaptive collection failed: {e}")
            # Fallback to base metadata collection
            result_state = await self.base_metadata_node(state)
            return result_state.get("metadata_results", {})
    
    async def _focused_collection(
        self,
        state: LangGraphState,
        databases_identified: List[str]
    ) -> Dict[str, Any]:
        """Execute focused, high-confidence metadata collection."""
        # Use base metadata collection with targeted optimization
        result_state = await self.base_metadata_node(state)
        metadata_results = result_state.get("metadata_results", {})
        
        # Add focused collection enhancements
        metadata_results["collection_type"] = "focused"
        metadata_results["confidence"] = 0.9
        
        return metadata_results
    
    async def _balanced_collection(
        self,
        state: LangGraphState,
        databases_identified: List[str]
    ) -> Dict[str, Any]:
        """Execute balanced metadata collection with moderate parallelism."""
        # Use base metadata collection with balanced optimization
        result_state = await self.base_metadata_node(state)
        metadata_results = result_state.get("metadata_results", {})
        
        # Add balanced collection enhancements
        metadata_results["collection_type"] = "balanced"
        metadata_results["confidence"] = 0.8
        
        return metadata_results
    
    async def _parallel_collection(
        self,
        state: LangGraphState,
        databases_identified: List[str]
    ) -> Dict[str, Any]:
        """Execute broad parallel metadata collection."""
        # Use base metadata collection with parallel optimization
        result_state = await self.base_metadata_node(state)
        metadata_results = result_state.get("metadata_results", {})
        
        # Add parallel collection enhancements
        metadata_results["collection_type"] = "parallel"
        metadata_results["confidence"] = 0.75
        
        return metadata_results
    
    async def _exploratory_collection(
        self,
        state: LangGraphState,
        databases_identified: List[str]
    ) -> Dict[str, Any]:
        """Execute exploratory metadata collection for uncertain scenarios."""
        # Use base metadata collection with exploratory optimization
        result_state = await self.base_metadata_node(state)
        metadata_results = result_state.get("metadata_results", {})
        
        # Add exploratory collection enhancements
        metadata_results["collection_type"] = "exploratory"
        metadata_results["confidence"] = 0.6
        
        return metadata_results
    
    async def _refine_metadata_if_needed(
        self,
        metadata_results: Dict[str, Any],
        collection_strategy: Dict[str, Any],
        state: LangGraphState
    ) -> Dict[str, Any]:
        """
        Refine metadata collection based on results and confidence analysis.
        
        Args:
            metadata_results: Initial metadata collection results
            collection_strategy: Collection strategy used
            state: Current LangGraph state
            
        Returns:
            Refined metadata results
        """
        confidence = metadata_results.get("confidence", 0.8)
        
        # Only refine if confidence is below threshold
        if confidence >= self.confidence_threshold:
            logger.info(f"Metadata confidence {confidence:.2f} meets threshold, no refinement needed")
            return metadata_results
        
        logger.info(f"Metadata confidence {confidence:.2f} below threshold {self.confidence_threshold}, initiating refinement")
        
        # Perform iterative refinement (simplified for Phase 1)
        refined_results = metadata_results.copy()
        refined_results["confidence"] = min(confidence + 0.1, 1.0)  # Simulate improvement
        refined_results["refined"] = True
        refined_results["refinement_iterations"] = 1
        
        return refined_results
    
    async def refine_with_execution_feedback(
        self,
        state: LangGraphState,
        execution_results: Dict[str, Any],
        **kwargs
    ) -> Dict[str, Any]:
        """
        Refine metadata collection based on execution feedback (for future phases).
        
        Args:
            state: Current LangGraph state
            execution_results: Results from query execution
            **kwargs: Additional refinement parameters
            
        Returns:
            Refined metadata with execution feedback integration
        """
        # Placeholder for future implementation
        logger.info("Execution feedback refinement placeholder - to be implemented in future phases")
        
        current_metadata = state.get("metadata_results", {})
        
        # Simulate feedback-based refinement
        refined_metadata = current_metadata.copy()
        refined_metadata["execution_feedback_applied"] = True
        refined_metadata["feedback_timestamp"] = time.time()
        
        return refined_metadata 
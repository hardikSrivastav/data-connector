"""
Database Classification Node for Iterative LangGraph Workflows

Provides intelligent database classification with the ability to dynamically refine
classifications based on execution results and metadata discovery.
"""

import logging
import time
from typing import Dict, List, Any, Optional, AsyncIterator, Set

from ..state import LangGraphState
from ..streaming import StreamingNodeBase
from ...db.classifier import DatabaseClassifier
from ...llm.client import get_llm_client, get_classification_client

logger = logging.getLogger(__name__)

class DatabaseClassificationNode(StreamingNodeBase):
    """
    LangGraph node for intelligent database classification with iterative refinement.
    
    Features:
    - Initial classification based on user query
    - Confidence scoring and uncertainty handling
    - Dynamic re-classification based on metadata discovery
    - Integration with existing DatabaseClassifier
    - Streaming progress updates
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("database_classification")
        self.config = config or {}
        
        # Initialize classification clients
        self.llm_client = get_llm_client()
        self.classification_client = get_classification_client()
        
        # Initialize existing classifier for integration
        self.database_classifier = DatabaseClassifier()
        
        # Classification settings
        self.confidence_threshold = self.config.get("confidence_threshold", 0.7)
        self.max_databases = self.config.get("max_databases", 5)
        self.enable_iterative_refinement = self.config.get("enable_iterative_refinement", True)
        
        logger.info("Initialized DatabaseClassificationNode with iterative capabilities")
    
    async def stream(
        self,
        state: LangGraphState,
        **kwargs
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Execute database classification with streaming progress updates.
        
        Args:
            state: Current LangGraph state
            **kwargs: Additional execution parameters
            
        Yields:
            Streaming chunks with classification progress
        """
        question = state["question"]
        session_id = state["session_id"]
        
        try:
            # Step 1: Initial classification
            yield self.create_progress_chunk(
                10.0,
                "Starting database classification",
                {"current_step": 1, "total_steps": 4}
            )
            
            start_time = time.time()
            
            # Get initial classification from existing classifier
            classification_result = await self.database_classifier.classify(question)
            
            initial_databases = [
                source.get("name", source.get("id", "unknown")) 
                for source in classification_result.get("sources", [])
            ]
            
            classification_time = time.time() - start_time
            
            yield self.create_progress_chunk(
                30.0,
                "Initial classification complete",
                {
                    "databases_identified": initial_databases,
                    "confidence_scores": self._extract_confidence_scores(classification_result),
                    "reasoning": classification_result.get("reasoning", ""),
                    "current_step": 2
                },
                {
                    "classified_databases": initial_databases,
                    "classification_confidence": classification_result.get("confidence", 0.8),
                    "time_taken": classification_time
                }
            )
            
            # Step 2: Confidence analysis and uncertainty handling
            yield self.create_progress_chunk(
                50.0,
                "Analyzing classification confidence",
                {"current_step": 3}
            )
            
            start_time = time.time()
            
            # Analyze confidence and identify uncertain areas
            confidence_analysis = await self._analyze_classification_confidence(
                question, 
                classification_result
            )
            
            confidence_time = time.time() - start_time
            
            # Step 3: Iterative refinement if needed
            refined_databases = initial_databases
            refinement_applied = False
            refinement_time = 0
            
            if (confidence_analysis["needs_refinement"] and 
                self.enable_iterative_refinement):
                
                yield self.create_progress_chunk(
                    70.0,
                    "Applying iterative refinement",
                    {"current_step": 4, "refinement_reason": confidence_analysis["refinement_reason"]}
                )
                
                start_time = time.time()
                
                refined_result = await self._apply_iterative_refinement(
                    question,
                    classification_result,
                    confidence_analysis
                )
                
                if refined_result["success"]:
                    refined_databases = refined_result["databases"]
                    refinement_applied = True
                
                refinement_time = time.time() - start_time
                
                yield self.create_progress_chunk(
                    85.0,
                    "Refinement complete",
                    {
                        "refined_databases": refined_databases,
                        "refinement_applied": refinement_applied,
                        "refinement_details": refined_result.get("details", {})
                    },
                    {
                        "refinement_applied": refinement_applied,
                        "time_taken": refinement_time
                    }
                )
            
            # Final result
            yield self.create_result_chunk(
                {
                    "databases_identified": refined_databases,
                    "classification_result": classification_result,
                    "confidence_analysis": confidence_analysis,
                    "refinement_applied": refinement_applied,
                    "classification_metadata": {
                        "initial_databases": initial_databases,
                        "final_databases": refined_databases,
                        "confidence_threshold": self.confidence_threshold,
                        "reasoning": classification_result.get("reasoning", "")
                    }
                },
                {
                    "databases_identified": refined_databases,
                    "classification_confidence": confidence_analysis.get("overall_confidence", 0.8),
                    "current_step": 4,
                    "total_steps": 4,
                    "performance_metrics": {
                        "total_classification_time": classification_time + confidence_time + refinement_time,
                        "classification_time": classification_time,
                        "confidence_time": confidence_time,
                        "refinement_time": refinement_time
                    },
                    "iterative_features": {
                        "refinement_enabled": self.enable_iterative_refinement,
                        "refinement_applied": refinement_applied,
                        "confidence_threshold": self.confidence_threshold
                    }
                },
                is_final=True
            )
            
        except Exception as e:
            logger.error(f"Error in database classification: {e}")
            yield self.create_result_chunk(
                {"error": str(e), "node": "database_classification"},
                {
                    "error_history": [{
                        "timestamp": time.time(),
                        "error": str(e),
                        "node": "database_classification"
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
        Execute classification and update state.
        
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
            state["databases_identified"] = final_result.get("databases_identified", [])
            state["classification_result"] = final_result.get("classification_result", {})
            state["classification_confidence"] = final_result.get("confidence_analysis", {}).get("overall_confidence", 0.8)
            
            # Store for potential re-classification
            state["_classification_history"] = state.get("_classification_history", [])
            state["_classification_history"].append({
                "timestamp": time.time(),
                "databases": final_result.get("databases_identified", []),
                "confidence": final_result.get("confidence_analysis", {}).get("overall_confidence", 0.8),
                "refinement_applied": final_result.get("refinement_applied", False)
            })
        
        return state
    
    async def _execute_direct(self, state: LangGraphState) -> Dict[str, Any]:
        """Direct execution fallback without streaming."""
        try:
            question = state["question"]
            
            # Execute classification directly
            classification_result = await self.database_classifier.classify(question)
            
            databases = [
                source.get("name", source.get("id", "unknown")) 
                for source in classification_result.get("sources", [])
            ]
            
            return {
                "databases_identified": databases,
                "classification_result": classification_result,
                "confidence_analysis": {
                    "overall_confidence": classification_result.get("confidence", 0.8),
                    "needs_refinement": False
                },
                "refinement_applied": False
            }
            
        except Exception as e:
            logger.error(f"Direct classification execution failed: {e}")
            return {"error": str(e), "node": "database_classification"}
    
    def _extract_confidence_scores(self, classification_result: Dict[str, Any]) -> Dict[str, float]:
        """Extract confidence scores for each database."""
        confidence_scores = {}
        
        for source in classification_result.get("sources", []):
            db_name = source.get("name", source.get("id", "unknown"))
            confidence = source.get("confidence", source.get("score", 0.8))
            confidence_scores[db_name] = confidence
        
        return confidence_scores
    
    async def _analyze_classification_confidence(
        self,
        question: str,
        classification_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Analyze classification confidence and determine if refinement is needed.
        
        Args:
            question: Original user question
            classification_result: Initial classification result
            
        Returns:
            Confidence analysis with refinement recommendations
        """
        try:
            sources = classification_result.get("sources", [])
            overall_confidence = classification_result.get("confidence", 0.8)
            
            # Calculate confidence metrics
            confidence_scores = self._extract_confidence_scores(classification_result)
            avg_confidence = sum(confidence_scores.values()) / max(len(confidence_scores), 1)
            min_confidence = min(confidence_scores.values()) if confidence_scores else 0.0
            
            # Determine if refinement is needed
            needs_refinement = (
                overall_confidence < self.confidence_threshold or
                avg_confidence < self.confidence_threshold or
                min_confidence < (self.confidence_threshold - 0.2) or
                len(sources) == 0
            )
            
            # Determine refinement reason
            refinement_reason = "high_confidence"
            if overall_confidence < self.confidence_threshold:
                refinement_reason = "low_overall_confidence"
            elif avg_confidence < self.confidence_threshold:
                refinement_reason = "low_average_confidence"
            elif min_confidence < (self.confidence_threshold - 0.2):
                refinement_reason = "low_minimum_confidence"
            elif len(sources) == 0:
                refinement_reason = "no_databases_identified"
            
            return {
                "overall_confidence": overall_confidence,
                "average_confidence": avg_confidence,
                "minimum_confidence": min_confidence,
                "confidence_scores": confidence_scores,
                "needs_refinement": needs_refinement,
                "refinement_reason": refinement_reason,
                "analysis_details": {
                    "threshold": self.confidence_threshold,
                    "databases_count": len(sources),
                    "confidence_distribution": self._analyze_confidence_distribution(confidence_scores)
                }
            }
            
        except Exception as e:
            logger.error(f"Confidence analysis failed: {e}")
            return {
                "overall_confidence": 0.5,
                "needs_refinement": True,
                "refinement_reason": "analysis_error",
                "error": str(e)
            }
    
    def _analyze_confidence_distribution(self, confidence_scores: Dict[str, float]) -> Dict[str, Any]:
        """Analyze the distribution of confidence scores."""
        if not confidence_scores:
            return {"distribution": "empty"}
        
        values = list(confidence_scores.values())
        
        return {
            "distribution": "analyzed",
            "high_confidence_count": len([v for v in values if v >= 0.8]),
            "medium_confidence_count": len([v for v in values if 0.6 <= v < 0.8]),
            "low_confidence_count": len([v for v in values if v < 0.6]),
            "variance": max(values) - min(values) if values else 0
        }
    
    async def _apply_iterative_refinement(
        self,
        question: str,
        initial_result: Dict[str, Any],
        confidence_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Apply iterative refinement to improve classification accuracy.
        
        Args:
            question: Original user question
            initial_result: Initial classification result
            confidence_analysis: Confidence analysis results
            
        Returns:
            Refined classification result
        """
        try:
            # Use LLM client for enhanced classification
            if self.classification_client and self.classification_client.is_enabled():
                
                # Create enhanced prompt with context
                enhancement_prompt = f"""
                Original Question: {question}
                
                Initial Classification Results:
                {initial_result.get('reasoning', 'No reasoning provided')}
                
                Identified Issues:
                - Confidence Reason: {confidence_analysis.get('refinement_reason', 'unknown')}
                - Overall Confidence: {confidence_analysis.get('overall_confidence', 0.0)}
                - Average Confidence: {confidence_analysis.get('average_confidence', 0.0)}
                
                Please provide an improved database classification that addresses these confidence issues.
                Consider:
                1. Keywords and context that might indicate additional relevant databases
                2. Potential ambiguities in the original question
                3. Cross-database relationships that might be relevant
                
                Return a JSON response with:
                {{
                    "databases": ["list", "of", "database", "names"],
                    "reasoning": "detailed reasoning for the classification",
                    "confidence": 0.95,
                    "improvements": ["what", "was", "improved"]
                }}
                """
                
                # Get refined classification
                refined_response = await self.classification_client.classify_operation(
                    enhancement_prompt,
                    {
                        "operation_type": "database_classification",
                        "refinement": True,
                        "initial_result": initial_result
                    }
                )
                
                if refined_response.get("success", False):
                    return {
                        "success": True,
                        "databases": refined_response.get("databases", []),
                        "reasoning": refined_response.get("reasoning", ""),
                        "confidence": refined_response.get("confidence", 0.8),
                        "details": {
                            "method": "llm_refinement",
                            "improvements": refined_response.get("improvements", [])
                        }
                    }
            
            # Fallback: Rule-based refinement
            return await self._apply_rule_based_refinement(question, initial_result, confidence_analysis)
            
        except Exception as e:
            logger.error(f"Iterative refinement failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "databases": [
                    source.get("name", source.get("id", "unknown")) 
                    for source in initial_result.get("sources", [])
                ]
            }
    
    async def _apply_rule_based_refinement(
        self,
        question: str,
        initial_result: Dict[str, Any],
        confidence_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Apply rule-based refinement as fallback."""
        try:
            question_lower = question.lower()
            initial_databases = [
                source.get("name", source.get("id", "unknown")) 
                for source in initial_result.get("sources", [])
            ]
            
            # Rule-based enhancement
            additional_databases = []
            
            # Check for common patterns that might indicate additional databases
            if any(word in question_lower for word in ["user", "customer", "account"]):
                if "postgres" not in initial_databases:
                    additional_databases.append("postgres")
            
            if any(word in question_lower for word in ["product", "inventory", "order"]):
                if "shopify" not in initial_databases:
                    additional_databases.append("shopify")
            
            if any(word in question_lower for word in ["search", "find", "similar"]):
                if "qdrant" not in initial_databases:
                    additional_databases.append("qdrant")
            
            if any(word in question_lower for word in ["message", "conversation", "chat"]):
                if "slack" not in initial_databases:
                    additional_databases.append("slack")
            
            if any(word in question_lower for word in ["analytics", "traffic", "visitor"]):
                if "ga4" not in initial_databases:
                    additional_databases.append("ga4")
            
            # Combine initial and additional databases
            refined_databases = list(set(initial_databases + additional_databases))
            
            return {
                "success": True,
                "databases": refined_databases,
                "reasoning": f"Applied rule-based refinement, added: {additional_databases}",
                "confidence": min(0.9, confidence_analysis.get("overall_confidence", 0.5) + 0.2),
                "details": {
                    "method": "rule_based_refinement",
                    "added_databases": additional_databases,
                    "original_count": len(initial_databases),
                    "refined_count": len(refined_databases)
                }
            }
            
        except Exception as e:
            logger.error(f"Rule-based refinement failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "databases": [
                    source.get("name", source.get("id", "unknown")) 
                    for source in initial_result.get("sources", [])
                ]
            }
    
    async def reclassify_with_context(
        self,
        state: LangGraphState,
        execution_results: Dict[str, Any],
        **kwargs
    ) -> Dict[str, Any]:
        """
        Re-classify databases based on execution results and discovered metadata.
        
        This method supports the iterative approach by allowing re-classification
        after metadata discovery or partial execution results.
        
        Args:
            state: Current LangGraph state
            execution_results: Results from previous execution attempts
            **kwargs: Additional context
            
        Returns:
            Updated classification result
        """
        try:
            question = state["question"]
            
            # Extract context from execution results
            discovered_metadata = execution_results.get("metadata", {})
            execution_errors = execution_results.get("errors", [])
            partial_results = execution_results.get("partial_results", {})
            
            # Build enhanced context for re-classification
            context = {
                "original_question": question,
                "discovered_metadata": discovered_metadata,
                "execution_errors": execution_errors,
                "partial_results": partial_results,
                "previous_databases": state.get("databases_identified", []),
                "classification_history": state.get("_classification_history", [])
            }
            
            # Use enhanced classification with context
            if self.classification_client and self.classification_client.is_enabled():
                reclassification_result = await self.classification_client.classify_operation(
                    f"Re-classify databases based on execution context: {question}",
                    context
                )
                
                if reclassification_result.get("success", False):
                    new_databases = reclassification_result.get("databases", [])
                    
                    # Update state with new classification
                    state["databases_identified"] = new_databases
                    state["classification_confidence"] = reclassification_result.get("confidence", 0.8)
                    
                    # Track re-classification
                    state["_classification_history"] = state.get("_classification_history", [])
                    state["_classification_history"].append({
                        "timestamp": time.time(),
                        "databases": new_databases,
                        "confidence": reclassification_result.get("confidence", 0.8),
                        "context": "execution_based_reclassification",
                        "trigger": "execution_results"
                    })
                    
                    logger.info(f"Re-classified databases: {new_databases}")
                    
                    return {
                        "success": True,
                        "databases": new_databases,
                        "confidence": reclassification_result.get("confidence", 0.8),
                        "reasoning": reclassification_result.get("reasoning", "Context-based re-classification"),
                        "changes": {
                            "previous": state.get("databases_identified", []),
                            "current": new_databases,
                            "added": list(set(new_databases) - set(state.get("databases_identified", []))),
                            "removed": list(set(state.get("databases_identified", [])) - set(new_databases))
                        }
                    }
            
            # Fallback: no re-classification needed
            return {
                "success": True,
                "databases": state.get("databases_identified", []),
                "confidence": state.get("classification_confidence", 0.8),
                "reasoning": "No re-classification needed based on context",
                "changes": {"no_changes": True}
            }
            
        except Exception as e:
            logger.error(f"Re-classification failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "databases": state.get("databases_identified", [])
            } 
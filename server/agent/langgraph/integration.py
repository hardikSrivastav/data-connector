"""
LangGraph Integration Orchestrator for Ceneca

Main integration module that combines LangGraph capabilities with Ceneca's existing
infrastructure to provide enhanced database querying with advanced orchestration.
"""

import logging
import asyncio
import time
from typing import Dict, List, Any, Optional, AsyncIterator

from .state import HybridStateManager, LangGraphState
from .streaming import StreamingGraphCoordinator
from .graphs.builder import DatabaseDrivenGraphBuilder
from .graphs.bedrock_client import BedrockLangGraphClient
from .nodes.metadata import MetadataCollectionNode
from .nodes.planning import PlanningNode
from .nodes.execution import ExecutionNode
from .nodes.tool_execution_node import ToolExecutionNode

# Import existing components to preserve functionality
from ..tools.state_manager import StateManager, AnalysisState
from ..db.orchestrator.planning_agent import PlanningAgent
from ..config.settings import Settings
# Lazy import to avoid circular dependency
# from ..db.orchestrator.implementation_agent import ImplementationAgent

logger = logging.getLogger(__name__)

class LangGraphIntegrationOrchestrator:
    """
    Main orchestrator that integrates LangGraph capabilities with existing Ceneca infrastructure.
    
    Features:
    - Preserves existing high-performance trivial routing
    - Adds LangGraph orchestration for complex workflows
    - Provides transparent streaming and progress tracking
    - Maintains backward compatibility
    - Supports gradual migration and hybrid operation
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        
        # Initialize settings for tool execution
        self.settings = Settings()
        
        # Initialize tool registry for database adapter tools
        from ..tools.registry import ToolRegistry
        self.tool_registry = ToolRegistry(self.settings)
        
        # Initialize existing components (preserve functionality)
        self.existing_state_manager = StateManager()
        self.existing_planning_agent = PlanningAgent()
        # Lazy import to avoid circular dependency
        self.existing_implementation_agent = None
        
        # Initialize LangGraph components
        self.hybrid_state_manager = HybridStateManager()
        self.streaming_coordinator = StreamingGraphCoordinator(self.hybrid_state_manager)
        self.graph_builder = DatabaseDrivenGraphBuilder(config)
        self.llm_client = BedrockLangGraphClient(config.get("llm_config"))
        
        # Initialize tool execution node for database adapter tools
        self.tool_execution_node = ToolExecutionNode(self.settings)
        
        # Integration settings
        self.use_langgraph_for_complex = self.config.get("use_langgraph_for_complex", True)
        self.complexity_threshold = self.config.get("complexity_threshold", 5)
        self.preserve_trivial_routing = self.config.get("preserve_trivial_routing", True)
        
        # Performance monitoring
        self.execution_stats = {
            "traditional_executions": 0,
            "langgraph_executions": 0,
            "hybrid_executions": 0,
            "performance_improvements": []
        }
        
        logger.info(f"Initialized LangGraph Integration Orchestrator with complexity threshold: {self.complexity_threshold}")
    
    def _get_implementation_agent(self):
        """Lazily initialize implementation agent to avoid circular imports."""
        if self.existing_implementation_agent is None:
            from ..db.orchestrator.implementation_agent import ImplementationAgent
            self.existing_implementation_agent = ImplementationAgent()
        return self.existing_implementation_agent
    
    async def process_query(
        self,
        question: str,
        session_id: str,
        databases_available: Optional[List[str]] = None,
        force_langgraph: bool = False,
        stream_callback: Optional[AsyncIterator] = None
    ) -> Dict[str, Any]:
        """
        Process a database query using optimal routing between traditional and LangGraph workflows.
        
        Args:
            question: User's question
            session_id: Session identifier
            databases_available: Available database types
            force_langgraph: Force use of LangGraph workflow
            stream_callback: Optional streaming callback
            
        Returns:
            Query results with execution metadata
        """
        start_time = time.time()
        
        try:
            # Step 1: Analyze query complexity and routing decision
            routing_decision = await self._determine_routing(
                question,
                databases_available or [],
                force_langgraph
            )
            
            logger.info(f"Routing decision: {routing_decision['method']} (complexity: {routing_decision['complexity']})")
            
            # Step 2: Execute based on routing decision
            if routing_decision["method"] == "traditional":
                result = await self._execute_traditional_workflow(
                    question,
                    session_id,
                    databases_available,
                    stream_callback
                )
                self.execution_stats["traditional_executions"] += 1
                
            elif routing_decision["method"] == "langgraph":
                result = await self._execute_langgraph_workflow(
                    question,
                    session_id,
                    databases_available,
                    routing_decision,
                    stream_callback
                )
                self.execution_stats["langgraph_executions"] += 1
                
            else:  # hybrid
                result = await self._execute_hybrid_workflow(
                    question,
                    session_id,
                    databases_available,
                    routing_decision,
                    stream_callback
                )
                self.execution_stats["hybrid_executions"] += 1
            
            # Step 3: Add execution metadata
            execution_time = time.time() - start_time
            result["execution_metadata"] = {
                "routing_method": routing_decision["method"],
                "complexity_analysis": routing_decision,
                "execution_time": execution_time,
                "session_id": session_id,
                "timestamp": time.time()
            }
            
            # Step 4: Track performance improvements
            await self._track_performance(routing_decision, execution_time, result)
            
            return result
            
        except Exception as e:
            logger.error(f"Query processing failed: {e}")
            return {
                "error": str(e),
                "session_id": session_id,
                "question": question,
                "execution_metadata": {
                    "routing_method": "error",
                    "execution_time": time.time() - start_time,
                    "error_details": str(e)
                }
            }
    
    async def _determine_routing(
        self,
        question: str,
        databases_available: List[str],
        force_langgraph: bool = False
    ) -> Dict[str, Any]:
        """
        Determine optimal routing between traditional and LangGraph workflows.
        
        Args:
            question: User's question
            databases_available: Available databases
            force_langgraph: Force LangGraph usage
            
        Returns:
            Routing decision with complexity analysis
        """
        if force_langgraph:
            return {
                "method": "langgraph",
                "complexity": 10,
                "reason": "Forced LangGraph execution",
                "confidence": 1.0
            }
        
        try:
            # Use LLM to analyze query complexity
            complexity_analysis = await self.llm_client.generate_graph_plan(
                question,
                databases_available,
                {},  # Schema will be collected later
                {"analysis_type": "routing"}
            )
            
            if "error" in complexity_analysis:
                # Fallback to rule-based analysis
                return self._fallback_routing_analysis(question, databases_available)
            
            complexity = complexity_analysis.get("complexity", 5)
            cross_database = complexity_analysis.get("cross_database_needed", False)
            parallelization = complexity_analysis.get("parallelization_level", "low")
            
            # Routing logic
            if not self.use_langgraph_for_complex:
                return {"method": "traditional", "complexity": complexity, "reason": "LangGraph disabled"}
            
            if complexity <= self.complexity_threshold and not cross_database:
                return {
                    "method": "traditional",
                    "complexity": complexity,
                    "reason": f"Below complexity threshold ({self.complexity_threshold})",
                    "confidence": 0.8
                }
            
            if complexity >= 8 or parallelization == "high":
                return {
                    "method": "langgraph",
                    "complexity": complexity,
                    "reason": "High complexity requires advanced orchestration",
                    "confidence": 0.9
                }
            
            # Medium complexity - use hybrid approach
            return {
                "method": "hybrid",
                "complexity": complexity,
                "reason": "Medium complexity benefits from hybrid approach",
                "confidence": 0.7
            }
            
        except Exception as e:
            logger.warning(f"Routing analysis failed: {e}")
            return self._fallback_routing_analysis(question, databases_available)
    
    def _fallback_routing_analysis(
        self,
        question: str,
        databases_available: List[str]
    ) -> Dict[str, Any]:
        """Fallback rule-based routing analysis."""
        question_lower = question.lower()
        
        # Simple complexity heuristics
        complexity = 3
        
        if any(word in question_lower for word in ["analyze", "compare", "correlate", "trend", "pattern"]):
            complexity += 3
        
        if any(word in question_lower for word in ["join", "combine", "merge", "cross-reference"]):
            complexity += 2
        
        if len(databases_available) > 2:
            complexity += 2
        
        if len(question.split()) > 20:
            complexity += 1
        
        complexity = min(complexity, 10)
        
        if complexity <= self.complexity_threshold:
            method = "traditional"
        elif complexity >= 8:
            method = "langgraph"
        else:
            method = "hybrid"
        
        return {
            "method": method,
            "complexity": complexity,
            "reason": "Rule-based analysis (LLM unavailable)",
            "confidence": 0.6
        }
    
    async def _execute_traditional_workflow(
        self,
        question: str,
        session_id: str,
        databases_available: List[str],
        stream_callback: Optional[AsyncIterator] = None
    ) -> Dict[str, Any]:
        """Execute using traditional Ceneca workflow."""
        logger.info("Executing traditional workflow")
        
        try:
            # Use existing state manager and agents - fix constructor parameters
            state = AnalysisState(
                session_id=session_id,
                user_question=question
            )
            
            # Set available databases in metadata
            if databases_available:
                state.metadata = getattr(state, 'metadata', {})
                state.metadata["databases_identified"] = databases_available
            
            # Execute planning - fix method name
            query_plan, planning_metadata = await self.existing_planning_agent.create_plan(
                question=question,
                optimize=False
            )
            
            # Check if planning succeeded
            if query_plan is None or (hasattr(query_plan, 'error') and query_plan.error):
                error_msg = getattr(query_plan, 'error', "Planning failed")
                return {"error": error_msg, "workflow": "traditional"}
            
            # Execute implementation - pass the QueryPlan object directly
            implementation_agent = self._get_implementation_agent()
            execution_result = await implementation_agent.execute_plan(
                query_plan,  # Pass the QueryPlan object, not a dictionary
                user_question=question
            )
            
            # Convert QueryPlan to dict for result compatibility
            if hasattr(query_plan, 'to_dict'):
                planning_result = query_plan.to_dict()
            else:
                planning_result = {"operations": [], "metadata": planning_metadata}
            
            return {
                "workflow": "traditional",
                "planning_result": planning_result,
                "execution_result": execution_result,
                "final_result": execution_result.get("final_result", {}),
                "operation_results": execution_result.get("results", {})
            }
            
        except Exception as e:
            logger.error(f"Traditional workflow failed: {e}")
            return {"error": str(e), "workflow": "traditional"}
    
    async def _execute_langgraph_workflow(
        self,
        question: str,
        session_id: str,
        databases_available: List[str],
        routing_decision: Dict[str, Any],
        stream_callback: Optional[AsyncIterator] = None
    ) -> Dict[str, Any]:
        """Execute using pure LangGraph workflow."""
        logger.info("Executing LangGraph workflow")
        
        try:
            # Build optimal graph
            graph_result = await self.graph_builder.build_optimal_graph(
                question,
                databases_available or [],
                context={"routing_decision": routing_decision}
            )
            
            if "error" in graph_result:
                return {"error": graph_result["error"], "workflow": "langgraph"}
            
            # Execute graph
            executable_graph = graph_result["executable_graph"]
            execution_result = await executable_graph(session_id)
            
            return {
                "workflow": "langgraph",
                "graph_specification": graph_result["graph_specification"],
                "execution_result": execution_result,
                "final_result": execution_result.get("final_state", {}),
                "node_results": execution_result.get("node_results", {})
            }
            
        except Exception as e:
            logger.error(f"LangGraph workflow failed: {e}")
            return {"error": str(e), "workflow": "langgraph"}
    
    async def _execute_hybrid_workflow(
        self,
        question: str,
        session_id: str,
        databases_available: List[str],
        routing_decision: Dict[str, Any],
        stream_callback: Optional[AsyncIterator] = None
    ) -> Dict[str, Any]:
        """Execute using hybrid workflow (LangGraph orchestration with traditional components)."""
        logger.info("Executing hybrid workflow")
        
        try:
            # Create hybrid state that bridges both systems - fix parameter name
            hybrid_state = await self.hybrid_state_manager.create_graph_session(
                question,
                workflow_type="hybrid",
                migrate_from_legacy=True
            )
            
            graph_state = await self.hybrid_state_manager.get_graph_state(hybrid_state)
            if not graph_state:
                raise ValueError("Failed to create hybrid state")
            
            # Set available databases
            graph_state["databases_identified"] = databases_available or []
            
            # Step 1: Use LangGraph metadata collection
            metadata_node = MetadataCollectionNode()
            metadata_result = await metadata_node(graph_state)
            
            # Step 2: Use traditional planning agent (wrapped in LangGraph node)
            planning_node = PlanningNode()
            planning_result = await planning_node(metadata_result)
            
            # Step 3: Tool execution with LangGraph
            logger.info("Step 3: Executing tool execution with LangGraph")
            
            tool_execution_node = ToolExecutionNode(self.settings)
            
            # Pass schema metadata to tool execution node
            schema_metadata = metadata_result.get("schema_metadata", {})
            tool_execution_node.set_schema_metadata(schema_metadata)
            
            # Handle case where schema_metadata is a list instead of dict
            if isinstance(schema_metadata, list):
                logger.info(f"Passed schema metadata list to tool execution node: {len(schema_metadata)} items")
                # Convert list to dict for logging
                metadata_keys = [item.get('db_type', 'unknown') for item in schema_metadata if isinstance(item, dict)]
                logger.info(f"Schema metadata database types: {set(metadata_keys)}")
            else:
                logger.info(f"Passed schema metadata to tool execution node: {list(schema_metadata.keys()) if schema_metadata else 'empty'}")
            
            tool_execution_result = await tool_execution_node.execute_node({
                "user_query": planning_result.get("user_query", question),
                **planning_result
            })
            
            # Step 4: If tool execution succeeded, use those results
            if tool_execution_result.get("success", False):
                logger.info("ToolExecutionNode succeeded, using tool results")
                
                # Format tool results for compatibility with existing system
                operation_results = {}
                execution_results = tool_execution_result.get("execution_results", [])
                
                for i, result in enumerate(execution_results):
                    if result.success:
                        operation_results[f"tool_operation_{i}"] = {
                            "result": result.result,
                            "metadata": {
                                "tool_id": getattr(result, 'tool_call', {}).get('tool_id') if hasattr(result, 'tool_call') else result.tool_id if hasattr(result, 'tool_id') else "unknown",
                                "success": True,
                                "execution_time": getattr(result, 'execution_time', 0.0)
                            }
                        }
                    else:
                        operation_results[f"tool_operation_{i}"] = {
                            "error": result.error,
                            "metadata": {
                                "tool_id": getattr(result, 'tool_call', {}).get('tool_id') if hasattr(result, 'tool_call') else result.tool_id if hasattr(result, 'tool_id') else "unknown",
                                "success": False
                            }
                        }
                
                # Create final result from tool execution
                final_result = {
                    "data": [],
                    "formatted_result": tool_execution_result.get("response", "Tool execution completed successfully.")
                }
                
                # Aggregate data from all successful operations
                for op_result in operation_results.values():
                    if "result" in op_result and op_result["result"]:
                        # Handle different result types
                        result_data = op_result["result"]
                        if isinstance(result_data, list):
                            final_result["data"].extend(result_data)
                        elif isinstance(result_data, dict):
                            final_result["data"].append(result_data)
                        else:
                            final_result["data"].append({"result": result_data})
                
                return {
                    "workflow": "hybrid",
                    "metadata_collection": metadata_result.get("schema_metadata", {}),
                    "planning_result": planning_result.get("execution_plan", {}),
                    "tool_execution_result": tool_execution_result,
                    "final_result": final_result,
                    "operation_results": operation_results,
                    "hybrid_advantages": [
                        "Enhanced parallelism from LangGraph",
                        "Database adapter tools integration",
                        "Intelligent tool selection and execution",
                        "Preserved existing business logic",
                        "Improved error handling and streaming"
                    ]
                }
            
            else:
                # Step 5: Tool execution failed - return error for debugging
                logger.error("ToolExecutionNode failed, no fallback - debugging tool execution")
                
                return {
                    "workflow": "hybrid",
                    "metadata_collection": metadata_result.get("schema_metadata", {}),
                    "planning_result": planning_result.get("execution_plan", {}),
                    "tool_execution_result": tool_execution_result,
                    "error": "Tool execution failed - debugging mode",
                    "debug_info": {
                        "tool_execution_success": tool_execution_result.get("success", False),
                        "tool_execution_errors": tool_execution_result.get("errors", []),
                        "execution_results": tool_execution_result.get("execution_results", [])
                    },
                    "hybrid_advantages": [
                        "Enhanced parallelism from LangGraph",
                        "Database adapter tools integration",
                        "Intelligent tool selection and execution",
                        "No traditional fallback - debugging mode"
                    ]
                }
            
        except Exception as e:
            logger.error(f"Hybrid workflow failed: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            
            # Fallback to traditional workflow
            logger.info("Falling back to traditional workflow")
            return await self._execute_traditional_workflow(
                question,
                session_id,
                databases_available,
                stream_callback
            )
    
    async def _track_performance(
        self,
        routing_decision: Dict[str, Any],
        execution_time: float,
        result: Dict[str, Any]
    ):
        """Track performance metrics for optimization."""
        try:
            performance_data = {
                "method": routing_decision["method"],
                "complexity": routing_decision["complexity"],
                "execution_time": execution_time,
                "success": "error" not in result,
                "timestamp": time.time()
            }
            
            # Add to performance history
            self.execution_stats["performance_improvements"].append(performance_data)
            
            # Keep only recent history (last 100 executions)
            if len(self.execution_stats["performance_improvements"]) > 100:
                self.execution_stats["performance_improvements"] = \
                    self.execution_stats["performance_improvements"][-100:]
            
        except Exception as e:
            logger.warning(f"Performance tracking failed: {e}")
    
    async def optimize_future_queries(self) -> Dict[str, Any]:
        """
        Analyze performance history to optimize future query routing.
        
        Returns:
            Optimization recommendations
        """
        try:
            performance_history = self.execution_stats["performance_improvements"]
            
            if len(performance_history) < 10:
                return {"message": "Insufficient data for optimization"}
            
            # Analyze performance by method
            method_performance = {}
            for record in performance_history:
                method = record["method"]
                if method not in method_performance:
                    method_performance[method] = {"times": [], "success_rate": 0, "count": 0}
                
                method_performance[method]["times"].append(record["execution_time"])
                method_performance[method]["count"] += 1
                if record["success"]:
                    method_performance[method]["success_rate"] += 1
            
            # Calculate averages
            recommendations = []
            for method, data in method_performance.items():
                avg_time = sum(data["times"]) / len(data["times"])
                success_rate = data["success_rate"] / data["count"]
                
                method_performance[method]["avg_time"] = avg_time
                method_performance[method]["success_rate"] = success_rate
                
                if success_rate < 0.8:
                    recommendations.append(f"Consider fallback improvements for {method} method")
                
                if avg_time > 60:
                    recommendations.append(f"Optimize {method} method for better performance")
            
            # Use LLM for intelligent optimization recommendations
            optimization_analysis = await self.llm_client.optimize_graph_execution(
                {"current_performance": method_performance},
                {"optimization_goal": "improve_routing_decisions"}
            )
            
            return {
                "performance_analysis": method_performance,
                "recommendations": recommendations,
                "llm_analysis": optimization_analysis,
                "total_executions": sum(self.execution_stats[key] for key in 
                                      ["traditional_executions", "langgraph_executions", "hybrid_executions"])
            }
            
        except Exception as e:
            logger.error(f"Optimization analysis failed: {e}")
            return {"error": str(e)}
    
    def get_integration_status(self) -> Dict[str, Any]:
        """Get current status of the LangGraph integration."""
        return {
            "integration_active": True,
            "complexity_threshold": self.complexity_threshold,
            "langgraph_enabled": self.use_langgraph_for_complex,
            "trivial_routing_preserved": self.preserve_trivial_routing,
            "execution_statistics": self.execution_stats,
            "components_status": {
                "hybrid_state_manager": "active",
                "streaming_coordinator": "active",
                "graph_builder": "active",
                "bedrock_client": self.llm_client.get_client_status(),
                "existing_agents": "preserved"
            }
        }
    
    async def migrate_to_full_langgraph(
        self,
        migration_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Migrate to full LangGraph usage with fallback preservation.
        
        Args:
            migration_config: Configuration for migration process
            
        Returns:
            Migration status and recommendations
        """
        config = migration_config or {}
        
        try:
            # Analyze current performance to determine migration readiness
            optimization_analysis = await self.optimize_future_queries()
            
            if "error" in optimization_analysis:
                return {
                    "migration_ready": False,
                    "reason": "Performance analysis failed",
                    "recommendation": "Fix performance tracking before migration"
                }
            
            # Check LangGraph performance vs traditional
            performance_data = optimization_analysis.get("performance_analysis", {})
            
            langgraph_perf = performance_data.get("langgraph", {})
            traditional_perf = performance_data.get("traditional", {})
            
            if not langgraph_perf or not traditional_perf:
                return {
                    "migration_ready": False,
                    "reason": "Insufficient performance comparison data",
                    "recommendation": "Run more queries to gather performance data"
                }
            
            # Calculate migration readiness score
            langgraph_success = langgraph_perf.get("success_rate", 0)
            langgraph_time = langgraph_perf.get("avg_time", float('inf'))
            traditional_time = traditional_perf.get("avg_time", float('inf'))
            
            readiness_score = 0
            if langgraph_success >= 0.9:
                readiness_score += 40
            if langgraph_time <= traditional_time * 1.2:  # Within 20% of traditional performance
                readiness_score += 30
            if self.execution_stats["langgraph_executions"] >= 50:
                readiness_score += 30
            
            migration_ready = readiness_score >= 70
            
            return {
                "migration_ready": migration_ready,
                "readiness_score": readiness_score,
                "performance_comparison": {
                    "langgraph": langgraph_perf,
                    "traditional": traditional_perf
                },
                "recommendation": (
                    "Ready for migration - LangGraph is performing well" if migration_ready
                    else "Continue hybrid operation to gather more performance data"
                ),
                "migration_steps": [
                    "Increase complexity_threshold to route more queries to LangGraph",
                    "Monitor performance for 1 week",
                    "Gradually disable traditional routing",
                    "Maintain fallback capabilities"
                ] if migration_ready else []
            }
            
        except Exception as e:
            logger.error(f"Migration analysis failed: {e}")
            return {
                "migration_ready": False,
                "error": str(e),
                "recommendation": "Fix integration issues before considering migration"
            } 
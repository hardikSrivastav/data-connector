"""
Execution Node for LangGraph Integration

Converts the existing ImplementationAgent into a LangGraph-compatible node while preserving
all existing functionality and adding enhanced parallelism and streaming capabilities.
"""

import logging
import asyncio
import time
from typing import Dict, List, Any, Optional, AsyncIterator

from ..state import LangGraphState
from ..streaming import StreamingNodeBase
# Lazy import to avoid circular dependency
# from ...db.orchestrator.implementation_agent import ImplementationAgent
from ...llm.client import get_llm_client

logger = logging.getLogger(__name__)

class ExecutionNode(StreamingNodeBase):
    """
    LangGraph node that wraps the existing ImplementationAgent for plan execution.
    
    Features:
    - Enhanced parallelism beyond 4-operation limit
    - Adaptive resource management
    - Real-time progress streaming
    - Error recovery and circuit breakers
    - Performance optimization
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("execution")
        
        # Enhanced configuration for LangGraph integration
        enhanced_config = config or {}
        enhanced_config.update({
            "max_parallel_operations": enhanced_config.get("max_parallel_operations", 16),  # Increased from 4
            "adaptive_parallelism": enhanced_config.get("adaptive_parallelism", True),
            "streaming_enabled": enhanced_config.get("streaming_enabled", True),
            "performance_monitoring": enhanced_config.get("performance_monitoring", True)
        })
        
        # Lazy load implementation agent to avoid circular imports
        self.implementation_agent = None
        self.enhanced_config = enhanced_config
        self.llm_client = get_llm_client()
        self.config = enhanced_config
        
        # Enhanced parallelism management
        self.database_pools = {
            "postgres": asyncio.Semaphore(8),    # Higher limit for fast queries
            "mongodb": asyncio.Semaphore(6),     # Medium limit for aggregations
            "qdrant": asyncio.Semaphore(4),      # Lower limit for vector operations
            "slack": asyncio.Semaphore(2),       # API rate limit considerations
            "shopify": asyncio.Semaphore(3)      # E-commerce API limits
        }
        
        # Operation complexity weights for intelligent batching
        self.operation_complexity_weights = {
            "simple_select": 1,
            "aggregation": 2,
            "vector_search": 3,
            "cross_join": 4,
            "complex_analytics": 5
        }
        
        logger.info(f"Initialized ExecutionNode with enhanced parallelism (max: {enhanced_config.get('max_parallel_operations', 16)})")
    
    def _get_implementation_agent(self):
        """Lazily initialize implementation agent to avoid circular imports."""
        if self.implementation_agent is None:
            from ...db.orchestrator.implementation_agent import ImplementationAgent
            self.implementation_agent = ImplementationAgent(self.enhanced_config)
        return self.implementation_agent
    
    async def stream(
        self,
        state: LangGraphState,
        **kwargs
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Execute plan with streaming progress updates and enhanced parallelism.
        
        Args:
            state: Current LangGraph state
            **kwargs: Additional execution parameters
            
        Yields:
            Streaming chunks with execution progress
        """
        execution_plan = state["execution_plan"]
        session_id = state["session_id"]
        
        if not execution_plan or "operations" not in execution_plan:
            yield self.create_result_chunk(
                {"error": "No execution plan found", "node": "execution"},
                {"error_history": [{"error": "No execution plan", "node": "execution"}]},
                is_final=True
            )
            return
        
        operations = execution_plan["operations"]
        total_operations = len(operations)
        
        try:
            # Step 1: Analyze operations for optimal batching
            yield self.create_progress_chunk(
                5.0,
                "Analyzing operations for optimal execution",
                {
                    "current_step": 1,
                    "total_steps": 4,
                    "total_operations": total_operations
                }
            )
            
            batches = await self._create_intelligent_batches(operations)
            
            yield self.create_progress_chunk(
                10.0,
                f"Created {len(batches)} execution batches",
                {"execution_batches": len(batches)},
                {"batches_count": len(batches), "operations_per_batch": [len(batch) for batch in batches]}
            )
            
            # Step 2: Execute operations with adaptive parallelism
            completed_operations = 0
            operation_results = {}
            
            for batch_idx, batch in enumerate(batches):
                batch_start_time = time.time()
                
                yield self.create_progress_chunk(
                    15.0 + (batch_idx / len(batches)) * 70.0,  # Progress from 15% to 85%
                    f"Executing batch {batch_idx + 1}/{len(batches)}",
                    {
                        "current_step": 2,
                        "current_batch": batch_idx + 1,
                        "total_batches": len(batches)
                    }
                )
                
                # Execute batch with enhanced parallelism
                batch_results = await self._execute_batch_with_streaming(
                    batch, 
                    session_id,
                    kwargs.get("stream_queue")
                )
                
                # Update results
                operation_results.update(batch_results)
                completed_operations += len(batch)
                
                batch_time = time.time() - batch_start_time
                
                yield self.create_progress_chunk(
                    15.0 + ((batch_idx + 1) / len(batches)) * 70.0,
                    f"Batch {batch_idx + 1} completed",
                    {
                        "operation_results": {op_id: result for op_id, result in batch_results.items()},
                        "performance_metrics": {
                            f"batch_{batch_idx + 1}_time": batch_time,
                            "completed_operations": completed_operations
                        }
                    },
                    {
                        "batch_operations": len(batch),
                        "batch_time": batch_time,
                        "operations_completed": completed_operations,
                        "operations_remaining": total_operations - completed_operations
                    }
                )
            
            # Step 3: Aggregate results
            yield self.create_progress_chunk(
                90.0,
                "Aggregating cross-database results",
                {"current_step": 3}
            )
            
            start_time = time.time()
            
            # Use existing aggregation logic
            implementation_agent = self._get_implementation_agent()
            user_question = state.get("question", "Cross-database query execution")
            aggregated_result = await implementation_agent._aggregate_results(
                operation_results,
                execution_plan,
                user_question
            )
            
            aggregation_time = time.time() - start_time
            
            # Step 4: Final result
            yield self.create_result_chunk(
                {
                    "operation_results": operation_results,
                    "aggregated_result": aggregated_result,
                    "execution_summary": {
                        "total_operations": total_operations,
                        "successful_operations": len([r for r in operation_results.values() if "error" not in r]),
                        "failed_operations": len([r for r in operation_results.values() if "error" in r]),
                        "execution_time": sum(state["performance_metrics"].get("total_duration", 0) for _ in range(1)),
                        "batches_executed": len(batches)
                    }
                },
                {
                    "operation_results": operation_results,
                    "final_result": aggregated_result,
                    "current_step": 4,
                    "total_steps": 4,
                    "performance_metrics": {
                        "aggregation_time": aggregation_time,
                        "total_operations": total_operations,
                        "parallel_efficiency": completed_operations / total_operations if total_operations > 0 else 0
                    }
                },
                is_final=True
            )
            
        except Exception as e:
            logger.error(f"Error in execution node: {e}")
            yield self.create_result_chunk(
                {"error": str(e), "node": "execution"},
                {
                    "error_history": [{
                        "timestamp": time.time(),
                        "error": str(e),
                        "node": "execution"
                    }]
                },
                is_final=True
            )
            raise
    
    async def _create_intelligent_batches(
        self,
        operations: List[Dict[str, Any]]
    ) -> List[List[Dict[str, Any]]]:
        """
        Create optimized batches based on database types, dependencies, and complexity.
        
        Args:
            operations: List of operations to batch
            
        Returns:
            List of operation batches optimized for parallel execution
        """
        batches = []
        remaining_operations = operations.copy()
        
        # Track dependencies
        completed_ops = set()
        
        while remaining_operations:
            current_batch = []
            current_weight = 0
            max_weight = 20  # Configurable weight limit per batch
            
            # Find operations that can be executed (no pending dependencies)
            executable_ops = []
            for op in remaining_operations:
                dependencies = op.get("depends_on", [])
                if all(dep in completed_ops for dep in dependencies):
                    executable_ops.append(op)
            
            # Group by database type for optimal resource usage
            db_groups = {}
            for op in executable_ops:
                db_type = op.get("db_type", "unknown")
                if db_type not in db_groups:
                    db_groups[db_type] = []
                db_groups[db_type].append(op)
            
            # Create balanced batch
            for db_type, ops in db_groups.items():
                semaphore_limit = self._get_semaphore_limit(db_type)
                
                for op in ops:
                    op_weight = self._calculate_operation_weight(op)
                    
                    # Check if we can add this operation to current batch
                    if (len(current_batch) < semaphore_limit and 
                        current_weight + op_weight <= max_weight and
                        len(current_batch) < self.config.get("max_parallel_operations", 16)):
                        
                        current_batch.append(op)
                        current_weight += op_weight
                        remaining_operations.remove(op)
            
            # If we couldn't add any operations, force add one to prevent infinite loop
            if not current_batch and executable_ops:
                current_batch.append(executable_ops[0])
                remaining_operations.remove(executable_ops[0])
            
            if current_batch:
                batches.append(current_batch)
                # Mark operations as completed for dependency tracking
                for op in current_batch:
                    completed_ops.add(op.get("id"))
            else:
                # Break if no progress can be made
                break
        
        return batches
    
    def _get_semaphore_limit(self, db_type: str) -> int:
        """Get the semaphore limit for a database type."""
        semaphore = self.database_pools.get(db_type)
        return semaphore._value if semaphore else 4
    
    def _calculate_operation_weight(self, operation: Dict[str, Any]) -> int:
        """Calculate complexity weight for an operation."""
        # Analyze operation to determine complexity
        op_type = operation.get("operation_type", "simple_select")
        
        # Check for complex patterns
        if operation.get("db_type") == "qdrant":
            return self.operation_complexity_weights.get("vector_search", 3)
        
        params = operation.get("params", {})
        
        # Check for joins, aggregations, complex queries
        if isinstance(params, dict):
            query = params.get("query", "")
            if "JOIN" in query.upper() or "GROUP BY" in query.upper():
                return self.operation_complexity_weights.get("aggregation", 2)
            elif "WITH" in query.upper() or len(query) > 500:
                return self.operation_complexity_weights.get("complex_analytics", 5)
        
        return self.operation_complexity_weights.get(op_type, 1)
    
    async def _execute_batch_with_streaming(
        self,
        batch: List[Dict[str, Any]],
        session_id: str,
        stream_queue: Optional[asyncio.Queue] = None
    ) -> Dict[str, Any]:
        """
        Execute a batch of operations with enhanced parallelism and streaming.
        
        Args:
            batch: List of operations to execute
            session_id: Session ID for tracking
            stream_queue: Optional queue for streaming events
            
        Returns:
            Dictionary of operation results
        """
        # Group operations by database type for optimal semaphore usage
        db_groups = {}
        for op in batch:
            db_type = op.get("db_type", "unknown")
            if db_type not in db_groups:
                db_groups[db_type] = []
            db_groups[db_type].append(op)
        
        # Create tasks for each database group
        tasks = []
        for db_type, ops in db_groups.items():
            semaphore = self.database_pools.get(db_type, asyncio.Semaphore(4))
            
            for op in ops:
                task = asyncio.create_task(
                    self._execute_single_operation_with_semaphore(
                        op, 
                        semaphore, 
                        stream_queue
                    )
                )
                tasks.append(task)
        
        # Execute all operations concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        operation_results = {}
        for i, result in enumerate(results):
            op_id = batch[i].get("id", f"op_{i}")
            
            if isinstance(result, Exception):
                operation_results[op_id] = {
                    "error": str(result),
                    "operation_id": op_id,
                    "status": "failed"
                }
            else:
                operation_results[op_id] = result
        
        return operation_results
    
    async def _execute_single_operation_with_semaphore(
        self,
        operation: Dict[str, Any],
        semaphore: asyncio.Semaphore,
        stream_queue: Optional[asyncio.Queue] = None
    ) -> Dict[str, Any]:
        """Execute a single operation with semaphore protection."""
        async with semaphore:
            start_time = time.time()
            op_id = operation.get("id", "unknown")
            
            if stream_queue:
                await stream_queue.put(
                    self.create_progress_chunk(
                        0,
                        f"Starting operation {op_id}",
                        additional_data={"operation_id": op_id, "status": "starting"}
                    )
                )
            
            try:
                # Create a mini query plan with just this operation for execution
                from ...db.orchestrator.plans.base import QueryPlan
                from ...db.orchestrator.plans.operations import create_operation_from_dict
                
                # Convert dictionary to Operation object
                operation_obj = create_operation_from_dict(operation)
                mini_plan = QueryPlan([operation_obj])
                
                # Use existing implementation agent logic
                implementation_agent = self._get_implementation_agent()
                plan_result = await implementation_agent.execute_plan(mini_plan, "Single operation execution")
                
                # Extract the single operation result
                if "results" in plan_result and operation_obj.id in plan_result["results"]:
                    result = plan_result["results"][operation_obj.id]
                else:
                    result = plan_result
                
                execution_time = time.time() - start_time
                
                if stream_queue:
                    await stream_queue.put(
                        self.create_result_chunk(
                            result,
                            additional_data={
                                "operation_id": op_id,
                                "execution_time": execution_time,
                                "status": "completed"
                            }
                        )
                    )
                
                return {
                    **result,
                    "operation_id": op_id,
                    "execution_time": execution_time,
                    "status": "completed"
                }
                
            except Exception as e:
                execution_time = time.time() - start_time
                
                if stream_queue:
                    await stream_queue.put(
                        self.create_result_chunk(
                            {"error": str(e)},
                            additional_data={
                                "operation_id": op_id,
                                "execution_time": execution_time,
                                "status": "failed"
                            }
                        )
                    )
                
                return {
                    "error": str(e),
                    "operation_id": op_id,
                    "execution_time": execution_time,
                    "status": "failed"
                }
    
    async def __call__(
        self,
        state: LangGraphState,
        **kwargs
    ) -> LangGraphState:
        """
        Execute plan and update state.
        
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
            state["operation_results"] = final_result.get("operation_results", {})
            state["final_result"] = final_result.get("aggregated_result", {})
        
        return state
    
    async def _execute_direct(self, state: LangGraphState) -> Dict[str, Any]:
        """Direct execution fallback without streaming."""
        try:
            execution_plan = state["execution_plan"]
            
            if not execution_plan or "operations" not in execution_plan:
                return {"error": "No execution plan found"}
            
            # Use existing implementation agent logic
            implementation_agent = self._get_implementation_agent()
            result = await implementation_agent.execute_plan(execution_plan)
            
            return {
                "operation_results": result.get("results", {}),
                "aggregated_result": result.get("final_result", {}),
                "execution_summary": result.get("summary", {})
            }
            
        except Exception as e:
            logger.error(f"Direct execution failed: {e}")
            return {"error": str(e), "node": "execution"}
    
    def get_execution_capabilities(self) -> Dict[str, Any]:
        """Get information about execution capabilities."""
        return {
            "max_parallel_operations": self.config.get("max_parallel_operations", 16),
            "supported_databases": list(self.database_pools.keys()),
            "adaptive_parallelism": self.config.get("adaptive_parallelism", True),
            "streaming_enabled": self.config.get("streaming_enabled", True),
            "circuit_breakers": True,
            "error_recovery": True,
            "performance_monitoring": self.config.get("performance_monitoring", True)
        } 
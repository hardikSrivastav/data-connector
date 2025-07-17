"""
Adaptive Parallelism Manager for LangGraph Integration

This module implements intelligent parallelism scaling that goes beyond the current 
4-operation limit by using database-specific semaphores and operation complexity weighting.
"""

import logging
import asyncio
import time
from typing import Dict, List, Any, Optional, Set, Tuple
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class OperationComplexity(Enum):
    """Operation complexity levels for intelligent batching"""
    SIMPLE = 1      # Simple SELECT, basic queries
    MEDIUM = 2      # Aggregations, basic joins
    COMPLEX = 3     # Vector searches, complex joins
    HEAVY = 4       # Cross-database joins, large aggregations

@dataclass
class Operation:
    """Enhanced operation with complexity metadata"""
    id: str
    db_type: str
    operation_type: str
    complexity: OperationComplexity
    estimated_duration: float
    dependencies: List[str]
    params: Dict[str, Any]
    priority: int = 1

class AdaptiveParallelismManager:
    """
    Dynamically scales parallelism based on resource availability and operation types.
    
    Key improvements over the current 4-operation limit:
    - Database-specific semaphores (postgres: 8, mongodb: 6, qdrant: 4, etc.)
    - Operation complexity weighting for intelligent batching
    - Adaptive resource allocation based on system performance
    - Real-time performance monitoring and adjustment
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        
        # Database-specific parallelism limits (enhanced from current 4-operation limit)
        self.database_pools = {
            "postgres": asyncio.Semaphore(self.config.get("postgres_limit", 8)),    # Higher limit for fast queries
            "postgresql": asyncio.Semaphore(self.config.get("postgres_limit", 8)),  # Alias
            "mongodb": asyncio.Semaphore(self.config.get("mongodb_limit", 6)),      # Medium limit for aggregations
            "mongo": asyncio.Semaphore(self.config.get("mongodb_limit", 6)),        # Alias
            "qdrant": asyncio.Semaphore(self.config.get("qdrant_limit", 4)),        # Lower limit for vector operations
            "slack": asyncio.Semaphore(self.config.get("slack_limit", 2)),          # API rate limit considerations
            "shopify": asyncio.Semaphore(self.config.get("shopify_limit", 2)),      # API rate limit considerations
            "ga4": asyncio.Semaphore(self.config.get("ga4_limit", 1)),              # Very conservative for analytics API
        }
        
        # Operation complexity weights for intelligent batching
        self.complexity_weights = {
            OperationComplexity.SIMPLE: 1,
            OperationComplexity.MEDIUM: 2,
            OperationComplexity.COMPLEX: 3,
            OperationComplexity.HEAVY: 4
        }
        
        # Global limits
        self.max_total_weight = self.config.get("max_total_weight", 24)  # 6x increase from current limit
        self.max_concurrent_operations = self.config.get("max_concurrent_operations", 16)  # 4x increase
        
        # Performance tracking
        self.performance_history = {}
        self.operation_metrics = {}
        self.adaptive_adjustments = {}
        
        # Real-time monitoring
        self.active_operations = {}
        self.batch_performance = []
        
        logger.info(f"Initialized AdaptiveParallelismManager with enhanced limits:")
        logger.info(f"  Database limits: {dict((k, v._value) for k, v in self.database_pools.items())}")
        logger.info(f"  Max total weight: {self.max_total_weight}")
        logger.info(f"  Max concurrent operations: {self.max_concurrent_operations}")
    
    async def execute_parallel_operations(
        self, 
        operations: List[Operation],
        execution_callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """
        Execute operations with intelligent parallelism limits.
        
        Args:
            operations: List of operations to execute
            execution_callback: Optional callback for executing individual operations
            
        Returns:
            Dictionary of operation results keyed by operation ID
        """
        start_time = time.time()
        
        logger.info(f"🚀 Starting parallel execution of {len(operations)} operations")
        logger.info(f"📊 Operation breakdown: {self._analyze_operation_distribution(operations)}")
        
        # Group operations by database type and analyze dependencies
        grouped_ops = self._group_by_database(operations)
        dependency_graph = self._build_dependency_graph(operations)
        
        # Create weighted batches that respect both parallelism and complexity limits
        execution_batches = self._create_weighted_batches(grouped_ops, dependency_graph)
        
        logger.info(f"📦 Created {len(execution_batches)} execution batches")
        for i, batch in enumerate(execution_batches):
            batch_weight = sum(self.complexity_weights[op.complexity] for ops in batch.values() for op in ops)
            logger.info(f"  Batch {i+1}: {len(sum(batch.values(), []))} operations, weight: {batch_weight}")
        
        results = {}
        failed_operations = []
        
        # Execute all ready operations in true parallel fashion respecting dependencies
        results, failed_operations = await self._execute_with_true_parallelism(
            operations, execution_callback, dependency_graph
        )
        
        total_duration = time.time() - start_time
        
        # Log final results
        logger.info(f"🎯 Parallel execution completed:")
        logger.info(f"  Total duration: {total_duration:.2f}s")
        logger.info(f"  Successful operations: {len(results)}")
        logger.info(f"  Failed operations: {len(failed_operations)}")
        logger.info(f"  Success rate: {len(results)/(len(results)+len(failed_operations))*100:.1f}%")
        
        # Record batch performance for monitoring (even though we use dynamic batching)
        self.batch_performance.append({
            "batch_idx": 0,
            "duration": total_duration,
            "operation_count": len(operations),
            "success_rate": len(results) / (len(results) + len(failed_operations)) if (len(results) + len(failed_operations)) > 0 else 0
        })
        
        # Perform adaptive adjustments based on performance
        await self._perform_adaptive_adjustments()
        
        return {
            "results": results,
            "failed_operations": failed_operations,
            "execution_metrics": {
                "total_duration": total_duration,
                "batch_count": 1,  # True parallelism uses dynamic batching
                "success_rate": len(results) / (len(results) + len(failed_operations)) if (len(results) + len(failed_operations)) > 0 else 0,
                "operations_per_second": len(operations) / total_duration if total_duration > 0 else 0,
                "parallelism_achieved": len(operations) / total_duration if total_duration > 0 else 0,
                "max_concurrent_operations": self.max_concurrent_operations
            }
        }
    
    async def _execute_batch(
        self, 
        batch: Dict[str, List[Operation]], 
        execution_callback: Optional[callable],
        batch_idx: int
    ) -> Tuple[Dict[str, Any], List[str]]:
        """
        Execute a single batch with database-specific parallelism limits.
        
        Args:
            batch: Dictionary mapping database types to lists of operations
            execution_callback: Function to execute individual operations
            batch_idx: Index of the current batch
            
        Returns:
            Tuple of (successful_results, failed_operation_ids)
        """
        batch_tasks = []
        
        # Create tasks for each operation with appropriate semaphore
        for db_type, operations in batch.items():
            semaphore = self.database_pools.get(db_type.lower())
            if not semaphore:
                logger.warning(f"⚠️ No semaphore configured for database type: {db_type}, using default")
                semaphore = asyncio.Semaphore(2)  # Conservative default
            
            for operation in operations:
                task = asyncio.create_task(
                    self._execute_with_semaphore(
                        operation, 
                        semaphore, 
                        execution_callback,
                        batch_idx
                    )
                )
                batch_tasks.append(task)
        
        # Wait for all operations in the batch to complete
        batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
        
        # Separate successful results from failures
        successful_results = {}
        failed_operations = []
        
        for i, result in enumerate(batch_results):
            if isinstance(result, Exception):
                # Operation failed
                operation_id = batch_tasks[i].get_name() if hasattr(batch_tasks[i], 'get_name') else f"operation_{i}"
                failed_operations.append(operation_id)
                logger.error(f"❌ Operation {operation_id} failed: {result}")
            elif isinstance(result, dict) and "operation_id" in result:
                # Operation succeeded
                successful_results[result["operation_id"]] = result
            else:
                logger.warning(f"⚠️ Unexpected result format: {result}")
        
        return successful_results, failed_operations
    
    async def _execute_with_true_parallelism(
        self,
        operations: List[Operation],
        execution_callback: Optional[callable],
        dependency_graph: Dict[str, Set[str]]
    ) -> Tuple[Dict[str, Any], List[str]]:
        """
        Execute operations with true parallelism, respecting dependencies and database limits.
        
        This method executes all ready operations immediately instead of waiting for 
        artificial batch boundaries, achieving much better parallelism.
        
        Args:
            operations: List of all operations to execute
            execution_callback: Function to execute individual operations
            dependency_graph: Operation dependencies
            
        Returns:
            Tuple of (successful_results, failed_operation_ids)
        """
        results = {}
        failed_operations = []
        completed_ops = set()
        active_tasks = {}  # operation_id -> task
        
        # Create operation lookup
        op_lookup = {op.id: op for op in operations}
        
        logger.info(f"🚀 Starting true parallel execution with dependency resolution")
        
        while len(completed_ops) < len(operations):
            # Find operations that are ready to execute (dependencies satisfied)
            ready_ops = []
            for operation in operations:
                if (operation.id not in completed_ops and 
                    operation.id not in active_tasks and
                    dependency_graph.get(operation.id, set()).issubset(completed_ops)):
                    ready_ops.append(operation)
            
            # Start tasks for ready operations (respecting database limits)
            for operation in ready_ops:
                semaphore = self.database_pools.get(operation.db_type.lower())
                if not semaphore:
                    logger.warning(f"⚠️ No semaphore for {operation.db_type}, using default")
                    semaphore = asyncio.Semaphore(2)
                
                # Check if we can start this operation (semaphore available)
                if semaphore._value > 0 or len(active_tasks) < self.max_concurrent_operations:
                    task = asyncio.create_task(
                        self._execute_with_semaphore(
                            operation, semaphore, execution_callback, 0
                        )
                    )
                    active_tasks[operation.id] = task
                    logger.debug(f"🚀 Started operation {operation.id} ({operation.db_type})")
            
            # Wait for at least one task to complete if we have active tasks
            if active_tasks:
                # Wait for any task to complete
                done_tasks, pending_tasks = await asyncio.wait(
                    active_tasks.values(), 
                    return_when=asyncio.FIRST_COMPLETED
                )
                
                # Process completed tasks
                for task in done_tasks:
                    # Find which operation this task belongs to
                    completed_op_id = None
                    for op_id, active_task in active_tasks.items():
                        if active_task == task:
                            completed_op_id = op_id
                            break
                    
                    if completed_op_id:
                        try:
                            result = await task
                            results[completed_op_id] = result
                            completed_ops.add(completed_op_id)
                            logger.debug(f"✅ Completed operation {completed_op_id}")
                        except Exception as e:
                            failed_operations.append(completed_op_id)
                            completed_ops.add(completed_op_id)  # Mark as done even if failed
                            logger.error(f"❌ Failed operation {completed_op_id}: {e}")
                        
                        # Remove from active tasks
                        del active_tasks[completed_op_id]
            else:
                # No active tasks and no ready operations - check for deadlock
                if len(completed_ops) < len(operations):
                    logger.warning("⚠️ Possible deadlock detected - starting remaining operations")
                    # Start any remaining operations to break potential deadlock
                    for operation in operations:
                        if operation.id not in completed_ops and operation.id not in active_tasks:
                            semaphore = self.database_pools.get(operation.db_type.lower(), asyncio.Semaphore(1))
                            task = asyncio.create_task(
                                self._execute_with_semaphore(operation, semaphore, execution_callback, 0)
                            )
                            active_tasks[operation.id] = task
                            break
                else:
                    break
        
        # Wait for any remaining active tasks
        if active_tasks:
            remaining_results = await asyncio.gather(*active_tasks.values(), return_exceptions=True)
            for i, (op_id, result) in enumerate(zip(active_tasks.keys(), remaining_results)):
                if isinstance(result, Exception):
                    failed_operations.append(op_id)
                    logger.error(f"❌ Failed operation {op_id}: {result}")
                else:
                    results[op_id] = result
                    logger.debug(f"✅ Completed operation {op_id}")
        
        logger.info(f"🎯 True parallel execution completed: {len(results)} successful, {len(failed_operations)} failed")
        return results, failed_operations
    
    async def _execute_with_semaphore(
        self, 
        operation: Operation, 
        semaphore: asyncio.Semaphore,
        execution_callback: Optional[callable],
        batch_idx: int
    ) -> Dict[str, Any]:
        """
        Execute a single operation with semaphore protection.
        
        Args:
            operation: Operation to execute
            semaphore: Database-specific semaphore for rate limiting
            execution_callback: Function to execute the operation
            batch_idx: Index of the current batch
            
        Returns:
            Operation result dictionary
        """
        async with semaphore:
            start_time = time.time()
            self.active_operations[operation.id] = {
                "start_time": start_time,
                "db_type": operation.db_type,
                "complexity": operation.complexity,
                "batch_idx": batch_idx
            }
            
            try:
                logger.debug(f"🔄 Executing operation {operation.id} on {operation.db_type}")
                
                if execution_callback:
                    # Use provided callback for execution
                    result = await execution_callback(operation)
                else:
                    # Default execution (for testing)
                    result = await self._default_operation_execution(operation)
                
                duration = time.time() - start_time
                
                # Record performance metrics
                self._record_operation_metrics(operation, duration, True)
                
                logger.debug(f"✅ Operation {operation.id} completed in {duration:.2f}s")
                
                return {
                    "operation_id": operation.id,
                    "result": result,
                    "duration": duration,
                    "db_type": operation.db_type,
                    "complexity": operation.complexity.name
                }
                
            except Exception as e:
                duration = time.time() - start_time
                self._record_operation_metrics(operation, duration, False)
                
                logger.error(f"❌ Operation {operation.id} failed after {duration:.2f}s: {e}")
                raise
                
            finally:
                # Clean up active operation tracking
                self.active_operations.pop(operation.id, None)
    
    async def _default_operation_execution(self, operation: Operation) -> Dict[str, Any]:
        """
        Default operation execution for testing purposes.
        
        Args:
            operation: Operation to execute
            
        Returns:
            Mock result dictionary
        """
        # Simulate operation duration based on complexity
        base_duration = {
            OperationComplexity.SIMPLE: 0.1,
            OperationComplexity.MEDIUM: 0.3,
            OperationComplexity.COMPLEX: 0.8,
            OperationComplexity.HEAVY: 1.5
        }
        
        duration = base_duration.get(operation.complexity, 0.5)
        await asyncio.sleep(duration)
        
        return {
            "data": f"Mock result for {operation.operation_type} on {operation.db_type}",
            "row_count": 100,
            "execution_time": duration
        }
    
    def _group_by_database(self, operations: List[Operation]) -> Dict[str, List[Operation]]:
        """
        Group operations by database type.
        
        Args:
            operations: List of operations to group
            
        Returns:
            Dictionary mapping database types to lists of operations
        """
        grouped = {}
        for operation in operations:
            db_type = operation.db_type.lower()
            if db_type not in grouped:
                grouped[db_type] = []
            grouped[db_type].append(operation)
        
        return grouped
    
    def _build_dependency_graph(self, operations: List[Operation]) -> Dict[str, Set[str]]:
        """
        Build dependency graph for operations.
        
        Args:
            operations: List of operations with dependencies
            
        Returns:
            Dictionary mapping operation IDs to sets of dependency IDs
        """
        dependency_graph = {}
        for operation in operations:
            dependency_graph[operation.id] = set(operation.dependencies)
        
        return dependency_graph
    
    def _create_weighted_batches(
        self, 
        grouped_ops: Dict[str, List[Operation]], 
        dependency_graph: Dict[str, Set[str]]
    ) -> List[Dict[str, List[Operation]]]:
        """
        Create batches that respect both parallelism and complexity limits.
        
        Args:
            grouped_ops: Operations grouped by database type
            dependency_graph: Operation dependencies
            
        Returns:
            List of execution batches
        """
        batches = []
        remaining_ops = {db_type: ops.copy() for db_type, ops in grouped_ops.items()}
        completed_ops = set()
        
        while any(remaining_ops.values()):
            current_batch = {}
            current_weight = 0
            current_op_count = 0
            
            # Find operations that can be executed (dependencies satisfied)
            ready_ops = []
            for db_type, operations in remaining_ops.items():
                for operation in operations:
                    dependencies = dependency_graph.get(operation.id, set())
                    if dependencies.issubset(completed_ops):
                        ready_ops.append((db_type, operation))
            
            # If no operations are ready, we have a circular dependency or error
            if not ready_ops:
                logger.warning("⚠️ No operations ready for execution - possible circular dependency")
                # Add remaining operations anyway to avoid infinite loop
                for db_type, operations in remaining_ops.items():
                    if operations:
                        ready_ops.extend([(db_type, op) for op in operations])
                break
            
            # Sort ready operations by priority and complexity (lighter operations first for better packing)
            ready_ops.sort(key=lambda x: (x[1].priority, self.complexity_weights[x[1].complexity]))
            
            # Add operations to current batch within limits, but be more aggressive about packing
            for db_type, operation in ready_ops:
                op_weight = self.complexity_weights[operation.complexity]
                
                # Check database-specific limits
                db_ops_in_batch = len(current_batch.get(db_type, []))
                db_limit = self.database_pools.get(db_type.lower(), asyncio.Semaphore(2))._value
                
                # Check if adding this operation would exceed limits
                if (current_weight + op_weight <= self.max_total_weight and 
                    current_op_count < self.max_concurrent_operations and
                    db_ops_in_batch < db_limit):
                    
                    # Add to current batch
                    if db_type not in current_batch:
                        current_batch[db_type] = []
                    current_batch[db_type].append(operation)
                    current_weight += op_weight
                    current_op_count += 1
                    
                    # Remove from remaining operations
                    remaining_ops[db_type].remove(operation)
                    completed_ops.add(operation.id)
            
            # Add current batch if it has operations
            if current_batch:
                batches.append(current_batch)
            else:
                # If we couldn't add any operations, something is wrong
                logger.error("❌ Could not create any batches from remaining operations")
                break
        
        return batches
    
    def _analyze_operation_distribution(self, operations: List[Operation]) -> Dict[str, Any]:
        """
        Analyze the distribution of operations for logging purposes.
        
        Args:
            operations: List of operations to analyze
            
        Returns:
            Analysis dictionary
        """
        db_counts = {}
        complexity_counts = {}
        
        for operation in operations:
            # Count by database type
            db_type = operation.db_type.lower()
            db_counts[db_type] = db_counts.get(db_type, 0) + 1
            
            # Count by complexity
            complexity = operation.complexity.name
            complexity_counts[complexity] = complexity_counts.get(complexity, 0) + 1
        
        return {
            "by_database": db_counts,
            "by_complexity": complexity_counts,
            "total_operations": len(operations)
        }
    
    def _record_operation_metrics(self, operation: Operation, duration: float, success: bool):
        """
        Record metrics for an operation execution.
        
        Args:
            operation: The executed operation
            duration: Execution duration in seconds
            success: Whether the operation succeeded
        """
        key = f"{operation.db_type}_{operation.complexity.name}"
        
        if key not in self.operation_metrics:
            self.operation_metrics[key] = {
                "total_executions": 0,
                "successful_executions": 0,
                "total_duration": 0.0,
                "avg_duration": 0.0,
                "success_rate": 0.0
            }
        
        metrics = self.operation_metrics[key]
        metrics["total_executions"] += 1
        metrics["total_duration"] += duration
        
        if success:
            metrics["successful_executions"] += 1
        
        metrics["avg_duration"] = metrics["total_duration"] / metrics["total_executions"]
        metrics["success_rate"] = metrics["successful_executions"] / metrics["total_executions"]
    
    async def _perform_adaptive_adjustments(self):
        """
        Perform adaptive adjustments based on recent performance data.
        """
        if len(self.batch_performance) < 3:
            return  # Need more data for meaningful adjustments
        
        recent_batches = self.batch_performance[-5:]  # Last 5 batches
        avg_success_rate = sum(batch["success_rate"] for batch in recent_batches) / len(recent_batches)
        avg_duration = sum(batch["duration"] for batch in recent_batches) / len(recent_batches)
        
        logger.info(f"📈 Performance analysis: avg_success_rate={avg_success_rate:.2f}, avg_duration={avg_duration:.2f}s")
        
        # Adjust limits based on performance
        if avg_success_rate > 0.95 and avg_duration < 2.0:
            # Performance is good, can increase limits slightly
            self._increase_limits()
        elif avg_success_rate < 0.80 or avg_duration > 10.0:
            # Performance is poor, decrease limits
            self._decrease_limits()
    
    def _increase_limits(self):
        """Increase parallelism limits when performance is good."""
        for db_type, semaphore in self.database_pools.items():
            current_limit = semaphore._value
            new_limit = min(current_limit + 1, current_limit * 1.2)  # Max 20% increase
            if new_limit > current_limit:
                self.database_pools[db_type] = asyncio.Semaphore(int(new_limit))
                logger.info(f"📈 Increased {db_type} limit: {current_limit} → {int(new_limit)}")
    
    def _decrease_limits(self):
        """Decrease parallelism limits when performance is poor."""
        for db_type, semaphore in self.database_pools.items():
            current_limit = semaphore._value
            new_limit = max(1, current_limit - 1)  # Never go below 1
            if new_limit < current_limit:
                self.database_pools[db_type] = asyncio.Semaphore(int(new_limit))
                logger.info(f"📉 Decreased {db_type} limit: {current_limit} → {int(new_limit)}")
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive performance statistics.
        
        Returns:
            Dictionary containing performance metrics
        """
        return {
            "database_limits": {db: sem._value for db, sem in self.database_pools.items()},
            "operation_metrics": self.operation_metrics,
            "batch_performance": self.batch_performance,
            "active_operations": len(self.active_operations),
            "total_weight_limit": self.max_total_weight,
            "max_concurrent_operations": self.max_concurrent_operations
        }
    
    def reset_performance_tracking(self):
        """Reset all performance tracking data."""
        self.performance_history.clear()
        self.operation_metrics.clear()
        self.batch_performance.clear()
        self.active_operations.clear()
        logger.info("🔄 Performance tracking data reset") 
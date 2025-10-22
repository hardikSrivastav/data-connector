"""
Simple test to demonstrate enhanced parallelism capabilities

This test focuses on showing the clear performance improvement of the AdaptiveParallelismManager
over the current 4-operation limit without complex dependencies.
"""

import asyncio
import logging
import time
import sys
import os
from typing import Dict, List, Any

# Add the server directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'server'))

from server.agent.langgraph.parallelism import (
    AdaptiveParallelismManager, 
    Operation, 
    OperationComplexity
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def mock_database_operation(operation: Operation) -> Dict[str, Any]:
    """Simulate a database operation with realistic timing"""
    
    # Simulate different database response times
    base_times = {
        "postgres": 0.2,
        "mongodb": 0.3,
        "qdrant": 0.5,
        "slack": 0.8
    }
    
    execution_time = base_times.get(operation.db_type, 0.3)
    
    logger.info(f"🔄 Starting {operation.id} on {operation.db_type} (expected {execution_time}s)")
    await asyncio.sleep(execution_time)
    logger.info(f"✅ Completed {operation.id}")
    
    return {
        "operation_id": operation.id,
        "data": f"Result from {operation.db_type}",
        "rows": 100,
        "execution_time": execution_time
    }

async def test_parallelism_improvement():
    """Test the enhanced parallelism vs current 4-operation limit"""
    
    logger.info("🚀 ENHANCED PARALLELISM TEST")
    logger.info("=" * 60)
    
    # Create enhanced parallelism manager
    enhanced_manager = AdaptiveParallelismManager({
        "postgres_limit": 8,      # 2x improvement
        "mongodb_limit": 6,       # 1.5x improvement  
        "qdrant_limit": 4,        # Same as current total limit
        "slack_limit": 2,         # Conservative for API
        "max_concurrent_operations": 16  # 4x improvement
    })
    
    # Create 12 simple operations (3x current limit) with NO dependencies
    operations = []
    db_types = ["postgres", "mongodb", "qdrant", "slack"]
    
    for i in range(12):
        db_type = db_types[i % len(db_types)]
        operation = Operation(
            id=f"op_{i+1:03d}",
            db_type=db_type,
            operation_type="simple_query",
            complexity=OperationComplexity.SIMPLE,  # All simple to avoid complexity batching
            estimated_duration=0.3,
            dependencies=[],  # NO DEPENDENCIES for pure parallelism test
            params={"query": f"SELECT * FROM table_{i+1}"},
            priority=1
        )
        operations.append(operation)
    
    logger.info(f"📋 Created {len(operations)} operations across {len(set(op.db_type for op in operations))} databases")
    for db_type in db_types:
        count = len([op for op in operations if op.db_type == db_type])
        logger.info(f"  {db_type}: {count} operations")
    
    # Test 1: Enhanced Parallelism Manager
    logger.info("\n⚡ Testing Enhanced Parallelism Manager (16 concurrent)")
    start_time = time.time()
    
    enhanced_results = await enhanced_manager.execute_parallel_operations(
        operations,
        mock_database_operation
    )
    
    enhanced_duration = time.time() - start_time
    
    logger.info(f"✅ Enhanced parallelism results:")
    logger.info(f"  Duration: {enhanced_duration:.2f}s")
    logger.info(f"  Successful operations: {len(enhanced_results['results'])}/{len(operations)}")
    logger.info(f"  Operations per second: {enhanced_results['execution_metrics']['operations_per_second']:.2f}")
    logger.info(f"  Batches created: {enhanced_results['execution_metrics']['batch_count']}")
    
    # Test 2: Simulate Current 4-Operation Limit
    logger.info("\n🐌 Simulating Current 4-Operation Limit")
    start_time = time.time()
    
    # Process in sequential batches of 4
    current_results = []
    for i in range(0, len(operations), 4):
        batch = operations[i:i+4]
        logger.info(f"  Processing batch {i//4 + 1}: operations {i+1}-{min(i+4, len(operations))}")
        
        batch_tasks = [mock_database_operation(op) for op in batch]
        batch_results = await asyncio.gather(*batch_tasks)
        current_results.extend(batch_results)
    
    current_duration = time.time() - start_time
    
    logger.info(f"✅ Current limit simulation results:")
    logger.info(f"  Duration: {current_duration:.2f}s")
    logger.info(f"  Successful operations: {len(current_results)}/{len(operations)}")
    
    # Calculate and display improvement
    improvement_factor = current_duration / enhanced_duration if enhanced_duration > 0 else 0
    time_saved = current_duration - enhanced_duration
    
    logger.info("\n🎯 PERFORMANCE COMPARISON:")
    logger.info(f"  Enhanced Parallelism: {enhanced_duration:.2f}s")
    logger.info(f"  Current 4-Op Limit:   {current_duration:.2f}s")
    logger.info(f"  Speed Improvement:    {improvement_factor:.2f}x faster")
    logger.info(f"  Time Saved:           {time_saved:.2f}s ({time_saved/current_duration*100:.1f}% reduction)")
    
    # Performance stats
    stats = enhanced_manager.get_performance_stats()
    logger.info(f"\n📊 Enhanced Manager Configuration:")
    for db_type, limit in stats["database_limits"].items():
        if db_type in db_types:
            logger.info(f"  {db_type}: {limit} concurrent operations")
    
    # Validate results
    assert len(enhanced_results['results']) == len(operations), "All operations should succeed"
    assert len(current_results) == len(operations), "All operations should succeed in current simulation"
    assert enhanced_duration < current_duration, "Enhanced parallelism should be faster"
    assert improvement_factor >= 1.4, f"Should be at least 40% faster, got {improvement_factor:.2f}x"
    
    logger.info("\n🎉 ENHANCED PARALLELISM TEST PASSED!")
    logger.info(f"✅ Successfully demonstrated {improvement_factor:.2f}x performance improvement")
    logger.info(f"✅ Scaled from 4 to {stats['max_concurrent_operations']} concurrent operations")
    
    return {
        "enhanced_duration": enhanced_duration,
        "current_duration": current_duration,
        "improvement_factor": improvement_factor,
        "time_saved": time_saved
    }

if __name__ == "__main__":
    asyncio.run(test_parallelism_improvement()) 
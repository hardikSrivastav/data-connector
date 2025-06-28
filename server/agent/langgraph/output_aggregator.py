"""
LangGraph Output Aggregation System

This module provides a comprehensive system for extracting, aggregating, and 
presenting all the different outputs from the iterative LangGraph workflow:

1. Raw Data Outputs - Query results, API responses, file contents
2. Execution Plans - Planning decisions, dependency graphs, optimization choices
3. Tool Execution Trace - Each tool call, parameters, outputs, timing
4. Final Synthesis - The processed and formatted final response
5. Metadata & Performance - Timing, metrics, error handling, user context

This enables full observability and auditability of the entire workflow.
"""

import logging
import json
import time
import os
from typing import Dict, List, Any, Optional, Union, AsyncIterator
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict
from enum import Enum
import uuid

from .state import LangGraphState
from ..tools.state_manager import StateManager, AnalysisState

logger = logging.getLogger(__name__)

# Constants for file storage
AGGREGATOR_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "aggregator")

class OutputType(Enum):
    """Types of outputs we can capture from the workflow."""
    RAW_DATA = "raw_data"
    EXECUTION_PLAN = "execution_plan"
    TOOL_EXECUTION = "tool_execution"
    FINAL_SYNTHESIS = "final_synthesis"
    PERFORMANCE_METRICS = "performance_metrics"
    ERROR_TRACKING = "error_tracking"
    USER_CONTEXT = "user_context"
    STREAMING_EVENT = "streaming_event"

@dataclass
class WorkflowOutput:
    """Single output capture from the workflow."""
    output_id: str
    output_type: OutputType
    timestamp: datetime
    session_id: str
    node_id: Optional[str] = None
    content: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    size_bytes: Optional[int] = None
    processing_time_ms: Optional[float] = None

@dataclass
class RawDataOutput:
    """Structured representation of raw data outputs."""
    source: str  # e.g., "postgres", "mongodb", "api_call"
    query: Optional[str] = None
    rows: List[Dict[str, Any]] = field(default_factory=list)
    row_count: int = 0
    columns: List[str] = field(default_factory=list)
    schema_info: Dict[str, Any] = field(default_factory=dict)
    execution_time_ms: float = 0.0
    is_sample: bool = False
    sample_size: Optional[int] = None

@dataclass
class ExecutionPlanOutput:
    """Structured representation of execution plans."""
    plan_id: str
    strategy: str  # e.g., "sequential", "parallel", "hybrid"
    operations: List[Dict[str, Any]] = field(default_factory=list)
    dependencies: Dict[str, List[str]] = field(default_factory=dict)
    optimizations_applied: List[str] = field(default_factory=list)
    estimated_duration_ms: Optional[float] = None
    actual_duration_ms: Optional[float] = None
    success_rate: float = 0.0

@dataclass
class ToolExecutionOutput:
    """Structured representation of tool execution."""
    tool_id: str
    call_id: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    result: Any = None
    success: bool = False
    error_message: Optional[str] = None
    execution_time_ms: float = 0.0
    memory_used_mb: Optional[float] = None
    retry_count: int = 0
    dependencies_resolved: List[str] = field(default_factory=list)

@dataclass
class FinalSynthesisOutput:
    """Structured representation of final synthesis."""
    response_text: str
    confidence_score: float = 0.0
    sources_used: List[str] = field(default_factory=list)
    synthesis_method: str = "llm_based"
    quality_metrics: Dict[str, float] = field(default_factory=dict)
    alternative_responses: List[str] = field(default_factory=list)

@dataclass
class PerformanceMetrics:
    """Comprehensive performance metrics."""
    total_duration_ms: float = 0.0
    node_durations: Dict[str, float] = field(default_factory=dict)
    database_query_time: float = 0.0
    llm_processing_time: float = 0.0
    parallel_efficiency: Optional[float] = None
    cache_hit_rate: float = 0.0
    memory_peak_mb: Optional[float] = None
    operations_executed: int = 0
    operations_successful: int = 0

class WorkflowOutputAggregator:
    """
    Main aggregator that captures all outputs from the LangGraph workflow
    and provides unified access to them.
    """
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.outputs: List[WorkflowOutput] = []
        self.output_index: Dict[OutputType, List[WorkflowOutput]] = {
            output_type: [] for output_type in OutputType
        }
        self.finalized = False  # Track if workflow has been finalized
        
        # Performance tracking
        self.start_time = time.time()
        self.workflow_metadata = {
            "workflow_type": "iterative_langgraph",
            "session_id": session_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "version": "1.0.0"
        }
        
        # ✅ ENHANCEMENT: Load existing data if available
        self._load_from_disk()
        
        logger.info(f"🔄 [OUTPUT_AGGREGATOR] Initialized for session: {session_id}")
    
    def _get_aggregator_file_path(self) -> str:
        """Get the file path for storing aggregator data."""
        # Ensure aggregator directory exists
        os.makedirs(AGGREGATOR_DATA_DIR, exist_ok=True)
        return os.path.join(AGGREGATOR_DATA_DIR, f"{self.session_id}_aggregator.json")
    
    def _save_to_disk(self):
        """Save aggregator data to disk for persistence."""
        logger.info(f"🔧 [DEBUG_SAVE] _save_to_disk() called for session {self.session_id} with {len(self.outputs)} outputs")
        
        try:
            file_path = self._get_aggregator_file_path()
            logger.info(f"🔧 [DEBUG_SAVE] File path: {file_path}")
            
            # Convert outputs to serializable format
            serializable_data = {
                "session_id": self.session_id,
                "workflow_metadata": self.workflow_metadata,
                "start_time": self.start_time,
                "finalized": self.finalized,
                "outputs": [
                    {
                        "output_id": output.output_id,
                        "output_type": output.output_type.value,
                        "timestamp": output.timestamp.isoformat(),
                        "session_id": output.session_id,
                        "node_id": output.node_id,
                        "content": output.content,
                        "metadata": output.metadata,
                        "size_bytes": output.size_bytes,
                        "processing_time_ms": output.processing_time_ms
                    }
                    for output in self.outputs
                ],
                "saved_at": datetime.now(timezone.utc).isoformat()
            }
            
            logger.info(f"🔧 [DEBUG_SAVE] Serializable data created, outputs count: {len(serializable_data['outputs'])}")
            
            with open(file_path, 'w') as f:
                json.dump(serializable_data, f, indent=2, default=str)
            
            import os
            file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
            logger.info(f"🔧 [DEBUG_SAVE] ✅ Successfully saved {len(self.outputs)} outputs to {file_path} ({file_size} bytes)")
            
        except Exception as e:
            logger.error(f"🔧 [DEBUG_SAVE] ❌ Failed to save to disk for session {self.session_id}: {e}")
            import traceback
            logger.error(f"🔧 [DEBUG_SAVE] Full traceback: {traceback.format_exc()}")
    
    def _load_from_disk(self):
        """Load aggregator data from disk if it exists."""
        try:
            file_path = self._get_aggregator_file_path()
            
            if not os.path.exists(file_path):
                return  # No existing data to load
            
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            # Restore metadata
            self.workflow_metadata = data.get("workflow_metadata", self.workflow_metadata)
            self.start_time = data.get("start_time", self.start_time)
            self.finalized = data.get("finalized", False)
            
            # Restore outputs
            for output_data in data.get("outputs", []):
                output = WorkflowOutput(
                    output_id=output_data["output_id"],
                    output_type=OutputType(output_data["output_type"]),
                    timestamp=datetime.fromisoformat(output_data["timestamp"]),
                    session_id=output_data["session_id"],
                    node_id=output_data["node_id"],
                    content=output_data["content"],
                    metadata=output_data["metadata"],
                    size_bytes=output_data["size_bytes"],
                    processing_time_ms=output_data["processing_time_ms"]
                )
                self._store_output_memory_only(output)
            
            logger.info(f"🔄 [OUTPUT_AGGREGATOR] Loaded {len(self.outputs)} outputs from disk for session {self.session_id}")
            
        except Exception as e:
            logger.warning(f"🔄 [OUTPUT_AGGREGATOR] Failed to load from disk: {e}")
    
    def _store_output_memory_only(self, output: WorkflowOutput):
        """Store output in memory without triggering disk save (used during loading)."""
        self.outputs.append(output)
        self.output_index[output.output_type].append(output)
    
    def capture_raw_data(
        self,
        source: str,
        rows: List[Dict[str, Any]],
        query: Optional[str] = None,
        **metadata
    ) -> str:
        """Capture raw data output from database queries or API calls."""
        
        raw_data = RawDataOutput(
            source=source,
            query=query,
            rows=rows,
            row_count=len(rows),
            columns=list(rows[0].keys()) if rows else [],
            execution_time_ms=metadata.get("execution_time_ms", 0),
            is_sample=metadata.get("is_sample", False),
            sample_size=metadata.get("sample_size")
        )
        
        output = WorkflowOutput(
            output_id=str(uuid.uuid4()),
            output_type=OutputType.RAW_DATA,
            timestamp=datetime.now(timezone.utc),
            session_id=self.session_id,
            node_id=metadata.get("node_id"),
            content=asdict(raw_data),
            metadata=metadata,
            size_bytes=len(json.dumps(rows).encode('utf-8')) if rows else 0
        )
        
        self._store_output(output)
        logger.info(f"🔄 [OUTPUT_AGGREGATOR] Captured raw data: {source}, {len(rows)} rows")
        
        return output.output_id
    
    def capture_execution_plan(
        self,
        plan: Dict[str, Any],
        **metadata
    ) -> str:
        """Capture execution plan from planning nodes."""
        
        plan_output = ExecutionPlanOutput(
            plan_id=plan.get("id", str(uuid.uuid4())),
            strategy=plan.get("execution_strategy", "unknown"),
            operations=plan.get("operations", []),
            dependencies=plan.get("dependencies", {}),
            optimizations_applied=plan.get("optimizations_applied", []),
            estimated_duration_ms=plan.get("estimated_duration_ms")
        )
        
        output = WorkflowOutput(
            output_id=str(uuid.uuid4()),
            output_type=OutputType.EXECUTION_PLAN,
            timestamp=datetime.now(timezone.utc),
            session_id=self.session_id,
            node_id=metadata.get("node_id"),
            content=asdict(plan_output),
            metadata=metadata
        )
        
        self._store_output(output)
        logger.info(f"🔄 [OUTPUT_AGGREGATOR] Captured execution plan: {plan_output.plan_id}")
        
        return output.output_id
    
    def capture_tool_execution(
        self,
        tool_id: str,
        call_id: str,
        parameters: Dict[str, Any],
        result: Any,
        success: bool,
        execution_time_ms: float,
        error_message: Optional[str] = None,
        **metadata
    ) -> str:
        """Capture individual tool execution."""
        
        tool_output = ToolExecutionOutput(
            tool_id=tool_id,
            call_id=call_id,
            parameters=parameters,
            result=result,
            success=success,
            error_message=error_message,
            execution_time_ms=execution_time_ms,
            memory_used_mb=metadata.get("memory_used_mb"),
            retry_count=metadata.get("retry_count", 0),
            dependencies_resolved=metadata.get("dependencies_resolved", [])
        )
        
        output = WorkflowOutput(
            output_id=str(uuid.uuid4()),
            output_type=OutputType.TOOL_EXECUTION,
            timestamp=datetime.now(timezone.utc),
            session_id=self.session_id,
            node_id=metadata.get("node_id"),
            content=asdict(tool_output),
            metadata=metadata,
            processing_time_ms=execution_time_ms
        )
        
        self._store_output(output)
        logger.info(f"🔄 [OUTPUT_AGGREGATOR] Captured tool execution: {tool_id}, success={success}")
        
        return output.output_id
    
    def capture_final_synthesis(
        self,
        response_text: str,
        confidence_score: float = 0.0,
        sources_used: List[str] = None,
        **metadata
    ) -> str:
        """Capture final synthesis and response generation."""
        
        synthesis_output = FinalSynthesisOutput(
            response_text=response_text,
            confidence_score=confidence_score,
            sources_used=sources_used or [],
            synthesis_method=metadata.get("synthesis_method", "llm_based"),
            quality_metrics=metadata.get("quality_metrics", {}),
            alternative_responses=metadata.get("alternative_responses", [])
        )
        
        output = WorkflowOutput(
            output_id=str(uuid.uuid4()),
            output_type=OutputType.FINAL_SYNTHESIS,
            timestamp=datetime.now(timezone.utc),
            session_id=self.session_id,
            node_id=metadata.get("node_id"),
            content=asdict(synthesis_output),
            metadata=metadata,
            size_bytes=len(response_text.encode('utf-8'))
        )
        
        self._store_output(output)
        logger.info(f"🔄 [OUTPUT_AGGREGATOR] Captured final synthesis: {len(response_text)} chars")
        
        return output.output_id
    
    def capture_performance_metrics(
        self,
        metrics: Dict[str, Any],
        **metadata
    ) -> str:
        """Capture performance and timing metrics."""
        
        perf_metrics = PerformanceMetrics(
            total_duration_ms=metrics.get("total_duration_ms", 0),
            node_durations=metrics.get("node_durations", {}),
            database_query_time=metrics.get("database_query_time", 0),
            llm_processing_time=metrics.get("llm_processing_time", 0),
            parallel_efficiency=metrics.get("parallel_efficiency"),
            cache_hit_rate=metrics.get("cache_hit_rate", 0),
            memory_peak_mb=metrics.get("memory_peak_mb"),
            operations_executed=metrics.get("operations_executed", 0),
            operations_successful=metrics.get("operations_successful", 0)
        )
        
        output = WorkflowOutput(
            output_id=str(uuid.uuid4()),
            output_type=OutputType.PERFORMANCE_METRICS,
            timestamp=datetime.now(timezone.utc),
            session_id=self.session_id,
            content=asdict(perf_metrics),
            metadata=metadata
        )
        
        self._store_output(output)
        logger.info(f"🔄 [OUTPUT_AGGREGATOR] Captured performance metrics")
        
        return output.output_id
    
    def capture_streaming_event(
        self,
        event_type: str,
        event_data: Dict[str, Any],
        **metadata
    ) -> str:
        """Capture streaming events for real-time monitoring."""
        
        output = WorkflowOutput(
            output_id=str(uuid.uuid4()),
            output_type=OutputType.STREAMING_EVENT,
            timestamp=datetime.now(timezone.utc),
            session_id=self.session_id,
            node_id=metadata.get("node_id"),
            content={
                "event_type": event_type,
                "event_data": event_data
            },
            metadata=metadata
        )
        
        self._store_output(output)
        return output.output_id
    
    def _store_output(self, output: WorkflowOutput):
        """Store output in both main list and type-indexed collections, then save to disk."""
        logger.info(f"🔧 [DEBUG_SAVE] _store_output called for session {self.session_id}, output_type: {output.output_type.value}")
        logger.info(f"🔧 [DEBUG_SAVE] Output content preview: {str(output.content)[:100]}...")
        
        self.outputs.append(output)
        self.output_index[output.output_type].append(output)
        
        logger.info(f"🔧 [DEBUG_SAVE] Added to memory, total outputs: {len(self.outputs)}")
        
        # ✅ ENHANCEMENT: Auto-save to disk after every capture
        logger.info(f"🔧 [DEBUG_SAVE] About to call _save_to_disk() for session {self.session_id}")
        self._save_to_disk()
        logger.info(f"🔧 [DEBUG_SAVE] _save_to_disk() completed for session {self.session_id}")
    
    def finalize_aggregator(self):
        """Mark aggregator as finalized and save final state."""
        self.finalized = True
        self._save_to_disk()
        logger.info(f"🔄 [OUTPUT_AGGREGATOR] Finalized session {self.session_id}")
    
    def cleanup_disk_storage(self):
        """Remove disk storage for this session (cleanup method)."""
        try:
            file_path = self._get_aggregator_file_path()
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"🔄 [OUTPUT_AGGREGATOR] Cleaned up disk storage for session {self.session_id}")
        except Exception as e:
            logger.warning(f"🔄 [OUTPUT_AGGREGATOR] Failed to cleanup disk storage: {e}")
    
    # === AGGREGATION AND RETRIEVAL METHODS ===
    
    def get_all_raw_data(self) -> List[RawDataOutput]:
        """Get all raw data outputs as structured objects."""
        return [
            RawDataOutput(**output.content)
            for output in self.output_index[OutputType.RAW_DATA]
        ]
    
    def get_all_execution_plans(self) -> List[ExecutionPlanOutput]:
        """Get all execution plans as structured objects."""
        return [
            ExecutionPlanOutput(**output.content)
            for output in self.output_index[OutputType.EXECUTION_PLAN]
        ]
    
    def get_all_tool_executions(self) -> List[ToolExecutionOutput]:
        """Get all tool executions as structured objects."""
        return [
            ToolExecutionOutput(**output.content)
            for output in self.output_index[OutputType.TOOL_EXECUTION]
        ]
    
    def get_final_synthesis(self) -> Optional[FinalSynthesisOutput]:
        """Get the final synthesis output."""
        synthesis_outputs = self.output_index[OutputType.FINAL_SYNTHESIS]
        if synthesis_outputs:
            # Get the most recent synthesis
            latest = max(synthesis_outputs, key=lambda x: x.timestamp)
            return FinalSynthesisOutput(**latest.content)
        return None
    
    def get_performance_summary(self) -> Optional[PerformanceMetrics]:
        """Get aggregated performance metrics."""
        perf_outputs = self.output_index[OutputType.PERFORMANCE_METRICS]
        if perf_outputs:
            # Get the most recent metrics
            latest = max(perf_outputs, key=lambda x: x.timestamp)
            return PerformanceMetrics(**latest.content)
        return None
    
    def get_workflow_timeline(self) -> List[Dict[str, Any]]:
        """Get chronological timeline of all workflow events."""
        timeline = sorted(self.outputs, key=lambda x: x.timestamp)
        
        return [
            {
                "timestamp": output.timestamp.isoformat(),
                "output_type": output.output_type.value,
                "node_id": output.node_id,
                "output_id": output.output_id,
                "content_summary": self._summarize_content(output),
                "size_bytes": output.size_bytes,
                "processing_time_ms": output.processing_time_ms
            }
            for output in timeline
        ]
    
    def _summarize_content(self, output: WorkflowOutput) -> str:
        """Create a brief summary of output content."""
        if output.output_type == OutputType.RAW_DATA:
            return f"Data from {output.content.get('source')}: {output.content.get('row_count', 0)} rows"
        elif output.output_type == OutputType.EXECUTION_PLAN:
            return f"Plan {output.content.get('plan_id')}: {len(output.content.get('operations', []))} operations"
        elif output.output_type == OutputType.TOOL_EXECUTION:
            return f"Tool {output.content.get('tool_id')}: {'success' if output.content.get('success') else 'failed'}"
        elif output.output_type == OutputType.FINAL_SYNTHESIS:
            return f"Synthesis: {len(output.content.get('response_text', ''))} chars"
        elif output.output_type == OutputType.PERFORMANCE_METRICS:
            return f"Metrics: {output.content.get('total_duration_ms', 0):.0f}ms total"
        else:
            return f"{output.output_type.value} output"
    
    def create_unified_result(self) -> Dict[str, Any]:
        """
        Create a unified result that combines all outputs into a single,
        comprehensive response structure.
        """
        
        # Get structured outputs
        raw_data = self.get_all_raw_data()
        execution_plans = self.get_all_execution_plans()
        tool_executions = self.get_all_tool_executions()
        final_synthesis = self.get_final_synthesis()
        performance = self.get_performance_summary()
        
        # Aggregate raw data results
        all_rows = []
        data_sources = []
        
        for data_output in raw_data:
            all_rows.extend(data_output.rows)
            data_sources.append({
                "source": data_output.source,
                "row_count": data_output.row_count,
                "query": data_output.query,
                "execution_time_ms": data_output.execution_time_ms
            })
        
        # Create execution summary
        execution_summary = {
            "total_plans": len(execution_plans),
            "total_tools_executed": len(tool_executions),
            "successful_tools": sum(1 for tool in tool_executions if tool.success),
            "data_sources_accessed": len(data_sources),
            "total_rows_retrieved": len(all_rows)
        }
        
        # Calculate overall success
        tool_success_rate = (
            execution_summary["successful_tools"] / execution_summary["total_tools_executed"]
            if execution_summary["total_tools_executed"] > 0 else 1.0
        )
        
        # More flexible success criteria for LangGraph workflows
        overall_success = (
            len(all_rows) > 0 and  # We got data
            tool_success_rate >= 0.5  # At least 50% tool success
            # Note: final_synthesis is optional for data-focused workflows
        )
        
        # Build unified result
        unified_result = {
            # Standard API Response Format
            "rows": all_rows,
            "sql": self._get_representative_sql(),
            "analysis": final_synthesis.response_text if final_synthesis else None,
            "success": overall_success,
            "session_id": self.session_id,
            
            # Extended Workflow Information
            "workflow_metadata": {
                **self.workflow_metadata,
                "total_duration_ms": (time.time() - self.start_time) * 1000,
                "outputs_captured": len(self.outputs)
            },
            
            # Detailed Execution Information
            "execution_details": {
                "data_sources": data_sources,
                "execution_plans": [asdict(plan) for plan in execution_plans],
                "tool_executions": [asdict(tool) for tool in tool_executions],
                "execution_summary": execution_summary
            },
            
            # Performance and Quality Metrics
            "performance_metrics": asdict(performance) if performance else {},
            "quality_indicators": {
                "tool_success_rate": tool_success_rate,
                "confidence_score": final_synthesis.confidence_score if final_synthesis else 0.0,
                "data_completeness": min(1.0, len(all_rows) / 100),  # Rough estimate
                "response_quality": len(final_synthesis.response_text) if final_synthesis else 0
            },
            
            # Full Timeline for Debugging
            "workflow_timeline": self.get_workflow_timeline(),
            
            # Compatibility with Existing Systems
            "plan_info": execution_plans[0].__dict__ if execution_plans else None,
            "operation_results": {
                f"tool_{tool.tool_id}": tool.result 
                for tool in tool_executions if tool.success
            }
        }
        
        logger.info(f"🔄 [OUTPUT_AGGREGATOR] Created unified result: {len(all_rows)} rows, "
                   f"{execution_summary['total_tools_executed']} tools, success={overall_success}")
        
        return unified_result
    
    def _get_representative_sql(self) -> str:
        """Get a representative SQL query from the captured data."""
        raw_data = self.get_all_raw_data()
        
        queries = [data.query for data in raw_data if data.query]
        if queries:
            # Return the first non-empty query, or combine multiple
            if len(queries) == 1:
                return queries[0]
            else:
                return f"-- Multiple queries executed:\n" + "\n-- Next query:\n".join(queries)
        
        return "-- LangGraph iterative workflow (no direct SQL)"
    
    def export_for_analysis(self) -> Dict[str, Any]:
        """Export all captured data for detailed analysis and debugging."""
        return {
            "session_metadata": self.workflow_metadata,
            "output_summary": {
                output_type.value: len(outputs)
                for output_type, outputs in self.output_index.items()
            },
            "full_outputs": [
                {
                    "output_id": output.output_id,
                    "output_type": output.output_type.value,
                    "timestamp": output.timestamp.isoformat(),
                    "node_id": output.node_id,
                    "content": output.content,
                    "metadata": output.metadata,
                    "size_bytes": output.size_bytes,
                    "processing_time_ms": output.processing_time_ms
                }
                for output in self.outputs
            ],
            "timeline": self.get_workflow_timeline(),
            "unified_result": self.create_unified_result()
        }

    def create_api_response(self) -> Dict[str, Any]:
        """
        Create an API-ready response format with structured data
        for both local file saving and inline API mechanisms.
        """
        
        # Get all structured outputs
        raw_data = self.get_all_raw_data()
        execution_plans = self.get_all_execution_plans()
        tool_executions = self.get_all_tool_executions()
        final_synthesis = self.get_final_synthesis()
        performance = self.get_performance_summary()
        
        # Create API-friendly data structure
        api_response = {
            # Core data for API consumers
            "data": {
                "rows": [],
                "sources": [],
                "total_rows": 0
            },
            
            # Execution plans as JSON objects
            "execution_plans": [],
            
            # Tool results with success status
            "tool_results": [],
            
            # Performance metrics
            "performance": {
                "total_duration_ms": (time.time() - self.start_time) * 1000,
                "success_rate": 0.0,
                "operations_count": 0
            },
            
            # Final analysis/synthesis
            "analysis": None,
            
            # Session metadata
            "session_info": {
                "session_id": self.session_id,
                "outputs_captured": len(self.outputs),
                "workflow_type": self.workflow_metadata.get("workflow_type", "unknown"),
                "created_at": self.workflow_metadata.get("created_at")
            },
            
            # Mechanism indicators
            "available_mechanisms": {
                "local_file_export": True,
                "inline_api_data": True
            }
        }
        
        # Aggregate raw data from all sources
        for data_output in raw_data:
            api_response["data"]["rows"].extend(data_output.rows)
            api_response["data"]["sources"].append({
                "source": data_output.source,
                "row_count": data_output.row_count,
                "query": data_output.query,
                "execution_time_ms": data_output.execution_time_ms
            })
        
        api_response["data"]["total_rows"] = len(api_response["data"]["rows"])
        
        # Structure execution plans
        for plan in execution_plans:
            api_response["execution_plans"].append({
                "plan_id": plan.plan_id,
                "strategy": plan.strategy,
                "operations": plan.operations,
                "dependencies": plan.dependencies,
                "estimated_duration_ms": plan.estimated_duration_ms,
                "actual_duration_ms": plan.actual_duration_ms,
                "success_rate": plan.success_rate
            })
        
        # Structure tool results
        successful_tools = 0
        for tool in tool_executions:
            if tool.success:
                successful_tools += 1
            
            api_response["tool_results"].append({
                "tool_id": tool.tool_id,
                "call_id": tool.call_id,
                "parameters": tool.parameters,
                "result": tool.result,
                "success": tool.success,
                "error_message": tool.error_message,
                "execution_time_ms": tool.execution_time_ms
            })
        
        # Calculate performance metrics
        api_response["performance"]["operations_count"] = len(tool_executions)
        if len(tool_executions) > 0:
            api_response["performance"]["success_rate"] = successful_tools / len(tool_executions)
        
        # Add performance details if available
        if performance:
            api_response["performance"].update({
                "database_query_time": performance.database_query_time,
                "llm_processing_time": performance.llm_processing_time,
                "operations_executed": performance.operations_executed,
                "operations_successful": performance.operations_successful
            })
        
        # Add final synthesis
        if final_synthesis:
            api_response["analysis"] = {
                "response_text": final_synthesis.response_text,
                "confidence_score": final_synthesis.confidence_score,
                "sources_used": final_synthesis.sources_used,
                "synthesis_method": final_synthesis.synthesis_method
            }
        
        logger.info(f"🔄 [OUTPUT_AGGREGATOR] Created API response: {api_response['data']['total_rows']} rows, "
                   f"{len(api_response['execution_plans'])} plans, {len(api_response['tool_results'])} tools")
        
        return api_response

class LangGraphOutputIntegrator:
    """
    Integration layer that connects the output aggregator with existing
    state management systems and LangGraph nodes.
    """
    
    def __init__(self):
        self.active_aggregators: Dict[str, WorkflowOutputAggregator] = {}
        self.state_manager = StateManager()
    
    def get_aggregator(self, session_id: str) -> WorkflowOutputAggregator:
        """Get or create an output aggregator for a session."""
        if session_id not in self.active_aggregators:
            self.active_aggregators[session_id] = WorkflowOutputAggregator(session_id)
        
        return self.active_aggregators[session_id]
    
    def cleanup_session(self, session_id: str):
        """Manually cleanup a specific session."""
        if session_id in self.active_aggregators:
            del self.active_aggregators[session_id]
            logger.info(f"🔄 [OUTPUT_AGGREGATOR] Cleaned up session: {session_id}")
    
    def cleanup_finalized_sessions(self):
        """Clean up all finalized sessions to free memory."""
        finalized_sessions = [
            session_id for session_id, aggregator in self.active_aggregators.items()
            if getattr(aggregator, 'finalized', False)
        ]
        
        for session_id in finalized_sessions:
            del self.active_aggregators[session_id]
            logger.info(f"🔄 [OUTPUT_AGGREGATOR] Cleaned up finalized session: {session_id}")
        
        return len(finalized_sessions)
    
    def get_session_info(self) -> Dict[str, Any]:
        """Get information about all active sessions."""
        return {
            "active_sessions": len(self.active_aggregators),
            "sessions": {
                session_id: {
                    "finalized": getattr(aggregator, 'finalized', False),
                    "outputs_count": len(aggregator.outputs),
                    "start_time": aggregator.start_time,
                    "session_age_seconds": time.time() - aggregator.start_time
                }
                for session_id, aggregator in self.active_aggregators.items()
            }
        }
    
    async def integrate_with_node_execution(
        self,
        node_id: str,
        session_id: str,
        node_execution_result: Dict[str, Any]
    ):
        """Integrate node execution results with output aggregation."""
        aggregator = self.get_aggregator(session_id)
        
        # Capture different types of outputs based on node result content
        if "raw_data" in node_execution_result:
            aggregator.capture_raw_data(
                source=node_execution_result.get("source", node_id),
                rows=node_execution_result["raw_data"],
                node_id=node_id,
                **node_execution_result.get("metadata", {})
            )
        
        if "execution_plan" in node_execution_result:
            aggregator.capture_execution_plan(
                plan=node_execution_result["execution_plan"],
                node_id=node_id,
                **node_execution_result.get("metadata", {})
            )
        
        if "tool_executions" in node_execution_result:
            for tool_exec in node_execution_result["tool_executions"]:
                aggregator.capture_tool_execution(
                    tool_id=tool_exec["tool_id"],
                    call_id=tool_exec.get("call_id", str(uuid.uuid4())),
                    parameters=tool_exec.get("parameters", {}),
                    result=tool_exec.get("result"),
                    success=tool_exec.get("success", False),
                    execution_time_ms=tool_exec.get("execution_time_ms", 0),
                    error_message=tool_exec.get("error_message"),
                    node_id=node_id
                )
        
        if "final_response" in node_execution_result:
            aggregator.capture_final_synthesis(
                response_text=node_execution_result["final_response"],
                confidence_score=node_execution_result.get("confidence_score", 0.0),
                sources_used=node_execution_result.get("sources_used", []),
                node_id=node_id,
                **node_execution_result.get("metadata", {})
            )
    
    async def finalize_workflow_outputs(self, session_id: str) -> Dict[str, Any]:
        """Finalize and return unified results for a completed workflow."""
        if session_id not in self.active_aggregators:
            logger.warning(f"No aggregator found for session {session_id}")
            return {"error": "No outputs captured for this session"}
        
        aggregator = self.active_aggregators[session_id]
        
        # Capture final performance metrics
        aggregator.capture_performance_metrics({
            "total_duration_ms": (time.time() - aggregator.start_time) * 1000,
            "outputs_captured": len(aggregator.outputs)
        })
        
        # Create unified result
        unified_result = aggregator.create_unified_result()
        
        # ✅ ENHANCEMENT: Finalize aggregator and save to disk
        aggregator.finalize_aggregator()
        
        # Integrate with legacy state management
        try:
            analysis_state = await self.state_manager.get_state(session_id)
            if analysis_state:
                # Update legacy state with new information
                if unified_result.get("rows"):
                    analysis_state.final_result = {"rows": unified_result["rows"]}
                if unified_result.get("analysis"):
                    analysis_state.final_analysis = unified_result["analysis"]
                
                await self.state_manager.update_state(analysis_state)
        except Exception as e:
            logger.warning(f"Failed to update legacy state: {e}")
        
        # DON'T clean up aggregator immediately - let CLI export access it
        # Mark as finalized instead
        logger.info(f"🔄 [OUTPUT_AGGREGATOR] Session {session_id} finalized with persistence, keeping aggregator for export")
        
        return unified_result

# Global integrator instance
_output_integrator = None

def get_output_integrator() -> LangGraphOutputIntegrator:
    """Get the global output integrator instance."""
    global _output_integrator
    if _output_integrator is None:
        _output_integrator = LangGraphOutputIntegrator()
    return _output_integrator
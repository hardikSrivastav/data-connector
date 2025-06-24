"""
Hybrid State Management for LangGraph Integration

Combines LangGraph's typed state management with Ceneca's existing session-based state
to enable a gradual migration while gaining LangGraph's advanced features.
"""

import logging
import uuid
import json
from typing import Dict, List, Any, Optional, TypedDict, Union
from datetime import datetime
import asyncio

from ..tools.state_manager import StateManager, AnalysisState

logger = logging.getLogger(__name__)

class LangGraphState(TypedDict):
    """
    LangGraph-compatible state definition for orchestration workflows.
    
    This provides typed state management with automatic persistence and 
    compatibility with existing Ceneca infrastructure.
    """
    # Core workflow information
    question: str
    session_id: str
    workflow_type: str  # 'planning', 'execution', 'analysis'
    
    # Database and schema information
    databases_identified: List[str]
    available_tables: List[Dict[str, Any]]
    schema_metadata: Dict[str, Any]
    
    # Execution planning and progress
    execution_plan: Dict[str, Any]
    current_step: int
    total_steps: int
    step_history: List[Dict[str, Any]]
    
    # Data and results
    partial_results: Dict[str, Any]
    operation_results: Dict[str, Any]  # Results keyed by operation ID
    final_result: Dict[str, Any]
    
    # Performance and observability
    performance_metrics: Dict[str, Any]
    error_history: List[Dict[str, Any]]
    retry_count: int
    
    # Streaming and user experience
    streaming_buffer: List[Dict[str, Any]]
    last_update_timestamp: str
    
    # Tool selection and composition
    selected_tools: List[str]
    tool_execution_history: List[Dict[str, Any]]
    tool_performance_data: Dict[str, Any]
    
    # Configuration and preferences
    user_preferences: Dict[str, Any]
    quality_thresholds: Dict[str, float]
    timeout_settings: Dict[str, int]

class HybridStateManager:
    """
    Hybrid state manager that bridges LangGraph state with existing session management.
    
    Features:
    - Preserves existing session-based workflows
    - Provides LangGraph TypedDict state for new workflows  
    - Automatic state synchronization
    - Migration path from legacy to LangGraph state
    - Backward compatibility with existing agents
    """
    
    def __init__(self):
        self.legacy_state_manager = StateManager()
        self.session_graph_mapping: Dict[str, str] = {}  # session_id -> graph_session_id
        self.graph_state_store: Dict[str, LangGraphState] = {}
        self.state_sync_enabled = True
        
        logger.info("Initialized HybridStateManager with LangGraph integration")
    
    def _create_initial_langgraph_state(
        self, 
        question: str, 
        session_id: str = None,
        workflow_type: str = "planning"
    ) -> LangGraphState:
        """Create an initial LangGraph state with sensible defaults."""
        if session_id is None:
            session_id = str(uuid.uuid4())
            
        return LangGraphState(
            question=question,
            session_id=session_id,
            workflow_type=workflow_type,
            databases_identified=[],
            available_tables=[],
            schema_metadata={},
            execution_plan={},
            current_step=0,
            total_steps=0,
            step_history=[],
            partial_results={},
            operation_results={},
            final_result={},
            performance_metrics={
                "start_time": datetime.utcnow().isoformat(),
                "total_duration": 0,
                "operations_executed": 0,
                "cache_hits": 0
            },
            error_history=[],
            retry_count=0,
            streaming_buffer=[],
            last_update_timestamp=datetime.utcnow().isoformat(),
            selected_tools=[],
            tool_execution_history=[],
            tool_performance_data={},
            user_preferences={
                "max_parallel_operations": 4,
                "streaming_enabled": True,
                "auto_optimization": True
            },
            quality_thresholds={
                "data_completeness": 0.8,
                "confidence_threshold": 0.7,
                "performance_threshold": 0.9
            },
            timeout_settings={
                "operation_timeout": 60,
                "total_workflow_timeout": 300,
                "streaming_timeout": 5
            }
        )
    
    async def create_graph_session(
        self, 
        question: str, 
        workflow_type: str = "planning",
        migrate_from_legacy: bool = True
    ) -> str:
        """
        Create a new LangGraph-enabled session.
        
        Args:
            question: The user's question
            workflow_type: Type of workflow (planning, execution, analysis)
            migrate_from_legacy: Whether to also create a legacy session for compatibility
            
        Returns:
            Graph session ID
        """
        graph_session_id = str(uuid.uuid4())
        
        # Create LangGraph state
        initial_state = self._create_initial_langgraph_state(
            question, 
            graph_session_id, 
            workflow_type
        )
        
        self.graph_state_store[graph_session_id] = initial_state
        
        # Optionally create legacy session for compatibility
        if migrate_from_legacy:
            try:
                legacy_session_id = await self.legacy_state_manager.create_session(question)
                self.session_graph_mapping[legacy_session_id] = graph_session_id
                
                logger.info(f"Created hybrid session: legacy={legacy_session_id}, graph={graph_session_id}")
            except Exception as e:
                logger.warning(f"Failed to create legacy session: {e}")
        
        logger.info(f"Created LangGraph session {graph_session_id} for workflow type: {workflow_type}")
        return graph_session_id
    
    async def get_graph_state(self, session_id: str) -> Optional[LangGraphState]:
        """
        Get LangGraph state by session ID.
        
        Args:
            session_id: Either graph session ID or legacy session ID
            
        Returns:
            LangGraph state or None if not found
        """
        # Check if it's a direct graph session ID
        if session_id in self.graph_state_store:
            return self.graph_state_store[session_id]
        
        # Check if it's a legacy session ID mapped to a graph session
        if session_id in self.session_graph_mapping:
            graph_session_id = self.session_graph_mapping[session_id]
            return self.graph_state_store.get(graph_session_id)
        
        return None
    
    async def update_graph_state(
        self, 
        session_id: str, 
        state_updates: Dict[str, Any],
        sync_to_legacy: bool = True
    ) -> bool:
        """
        Update LangGraph state with new information.
        
        Args:
            session_id: Session ID (graph or legacy)
            state_updates: Dictionary of state updates to apply
            sync_to_legacy: Whether to sync changes to legacy state
            
        Returns:
            True if update succeeded, False otherwise
        """
        try:
            # Get current state
            current_state = await self.get_graph_state(session_id)
            if not current_state:
                logger.error(f"No graph state found for session {session_id}")
                return False
            
            # Apply updates
            for key, value in state_updates.items():
                if key in current_state:
                    current_state[key] = value
                else:
                    logger.warning(f"Unknown state key: {key}")
            
            # Update timestamp
            current_state["last_update_timestamp"] = datetime.utcnow().isoformat()
            
            # Get the actual graph session ID for storage
            graph_session_id = current_state["session_id"]
            self.graph_state_store[graph_session_id] = current_state
            
            # Optionally sync to legacy state
            if sync_to_legacy and self.state_sync_enabled:
                await self._sync_to_legacy_state(session_id, state_updates)
            
            logger.debug(f"Updated graph state for session {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update graph state for session {session_id}: {e}")
            return False
    
    async def _sync_to_legacy_state(self, session_id: str, state_updates: Dict[str, Any]):
        """Sync relevant state changes to legacy state manager."""
        try:
            # Find legacy session ID
            legacy_session_id = None
            if session_id in self.session_graph_mapping:
                # session_id is legacy
                legacy_session_id = session_id
            else:
                # session_id is graph, find reverse mapping
                for legacy_id, graph_id in self.session_graph_mapping.items():
                    if graph_id == session_id:
                        legacy_session_id = legacy_id
                        break
            
            if not legacy_session_id:
                return
            
            # Get legacy state
            legacy_state = await self.legacy_state_manager.get_state(legacy_session_id)
            if not legacy_state:
                return
            
            # Sync relevant fields
            if "final_result" in state_updates and state_updates["final_result"]:
                legacy_state.set_final_result(
                    state_updates.get("execution_plan", {}),
                    state_updates["final_result"]
                )
            
            if "operation_results" in state_updates:
                for op_id, result in state_updates["operation_results"].items():
                    legacy_state.add_executed_tool(
                        f"langgraph_operation_{op_id}",
                        {"operation_id": op_id},
                        result
                    )
            
            await self.legacy_state_manager.update_state(legacy_state)
            
        except Exception as e:
            logger.warning(f"Failed to sync to legacy state: {e}")
    
    async def add_operation_result(
        self, 
        session_id: str, 
        operation_id: str, 
        result: Any,
        execution_time: float = 0
    ):
        """Add an operation result to the graph state."""
        state_updates = {
            "operation_results": {operation_id: result},
            "performance_metrics": {}
        }
        
        # Update performance metrics
        current_state = await self.get_graph_state(session_id)
        if current_state:
            current_metrics = current_state["performance_metrics"]
            current_metrics["operations_executed"] = current_metrics.get("operations_executed", 0) + 1
            if execution_time > 0:
                current_metrics["total_duration"] = current_metrics.get("total_duration", 0) + execution_time
            
            state_updates["performance_metrics"] = current_metrics
        
        await self.update_graph_state(session_id, state_updates)
    
    async def add_streaming_event(
        self, 
        session_id: str, 
        event: Dict[str, Any]
    ):
        """Add a streaming event to the buffer."""
        current_state = await self.get_graph_state(session_id)
        if current_state:
            # Add timestamp to event
            event["timestamp"] = datetime.utcnow().isoformat()
            
            # Add to buffer (keep last 100 events)
            buffer = current_state["streaming_buffer"]
            buffer.append(event)
            if len(buffer) > 100:
                buffer.pop(0)
            
            await self.update_graph_state(session_id, {
                "streaming_buffer": buffer
            }, sync_to_legacy=False)  # Don't sync streaming events
    
    async def record_error(
        self, 
        session_id: str, 
        error: Exception, 
        context: Dict[str, Any] = None
    ):
        """Record an error in the graph state."""
        current_state = await self.get_graph_state(session_id)
        if current_state:
            error_entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "error_type": type(error).__name__,
                "error_message": str(error),
                "context": context or {},
                "retry_count": current_state["retry_count"]
            }
            
            error_history = current_state["error_history"]
            error_history.append(error_entry)
            
            await self.update_graph_state(session_id, {
                "error_history": error_history,
                "retry_count": current_state["retry_count"] + 1
            })
    
    async def get_legacy_state(self, session_id: str) -> Optional[AnalysisState]:
        """Get legacy state for backward compatibility."""
        # Check if it's a graph session that needs legacy lookup
        if session_id in self.graph_state_store:
            # Find legacy session
            for legacy_id, graph_id in self.session_graph_mapping.items():
                if graph_id == session_id:
                    return await self.legacy_state_manager.get_state(legacy_id)
        
        # Direct legacy lookup
        return await self.legacy_state_manager.get_state(session_id)
    
    async def migrate_legacy_session(self, legacy_session_id: str) -> Optional[str]:
        """
        Migrate an existing legacy session to LangGraph state.
        
        Args:
            legacy_session_id: Existing legacy session ID
            
        Returns:
            New graph session ID or None if migration failed
        """
        try:
            legacy_state = await self.legacy_state_manager.get_state(legacy_session_id)
            if not legacy_state:
                return None
            
            # Create new graph session
            question = legacy_state.question if hasattr(legacy_state, 'question') else "Migrated session"
            graph_session_id = await self.create_graph_session(
                question, 
                workflow_type="migrated",
                migrate_from_legacy=False  # Don't create another legacy session
            )
            
            # Map the sessions
            self.session_graph_mapping[legacy_session_id] = graph_session_id
            
            # Migrate relevant data
            graph_state = self.graph_state_store[graph_session_id]
            
            # Migrate executed tools to operation results
            if hasattr(legacy_state, 'executed_tools'):
                for tool_name, tool_data in legacy_state.executed_tools.items():
                    graph_state["operation_results"][tool_name] = tool_data
            
            # Migrate final result
            if hasattr(legacy_state, 'final_result') and legacy_state.final_result:
                graph_state["final_result"] = legacy_state.final_result
            
            self.graph_state_store[graph_session_id] = graph_state
            
            logger.info(f"Migrated legacy session {legacy_session_id} to graph session {graph_session_id}")
            return graph_session_id
            
        except Exception as e:
            logger.error(f"Failed to migrate legacy session {legacy_session_id}: {e}")
            return None
    
    def get_session_stats(self) -> Dict[str, Any]:
        """Get statistics about current sessions."""
        return {
            "total_graph_sessions": len(self.graph_state_store),
            "legacy_graph_mappings": len(self.session_graph_mapping),
            "active_workflows": {
                workflow_type: len([
                    s for s in self.graph_state_store.values() 
                    if s["workflow_type"] == workflow_type
                ])
                for workflow_type in ["planning", "execution", "analysis", "migrated"]
            }
        } 
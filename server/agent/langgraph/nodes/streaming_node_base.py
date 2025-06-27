import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, AsyncIterator
from ..output_aggregator import get_output_integrator
from ..compat import NodeType

logger = logging.getLogger(__name__)

class StreamingNodeBase:
    """
    Enhanced base class for all LangGraph nodes with output aggregation integration.
    """
    
    def __init__(self, node_id: str):
        self.node_id = node_id
        self.node_type = NodeType.EXECUTION
        self.stream_capable = True
        
        # Add output integration
        self.output_integrator = get_output_integrator()
        
        logger.info(f"🔄 [STREAMING_NODE] Initialized {node_id} with output aggregation")
    
    # ... existing methods ...
    
    async def _capture_node_outputs(
        self,
        session_id: str,
        execution_result: Dict[str, Any]
    ):
        """Capture all outputs from this node's execution."""
        try:
            await self.output_integrator.integrate_with_node_execution(
                node_id=self.node_id,
                session_id=session_id,
                node_execution_result=execution_result
            )
            
            logger.debug(f"🔄 [STREAMING_NODE] Captured outputs for {self.node_id}")
            
        except Exception as e:
            logger.warning(f"🔄 [STREAMING_NODE] Failed to capture outputs for {self.node_id}: {e}")
    
    def create_result_chunk(
        self,
        result_data: Dict[str, Any],
        state_update: Dict[str, Any] = None,
        is_final: bool = False,
        capture_outputs: bool = True
    ) -> Dict[str, Any]:
        """
        Enhanced result chunk creation with automatic output capture.
        """
        chunk = {
            "type": "result",
            "node_id": self.node_id,
            "result_data": result_data,
            "state_update": state_update or {},
            "is_final": is_final,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": {
                "node_type": self.node_type.value,
                "stream_capable": self.stream_capable,
                "output_captured": False
            }
        }
        
        # Capture outputs if requested and we have a session_id
        if capture_outputs and state_update and "session_id" in state_update:
            try:
                # Create a task to capture outputs asynchronously
                import asyncio
                session_id = state_update["session_id"]
                
                # Create combined execution result for output capture
                execution_result = {
                    **result_data,
                    "metadata": chunk["metadata"],
                    "node_execution_timestamp": chunk["timestamp"]
                }
                
                # Schedule output capture (don't await to avoid blocking)
                asyncio.create_task(self._capture_node_outputs(session_id, execution_result))
                
                chunk["metadata"]["output_captured"] = True
                
            except Exception as e:
                logger.warning(f"🔄 [STREAMING_NODE] Failed to schedule output capture: {e}")
        
        return chunk
    
    def create_progress_chunk(
        self,
        progress: float,
        message: str,
        data: Dict[str, Any] = None,
        state_update: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Enhanced progress chunk with streaming event capture.
        """
        chunk = {
            "type": "progress",
            "node_id": self.node_id,
            "progress": min(100.0, max(0.0, progress)),
            "message": message,
            "data": data or {},
            "state_update": state_update or {},
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": {
                "node_type": self.node_type.value,
                "is_streaming": True
            }
        }
        
        # Capture streaming events if we have session context
        if state_update and "session_id" in state_update:
            try:
                session_id = state_update["session_id"]
                aggregator = self.output_integrator.get_aggregator(session_id)
                
                # Capture streaming event
                aggregator.capture_streaming_event(
                    event_type="progress_update",
                    event_data={
                        "progress": progress,
                        "message": message,
                        "node_id": self.node_id,
                        "data": data or {}
                    },
                    node_id=self.node_id
                )
                
            except Exception as e:
                logger.warning(f"🔄 [STREAMING_NODE] Failed to capture progress event: {e}")
        
        return chunk 
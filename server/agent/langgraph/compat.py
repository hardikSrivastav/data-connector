"""
LangGraph Compatibility Layer for Python 3.8

This module provides a simplified implementation of LangGraph concepts
that works with Python 3.8 and existing dependencies.
"""

import asyncio
import logging
import json
import time
import uuid
from typing import Dict, List, Any, Optional, Callable, AsyncIterator, Union
from datetime import datetime
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)

# Core LangGraph-style Types and Classes
class NodeType(Enum):
    """Types of nodes in our graph"""
    METADATA = "metadata"
    PLANNING = "planning"
    EXECUTION = "execution"
    AGGREGATION = "aggregation"
    TOOL_SELECTION = "tool_selection"

@dataclass
class GraphState:
    """
    LangGraph-style state management using dataclasses (Python 3.8 compatible)
    """
    # Core workflow information
    question: str = ""
    session_id: str = ""
    
    # Database and metadata
    databases_identified: List[str] = field(default_factory=list)
    schema_metadata: Dict[str, Any] = field(default_factory=dict)
    available_tables: List[Dict[str, Any]] = field(default_factory=list)
    
    # Execution planning
    execution_plan: Dict[str, Any] = field(default_factory=dict)
    selected_tools: List[str] = field(default_factory=list)
    
    # Results
    partial_results: Dict[str, Any] = field(default_factory=dict)
    operation_results: Dict[str, Any] = field(default_factory=dict)
    final_result: Dict[str, Any] = field(default_factory=dict)
    
    # Streaming and progress
    streaming_buffer: List[Dict[str, Any]] = field(default_factory=list)
    progress_percentage: float = 0.0
    current_node: str = ""
    
    # Error handling
    error_history: List[Dict[str, Any]] = field(default_factory=list)
    retry_count: int = 0
    fallback_used: bool = False
    
    # Performance tracking
    performance_metrics: Dict[str, Any] = field(default_factory=dict)
    start_time: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert state to dictionary for serialization"""
        return {
            'question': self.question,
            'session_id': self.session_id,
            'databases_identified': self.databases_identified,
            'schema_metadata': self.schema_metadata,
            'available_tables': self.available_tables,
            'execution_plan': self.execution_plan,
            'selected_tools': self.selected_tools,
            'partial_results': self.partial_results,
            'operation_results': self.operation_results,
            'final_result': self.final_result,
            'streaming_buffer': self.streaming_buffer,
            'progress_percentage': self.progress_percentage,
            'current_node': self.current_node,
            'error_history': self.error_history,
            'retry_count': self.retry_count,
            'fallback_used': self.fallback_used,
            'performance_metrics': self.performance_metrics,
            'start_time': self.start_time
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GraphState':
        """Create state from dictionary"""
        return cls(**data)

class BaseNode(ABC):
    """
    Base class for all graph nodes (LangGraph-style)
    """
    
    def __init__(self, node_id: str, node_type: NodeType):
        self.node_id = node_id
        self.node_type = node_type
        self.stream_capable = False
    
    @abstractmethod
    async def execute(self, state: GraphState) -> GraphState:
        """Execute the node and return updated state"""
        pass
    
    async def stream(self, state: GraphState) -> AsyncIterator[Dict[str, Any]]:
        """Optional streaming implementation"""
        if hasattr(self, '_stream_impl'):
            async for chunk in self._stream_impl(state):
                yield chunk
        else:
            # Fallback: execute normally and yield final result
            result_state = await self.execute(state)
            yield {
                "type": "node_complete",
                "node_id": self.node_id,
                "state": result_state.to_dict()
            }

class Edge:
    """
    Graph edge definition
    """
    
    def __init__(self, from_node: str, to_node: str, condition: Optional[Callable] = None):
        self.from_node = from_node
        self.to_node = to_node
        self.condition = condition
    
    def should_traverse(self, state: GraphState) -> bool:
        """Check if this edge should be traversed"""
        if self.condition is None:
            return True
        return self.condition(state)

class Graph:
    """
    Simple graph implementation (LangGraph-style)
    """
    
    def __init__(self):
        self.nodes: Dict[str, BaseNode] = {}
        self.edges: List[Edge] = []
        self.entry_point: Optional[str] = None
        self.finish_points: List[str] = []
    
    def add_node(self, node_id: str, node: BaseNode):
        """Add a node to the graph"""
        self.nodes[node_id] = node
    
    def add_edge(self, from_node: str, to_node: str, condition: Optional[Callable] = None):
        """Add an edge to the graph"""
        self.edges.append(Edge(from_node, to_node, condition))
    
    def set_entry_point(self, node_id: str):
        """Set the entry point for graph execution"""
        self.entry_point = node_id
    
    def add_finish_point(self, node_id: str):
        """Add a finish point to the graph"""
        self.finish_points.append(node_id)
    
    def get_next_nodes(self, current_node: str, state: GraphState) -> List[str]:
        """Get the next nodes to execute based on current state"""
        next_nodes = []
        for edge in self.edges:
            if edge.from_node == current_node and edge.should_traverse(state):
                next_nodes.append(edge.to_node)
        return next_nodes
    
    async def execute(self, initial_state: GraphState) -> GraphState:
        """Execute the graph"""
        if not self.entry_point:
            raise ValueError("No entry point set for graph")
        
        state = initial_state
        current_nodes = [self.entry_point]
        executed_nodes = set()
        
        while current_nodes:
            next_nodes = []
            
            # Execute current nodes (potentially in parallel)
            if len(current_nodes) == 1:
                # Single node execution
                node_id = current_nodes[0]
                node = self.nodes[node_id]
                state.current_node = node_id
                
                logger.info(f"Executing node: {node_id}")
                state = await node.execute(state)
                executed_nodes.add(node_id)
                
                # Get next nodes
                next_nodes.extend(self.get_next_nodes(node_id, state))
            else:
                # Parallel execution
                tasks = []
                for node_id in current_nodes:
                    node = self.nodes[node_id]
                    task = asyncio.create_task(node.execute(state))
                    tasks.append((node_id, task))
                
                # Wait for all parallel tasks
                for node_id, task in tasks:
                    try:
                        state = await task
                        executed_nodes.add(node_id)
                        next_nodes.extend(self.get_next_nodes(node_id, state))
                    except Exception as e:
                        logger.error(f"Node {node_id} failed: {e}")
                        state.error_history.append({
                            "node": node_id,
                            "error": str(e),
                            "timestamp": time.time()
                        })
            
            # Remove duplicates and already executed nodes
            current_nodes = list(set(next_nodes) - executed_nodes)
            
            # Check for finish condition
            if any(node_id in self.finish_points for node_id in executed_nodes):
                break
        
        # Update final metrics
        state.performance_metrics["total_duration"] = time.time() - state.start_time
        state.performance_metrics["nodes_executed"] = len(executed_nodes)
        
        return state
    
    async def stream_execute(self, initial_state: GraphState) -> AsyncIterator[Dict[str, Any]]:
        """Execute graph with streaming updates"""
        if not self.entry_point:
            raise ValueError("No entry point set for graph")
        
        state = initial_state
        current_nodes = [self.entry_point]
        executed_nodes = set()
        total_nodes = len(self.nodes)
        
        yield {
            "type": "graph_start",
            "total_nodes": total_nodes,
            "entry_point": self.entry_point
        }
        
        while current_nodes:
            next_nodes = []
            
            for node_id in current_nodes:
                node = self.nodes[node_id]
                state.current_node = node_id
                
                yield {
                    "type": "node_start",
                    "node_id": node_id,
                    "node_type": node.node_type.value,
                    "progress": len(executed_nodes) / total_nodes * 100
                }
                
                try:
                    if node.stream_capable:
                        # Stream node execution
                        async for chunk in node.stream(state):
                            yield chunk
                        
                        # Get final state (assuming last chunk contains it)
                        # This is a simplified approach
                        state = await node.execute(state)
                    else:
                        # Regular execution
                        state = await node.execute(state)
                    
                    executed_nodes.add(node_id)
                    
                    yield {
                        "type": "node_complete",
                        "node_id": node_id,
                        "progress": len(executed_nodes) / total_nodes * 100
                    }
                    
                    # Get next nodes
                    next_nodes.extend(self.get_next_nodes(node_id, state))
                    
                except Exception as e:
                    logger.error(f"Node {node_id} failed: {e}")
                    state.error_history.append({
                        "node": node_id,
                        "error": str(e),
                        "timestamp": time.time()
                    })
                    
                    yield {
                        "type": "node_error",
                        "node_id": node_id,
                        "error": str(e)
                    }
            
            # Remove duplicates and already executed nodes
            current_nodes = list(set(next_nodes) - executed_nodes)
            
            # Check for finish condition
            if any(node_id in self.finish_points for node_id in executed_nodes):
                break
        
        # Update final metrics
        state.performance_metrics["total_duration"] = time.time() - state.start_time
        state.performance_metrics["nodes_executed"] = len(executed_nodes)
        
        yield {
            "type": "graph_complete",
            "final_state": state.to_dict(),
            "execution_time": state.performance_metrics["total_duration"]
        }

class GraphBuilder:
    """
    Builder for constructing graphs
    """
    
    def __init__(self):
        self.graph = Graph()
    
    def add_node(self, node_id: str, node: BaseNode) -> 'GraphBuilder':
        """Add a node to the graph"""
        self.graph.add_node(node_id, node)
        return self
    
    def add_edge(self, from_node: str, to_node: str, condition: Optional[Callable] = None) -> 'GraphBuilder':
        """Add an edge to the graph"""
        self.graph.add_edge(from_node, to_node, condition)
        return self
    
    def set_entry_point(self, node_id: str) -> 'GraphBuilder':
        """Set the entry point"""
        self.graph.set_entry_point(node_id)
        return self
    
    def add_finish_point(self, node_id: str) -> 'GraphBuilder':
        """Add a finish point"""
        self.graph.add_finish_point(node_id)
        return self
    
    def compile(self) -> Graph:
        """Compile and return the graph"""
        return self.graph

# Utility functions for compatibility
def create_graph_state(question: str, session_id: str = None) -> GraphState:
    """Create a new graph state"""
    if session_id is None:
        session_id = str(uuid.uuid4())
    
    return GraphState(
        question=question,
        session_id=session_id,
        start_time=time.time()
    )

def create_simple_graph() -> GraphBuilder:
    """Create a simple graph builder"""
    return GraphBuilder()

# Circuit breaker implementation
class CircuitBreaker:
    """
    Simple circuit breaker implementation
    """
    
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half-open
    
    def __enter__(self):
        if self.state == "open":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "half-open"
            else:
                raise CircuitBreakerOpenError("Circuit breaker is open")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            # Success
            if self.state == "half-open":
                self.state = "closed"
                self.failure_count = 0
        else:
            # Failure
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.failure_count >= self.failure_threshold:
                self.state = "open"

class CircuitBreakerOpenError(Exception):
    """Exception raised when circuit breaker is open"""
    pass

# Retry mechanism
class RetryPolicy:
    """
    Simple retry policy implementation
    """
    
    def __init__(self, max_attempts: int = 3, base_delay: float = 1.0, max_delay: float = 30.0):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
    
    async def execute(self, func: Callable, *args, **kwargs):
        """Execute function with retry policy"""
        last_exception = None
        
        for attempt in range(self.max_attempts):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                
                if attempt < self.max_attempts - 1:
                    delay = min(self.base_delay * (2 ** attempt), self.max_delay)
                    await asyncio.sleep(delay)
                else:
                    break
        
        raise MaxRetriesExceededError(f"Max retries ({self.max_attempts}) exceeded") from last_exception

class MaxRetriesExceededError(Exception):
    """Exception raised when max retries are exceeded"""
    pass

# Logging setup
def setup_compat_logging():
    """Setup logging for compatibility layer"""
    logger = logging.getLogger("server.agent.langgraph.compat")
    logger.setLevel(logging.INFO)
    
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    return logger

# Initialize logging
setup_compat_logging()

logger.info("LangGraph compatibility layer initialized for Python 3.8") 
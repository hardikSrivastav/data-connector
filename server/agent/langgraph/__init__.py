"""
LangGraph Integration for Ceneca's Multi-Tier LLM Infrastructure

This package provides LangGraph-based orchestration capabilities while preserving
the existing high-performance trivial routing system.

Components:
- compat: LangGraph compatibility layer for Python 3.8
- state: Hybrid state management combining LangGraph with existing sessions
- streaming: Transparent streaming layer for LangGraph workflows
- nodes: LangGraph nodes converted from existing agents
- graphs: Dynamic graph construction and optimization
"""

# Import compatibility layer first
from .compat import GraphState, BaseNode, Graph, GraphBuilder, create_graph_state, create_simple_graph

# Import main components
from .state import HybridStateManager
from .streaming import StreamingGraphCoordinator
from .graphs.builder import DatabaseDrivenGraphBuilder

# For backwards compatibility, alias GraphState as LangGraphState
LangGraphState = GraphState

__all__ = [
    "GraphState",
    "LangGraphState",
    "BaseNode", 
    "Graph",
    "GraphBuilder",
    "create_graph_state",
    "create_simple_graph",
    "HybridStateManager",
    "StreamingGraphCoordinator",
    "DatabaseDrivenGraphBuilder"
] 
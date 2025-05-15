"""
Cross-Database Orchestration

This package contains the implementation of the cross-database orchestrator,
which enables querying multiple databases with a single natural language query.
"""

# Import other modules first to avoid circular imports
from .result_aggregator import ResultAggregator

# Import main class lazily to avoid circular references
def get_cross_db_orchestrator():
    """Lazily import and return the CrossDatabaseOrchestrator class to avoid circular imports"""
    from .cross_db_orchestrator import CrossDatabaseOrchestrator
    return CrossDatabaseOrchestrator

__all__ = ['ResultAggregator', 'get_cross_db_orchestrator'] 
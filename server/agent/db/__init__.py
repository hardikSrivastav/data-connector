"""
Database module for data-connector agent

This module contains database adapters, execution helpers,
and the orchestrator for translating natural language to queries.
"""

# Import public API exports
from .execute import test_conn
from .db_orchestrator import Orchestrator
from . import adapters
from .introspect import get_schema_metadata

# Re-export core classes
__all__ = [
    'test_conn',
    'Orchestrator',
    'adapters',
    'get_schema_metadata',
]

# Import orchestrator package if needed - as a separate namespace
from . import orchestrator as orchestrator_pkg

async def get_orchestrator(**kwargs):
    """
    Factory function to get an Orchestrator instance
    
    This function creates a new Orchestrator instance with the
    provided arguments.
    
    Args:
        **kwargs: Arguments to pass to the Orchestrator constructor
        
    Returns:
        Orchestrator instance
    """
    from ..config.settings import Settings
    
    settings = Settings()
    
    # If URI is not provided, use the one from settings
    if 'uri' not in kwargs:
        kwargs['uri'] = settings.connection_uri
    
    # Create and return the orchestrator
    return Orchestrator(**kwargs)

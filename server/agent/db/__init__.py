"""
Database module for the agent.
Provides access to database functionality through adapters.
"""

async def get_orchestrator(**kwargs):
    """
    Get an orchestrator instance configured with the default connection URI.
    
    Args:
        **kwargs: Additional parameters to pass to the adapter
        
    Returns:
        Orchestrator instance
    """
    from .orchestrator import Orchestrator
    from ..config.settings import Settings
    
    settings = Settings()
    return Orchestrator(settings.connection_uri, **kwargs)

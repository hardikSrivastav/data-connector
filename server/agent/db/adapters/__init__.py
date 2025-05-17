"""
Database adapters module.
Provides a common interface for different types of databases.
"""

import logging
from typing import Dict, Type

from .base import DBAdapter
from .postgres import PostgresAdapter
from .mongo import MongoAdapter
from .qdrant import QdrantAdapter, EmbeddingProvider
from .slack import SlackAdapter
from .ga4 import GA4Adapter

# Configure logging
logger = logging.getLogger(__name__)

# Registry of database adapters
ADAPTER_REGISTRY: Dict[str, Type[DBAdapter]] = {
    "postgres": PostgresAdapter,
    "postgresql": PostgresAdapter,
    "mongodb": MongoAdapter,
    "mongo": MongoAdapter,
    "qdrant": QdrantAdapter,
    "slack": SlackAdapter,
    "ga4": GA4Adapter,
}

__all__ = ['DBAdapter', 'PostgresAdapter', 'MongoAdapter', 'QdrantAdapter', 'EmbeddingProvider', 'SlackAdapter', 'GA4Adapter'] 
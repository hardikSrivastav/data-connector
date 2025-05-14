"""
Database adapters module.
Provides a common interface for different types of databases.
"""

from .base import DBAdapter
from .postgres import PostgresAdapter
from .mongo import MongoAdapter
from .qdrant import QdrantAdapter, EmbeddingProvider
from .slack import SlackAdapter

# Register adapter classes
ADAPTER_REGISTRY = {
    "postgres": PostgresAdapter,
    "postgresql": PostgresAdapter,
    "mongodb": MongoAdapter,
    "mongo": MongoAdapter,
    "qdrant": QdrantAdapter,
    "slack": SlackAdapter,
}

__all__ = ['DBAdapter', 'PostgresAdapter', 'MongoAdapter', 'QdrantAdapter', 'EmbeddingProvider', 'SlackAdapter'] 
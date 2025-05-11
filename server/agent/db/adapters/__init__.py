"""
Database adapters module.
Provides a common interface for different types of databases.
"""

from .base import DBAdapter
from .postgres import PostgresAdapter
from .mongo import MongoAdapter
from .qdrant import QdrantAdapter, EmbeddingProvider

__all__ = ['DBAdapter', 'PostgresAdapter', 'MongoAdapter', 'QdrantAdapter', 'EmbeddingProvider'] 
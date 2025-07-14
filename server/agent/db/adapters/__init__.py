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
from .shopify import ShopifyAdapter
from .ga4 import GA4Adapter
from .uniware import UniwareAdapter
from .payu import PayUAdapter
from .easebuzz import EasebuzzAdapter
from .shiprocket import ShiprocketAdapter

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
    "shopify": ShopifyAdapter,
    "ga4": GA4Adapter,
    "uniware": UniwareAdapter,
    "payu": PayUAdapter,
    "easebuzz": EasebuzzAdapter,
    "shiprocket": ShiprocketAdapter,
}

__all__ = ['DBAdapter', 'PostgresAdapter', 'MongoAdapter', 'QdrantAdapter', 'EmbeddingProvider', 'SlackAdapter', 'ShopifyAdapter', 'GA4Adapter', 'UniwareAdapter', 'PayUAdapter', 'EasebuzzAdapter', 'ShiprocketAdapter'] 
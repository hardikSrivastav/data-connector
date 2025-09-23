#!/usr/bin/env python3
"""
Multi-Instance Configuration Parser

This module provides an intelligent abstraction layer that automatically detects
and handles multiple instances of database types from config.yaml files.

Key Features:
- Auto-detects single vs multiple instance configurations
- Supports nested named instances (e.g., mongodb: { main: {...}, cmots: {...} })
- Maintains backward compatibility with existing single-instance configs
- Extensible to any database type without hardcoding
- Validates configuration structure and provides helpful error messages
"""

import logging
from typing import Dict, List, Any, Optional, Union, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class DatabaseInstance:
    """Represents a single database instance configuration."""
    id: str
    uri: str
    type: str
    version: str = "1.0.0"
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format expected by schema registry."""
        result = {
            "id": self.id,
            "uri": self.uri,
            "type": self.type,
            "version": self.version
        }
        if self.metadata:
            result.update(self.metadata)
        return result

@dataclass
class DatabaseTypeConfig:
    """Represents configuration for a database type (single or multiple instances)."""
    db_type: str
    instances: List[DatabaseInstance]
    is_multi_instance: bool
    
    def get_instance_count(self) -> int:
        return len(self.instances)
    
    def get_instance_ids(self) -> List[str]:
        return [instance.id for instance in self.instances]

class MultiInstanceConfigParser:
    """
    Intelligent configuration parser that automatically detects and handles
    multiple database instances of the same type.
    """
    
    # Known database types that Ceneca supports
    SUPPORTED_DB_TYPES = {
        'postgres', 'postgresql', 'mongodb', 'mongo', 'qdrant', 
        'slack', 'shopify', 'ga4', 'uniware', 'payu', 'easebuzz', 'shiprocket'
    }
    
    # Fields that indicate a direct database configuration (single instance)
    DIRECT_CONFIG_FIELDS = {'uri', 'host', 'port', 'database', 'user', 'password'}
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize parser with configuration dictionary.
        
        Args:
            config: Loaded YAML configuration dictionary
        """
        self.config = config
        self.parsed_configs: Dict[str, DatabaseTypeConfig] = {}
        self._parse_all_databases()
    
    def _parse_all_databases(self) -> None:
        """Parse all database configurations in the config."""
        for db_type in self.SUPPORTED_DB_TYPES:
            if db_type in self.config:
                try:
                    db_config = self._parse_database_type(db_type, self.config[db_type])
                    if db_config.instances:  # Only add if we found valid instances
                        self.parsed_configs[db_type] = db_config
                        logger.info(f"Parsed {db_type}: {db_config.get_instance_count()} instance(s)")
                except Exception as e:
                    logger.error(f"Failed to parse {db_type} configuration: {e}")
    
    def _parse_database_type(self, db_type: str, config_section: Dict[str, Any]) -> DatabaseTypeConfig:
        """
        Parse configuration section for a specific database type.
        
        Args:
            db_type: Database type (e.g., 'mongodb', 'postgres')
            config_section: Configuration section for this database type
            
        Returns:
            DatabaseTypeConfig with parsed instances
        """
        instances = []
        
        # Check if this is a direct single-instance configuration
        if self._is_direct_config(config_section):
            instance = self._parse_single_instance(db_type, "main", config_section)
            if instance:
                instances.append(instance)
            return DatabaseTypeConfig(
                db_type=db_type,
                instances=instances,
                is_multi_instance=False
            )
        
        # Parse as multi-instance configuration
        for instance_name, instance_config in config_section.items():
            if isinstance(instance_config, dict):
                instance = self._parse_single_instance(db_type, instance_name, instance_config)
                if instance:
                    instances.append(instance)
                else:
                    logger.warning(f"Skipping invalid {db_type} instance: {instance_name}")
        
        return DatabaseTypeConfig(
            db_type=db_type,
            instances=instances,
            is_multi_instance=len(instances) > 1
        )
    
    def _is_direct_config(self, config_section: Dict[str, Any]) -> bool:
        """
        Determine if config section is a direct database configuration.
        
        Args:
            config_section: Configuration section to analyze
            
        Returns:
            True if this appears to be a direct database config, False if nested instances
        """
        # If any direct config fields are present, treat as single instance
        return any(field in config_section for field in self.DIRECT_CONFIG_FIELDS)
    
    def _parse_single_instance(
        self, 
        db_type: str, 
        instance_name: str, 
        instance_config: Dict[str, Any]
    ) -> Optional[DatabaseInstance]:
        """
        Parse a single database instance configuration.
        
        Args:
            db_type: Database type
            instance_name: Name of this instance
            instance_config: Configuration for this instance
            
        Returns:
            DatabaseInstance if valid, None if invalid
        """
        # Extract URI - try direct uri field first
        uri = instance_config.get('uri')
        
        # If no direct URI, try to construct from components
        if not uri:
            uri = self._construct_uri_from_components(db_type, instance_config)
        
        if not uri:
            logger.error(f"No valid URI found for {db_type} instance '{instance_name}'")
            return None
        
        # Create instance ID
        instance_id = f"{db_type}_{instance_name}"
        
        # Extract additional metadata (everything except URI components)
        metadata = {}
        for key, value in instance_config.items():
            if key not in self.DIRECT_CONFIG_FIELDS:
                metadata[key] = value
        
        return DatabaseInstance(
            id=instance_id,
            uri=uri,
            type=db_type,
            metadata=metadata if metadata else None
        )
    
    def _construct_uri_from_components(
        self, 
        db_type: str, 
        config: Dict[str, Any]
    ) -> Optional[str]:
        """
        Construct database URI from individual components.
        
        Args:
            db_type: Database type
            config: Configuration with individual components
            
        Returns:
            Constructed URI or None if insufficient information
        """
        host = config.get('host')
        port = config.get('port')
        database = config.get('database')
        user = config.get('user')
        password = config.get('password')
        
        if not host:
            return None
        
        # Database-specific URI construction
        if db_type in ['postgres', 'postgresql']:
            if not all([database, user, password]):
                return None
            port = port or 5432
            return f"postgresql://{user}:{password}@{host}:{port}/{database}"
        
        elif db_type in ['mongodb', 'mongo']:
            port = port or 27017
            if user and password:
                if database:
                    return f"mongodb://{user}:{password}@{host}:{port}/{database}?authSource=admin"
                else:
                    return f"mongodb://{user}:{password}@{host}:{port}/?authSource=admin"
            else:
                if database:
                    return f"mongodb://{host}:{port}/{database}"
                else:
                    return f"mongodb://{host}:{port}/"
        
        elif db_type == 'qdrant':
            port = port or 6333
            return f"http://{host}:{port}"
        
        # For other database types, we might need URI directly
        return None
    
    def get_all_instances(self) -> List[DatabaseInstance]:
        """Get all parsed database instances across all types."""
        instances = []
        for db_config in self.parsed_configs.values():
            instances.extend(db_config.instances)
        return instances
    
    def get_instances_by_type(self, db_type: str) -> List[DatabaseInstance]:
        """Get all instances for a specific database type."""
        if db_type in self.parsed_configs:
            return self.parsed_configs[db_type].instances
        return []
    
    def get_instance_by_id(self, instance_id: str) -> Optional[DatabaseInstance]:
        """Get a specific instance by its ID."""
        for instance in self.get_all_instances():
            if instance.id == instance_id:
                return instance
        return None
    
    def has_multi_instance_type(self, db_type: str) -> bool:
        """Check if a database type has multiple instances configured."""
        if db_type in self.parsed_configs:
            return self.parsed_configs[db_type].is_multi_instance
        return False
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of parsed configuration."""
        summary = {
            "total_instances": len(self.get_all_instances()),
            "database_types": len(self.parsed_configs),
            "multi_instance_types": [],
            "single_instance_types": [],
            "instances_by_type": {}
        }
        
        for db_type, db_config in self.parsed_configs.items():
            if db_config.is_multi_instance:
                summary["multi_instance_types"].append(db_type)
            else:
                summary["single_instance_types"].append(db_type)
            
            summary["instances_by_type"][db_type] = {
                "count": db_config.get_instance_count(),
                "instance_ids": db_config.get_instance_ids()
            }
        
        return summary
    
    def to_schema_registry_format(self) -> List[Dict[str, Any]]:
        """
        Convert all parsed instances to schema registry format.
        
        Returns:
            List of data source configurations compatible with existing schema registry
        """
        return [instance.to_dict() for instance in self.get_all_instances()]


def parse_multi_instance_config(config: Dict[str, Any]) -> MultiInstanceConfigParser:
    """
    Convenience function to parse multi-instance configuration.
    
    Args:
        config: Loaded YAML configuration dictionary
        
    Returns:
        Configured MultiInstanceConfigParser
    """
    return MultiInstanceConfigParser(config)


# Example usage and testing
if __name__ == "__main__":
    # Test with sample configurations
    
    # Single instance config (backward compatibility)
    single_config = {
        "mongodb": {
            "uri": "mongodb://user:pass@localhost:27017/mydb"
        },
        "postgres": {
            "host": "localhost",
            "port": 5432,
            "database": "mydb",
            "user": "user",
            "password": "pass"
        }
    }
    
    # Multi-instance config (new format)
    multi_config = {
        "mongodb": {
            "main": {
                "uri": "mongodb://172.31.18.152:27017/financial_data",
                "database": "financial_data",
                "pool_size": 10,
                "connect_timeout_ms": 5000
            },
            "cmots": {
                "uri": "mongodb://172.31.18.152:27017/discvr_finance",
                "database": "discvr_finance",
                "pool_size": 10,
                "connect_timeout_ms": 5000
            },
            "backend": {
                "uri": "mongodb://172.31.18.152:27017/finance_cards",
                "database": "finance_cards",
                "pool_size": 10,
                "connect_timeout_ms": 5000
            }
        }
    }
    
    print("=== Testing Single Instance Config ===")
    parser1 = parse_multi_instance_config(single_config)
    print(f"Summary: {parser1.get_summary()}")
    print(f"Schema registry format: {parser1.to_schema_registry_format()}")
    
    print("\n=== Testing Multi-Instance Config ===")
    parser2 = parse_multi_instance_config(multi_config)
    print(f"Summary: {parser2.get_summary()}")
    print(f"Schema registry format: {parser2.to_schema_registry_format()}")

"""
Base classes for query plan representation.

Provides the core abstractions for operations and query plans.
"""

import uuid
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Set, Union
from datetime import datetime
import logging
from enum import Enum, auto

# Configure logging
logger = logging.getLogger(__name__)

class OperationStatus(str, Enum):
    """Status of a database operation"""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class Operation(ABC):
    """
    Abstract base class for all database operations
    
    Operations represent individual database queries or commands that can be
    executed as part of a query plan. Operations can depend on other operations.
    """
    
    def __init__(
        self, 
        id: str = None, 
        source_id: str = None, 
        depends_on: List[str] = None,
        metadata: Dict[str, Any] = None
    ):
        """
        Initialize a database operation
        
        Args:
            id: Unique identifier for this operation
            source_id: ID of the data source this operation targets
            depends_on: List of operation IDs this operation depends on
            metadata: Additional metadata for this operation
        """
        self.id = id or str(uuid.uuid4())
        self.source_id = source_id
        self.depends_on = depends_on or []
        self.metadata = metadata or {}
        self.result = None
        self.error = None
        self.execution_time = 0
        self.status = OperationStatus.PENDING
    
    @abstractmethod
    def get_adapter_params(self) -> Dict[str, Any]:
        """
        Get parameters to pass to the database adapter
        
        Returns:
            Dictionary of parameters specific to this operation type
        """
        pass
    
    def validate(self, schema_registry=None) -> bool:
        """
        Validate this operation against the schema registry
        
        Args:
            schema_registry: Schema registry client
            
        Returns:
            True if valid, False otherwise
        """
        # Base validation: ensure we have a source_id
        if not self.source_id:
            logger.error(f"Operation {self.id} missing source_id")
            return False
            
        return True
    
    def __str__(self) -> str:
        """String representation of this operation"""
        return f"{self.__class__.__name__}(id={self.id}, source={self.source_id})"
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert operation to dictionary representation
        
        Returns:
            Dictionary representation of this operation
        """
        return {
            "id": self.id,
            "source_id": self.source_id,
            "depends_on": self.depends_on,
            "metadata": self.metadata,
            "type": self.__class__.__name__,
            "result": self.result,
            "error": self.error,
            "execution_time": self.execution_time,
            "status": self.status
        }


class QueryPlan:
    """
    Represents a complete query plan with multiple operations
    
    A query plan is a collection of database operations with dependencies
    between them, forming a directed acyclic graph (DAG).
    """
    
    def __init__(
        self, 
        operations: List[Operation] = None,
        metadata: Dict[str, Any] = None
    ):
        """
        Initialize a query plan
        
        Args:
            operations: List of operations in this plan
            metadata: Additional metadata for this plan
        """
        self.operations = operations or []
        self.metadata = metadata or {
            "created_at": datetime.now().isoformat(),
            "version": "1.0"
        }
        self.id = str(uuid.uuid4())
    
    @property
    def plan_id(self) -> str:
        """Alias for id to maintain compatibility with implementation agent"""
        return self.id
        
    @property
    def output_operation_id(self) -> Optional[str]:
        """ID of the operation to use as final output"""
        return self.metadata.get("output_operation_id")
    
    def add_operation(self, operation: Operation) -> None:
        """
        Add an operation to this plan
        
        Args:
            operation: Operation to add
        """
        self.operations.append(operation)
    
    def get_operation(self, operation_id: str) -> Optional[Operation]:
        """
        Get an operation by ID
        
        Args:
            operation_id: ID of the operation to get
            
        Returns:
            Operation or None if not found
        """
        for op in self.operations:
            if op.id == operation_id:
                return op
        return None
    
    def validate(self, schema_registry=None) -> Dict[str, Any]:
        """
        Validate all operations in this plan
        
        Args:
            schema_registry: Schema registry client to validate against
            
        Returns:
            Dictionary with validation results
        """
        results = {
            "valid": True,
            "errors": []
        }
        
        # Check if the plan has operations
        if not self.operations:
            results["valid"] = False
            results["errors"].append("Plan has no operations")
            return results
        
        # Validate each operation
        for op in self.operations:
            logger.info(f"Validating operation {op.id} of type {op.__class__.__name__}")
            if not op.validate(schema_registry):
                logger.warning(f"Operation {op.id} failed validation")
                results["valid"] = False
                results["errors"].append(f"Invalid operation: {op.id}")
        
        # Check for cycles in the dependency graph
        try:
            from .dag import OperationDAG
            logger.info("Checking for cycles in the operation dependency graph")
            dag = OperationDAG(self)
            
            # Log the dependency structure
            logger.info("Dependency structure:")
            for op in self.operations:
                logger.info(f"  {op.id} depends on: {op.depends_on}")
            
            if dag.has_cycles():
                logger.warning("Cyclic dependencies detected in the plan")
                results["valid"] = False
                results["errors"].append("Plan has cyclic dependencies")
            else:
                logger.info("No cyclic dependencies detected in the plan")
        except Exception as e:
            logger.error(f"Error checking for cycles: {str(e)}")
            results["valid"] = False
            results["errors"].append(f"Error checking for cycles: {str(e)}")
        
        return results
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert plan to dictionary representation
        
        Returns:
            Dictionary representation of this plan
        """
        return {
            "id": self.id,
            "metadata": self.metadata,
            "operations": [op.to_dict() for op in self.operations]
        } 
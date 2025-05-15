"""
Result Aggregator

This module provides functionality for aggregating results from different databases
with different schemas and data types.
"""

import logging
from typing import Dict, List, Any, Optional, Set, Tuple, Callable
from datetime import datetime
import json

# Configure logging
logger = logging.getLogger(__name__)

class ResultAggregator:
    """
    Aggregator for combining results from different databases.
    
    This class provides functionality for:
    1. Type coercion between different database types
    2. Joining results from different databases
    3. Handling different result formats
    """
    
    def __init__(self):
        """Initialize the result aggregator"""
        # Type coercion functions
        self.type_coercers = {
            'date': lambda v: (
                datetime.fromisoformat(v.replace('Z', '+00:00')) 
                if isinstance(v, str) else v
            ),
            'int': lambda v: int(float(v)) if v is not None and (isinstance(v, (int, float, str))) else v,
            'float': lambda v: float(v) if v is not None and (isinstance(v, (int, float, str))) else v,
            'str': lambda v: str(v) if v is not None else v,
            'bool': lambda v: bool(v) if v is not None else v,
            'array': lambda v: v if isinstance(v, list) else [v] if v is not None else [],
            'object': lambda v: v if isinstance(v, dict) else json.loads(v) if isinstance(v, str) else {},
        }
    
    def coerce_value(self, value: Any, target_type: str) -> Any:
        """
        Coerce a value to a specific type.
        
        Args:
            value: The value to coerce
            target_type: The target type
            
        Returns:
            The coerced value
        """
        if target_type in self.type_coercers:
            try:
                return self.type_coercers[target_type](value)
            except Exception as e:
                logger.warning(f"Error coercing {value} to {target_type}: {e}")
                return value
        
        # Default: return as-is
        return value
    
    def coerce_record(self, record: Dict[str, Any], type_mapping: Dict[str, str]) -> Dict[str, Any]:
        """
        Coerce a record based on a type mapping.
        
        Args:
            record: The record to coerce
            type_mapping: Mapping of field names to target types
            
        Returns:
            The coerced record
        """
        if not isinstance(record, dict):
            logger.warning(f"Cannot coerce non-dict record: {record}")
            return record
        
        coerced = {}
        for field, value in record.items():
            if field in type_mapping:
                coerced[field] = self.coerce_value(value, type_mapping[field])
            else:
                coerced[field] = value
        
        return coerced
    
    def merge_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Simple merge of results from different databases.
        
        This just combines all results into a single list.
        
        Args:
            results: List of result dictionaries from different databases
            
        Returns:
            Combined list of results
        """
        all_data = []
        
        for result in results:
            if not result.get("success", False):
                continue
            
            source_id = result.get("source_id", "unknown")
            data = result.get("data", [])
            
            # Add source_id to each record
            for record in data:
                if isinstance(record, dict):
                    record["_source"] = source_id
            
            all_data.extend(data)
        
        return all_data
    
    def join_results(
        self, 
        results: List[Dict[str, Any]], 
        join_fields: Dict[str, str],
        type_mappings: Optional[Dict[str, Dict[str, str]]] = None
    ) -> List[Dict[str, Any]]:
        """
        Join results from different databases based on join fields.
        
        Args:
            results: List of result dictionaries from different databases
            join_fields: Mapping of source_id to join field
            type_mappings: Optional mapping of field names to target types for each source
            
        Returns:
            Joined list of results
        """
        if not results:
            return []
        
        # First, coerce types if mappings provided
        if type_mappings:
            for result in results:
                source_id = result.get("source_id", "unknown")
                if source_id in type_mappings:
                    mapping = type_mappings[source_id]
                    if result.get("success", False) and "data" in result:
                        result["data"] = [
                            self.coerce_record(record, mapping)
                            for record in result["data"]
                        ]
        
        # Extract data from successful results
        data_by_source = {}
        for result in results:
            if not result.get("success", False):
                continue
            
            source_id = result.get("source_id", "unknown")
            data = result.get("data", [])
            
            data_by_source[source_id] = data
        
        # If we don't have at least two sources with data, just merge
        if len(data_by_source) < 2:
            return self.merge_results(results)
        
        # Prepare join index
        join_indices = {}
        for source_id, data in data_by_source.items():
            if source_id not in join_fields:
                logger.warning(f"No join field specified for source {source_id}")
                continue
            
            join_field = join_fields[source_id]
            join_index = {}
            
            for i, record in enumerate(data):
                if not isinstance(record, dict):
                    continue
                
                if join_field not in record:
                    continue
                
                key = record[join_field]
                if key in join_index:
                    join_index[key].append(i)
                else:
                    join_index[key] = [i]
            
            join_indices[source_id] = join_index
        
        # Choose a primary source (the one with the most data)
        primary_source = max(data_by_source.keys(), key=lambda s: len(data_by_source[s]))
        
        # Perform the join
        joined_results = []
        primary_data = data_by_source[primary_source]
        primary_join_field = join_fields.get(primary_source)
        
        for primary_record in primary_data:
            if not isinstance(primary_record, dict):
                continue
            
            if primary_join_field not in primary_record:
                joined_record = primary_record.copy()
                joined_record["_source"] = primary_source
                joined_results.append(joined_record)
                continue
            
            key = primary_record[primary_join_field]
            joined_record = primary_record.copy()
            joined_record["_source"] = primary_source
            joined_record["_joined"] = True
            
            # Join with other sources
            for source_id, join_index in join_indices.items():
                if source_id == primary_source:
                    continue
                
                if key not in join_index:
                    continue
                
                # Get matching records
                matching_indices = join_index[key]
                matching_data = data_by_source[source_id]
                
                # Get the first matching record
                if matching_indices:
                    matching_record = matching_data[matching_indices[0]]
                    
                    # Add fields from matching record
                    for field, value in matching_record.items():
                        if field not in joined_record and field != join_fields.get(source_id):
                            joined_record[f"{source_id}_{field}"] = value
            
            joined_results.append(joined_record)
        
        return joined_results
    
    def union_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Union results from different databases.
        
        This returns a single list with duplicate values removed.
        
        Args:
            results: List of result dictionaries from different databases
            
        Returns:
            Union of results
        """
        # First, merge all results
        merged = self.merge_results(results)
        
        # Convert records to tuples for deduplication
        seen = set()
        unique_records = []
        
        for record in merged:
            if not isinstance(record, dict):
                unique_records.append(record)
                continue
            
            # Remove _source field for deduplication
            record_copy = record.copy()
            source = record_copy.pop("_source", None)
            
            # Convert to tuple for hashing
            try:
                record_tuple = tuple(sorted(record_copy.items()))
                if record_tuple not in seen:
                    seen.add(record_tuple)
                    unique_records.append(record)
            except:
                # If the record cannot be hashed, just include it
                unique_records.append(record)
        
        return unique_records
    
    def aggregate_results(
        self, 
        results: List[Dict[str, Any]], 
        operation: str = "merge",
        join_fields: Optional[Dict[str, str]] = None,
        type_mappings: Optional[Dict[str, Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Aggregate results from different databases.
        
        Args:
            results: List of result dictionaries from different databases
            operation: Aggregation operation: "merge", "join", or "union"
            join_fields: Mapping of source_id to join field (for join operation)
            type_mappings: Optional mapping of field names to target types for each source
            
        Returns:
            Dictionary with aggregated results
        """
        # Default response structure
        response = {
            "success": True,
            "sources_queried": [],
            "sources_succeeded": [],
            "sources_failed": [],
            "warnings": [],
            "results": []
        }
        
        # Collect metadata
        for result in results:
            source_id = result.get("source_id", "unknown")
            response["sources_queried"].append(source_id)
            
            if result.get("success", False):
                response["sources_succeeded"].append(source_id)
            else:
                response["sources_failed"].append(source_id)
                error = result.get("error", "Unknown error")
                response["warnings"].append(f"Query failed on {source_id}: {error}")
        
        # Perform the specified operation
        if operation == "join" and join_fields:
            response["results"] = self.join_results(results, join_fields, type_mappings)
        elif operation == "union":
            response["results"] = self.union_results(results)
        else:
            # Default to merge
            response["results"] = self.merge_results(results)
        
        # Set overall success
        response["success"] = len(response["sources_succeeded"]) > 0
        
        return response 
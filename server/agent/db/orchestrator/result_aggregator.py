"""
Result Aggregator for Cross-Database Orchestration

This module implements the result aggregation for cross-database queries.
It combines results from multiple database operations into a unified result.
"""

import logging
import json
import time
from datetime import datetime, date
from typing import Dict, List, Any, Optional, Union, Callable, Tuple, Iterator
import asyncio
import importlib
import uuid
from enum import Enum
import functools
import itertools
from collections import defaultdict

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define join types
class JoinType(str, Enum):
    INNER = "inner"
    LEFT = "left"
    RIGHT = "right"
    FULL = "full"

# Define supported aggregation functions
class AggregationFunction(str, Enum):
    COUNT = "count"
    SUM = "sum"
    AVG = "avg"
    MIN = "min"
    MAX = "max"
    MEDIAN = "median"
    STDDEV = "stddev"

class ResultAggregator:
    """
    Aggregator for combining results from multiple database operations.
    
    This class handles the combination of heterogeneous results from
    different database operations into a unified result set with advanced
    type coercion, join strategies, and performance optimizations.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the result aggregator.
        
        Args:
            config: Optional configuration dictionary with the following options:
                - cache_enabled: Whether to enable caching (default: False)
                - cache_ttl_seconds: Cache time-to-live in seconds (default: 300)
                - streaming_chunk_size: Number of rows to process in each chunk (default: 1000)
                - max_retry_attempts: Maximum number of retry attempts for failed operations (default: 3)
                - observability_enabled: Whether to collect metrics (default: True)
        """
        self.config = config or {}
        self._llm_client = None
        
        # Initialize cache if enabled
        self.cache_enabled = self.config.get("cache_enabled", False)
        self.cache_ttl_seconds = self.config.get("cache_ttl_seconds", 300)
        self.cache = {} if self.cache_enabled else None
        self.cache_timestamps = {} if self.cache_enabled else None
        
        # Configure performance settings
        self.streaming_chunk_size = self.config.get("streaming_chunk_size", 1000)
        self.max_retry_attempts = self.config.get("max_retry_attempts", 3)
        
        # Metric collection
        self.observability_enabled = self.config.get("observability_enabled", True)
        self.metrics = defaultdict(list) if self.observability_enabled else None
        
        # Type coercion registry: maps database-specific types to Python types
        self.type_coercions = {
            "postgres": {
                "uuid": lambda v: uuid.UUID(v) if isinstance(v, str) else v,
                "timestamp": lambda v: datetime.fromisoformat(v.replace("Z", "+00:00")) 
                              if isinstance(v, str) else v,
                "date": lambda v: date.fromisoformat(v) if isinstance(v, str) else v,
                "json": lambda v: json.loads(v) if isinstance(v, str) else v,
                "jsonb": lambda v: json.loads(v) if isinstance(v, str) else v,
                "array": lambda v: v if isinstance(v, list) else [v] if v is not None else []
            },
            "mongodb": {
                "objectId": lambda v: str(v),
                "date": lambda v: v.isoformat() if hasattr(v, 'isoformat') else v,
                "binary": lambda v: str(v) if not isinstance(v, str) else v,
                "array": lambda v: v if isinstance(v, list) else [v] if v is not None else []
            },
            # Add more database types as needed
        }
    
    @property
    def llm_client(self):
        """Lazy loading of LLM client to avoid circular imports"""
        if self._llm_client is None:
            # Import here to avoid circular dependency
            from ...llm.client import get_llm_client
            self._llm_client = get_llm_client()
        return self._llm_client
    
    def _record_metric(self, name: str, value: Any):
        """Record a metric for observability"""
        if self.observability_enabled and self.metrics is not None:
            self.metrics[name].append({"timestamp": time.time(), "value": value})
    
    def _convert_for_aggregation(self, value: Any, target_type: Optional[str] = None, 
                                source_db_type: Optional[str] = None) -> Any:
        """
        Convert a value to a format suitable for aggregation with enhanced type handling.
        
        Args:
            value: Value to convert
            target_type: Optional target type to convert to
            source_db_type: Source database type (postgres, mongodb, etc.)
            
        Returns:
            Converted value
        """
        if value is None:
            return None
            
        # Apply database-specific type conversions first
        if source_db_type and source_db_type in self.type_coercions:
            db_type_map = self.type_coercions[source_db_type]
            
            # This is a simplification - in a real system, you'd have more
            # information about the actual DB-specific type of each field
            for type_name, converter in db_type_map.items():
                # Try to match types based on patterns (a more robust system would use schema info)
                if type_name == "objectId" and isinstance(value, str) and len(value) == 24:
                    # This looks like a MongoDB ObjectId
                    return converter(value)
                elif type_name == "uuid" and isinstance(value, str) and "-" in value and len(value) == 36:
                    # This looks like a UUID
                    try:
                        return converter(value)
                    except (ValueError, TypeError):
                        pass
                elif type_name in ("timestamp", "date") and isinstance(value, str) and ("T" in value or "-" in value):
                    # This looks like a date/timestamp
                    try:
                        return converter(value)
                    except (ValueError, TypeError):
                        pass
                        
        # Handle custom types that might not be JSON serializable
        if hasattr(value, 'isoformat'):  # datetime objects
            return value.isoformat()
        elif isinstance(value, uuid.UUID):  # UUID objects
            return str(value)
        elif hasattr(value, '__dict__'):  # custom objects
            return str(value)
        elif isinstance(value, (set, frozenset)):
            return list(value)
        elif isinstance(value, (list, tuple)):
            return [self._convert_for_aggregation(item, target_type, source_db_type) for item in value]
        elif isinstance(value, dict):
            return {k: self._convert_for_aggregation(v, target_type, source_db_type) for k, v in value.items()}
        
        # Explicit type conversion if requested
        if target_type:
            try:
                if target_type == "int":
                    return int(value)
                elif target_type == "float":
                    return float(value)
                elif target_type == "str":
                    return str(value)
                elif target_type == "bool":
                    if isinstance(value, str):
                        return value.lower() in ("true", "yes", "1", "t", "y")
                    return bool(value)
                elif target_type == "date":
                    if isinstance(value, str):
                        return date.fromisoformat(value)
                    return value
                elif target_type == "datetime":
                    if isinstance(value, str):
                        return datetime.fromisoformat(value.replace("Z", "+00:00"))
                    return value
            except (ValueError, TypeError):
                logger.warning(f"Failed to convert {value} to {target_type}")
                return value
                
        return value
    
    async def aggregate_results(
        self, 
        query_plan: Any, 
        operation_results: Dict[str, Any],
        user_question: str
    ) -> Dict[str, Any]:
        """
        Aggregate results from multiple operations into a unified result.
        
        Args:
            query_plan: The query plan that was executed
            operation_results: Dictionary mapping operation IDs to results
            user_question: Original user question for context
            
        Returns:
            Aggregated result
        """
        logger.info("Aggregating results from multiple operations")
        start_time = time.time()
        
        try:
            # Convert operation results to JSON-serializable format
            processed_results = {}
            for op_id, result in operation_results.items():
                processed_results[op_id] = self._convert_for_aggregation(result)
            
            # Convert query plan to dict if it's not already
            if hasattr(query_plan, 'to_dict'):
                plan_dict = query_plan.to_dict()
            else:
                plan_dict = query_plan
            
            # Use LLM to aggregate results
            prompt = self.llm_client.render_template(
                "result_aggregator.tpl",
                query_plan=json.dumps(plan_dict, indent=2),
                operation_results=processed_results,
                user_question=user_question
            )
            
            # Call LLM for aggregation
            response = await self.llm_client.client.chat.completions.create(
                model=self.llm_client.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2
            )
            
            # Parse the JSON response
            content = response.choices[0].message.content
            # Extract JSON string from content
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0].strip()
            else:
                json_str = content.strip()
                
            aggregated_result = json.loads(json_str)
            
            # Record metrics
            end_time = time.time()
            if self.observability_enabled:
                self._record_metric("aggregation_time", end_time - start_time)
                self._record_metric("aggregation_success", True)
                self._record_metric("operations_count", len(operation_results))
            
            logger.info(f"Successfully aggregated results in {end_time - start_time:.2f}s")
            
            return aggregated_result
        except Exception as e:
            # Record metrics for failure
            if self.observability_enabled:
                self._record_metric("aggregation_success", False)
                self._record_metric("aggregation_error", str(e))
            
            logger.error(f"Error aggregating results: {e}")
            # Return a basic aggregation with error information
            return {
                "error": f"Failed to aggregate results: {str(e)}",
                "partial_results": operation_results
            }

    def get_metrics(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get collected metrics for observability"""
        if not self.observability_enabled or self.metrics is None:
            return {}
        return dict(self.metrics)
    
    def clear_metrics(self):
        """Clear collected metrics"""
        if self.observability_enabled and self.metrics is not None:
            self.metrics.clear()
    
    def _compare_values_with_coercion(
        self, 
        value1: Any, 
        value2: Any, 
        db1_type: Optional[str] = None,
        db2_type: Optional[str] = None,
        field1_type: Optional[str] = None,
        field2_type: Optional[str] = None
    ) -> bool:
        """
        Compare two values with appropriate type coercion.
        
        Args:
            value1: First value
            value2: Second value
            db1_type: Database type of first value
            db2_type: Database type of second value
            field1_type: Field type of first value
            field2_type: Field type of second value
            
        Returns:
            True if values are considered equal after coercion
        """
        # Convert both values
        v1 = self._convert_for_aggregation(value1, field2_type, db1_type)
        v2 = self._convert_for_aggregation(value2, field1_type, db2_type)
        
        # Special handling for common comparison cases
        
        # String comparison
        if isinstance(v1, str) or isinstance(v2, str):
            return str(v1) == str(v2)
            
        # Numeric comparison (allow int/float comparison)
        if isinstance(v1, (int, float)) and isinstance(v2, (int, float)):
            return abs(float(v1) - float(v2)) < 1e-10
            
        # Date/datetime comparison
        if (isinstance(v1, (date, datetime)) and isinstance(v2, (date, datetime))):
            # Compare dates, ignoring timezone info
            if isinstance(v1, datetime) and isinstance(v2, datetime):
                return v1.replace(tzinfo=None) == v2.replace(tzinfo=None)
            return v1 == v2
            
        # Lists comparison
        if isinstance(v1, list) and isinstance(v2, list):
            # For lists, check if they have the same elements (allowing for different order)
            try:
                return sorted(v1) == sorted(v2)
            except TypeError:
                # If sorting fails, just do normal equality check
                return v1 == v2
                
        # Default: direct comparison
        return v1 == v2
    
    def merge_results(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Merge results from multiple sources without LLM involvement.
        
        This is a simpler alternative to LLM-based aggregation.
        
        Args:
            results: List of result dictionaries from different sources
            
        Returns:
            Merged result dictionary
        """
        # Count successful and failed operations
        success_count = sum(1 for r in results if r.get("success", False))
        failed_count = len(results) - success_count
        
        # Collect all data
        all_data = []
        for result in results:
            if result.get("success", False) and "data" in result:
                data = result.get("data", [])
                if isinstance(data, list):
                    all_data.extend(data)
                else:
                    all_data.append(data)
        
        # Create merged result
        merged = {
            "success": success_count > 0,
            "sources_queried": len(results),
            "successful_sources": success_count,
            "failed_sources": failed_count,
            "total_rows": len(all_data),
            "results": all_data
        }
        
        # Add errors if any
        errors = []
        for result in results:
            if not result.get("success", False) and "error" in result:
                errors.append({
                    "source_id": result.get("source_id", "unknown"),
                    "error": result.get("error")
                })
        
        if errors:
            merged["errors"] = errors
        
        return merged
    
    def join_results(
        self, 
        results: List[Dict[str, Any]], 
        join_fields: Optional[Dict[str, str]] = None,
        join_type: JoinType = JoinType.INNER,
        type_mappings: Optional[Dict[str, Dict[str, str]]] = None,
        db_types: Optional[Dict[str, str]] = None,
        multi_field_joins: Optional[Dict[str, List[str]]] = None,
        join_predicates: Optional[Dict[str, Callable[[Any, Any], bool]]] = None
    ) -> Dict[str, Any]:
        """
        Join results from multiple sources with enhanced join capabilities.
        
        Args:
            results: List of result dictionaries from different sources
            join_fields: Mapping of source_id to field name to join on
            join_type: Type of join to perform (INNER, LEFT, RIGHT, FULL)
            type_mappings: Mapping of source_id to field type mappings
            db_types: Mapping of source_id to database type
            multi_field_joins: Mapping of source_id to list of fields for composite joins
            join_predicates: Custom predicates for complex join conditions
            
        Returns:
            Joined result dictionary
        """
        start_time = time.time()
        
        if not join_fields and not multi_field_joins:
            logger.warning("No join fields specified, falling back to merge")
            return self.merge_results(results)
        
        # Process each source's data
        source_data = {}
        for result in results:
            if result.get("success", False) and "data" in result:
                source_id = result.get("source_id", "unknown")
                data = result.get("data", [])
                if isinstance(data, list):
                    source_data[source_id] = data
                else:
                    source_data[source_id] = [data]
        
        # If we don't have enough sources, fall back to merge
        if len(source_data) < 2:
            logger.warning("Not enough successful sources for join, falling back to merge")
            return self.merge_results(results)
        
        # Perform join
        joined_data = []
        
        # Get the primary source (first one)
        primary_source_id = list(source_data.keys())[0]
        primary_data = source_data[primary_source_id]
        
        # For single field joins
        primary_join_field = join_fields.get(primary_source_id) if join_fields else None
        
        # For multi-field joins
        primary_join_fields = multi_field_joins.get(primary_source_id) if multi_field_joins else None
        
        if not primary_join_field and not primary_join_fields:
            logger.warning(f"No join field for primary source {primary_source_id}")
            return self.merge_results(results)
        
        # Get database type for the primary source
        primary_db_type = db_types.get(primary_source_id) if db_types else None
        
        # For each row in the primary source
        for primary_row in primary_data:
            # Check join field(s) existence
            if primary_join_field and primary_join_field not in primary_row:
                continue
                
            # For multi-field joins, check all fields exist
            if primary_join_fields and not all(f in primary_row for f in primary_join_fields):
                continue
                
            # Get join value(s)
            if primary_join_field:
                join_value = primary_row[primary_join_field]
            else:
                # For multi-field joins, create a tuple of values
                join_value = tuple(primary_row[f] for f in primary_join_fields)
            
            # Create a new row with primary data
            joined_row = {f"{primary_source_id}_{k}": v for k, v in primary_row.items()}
            
            # Tracks whether this primary row matched any secondary rows
            primary_had_match = False
            
            # Add data from other sources
            for source_id, data in source_data.items():
                if source_id == primary_source_id:
                    continue
                
                # Get join configuration for this source
                join_field = join_fields.get(source_id) if join_fields else None
                join_fields_list = multi_field_joins.get(source_id) if multi_field_joins else None
                db_type = db_types.get(source_id) if db_types else None
                
                if not join_field and not join_fields_list:
                    continue
                
                # Find matching rows
                matches = []
                source_matched = False
                
                for row in data:
                    match_found = False
                    
                    # Single field join
                    if join_field and join_field in row:
                        row_value = row[join_field]
                        
                        # Handle custom join predicate if provided
                        if join_predicates and (primary_source_id, source_id) in join_predicates:
                            predicate = join_predicates[(primary_source_id, source_id)]
                            if predicate(join_value, row_value):
                                matches.append(row)
                                match_found = True
                                source_matched = True
                        else:
                            # Use type coercion for comparison
                            field_type1 = type_mappings.get(primary_source_id, {}).get(primary_join_field) if type_mappings else None
                            field_type2 = type_mappings.get(source_id, {}).get(join_field) if type_mappings else None
                            
                            if self._compare_values_with_coercion(
                                join_value, row_value, 
                                primary_db_type, db_type,
                                field_type1, field_type2
                            ):
                                matches.append(row)
                                match_found = True
                                source_matched = True
                    
                    # Multi-field join
                    elif join_fields_list and all(f in row for f in join_fields_list):
                        row_values = tuple(row[f] for f in join_fields_list)
                        
                        # Only support direct comparison for multi-field joins
                        # A more sophisticated approach would check each field individually with type coercion
                        if join_value == row_values:
                            matches.append(row)
                            match_found = True
                            source_matched = True
                
                # Record if the primary row matched any row from this source
                if source_matched:
                    primary_had_match = True
                
                # Add matches to joined row
                if matches:
                    # For simplicity, use first match only
                    # A more advanced implementation would handle multiple matches
                    for k, v in matches[0].items():
                        joined_row[f"{source_id}_{k}"] = v
                elif join_type in (JoinType.LEFT, JoinType.FULL):
                    # For LEFT and FULL joins, add empty values for unmatched rows
                    if join_field:
                        joined_row[f"{source_id}_{join_field}"] = None
                    if join_fields_list:
                        for f in join_fields_list:
                            joined_row[f"{source_id}_{f}"] = None
            
            # Add the joined row to results based on join type
            if primary_had_match or join_type in (JoinType.LEFT, JoinType.FULL):
                joined_data.append(joined_row)
        
        # For RIGHT and FULL joins, add unmatched rows from secondary sources
        if join_type in (JoinType.RIGHT, JoinType.FULL):
            # Implementation would be similar to the above but starting from secondary sources
            # This is left as an exercise or future enhancement
            pass
        
        # Record metrics
        if self.observability_enabled:
            end_time = time.time()
            self._record_metric("join_time", end_time - start_time)
            self._record_metric("join_rows", len(joined_data))
            self._record_metric("join_sources", len(source_data))
        
        return {
            "success": True,
            "sources_joined": len(source_data),
            "join_type": join_type,
            "join_fields": join_fields,
            "multi_field_joins": multi_field_joins if multi_field_joins else None,
            "total_rows": len(joined_data),
            "results": joined_data
        }
    
    def stream_aggregation(
        self, 
        data_iterators: Dict[str, Iterator[Dict[str, Any]]],
        aggregation_func: Callable,
        chunk_size: Optional[int] = None
    ) -> Iterator[Dict[str, Any]]:
        """
        Stream-process large datasets without loading everything into memory.
        
        Args:
            data_iterators: Dictionary of source_id -> data iterators
            aggregation_func: Function to aggregate chunks of data
            chunk_size: Number of items to process in each chunk
            
        Returns:
            Iterator of aggregated result chunks
        """
        chunk_size = chunk_size or self.streaming_chunk_size
        
        # Process data in chunks
        while True:
            # Get chunks from each iterator
            chunks = {}
            any_data = False
            
            for source_id, iterator in data_iterators.items():
                chunk = list(itertools.islice(iterator, chunk_size))
                if chunk:
                    chunks[source_id] = chunk
                    any_data = True
            
            # If no more data from any source, we're done
            if not any_data:
                break
                
            # Apply aggregation function to chunks
            result = aggregation_func(chunks)
            yield result
    
    def apply_aggregate_function(
        self, 
        data: List[Dict[str, Any]],
        function: AggregationFunction,
        field: str
    ) -> Any:
        """
        Apply an aggregation function to a field in the data.
        
        Args:
            data: List of data records
            function: Aggregation function to apply
            field: Field to aggregate
            
        Returns:
            Aggregated value
        """
        if not data:
            return None
            
        # Extract field values, skipping None values
        values = [record[field] for record in data if field in record and record[field] is not None]
        
        if not values:
            return None
            
        # Apply the aggregation function
        if function == AggregationFunction.COUNT:
            return len(values)
        elif function == AggregationFunction.SUM:
            try:
                return sum(float(v) for v in values)
            except (ValueError, TypeError):
                logger.warning(f"Cannot sum non-numeric values for field {field}")
                return None
        elif function == AggregationFunction.AVG:
            try:
                return sum(float(v) for v in values) / len(values)
            except (ValueError, TypeError):
                logger.warning(f"Cannot average non-numeric values for field {field}")
                return None
        elif function == AggregationFunction.MIN:
            try:
                return min(values)
            except (ValueError, TypeError):
                logger.warning(f"Cannot find minimum of incomparable values for field {field}")
                return None
        elif function == AggregationFunction.MAX:
            try:
                return max(values)
            except (ValueError, TypeError):
                logger.warning(f"Cannot find maximum of incomparable values for field {field}")
                return None
        elif function == AggregationFunction.MEDIAN:
            try:
                sorted_values = sorted(float(v) for v in values)
                mid = len(sorted_values) // 2
                if len(sorted_values) % 2 == 0:
                    return (sorted_values[mid-1] + sorted_values[mid]) / 2
                else:
                    return sorted_values[mid]
            except (ValueError, TypeError):
                logger.warning(f"Cannot find median of non-numeric values for field {field}")
                return None
        elif function == AggregationFunction.STDDEV:
            try:
                values_float = [float(v) for v in values]
                mean = sum(values_float) / len(values_float)
                variance = sum((x - mean) ** 2 for x in values_float) / len(values_float)
                return variance ** 0.5
            except (ValueError, TypeError):
                logger.warning(f"Cannot calculate standard deviation of non-numeric values for field {field}")
                return None
        else:
            logger.warning(f"Unsupported aggregation function: {function}")
            return None
    
    def group_by_aggregation(
        self,
        data: List[Dict[str, Any]],
        group_by_fields: List[str],
        aggregations: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Perform GROUP BY-like aggregation on data.
        
        Args:
            data: List of data records
            group_by_fields: Fields to group by
            aggregations: List of aggregation specifications, each with:
                - function: Aggregation function to apply
                - field: Field to aggregate
                - output_field: Name for the output field
            
        Returns:
            List of aggregated records
        """
        if not data or not group_by_fields or not aggregations:
            return []
            
        # Group data by the specified fields
        groups = defaultdict(list)
        
        for record in data:
            # Create a composite key for grouping
            # Skip records that don't have all group_by fields
            try:
                key = tuple(record[field] for field in group_by_fields)
                groups[key].append(record)
            except KeyError:
                continue
                
        # Apply aggregations to each group
        result = []
        
        for key, group_data in groups.items():
            # Create a new record with group by fields
            record = {field: value for field, value in zip(group_by_fields, key)}
            
            # Apply each aggregation
            for agg in aggregations:
                function = AggregationFunction(agg["function"])
                field = agg["field"]
                output_field = agg.get("output_field", f"{function.value}_{field}")
                
                record[output_field] = self.apply_aggregate_function(group_data, function, field)
                
            result.append(record)
            
        return result
    
    def aggregate_results_legacy(
        self, 
        results: List[Dict[str, Any]], 
        operation: str = "merge",
        join_fields: Optional[Dict[str, str]] = None,
        type_mappings: Optional[Dict[str, Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Legacy method for aggregating results.
        
        This method is kept for backward compatibility.
        
        Args:
            results: List of result dictionaries from different sources
            operation: Aggregation operation (merge, join, union)
            join_fields: Mapping of source_id to field name to join on
            type_mappings: Mapping of source_id to field type mappings
            
        Returns:
            Aggregated result dictionary
        """
        if operation == "join":
            return self.join_results(results, join_fields, JoinType.INNER, type_mappings)
        else:
            return self.merge_results(results) 
"""
Result Aggregator for Cross-Database Orchestration

This module implements the result aggregation for cross-database queries.
It combines results from multiple database operations into a unified result.
"""

import logging
import json
from typing import Dict, List, Any, Optional, Union
import asyncio
import importlib

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ResultAggregator:
    """
    Aggregator for combining results from multiple database operations.
    
    This class handles the combination of heterogeneous results from
    different database operations into a unified result set.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the result aggregator.
        
        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
        self._llm_client = None
    
    @property
    def llm_client(self):
        """Lazy loading of LLM client to avoid circular imports"""
        if self._llm_client is None:
            # Import here to avoid circular dependency
            from ...llm.client import get_llm_client
            self._llm_client = get_llm_client()
        return self._llm_client
    
    def _convert_for_aggregation(self, value: Any) -> Any:
        """
        Convert a value to a format suitable for aggregation.
        
        Args:
            value: Value to convert
            
        Returns:
            Converted value
        """
        # Handle custom types that might not be JSON serializable
        if hasattr(value, 'isoformat'):  # datetime objects
            return value.isoformat()
        elif hasattr(value, '__dict__'):  # custom objects
            return str(value)
        elif isinstance(value, (set, frozenset)):
            return list(value)
        elif isinstance(value, (list, tuple)):
            return [self._convert_for_aggregation(item) for item in value]
        elif isinstance(value, dict):
            return {k: self._convert_for_aggregation(v) for k, v in value.items()}
        else:
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
            
            logger.info("Successfully aggregated results")
            
            return aggregated_result
        except Exception as e:
            logger.error(f"Error aggregating results: {e}")
            # Return a basic aggregation with error information
            return {
                "error": f"Failed to aggregate results: {str(e)}",
                "partial_results": operation_results
            }
    
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
        type_mappings: Optional[Dict[str, Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Join results from multiple sources on specified fields.
        
        Args:
            results: List of result dictionaries from different sources
            join_fields: Mapping of source_id to field name to join on
            type_mappings: Mapping of source_id to field type mappings
            
        Returns:
            Joined result dictionary
        """
        if not join_fields:
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
        primary_join_field = join_fields.get(primary_source_id)
        
        if not primary_join_field:
            logger.warning(f"No join field for primary source {primary_source_id}")
            return self.merge_results(results)
        
        # For each row in the primary source
        for primary_row in primary_data:
            # Skip if join field doesn't exist
            if primary_join_field not in primary_row:
                continue
                
            join_value = primary_row[primary_join_field]
            
            # Create a new row with primary data
            joined_row = {f"{primary_source_id}_{k}": v for k, v in primary_row.items()}
            
            # Add data from other sources
            for source_id, data in source_data.items():
                if source_id == primary_source_id:
                    continue
                    
                join_field = join_fields.get(source_id)
                if not join_field:
                    continue
                
                # Find matching rows
                matches = []
                for row in data:
                    if join_field in row:
                        # Apply type coercion if needed
                        row_value = row[join_field]
                        if type_mappings and source_id in type_mappings:
                            field_type = type_mappings[source_id].get(join_field)
                            primary_type = (type_mappings.get(primary_source_id, {})
                                           .get(primary_join_field))
                            
                            # Convert to common type if possible
                            if field_type and primary_type:
                                if field_type == "str" or primary_type == "str":
                                    # Convert both to string
                                    row_value = str(row_value)
                                    join_value = str(join_value)
                                elif field_type == "int" and primary_type == "int":
                                    # Convert to int
                                    try:
                                        row_value = int(row_value)
                                        join_value = int(join_value)
                                    except:
                                        pass
                        
                        # Compare values (with coercion for common cases)
                        if isinstance(row_value, str) and not isinstance(join_value, str):
                            if str(join_value) == row_value:
                                matches.append(row)
                        elif isinstance(row_value, (int, float)) and isinstance(join_value, (int, float)):
                            if float(row_value) == float(join_value):
                                matches.append(row)
                        elif row_value == join_value:
                            matches.append(row)
                
                # Add first match to joined row
                if matches:
                    for k, v in matches[0].items():
                        joined_row[f"{source_id}_{k}"] = v
            
            # Add the joined row to results
            joined_data.append(joined_row)
        
        return {
            "success": True,
            "sources_joined": len(source_data),
            "join_fields": join_fields,
            "total_rows": len(joined_data),
            "results": joined_data
        }
    
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
            return self.join_results(results, join_fields, type_mappings)
        else:
            return self.merge_results(results) 
"""
Google Analytics 4 (GA4) adapter implementation.
Provides access to GA4 data through the DBAdapter interface.
"""

import logging
import json
import os
from typing import Any, Dict, List, Optional
from pathlib import Path
from datetime import datetime, timedelta

# Google API libraries
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    RunReportRequest,
    DateRange,
    Dimension,
    Metric,
    OrderBy
)
# Import OrderBy types directly
from google.oauth2 import service_account
from google.auth.transport.requests import Request

from .base import DBAdapter

# Configure logging
logger = logging.getLogger(__name__)

class GA4Adapter(DBAdapter):
    """
    Google Analytics 4 adapter implementation.
    
    This adapter provides GA4 support through the DBAdapter interface,
    translating natural language to GA4 API requests.
    """
    
    def __init__(self, conn_uri: str, **kwargs):
        """
        Initialize the GA4 adapter.
        
        Args:
            conn_uri: GA4 connection URI (format: ga4://{property_id})
            **kwargs: Additional parameters
        """
        super().__init__(conn_uri)
        
        # Parse property ID from URI (format: ga4://{property_id})
        self.property_id = self._parse_property_id(conn_uri)
        
        # Import settings to access GA4 configuration
        from ...config.settings import Settings
        settings = Settings()
        
        # Load service account credentials
        self.key_file = settings.GA4_KEY_FILE
        self.scopes = settings.GA4_SCOPES
        self.token_cache_db = settings.GA4_TOKEN_CACHE_DB
        
        # Initialize GA4 client
        self.client = self._initialize_client()
        
        logger.info(f"Initialized GA4 adapter for property ID: {self.property_id}")
    
    def _parse_property_id(self, conn_uri: str) -> str:
        """
        Parse the property ID from the connection URI.
        
        Args:
            conn_uri: Connection URI in format ga4://{property_id}
            
        Returns:
            The GA4 property ID
        """
        try:
            # Import settings to access GA4 configuration if needed
            from ...config.settings import Settings
            settings = Settings()
            
            # Remove the ga4:// prefix
            if conn_uri.startswith("ga4://"):
                property_id = conn_uri[6:]
                logger.info(f"Extracted property ID from URI: {property_id}")
                return property_id
            
            # If not in expected format, log warning and try fallbacks
            logger.warning(f"GA4 URI not in expected format (ga4://property_id): {conn_uri}")
            
            # Fallback 1: Try to extract property ID from the settings
            if hasattr(settings, 'GA4_PROPERTY_ID') and settings.GA4_PROPERTY_ID:
                property_id = str(settings.GA4_PROPERTY_ID)
                logger.info(f"Using property ID from settings: {property_id}")
                return property_id
            
            # Fallback 2: Just return the URI as is (last resort)
            logger.error(f"Unable to determine GA4 property ID, using URI as fallback: {conn_uri}")
            return conn_uri
            
        except Exception as e:
            logger.error(f"Failed to parse GA4 property ID from URI: {e}")
            raise ValueError(f"Invalid GA4 connection URI: {conn_uri}")
    
    def _initialize_client(self) -> BetaAnalyticsDataClient:
        """
        Initialize the GA4 API client with credentials.
        
        Returns:
            BetaAnalyticsDataClient: The initialized GA4 client
        """
        try:
            # Resolve path if it uses ~
            key_file_path = os.path.expanduser(self.key_file)
            
            # Load credentials from service account file
            credentials = service_account.Credentials.from_service_account_file(
                key_file_path,
                scopes=self.scopes
            )
            
            # Create the client
            client = BetaAnalyticsDataClient(credentials=credentials)
            return client
            
        except Exception as e:
            logger.error(f"Failed to initialize GA4 client: {e}")
            raise
    
    async def llm_to_query(self, nl_prompt: str, **kwargs) -> Dict:
        """
        Convert natural language to a GA4 query.
        
        Args:
            nl_prompt: Natural language query
            **kwargs: Additional parameters:
                - schema_chunks: Schema information (optional)
                
        Returns:
            Dict containing GA4 RunReportRequest parameters:
                - date_ranges: List of date ranges
                - dimensions: List of dimensions
                - metrics: List of metrics
                - dimension_filter: Optional dimension filter
                - metric_filter: Optional metric filter
                - order_bys: Optional ordering
                - limit: Optional result limit
        """
        from ...llm.client import get_llm_client
        
        # Get schema metadata if not provided
        schema_chunks = kwargs.get('schema_chunks')
        if not schema_chunks:
            # Import SchemaSearcher only when needed to avoid circular imports
            from ...meta.ingest import SchemaSearcher
            # Search schema metadata
            searcher = SchemaSearcher()
            schema_chunks = await searcher.search(nl_prompt, top_k=5)
        
        # Get LLM client
        llm = get_llm_client()
        
        # Use a GA4-specific prompt template
        prompt = llm.render_template("ga4_query.tpl", 
                                   schema_chunks=schema_chunks, 
                                   user_question=nl_prompt,
                                   property_id=self.property_id)
        
        # Generate GA4 query using the LLM
        raw_response = await llm.generate_ga4_query(prompt)
        
        # Parse the response as JSON
        try:
            # The response should contain GA4 query parameters
            query_data = json.loads(raw_response)
            
            # Validate response structure
            if not isinstance(query_data, dict):
                raise ValueError("LLM response is not a dictionary")
            
            # Validate required fields
            required_fields = ["metrics", "date_ranges"]
            for field in required_fields:
                if field not in query_data:
                    raise ValueError(f"LLM response missing required field: {field}")
            
            # Handle date ranges with relative dates (e.g., "last 7 days")
            query_data = self._process_date_ranges(query_data)
            
            return query_data
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            raise ValueError(f"Failed to parse LLM response as JSON: {e}")
    
    async def _convert_query_format(self, query: Any) -> Dict:
        """
        Convert different query formats to GA4-compatible format.
        Handles string queries from LangGraph by converting them to GA4 report parameters.
        
        Args:
            query: Query in various formats (string, dict)
            
        Returns:
            Dict in GA4 format
        """
        if isinstance(query, dict):
            # Already in proper format, return as-is
            return query
        
        elif isinstance(query, str):
            # Convert string query to GA4 report format
            logger.info(f"📊 GA4 Query Conversion: Converting string query to report parameters")
            
            try:
                # Use the existing llm_to_query method to convert string to GA4 format
                ga4_query = await self.llm_to_query(query)
                
                logger.info(f"📊 GA4 Query Conversion: \"{query}\" → GA4 report with {len(ga4_query.get('metrics', []))} metrics")
                return ga4_query
                
            except Exception as e:
                logger.error(f"Error converting string query to GA4 format: {e}")
                # Fallback to a basic GA4 query
                today = datetime.now().date()
                fallback_query = {
                    "date_ranges": [{
                        "start_date": (today - timedelta(days=7)).isoformat(),
                        "end_date": today.isoformat()
                    }],
                    "metrics": ["activeUsers", "sessions"],
                    "dimensions": ["date"],
                    "limit": 10,
                    "error": f"Fallback query used due to conversion error: {str(e)}",
                    "original_query": query
                }
                return fallback_query
        
        else:
            # Unknown format, try to handle gracefully
            logger.warning(f"Unknown query format: {type(query)}")
            today = datetime.now().date()
            return {
                "date_ranges": [{
                    "start_date": (today - timedelta(days=7)).isoformat(),
                    "end_date": today.isoformat()
                }],
                "metrics": ["activeUsers"],
                "dimensions": ["date"],
                "error": f"Unsupported query format: {type(query)}",
                "original_query": str(query)
            }
    
    def _process_date_ranges(self, query_data: Dict) -> Dict:
        """
        Process date ranges in the query data, converting relative dates to absolute dates.
        
        Args:
            query_data: The query data dict with date_ranges
            
        Returns:
            Updated query data with processed date ranges
        """
        if "date_ranges" not in query_data:
            # Default to last 7 days if not specified
            today = datetime.now().date()
            query_data["date_ranges"] = [{
                "start_date": (today - timedelta(days=7)).isoformat(),
                "end_date": today.isoformat()
            }]
            return query_data
        
        # Process each date range
        for i, date_range in enumerate(query_data["date_ranges"]):
            # Check if we need to process this date range
            if "relative" in date_range:
                relative_range = date_range["relative"].lower()
                today = datetime.now().date()
                
                # Handle common relative date patterns
                if relative_range == "yesterday":
                    yesterday = today - timedelta(days=1)
                    date_range["start_date"] = yesterday.isoformat()
                    date_range["end_date"] = yesterday.isoformat()
                elif relative_range == "last 7 days":
                    date_range["start_date"] = (today - timedelta(days=7)).isoformat()
                    date_range["end_date"] = today.isoformat()
                elif relative_range == "last 30 days":
                    date_range["start_date"] = (today - timedelta(days=30)).isoformat()
                    date_range["end_date"] = today.isoformat()
                elif relative_range == "this month":
                    first_day = today.replace(day=1)
                    date_range["start_date"] = first_day.isoformat()
                    date_range["end_date"] = today.isoformat()
                elif relative_range == "last month":
                    this_month_first = today.replace(day=1)
                    last_month_last = this_month_first - timedelta(days=1)
                    last_month_first = last_month_last.replace(day=1)
                    date_range["start_date"] = last_month_first.isoformat()
                    date_range["end_date"] = last_month_last.isoformat()
                else:
                    # Default to last 7 days for unrecognized patterns
                    logger.warning(f"Unrecognized relative date range: {relative_range}, using last 7 days")
                    date_range["start_date"] = (today - timedelta(days=7)).isoformat()
                    date_range["end_date"] = today.isoformat()
                
                # Remove the relative field
                del date_range["relative"]
                
            # Ensure both start_date and end_date are present
            if "start_date" not in date_range or "end_date" not in date_range:
                raise ValueError(f"Invalid date range at index {i}: must have start_date and end_date")
        
        return query_data
    
    async def execute(self, query: Dict) -> List[Dict]:
        """
        Execute a GA4 query.
        
        Args:
            query: Dict containing GA4 RunReportRequest parameters
                
        Returns:
            List of dictionaries with query results
        """
        # Convert query format if needed (handles string queries from LangGraph)
        query = await self._convert_query_format(query)
        
        if not isinstance(query, dict):
            raise ValueError("Query must be a dictionary with GA4 parameters")
        
        try:
            # Build the GA4 RunReportRequest
            request = self._build_run_report_request(query)
            
            # Execute the request
            response = self.client.run_report(request)
            
            # Convert the response to a list of dictionaries
            results = self._process_report_response(response)
            
            return results
            
        except Exception as e:
            logger.error(f"Error executing GA4 query: {e}")
            raise
    
    def _build_run_report_request(self, query: Dict) -> RunReportRequest:
        """
        Build a GA4 RunReportRequest from the query parameters.
        
        Args:
            query: Dict with query parameters
            
        Returns:
            RunReportRequest object
        """
        # Format property ID for GA4 API (requires 'properties/XXXX' format)
        property_id = f"properties/{self.property_id}"
        
        # Convert date ranges
        date_ranges = []
        for dr in query.get("date_ranges", []):
            date_ranges.append(DateRange(
                start_date=dr.get("start_date"),
                end_date=dr.get("end_date")
            ))
        
        # Convert dimensions
        dimensions = []
        for dim in query.get("dimensions", []):
            dimensions.append(Dimension(name=dim))
        
        # Convert metrics
        metrics = []
        for met in query.get("metrics", []):
            metrics.append(Metric(name=met))
        
        # Build order by clauses if present
        order_bys = []
        for order in query.get("order_bys", []):
            if "dimension" in order:
                desc = order.get("desc", False)
                order_bys.append(OrderBy(
                    dimension=OrderBy.DimensionOrderBy(dimension_name=order["dimension"]),
                    desc=desc
                ))
            elif "metric" in order:
                desc = order.get("desc", False)
                order_bys.append(OrderBy(
                    metric=OrderBy.MetricOrderBy(metric_name=order["metric"]),
                    desc=desc
                ))
        
        # Build the request
        request = RunReportRequest(
            property=property_id,
            dimensions=dimensions,
            metrics=metrics,
            date_ranges=date_ranges,
            order_bys=order_bys
        )
        
        # Add limit if specified
        if "limit" in query:
            request.limit = query["limit"]
        
        # Add dimension and metric filters if present (simplified for now)
        # In a full implementation, we would need to build complex filter expressions
        
        return request
    
    def _process_report_response(self, response) -> List[Dict]:
        """
        Process the GA4 report response into a list of dictionaries.
        
        Args:
            response: GA4 RunReportResponse
            
        Returns:
            List of dictionaries with results
        """
        results = []
        
        # Get dimension and metric headers
        dimension_headers = [header.name for header in response.dimension_headers]
        metric_headers = [header.name for header in response.metric_headers]
        
        # Process each row
        for row in response.rows:
            result = {}
            
            # Add dimensions
            for i, dimension_value in enumerate(row.dimension_values):
                header_name = dimension_headers[i]
                result[header_name] = dimension_value.value
            
            # Add metrics
            for i, metric_value in enumerate(row.metric_values):
                header_name = metric_headers[i]
                result[header_name] = metric_value.value
            
            results.append(result)
        
        return results
            
    async def execute_query(self, query: Dict) -> List[Dict]:
        """
        Execute a GA4 query (alias for execute).
        
        Args:
            query: Dict with GA4 query parameters
                
        Returns:
            List of dictionaries with query results
        """
        return await self.execute(query)
    
    async def introspect_schema(self) -> List[Dict[str, str]]:
        """
        Introspect GA4 metadata (dimensions and metrics) and populate the schema registry.
        
        Returns:
            List of document dictionaries for embedding
        """
        documents = []
        
        try:
            # Format property ID for GA4 API with /metadata suffix
            property_id = f"properties/{self.property_id}/metadata"
            
            # Fetch metadata
            metadata = self.client.get_metadata(name=property_id)
            
            # Import registry functions
            from ...db.registry import (
                upsert_data_source,
                upsert_table_meta
            )
            
            # Register GA4 as a data source
            source_id = f"ga4_{self.property_id}"
            source_uri = f"ga4://{self.property_id}"
            upsert_data_source(source_id, source_uri, "ga4")
            
            # Create schema dictionaries for dimensions and metrics
            dimension_schema = {"fields": {}, "ga4_metadata": {"property_id": self.property_id, "table_type": "dimension"}}
            metric_schema = {"fields": {}, "ga4_metadata": {"property_id": self.property_id, "table_type": "metric"}}
            
            # Process dimensions
            for dimension in metadata.dimensions:
                # Add to dimension schema
                dimension_schema["fields"][dimension.api_name] = {
                    "data_type": "string",
                    "description": dimension.description,
                    "category": dimension.category,
                    "ui_name": dimension.ui_name,
                    "custom_definition": dimension.custom_definition if dimension.custom_definition else None
                }
                
                # Create document content for FAISS
                content = f"""
                DIMENSION: {dimension.api_name}
                DISPLAY NAME: {dimension.ui_name}
                DESCRIPTION: {dimension.description}
                CATEGORY: {dimension.category}
                CUSTOM DEFINITION: {dimension.custom_definition if dimension.custom_definition else "N/A"}
                """
                
                # Add document
                documents.append({
                    "id": f"dimension:{dimension.api_name}",
                    "content": content.strip()
                })
            
            # Process metrics
            for metric in metadata.metrics:
                # Add to metric schema
                metric_schema["fields"][metric.api_name] = {
                    "data_type": "number",
                    "description": metric.description,
                    "category": metric.category,
                    "ui_name": metric.ui_name,
                    "expression": metric.expression if metric.expression else None
                }
                
                # Create document content for FAISS
                content = f"""
                METRIC: {metric.api_name}
                DISPLAY NAME: {metric.ui_name}
                DESCRIPTION: {metric.description}
                CATEGORY: {metric.category}
                EXPRESSION: {metric.expression if metric.expression else "N/A"}
                """
                
                # Add document
                documents.append({
                    "id": f"metric:{metric.api_name}",
                    "content": content.strip()
                })
            
            # Add tables to registry
            upsert_table_meta(source_id, "dimensions", dimension_schema)
            upsert_table_meta(source_id, "metrics", metric_schema)
            
            # Add overview document
            overview = f"""
            GOOGLE ANALYTICS 4
            PROPERTY ID: {self.property_id}
            DIMENSIONS COUNT: {len(metadata.dimensions)}
            METRICS COUNT: {len(metadata.metrics)}
            
            Google Analytics 4 is an event-based analytics system that tracks user interactions as events.
            Key concepts include: users, sessions, events, parameters, dimensions, and metrics.
            """
            
            documents.append({
                "id": "ga4:overview",
                "content": overview.strip()
            })
            
            return documents
            
        except Exception as e:
            logger.error(f"Error during GA4 schema introspection: {e}")
            return [{"id": "error", "content": f"Error during GA4 schema introspection: {str(e)}"}]
    
    async def test_connection(self) -> bool:
        """
        Test the GA4 connection.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Format property ID for GA4 API with /metadata suffix
            property_id = f"properties/{self.property_id}/metadata"
            
            # Try to get property metadata
            self.client.get_metadata(name=property_id)
            
            # If no exception, connection is successful
            return True
            
        except Exception as e:
            logger.error(f"GA4 connection test failed: {e}")
            return False
    
    # Additional GA4-specific tools for the registry
    
    async def analyze_audience_performance(self, dimensions: List[str] = None, date_range_days: int = 30) -> Dict[str, Any]:
        """
        Analyze audience performance across different dimensions.
        
        Args:
            dimensions: GA4 dimensions to analyze (e.g., ['city', 'deviceCategory'])
            date_range_days: Number of days to analyze (default 30)
            
        Returns:
            Audience performance analysis results
        """
        logger.info(f"Analyzing audience performance for {dimensions} over {date_range_days} days")
        
        try:
            # Set default dimensions if none provided
            if not dimensions:
                dimensions = ["city", "deviceCategory", "operatingSystem"]
            
            # Create GA4 query for audience analysis
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=date_range_days)
            
            query = {
                "date_ranges": [{
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat()
                }],
                "dimensions": dimensions,
                "metrics": ["activeUsers", "sessions", "bounceRate", "averageSessionDuration", "screenPageViews"]
            }
            
            # Execute query
            results = await self.execute(query)
            
            # Analyze results
            total_users = sum(int(row.get("activeUsers", 0)) for row in results)
            total_sessions = sum(int(row.get("sessions", 0)) for row in results)
            
            # Group by dimensions
            dimension_analysis = {}
            for dimension in dimensions:
                dimension_values = {}
                for row in results:
                    dim_value = row.get(dimension, "Unknown")
                    if dim_value not in dimension_values:
                        dimension_values[dim_value] = {
                            "activeUsers": 0,
                            "sessions": 0,
                            "screenPageViews": 0,
                            "totalBounceRate": 0,
                            "totalDuration": 0,
                            "count": 0
                        }
                    
                    dimension_values[dim_value]["activeUsers"] += int(row.get("activeUsers", 0))
                    dimension_values[dim_value]["sessions"] += int(row.get("sessions", 0))
                    dimension_values[dim_value]["screenPageViews"] += int(row.get("screenPageViews", 0))
                    dimension_values[dim_value]["totalBounceRate"] += float(row.get("bounceRate", 0))
                    dimension_values[dim_value]["totalDuration"] += float(row.get("averageSessionDuration", 0))
                    dimension_values[dim_value]["count"] += 1
                
                # Calculate averages
                for value_data in dimension_values.values():
                    if value_data["count"] > 0:
                        value_data["avgBounceRate"] = value_data["totalBounceRate"] / value_data["count"]
                        value_data["avgSessionDuration"] = value_data["totalDuration"] / value_data["count"]
                
                dimension_analysis[dimension] = {
                    "values": dimension_values,
                    "top_performers": sorted(
                        dimension_values.items(),
                        key=lambda x: x[1]["activeUsers"],
                        reverse=True
                    )[:10]
                }
            
            analysis_result = {
                "analysis_period_days": date_range_days,
                "total_active_users": total_users,
                "total_sessions": total_sessions,
                "dimensions_analyzed": dimensions,
                "dimension_analysis": dimension_analysis,
                "recommendations": self._generate_audience_recommendations(dimension_analysis),
                "summary": {
                    "avg_users_per_day": total_users / date_range_days if date_range_days > 0 else 0,
                    "avg_sessions_per_day": total_sessions / date_range_days if date_range_days > 0 else 0,
                    "overall_sessions_per_user": total_sessions / total_users if total_users > 0 else 0
                }
            }
            
            logger.info(f"Audience analysis completed: {total_users} users, {total_sessions} sessions")
            return analysis_result
            
        except Exception as e:
            logger.error(f"Failed to analyze audience performance: {e}")
            raise
    
    def _generate_audience_recommendations(self, dimension_analysis: Dict) -> List[str]:
        """Generate recommendations based on audience analysis."""
        recommendations = []
        
        try:
            for dimension, analysis in dimension_analysis.items():
                top_performers = analysis["top_performers"]
                
                if top_performers:
                    top_value = top_performers[0]
                    recommendations.append(f"Top performing {dimension}: {top_value[0]} with {top_value[1]['activeUsers']} users")
                
                # Check for high bounce rates
                high_bounce = [v for k, v in analysis["values"].items() if v.get("avgBounceRate", 0) > 0.7]
                if high_bounce:
                    recommendations.append(f"High bounce rate detected in {dimension} - review content relevance")
                
        except Exception as e:
            logger.warning(f"Failed to generate audience recommendations: {e}")
        
        return recommendations
    
    async def get_property_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive statistics for the GA4 property.
        
        Returns:
            Property statistics and metadata
        """
        logger.info(f"Getting property statistics for GA4 property: {self.property_id}")
        
        try:
            # Get basic property metadata
            property_id = f"properties/{self.property_id}/metadata"
            metadata = self.client.get_metadata(name=property_id)
            
            # Get recent data for analysis
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=30)
            
            basic_query = {
                "date_ranges": [{
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat()
                }],
                "metrics": ["activeUsers", "sessions", "screenPageViews", "bounceRate"],
                "dimensions": ["date"]
            }
            
            recent_data = await self.execute(basic_query)
            
            # Calculate statistics
            total_users = sum(int(row.get("activeUsers", 0)) for row in recent_data)
            total_sessions = sum(int(row.get("sessions", 0)) for row in recent_data)
            total_page_views = sum(int(row.get("screenPageViews", 0)) for row in recent_data)
            
            statistics = {
                "property_id": self.property_id,
                "metadata": {
                    "dimensions_count": len(metadata.dimensions),
                    "metrics_count": len(metadata.metrics),
                    "dimensions": [d.api_name for d in metadata.dimensions[:20]],  # First 20
                    "metrics": [m.api_name for m in metadata.metrics[:20]]  # First 20
                },
                "recent_30_days": {
                    "total_active_users": total_users,
                    "total_sessions": total_sessions,
                    "total_page_views": total_page_views,
                    "avg_users_per_day": total_users / 30,
                    "avg_sessions_per_day": total_sessions / 30,
                    "avg_page_views_per_session": total_page_views / total_sessions if total_sessions > 0 else 0
                },
                "data_quality": {
                    "days_with_data": len([row for row in recent_data if int(row.get("activeUsers", 0)) > 0]),
                    "data_completeness": len(recent_data) / 30  # Should be close to 1.0
                },
                "recommendations": self._generate_property_recommendations(metadata, recent_data)
            }
            
            logger.info(f"Property statistics completed: {total_users} users in last 30 days")
            return statistics
            
        except Exception as e:
            logger.error(f"Failed to get property statistics: {e}")
            raise
    
    def _generate_property_recommendations(self, metadata, recent_data) -> List[str]:
        """Generate recommendations based on property analysis."""
        recommendations = []
        
        try:
            # Check data collection
            days_with_data = len([row for row in recent_data if int(row.get("activeUsers", 0)) > 0])
            if days_with_data < 25:  # Less than 25 days of data in 30 days
                recommendations.append("Inconsistent data collection detected - check tracking implementation")
            
            # Check available metrics and dimensions
            if len(metadata.dimensions) < 50:
                recommendations.append("Limited dimensions available - ensure proper GA4 configuration")
            
            if len(metadata.metrics) < 50:
                recommendations.append("Limited metrics available - verify GA4 setup")
            
            # Check user activity
            total_users = sum(int(row.get("activeUsers", 0)) for row in recent_data)
            if total_users < 100:
                recommendations.append("Low user activity - consider marketing efforts or tracking verification")
            
        except Exception as e:
            logger.warning(f"Failed to generate property recommendations: {e}")
        
        return recommendations 
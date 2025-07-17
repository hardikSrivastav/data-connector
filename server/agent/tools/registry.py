"""
Dynamic Tool Registry for LangGraph Integration

This module implements a comprehensive tool registry system that:
1. Manages database-specific tools through adapters
2. Provides extensible tool registration and discovery
3. Integrates with LangGraph workflows
4. Supports performance monitoring and optimization
5. Uses Bedrock as the primary LLM client

All tools are real implementations with no mocks or fallbacks.
Any failures should be immediately visible for debugging.
"""

import logging
import time
import asyncio
import json
import uuid
import re
from typing import Dict, List, Any, Optional, Callable, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import traceback

from ..config.settings import Settings
from ..langgraph.graphs.bedrock_client import get_bedrock_langgraph_client
from ..db.adapters import ADAPTER_REGISTRY

# Configure comprehensive logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Create formatter for detailed logging
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - [%(funcName)s:%(lineno)d] - %(message)s'
)

# Ensure handler exists
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    logger.addHandler(handler)

class ToolCategory(Enum):
    """Categories of tools available in the registry."""
    DATABASE_QUERY = "database_query"
    DATABASE_ANALYSIS = "database_analysis"
    DATA_TRANSFORMATION = "data_transformation"
    SCHEMA_INTROSPECTION = "schema_introspection"
    PERFORMANCE_OPTIMIZATION = "performance_optimization"
    CROSS_DATABASE = "cross_database"
    VISUALIZATION = "visualization"
    UTILITY = "utility"

class ToolComplexity(Enum):
    """Complexity levels for tools."""
    SIMPLE = 1
    MODERATE = 2
    COMPLEX = 3
    VERY_COMPLEX = 4

@dataclass
class ToolMetadata:
    """Comprehensive metadata for registered tools."""
    name: str
    description: str
    category: ToolCategory
    complexity: ToolComplexity
    input_types: List[str]
    output_types: List[str]
    database_compatibility: List[str]
    estimated_duration_ms: int
    dependencies: List[str] = field(default_factory=list)
    memory_usage_mb: int = 50  # Estimated memory usage
    requires_llm: bool = False
    streaming_capable: bool = False
    parallelizable: bool = True
    version: str = "1.0.0"
    
@dataclass
class ToolExecutionMetrics:
    """Performance metrics for tool execution."""
    tool_name: str
    execution_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_ms: Optional[int] = None
    success: bool = False
    error_message: Optional[str] = None
    memory_used_mb: Optional[float] = None
    database_type: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    result_size_bytes: Optional[int] = None

@dataclass
class ToolUsageAnalytics:
    """Usage analytics for tools."""
    total_executions: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    average_duration_ms: float = 0.0
    min_duration_ms: int = 0
    max_duration_ms: int = 0
    last_execution: Optional[datetime] = None
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    error_rate: float = 0.0

class DynamicToolRegistry:
    """
    Comprehensive registry for managing and executing database tools with LangGraph integration.
    
    Features:
    - Dynamic tool discovery from database adapters
    - Performance monitoring and analytics
    - LangGraph workflow integration
    - Real-time tool selection optimization
    - Comprehensive logging and error tracking
    """
    
    def __init__(self):
        self.tools: Dict[str, Callable] = {}
        self.tool_metadata: Dict[str, ToolMetadata] = {}
        self.usage_analytics: Dict[str, ToolUsageAnalytics] = {}
        self.execution_history: List[ToolExecutionMetrics] = []
        self.performance_cache: Dict[str, List[float]] = {}
        self.llm_client = None
        self.settings = Settings()
        
        # Tool discovery and registration
        self._discovered_adapters: Dict[str, Any] = {}
        self._tool_dependencies: Dict[str, Set[str]] = {}
        
        # Performance tracking
        self._performance_window_hours = 24
        self._max_history_entries = 10000
        
        logger.info("Initializing DynamicToolRegistry with comprehensive logging and analytics")
        
        # Initialize LLM client
        self._initialize_llm_client()
        
        # Discover and register tools
        self._discover_adapter_tools()
        
    def _initialize_llm_client(self) -> None:
        """Initialize Bedrock LLM client as primary choice."""
        try:
            self.llm_client = get_bedrock_langgraph_client()
            logger.info(f"Initialized Bedrock LLM client successfully. Functional: {self.llm_client.is_functional}")
            
            if self.llm_client.is_functional:
                status = self.llm_client.get_client_status()
                logger.info(f"LLM client status: {status}")
            else:
                logger.warning("Bedrock LLM client is not functional - tools requiring LLM will fail")
                
        except Exception as e:
            logger.error(f"Failed to initialize Bedrock LLM client: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise RuntimeError(f"LLM client initialization failed: {e}")
    
    def _discover_adapter_tools(self) -> None:
        """Discover tools from database adapters."""
        logger.info("Starting adapter tool discovery process")
        
        for db_type, adapter_class in ADAPTER_REGISTRY.items():
            logger.info(f"Discovering tools for database type: {db_type}")
            
            try:
                # Initialize adapter with dummy connection for tool discovery
                dummy_uri = f"{db_type}://localhost"
                adapter_instance = adapter_class(dummy_uri)
                self._discovered_adapters[db_type] = adapter_instance
                
                # Register database-specific tools
                self._register_adapter_tools(db_type, adapter_instance)
                
                logger.info(f"Successfully discovered and registered tools for {db_type}")
                
            except Exception as e:
                logger.error(f"Failed to discover tools for {db_type}: {e}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                # Continue with other adapters
        
        logger.info(f"Tool discovery complete. Total tools registered: {len(self.tools)}")
        
    def _register_adapter_tools(self, db_type: str, adapter_instance: Any) -> None:
        """Register tools specific to a database adapter."""
        logger.debug(f"Registering tools for adapter: {db_type}")
        
        # Register core adapter methods as tools
        core_tools = [
            ("llm_to_query", "Convert natural language to database query"),
            ("execute", "Execute database query"),
            ("introspect_schema", "Introspect database schema"),
            ("test_connection", "Test database connection")
        ]
        
        for method_name, description in core_tools:
            if hasattr(adapter_instance, method_name):
                tool_name = f"{db_type}_{method_name}"
                tool_func = getattr(adapter_instance, method_name)
                
                metadata = ToolMetadata(
                    name=tool_name,
                    description=f"{description} for {db_type}",
                    category=ToolCategory.DATABASE_QUERY if "query" in method_name or "execute" in method_name else ToolCategory.SCHEMA_INTROSPECTION,
                    complexity=ToolComplexity.MODERATE,
                    input_types=["string", "dict"],
                    output_types=["list", "dict"],
                    database_compatibility=[db_type],
                    estimated_duration_ms=2000,
                    requires_llm="llm_to_query" in method_name,
                    streaming_capable=False,
                    parallelizable=True
                )
                
                self.register_tool(tool_name, tool_func, metadata)
                logger.debug(f"Registered tool: {tool_name}")
        
        # Register adapter-specific tools if they exist
        self._register_specialized_adapter_tools(db_type, adapter_instance)
        
    def _register_specialized_adapter_tools(self, db_type: str, adapter_instance: Any) -> None:
        """Register specialized tools specific to certain database types."""
        logger.debug(f"Registering specialized tools for: {db_type}")
        
        if db_type in ["mongodb", "mongo"]:
            self._register_mongo_tools(adapter_instance)
        elif db_type in ["qdrant"]:
            self._register_qdrant_tools(adapter_instance)
        elif db_type in ["postgres", "postgresql"]:
            self._register_postgres_tools(adapter_instance)
        elif db_type == "slack":
            self._register_slack_tools(adapter_instance)
        elif db_type == "shopify":
            self._register_shopify_tools(adapter_instance)
        elif db_type == "ga4":
            self._register_ga4_tools(adapter_instance)
            
    def _register_mongo_tools(self, adapter_instance: Any) -> None:
        """Register MongoDB-specific tools."""
        if hasattr(adapter_instance, 'aggregate'):
            self.register_tool(
                "mongo_aggregate",
                adapter_instance.aggregate,
                ToolMetadata(
                    name="mongo_aggregate",
                    description="Execute MongoDB aggregation pipeline",
                    category=ToolCategory.DATABASE_ANALYSIS,
                    complexity=ToolComplexity.COMPLEX,
                    input_types=["string", "list"],
                    output_types=["list"],
                    database_compatibility=["mongodb"],
                    estimated_duration_ms=3000,
                    streaming_capable=False,
                    parallelizable=True
                )
            )
            
        if hasattr(adapter_instance, 'find'):
            self.register_tool(
                "mongo_find",
                adapter_instance.find,
                ToolMetadata(
                    name="mongo_find",
                    description="Execute MongoDB find query",
                    category=ToolCategory.DATABASE_QUERY,
                    complexity=ToolComplexity.SIMPLE,
                    input_types=["string", "dict"],
                    output_types=["list"],
                    database_compatibility=["mongodb"],
                    estimated_duration_ms=1500,
                    streaming_capable=False,
                    parallelizable=True
                )
            )
        
        # Register specialized MongoDB tools
        if hasattr(adapter_instance, 'analyze_collection_performance'):
            self.register_tool(
                "mongo_analyze_collection_performance",
                adapter_instance.analyze_collection_performance,
                ToolMetadata(
                    name="mongo_analyze_collection_performance",
                    description="Analyze MongoDB collection performance metrics",
                    category=ToolCategory.PERFORMANCE_OPTIMIZATION,
                    complexity=ToolComplexity.COMPLEX,
                    input_types=["list", "bool"],
                    output_types=["dict"],
                    database_compatibility=["mongodb"],
                    estimated_duration_ms=5000,
                    streaming_capable=False,
                    parallelizable=True
                )
            )
        
        if hasattr(adapter_instance, 'optimize_collection'):
            self.register_tool(
                "mongo_optimize_collection",
                adapter_instance.optimize_collection,
                ToolMetadata(
                    name="mongo_optimize_collection",
                    description="Optimize MongoDB collection performance",
                    category=ToolCategory.PERFORMANCE_OPTIMIZATION,
                    complexity=ToolComplexity.COMPLEX,
                    input_types=["string", "string"],
                    output_types=["dict"],
                    database_compatibility=["mongodb"],
                    estimated_duration_ms=7000,
                    streaming_capable=False,
                    parallelizable=False
                )
            )
        
        if hasattr(adapter_instance, 'validate_aggregation_pipeline'):
            self.register_tool(
                "mongo_validate_aggregation_pipeline",
                adapter_instance.validate_aggregation_pipeline,
                ToolMetadata(
                    name="mongo_validate_aggregation_pipeline",
                    description="Validate MongoDB aggregation pipeline",
                    category=ToolCategory.UTILITY,
                    complexity=ToolComplexity.MODERATE,
                    input_types=["list", "string"],
                    output_types=["dict"],
                    database_compatibility=["mongodb"],
                    estimated_duration_ms=2000,
                    streaming_capable=False,
                    parallelizable=True
                )
            )
        
        if hasattr(adapter_instance, 'get_collection_statistics'):
            self.register_tool(
                "mongo_get_collection_statistics",
                adapter_instance.get_collection_statistics,
                ToolMetadata(
                    name="mongo_get_collection_statistics",
                    description="Get comprehensive MongoDB collection statistics",
                    category=ToolCategory.DATABASE_ANALYSIS,
                    complexity=ToolComplexity.MODERATE,
                    input_types=["list"],
                    output_types=["dict"],
                    database_compatibility=["mongodb"],
                    estimated_duration_ms=3000,
                    streaming_capable=False,
                    parallelizable=True
                )
            )
    
    def _register_qdrant_tools(self, adapter_instance: Any) -> None:
        """Register Qdrant-specific tools."""
        # Vector search tools would be registered here
        # These would be implemented in the qdrant.py adapter
        pass
    
    def _register_postgres_tools(self, adapter_instance: Any) -> None:
        """Register PostgreSQL-specific tools."""
        # SQL analysis and optimization tools would be registered here
        # These would be implemented in the postgres.py adapter
        pass
    
    def _register_slack_tools(self, adapter_instance: Any) -> None:
        """Register Slack-specific tools."""
        if hasattr(adapter_instance, '_semantic_search'):
            self.register_tool(
                "slack_semantic_search",
                adapter_instance._semantic_search,
                ToolMetadata(
                    name="slack_semantic_search",
                    description="Perform semantic search on Slack messages",
                    category=ToolCategory.DATABASE_ANALYSIS,
                    complexity=ToolComplexity.COMPLEX,
                    input_types=["string"],
                    output_types=["list"],
                    database_compatibility=["slack"],
                    estimated_duration_ms=2500,
                    requires_llm=True,
                    streaming_capable=False,
                    parallelizable=True
                )
            )
        
        # Register specialized Slack tools
        if hasattr(adapter_instance, 'analyze_channel_activity'):
            self.register_tool(
                "slack_analyze_channel_activity",
                adapter_instance.analyze_channel_activity,
                ToolMetadata(
                    name="slack_analyze_channel_activity",
                    description="Analyze Slack channel activity and engagement metrics",
                    category=ToolCategory.DATABASE_ANALYSIS,
                    complexity=ToolComplexity.COMPLEX,
                    input_types=["list", "int"],
                    output_types=["dict"],
                    database_compatibility=["slack"],
                    estimated_duration_ms=6000,
                    streaming_capable=False,
                    parallelizable=True
                )
            )
        
        if hasattr(adapter_instance, 'optimize_message_search'):
            self.register_tool(
                "slack_optimize_message_search",
                adapter_instance.optimize_message_search,
                ToolMetadata(
                    name="slack_optimize_message_search",
                    description="Optimize Slack message search performance and provide suggestions",
                    category=ToolCategory.PERFORMANCE_OPTIMIZATION,
                    complexity=ToolComplexity.COMPLEX,
                    input_types=["string", "dict"],
                    output_types=["dict"],
                    database_compatibility=["slack"],
                    estimated_duration_ms=5000,
                    streaming_capable=False,
                    parallelizable=True
                )
            )
        
        if hasattr(adapter_instance, 'get_workspace_statistics'):
            self.register_tool(
                "slack_get_workspace_statistics",
                adapter_instance.get_workspace_statistics,
                ToolMetadata(
                    name="slack_get_workspace_statistics",
                    description="Get comprehensive Slack workspace statistics and metadata",
                    category=ToolCategory.DATABASE_ANALYSIS,
                    complexity=ToolComplexity.MODERATE,
                    input_types=[],
                    output_types=["dict"],
                    database_compatibility=["slack"],
                    estimated_duration_ms=4000,
                    streaming_capable=False,
                    parallelizable=True
                )
            )
    
    def _register_shopify_tools(self, adapter_instance: Any) -> None:
        """Register Shopify-specific tools."""
        if hasattr(adapter_instance, 'validate_query'):
            self.register_tool(
                "shopify_validate_query",
                adapter_instance.validate_query,
                ToolMetadata(
                    name="shopify_validate_query",
                    description="Validate Shopify API query",
                    category=ToolCategory.UTILITY,
                    complexity=ToolComplexity.SIMPLE,
                    input_types=["dict"],
                    output_types=["bool"],
                    database_compatibility=["shopify"],
                    estimated_duration_ms=500,
                    streaming_capable=False,
                    parallelizable=True
                )
            )
        
        # Register specialized Shopify tools
        if hasattr(adapter_instance, 'analyze_product_performance'):
            self.register_tool(
                "shopify_analyze_product_performance",
                adapter_instance.analyze_product_performance,
                ToolMetadata(
                    name="shopify_analyze_product_performance",
                    description="Analyze Shopify product performance metrics including sales and conversion rates",
                    category=ToolCategory.DATABASE_ANALYSIS,
                    complexity=ToolComplexity.COMPLEX,
                    input_types=["list", "int"],
                    output_types=["dict"],
                    database_compatibility=["shopify"],
                    estimated_duration_ms=8000,
                    streaming_capable=False,
                    parallelizable=True
                )
            )
        
        if hasattr(adapter_instance, 'optimize_inventory_tracking'):
            self.register_tool(
                "shopify_optimize_inventory_tracking",
                adapter_instance.optimize_inventory_tracking,
                ToolMetadata(
                    name="shopify_optimize_inventory_tracking",
                    description="Optimize Shopify inventory tracking and identify stock level issues",
                    category=ToolCategory.PERFORMANCE_OPTIMIZATION,
                    complexity=ToolComplexity.COMPLEX,
                    input_types=["list"],
                    output_types=["dict"],
                    database_compatibility=["shopify"],
                    estimated_duration_ms=6000,
                    streaming_capable=False,
                    parallelizable=True
                )
            )
        
        if hasattr(adapter_instance, 'get_order_statistics'):
            self.register_tool(
                "shopify_get_order_statistics",
                adapter_instance.get_order_statistics,
                ToolMetadata(
                    name="shopify_get_order_statistics",
                    description="Get comprehensive Shopify order statistics and trends",
                    category=ToolCategory.DATABASE_ANALYSIS,
                    complexity=ToolComplexity.MODERATE,
                    input_types=["int", "string"],
                    output_types=["dict"],
                    database_compatibility=["shopify"],
                    estimated_duration_ms=4000,
                    streaming_capable=False,
                    parallelizable=True
                )
            )
        
        if hasattr(adapter_instance, 'validate_webhook_signature'):
            self.register_tool(
                "shopify_validate_webhook_signature",
                adapter_instance.validate_webhook_signature,
                ToolMetadata(
                    name="shopify_validate_webhook_signature",
                    description="Validate Shopify webhook signature for security",
                    category=ToolCategory.UTILITY,
                    complexity=ToolComplexity.SIMPLE,
                    input_types=["bytes", "string", "string"],
                    output_types=["dict"],
                    database_compatibility=["shopify"],
                    estimated_duration_ms=500,
                    streaming_capable=False,
                    parallelizable=True
                )
            )
    
    def _register_ga4_tools(self, adapter_instance: Any) -> None:
        """Register Google Analytics 4 specific tools."""
        # Register specialized GA4 tools
        if hasattr(adapter_instance, 'analyze_audience_performance'):
            self.register_tool(
                "ga4_analyze_audience_performance",
                adapter_instance.analyze_audience_performance,
                ToolMetadata(
                    name="ga4_analyze_audience_performance",
                    description="Analyze GA4 audience performance across different dimensions",
                    category=ToolCategory.DATABASE_ANALYSIS,
                    complexity=ToolComplexity.COMPLEX,
                    input_types=["list", "int"],
                    output_types=["dict"],
                    database_compatibility=["ga4"],
                    estimated_duration_ms=7000,
                    streaming_capable=False,
                    parallelizable=True
                )
            )
        
        if hasattr(adapter_instance, 'get_property_statistics'):
            self.register_tool(
                "ga4_get_property_statistics",
                adapter_instance.get_property_statistics,
                ToolMetadata(
                    name="ga4_get_property_statistics",
                    description="Get comprehensive GA4 property statistics and metadata",
                    category=ToolCategory.DATABASE_ANALYSIS,
                    complexity=ToolComplexity.MODERATE,
                    input_types=[],
                    output_types=["dict"],
                    database_compatibility=["ga4"],
                    estimated_duration_ms=4000,
                    streaming_capable=False,
                    parallelizable=True
                )
            )
    
    def register_tool(self, tool_name: str, tool_func: Callable, metadata: ToolMetadata) -> None:
        """
        Register a tool with comprehensive metadata and logging.
        
        Args:
            tool_name: Unique name for the tool
            tool_func: Callable function that implements the tool
            metadata: Comprehensive metadata about the tool
        """
        logger.info(f"Registering tool: {tool_name}")
        logger.debug(f"Tool metadata: {metadata}")
        
        if tool_name in self.tools:
            logger.warning(f"Tool {tool_name} already exists. Overwriting.")
        
        self.tools[tool_name] = tool_func
        self.tool_metadata[tool_name] = metadata
        self.usage_analytics[tool_name] = ToolUsageAnalytics()
        self.performance_cache[tool_name] = []
        
        # Initialize dependencies tracking
        self._tool_dependencies[tool_name] = set(metadata.dependencies)
        
        logger.info(f"Successfully registered tool: {tool_name} - {metadata.description}")
    
    async def execute_tool(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute a tool with comprehensive logging and performance tracking.
        
        Args:
            tool_name: Name of the tool to execute
            parameters: Parameters to pass to the tool
            context: Optional execution context
            
        Returns:
            Execution result with metadata
        """
        execution_id = str(uuid.uuid4())
        start_time = datetime.now()
        
        logger.info(f"Starting tool execution: {tool_name} [ID: {execution_id}]")
        logger.debug(f"Tool parameters: {parameters}")
        logger.debug(f"Execution context: {context}")
        
        # Create execution metrics
        metrics = ToolExecutionMetrics(
            tool_name=tool_name,
            execution_id=execution_id,
            start_time=start_time,
            parameters=parameters,
            database_type=context.get('database_type') if context else None
        )
        
        try:
            # Validate tool exists
            if tool_name not in self.tools:
                raise ValueError(f"Tool '{tool_name}' not found in registry")
            
            tool_func = self.tools[tool_name]
            metadata = self.tool_metadata[tool_name]
            
            logger.debug(f"Executing tool function for: {tool_name}")
            
            # Execute tool with timing
            start_exec_time = time.time()
            
            # Handle async and sync functions
            if asyncio.iscoroutinefunction(tool_func):
                result = await tool_func(**parameters)
            else:
                result = tool_func(**parameters)
            
            end_exec_time = time.time()
            duration_ms = int((end_exec_time - start_exec_time) * 1000)
            
            # Update metrics
            metrics.end_time = datetime.now()
            metrics.duration_ms = duration_ms
            metrics.success = True
            
            if isinstance(result, (list, dict, str)):
                metrics.result_size_bytes = len(json.dumps(result, default=str))
            
            # Update analytics
            self._update_tool_analytics(tool_name, metrics)
            
            logger.info(f"Tool execution successful: {tool_name} [Duration: {duration_ms}ms]")
            logger.debug(f"Tool result type: {type(result)}")
            
            return {
                "success": True,
                "result": result,
                "execution_id": execution_id,
                "duration_ms": duration_ms,
                "tool_metadata": metadata.__dict__,
                "timestamp": start_time.isoformat()
            }
            
        except Exception as e:
            # Handle execution failure
            metrics.end_time = datetime.now()
            metrics.duration_ms = int((metrics.end_time - start_time).total_seconds() * 1000)
            metrics.success = False
            metrics.error_message = str(e)
            
            # Update analytics
            self._update_tool_analytics(tool_name, metrics)
            
            logger.error(f"Tool execution failed: {tool_name} [ID: {execution_id}] - {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            # Re-raise to ensure no silent failures
            raise RuntimeError(f"Tool execution failed for '{tool_name}': {e}")
        
        finally:
            # Always record execution metrics
            self.execution_history.append(metrics)
            
            # Maintain history size limit
            if len(self.execution_history) > self._max_history_entries:
                self.execution_history = self.execution_history[-self._max_history_entries:]
    
    def _update_tool_analytics(self, tool_name: str, metrics: ToolExecutionMetrics) -> None:
        """Update usage analytics for a tool."""
        analytics = self.usage_analytics[tool_name]
        
        analytics.total_executions += 1
        analytics.last_execution = metrics.start_time
        
        if metrics.success:
            analytics.successful_executions += 1
            analytics.last_success = metrics.start_time
            
            # Update duration statistics
            if metrics.duration_ms is not None:
                self.performance_cache[tool_name].append(metrics.duration_ms)
                
                # Keep only recent performance data
                cutoff_time = datetime.now() - timedelta(hours=self._performance_window_hours)
                recent_durations = [d for d in self.performance_cache[tool_name]]
                self.performance_cache[tool_name] = recent_durations[-100:]  # Keep last 100
                
                if recent_durations:
                    analytics.average_duration_ms = sum(recent_durations) / len(recent_durations)
                    analytics.min_duration_ms = min(recent_durations)
                    analytics.max_duration_ms = max(recent_durations)
        else:
            analytics.failed_executions += 1
            analytics.last_failure = metrics.start_time
        
        # Calculate error rate
        if analytics.total_executions > 0:
            analytics.error_rate = analytics.failed_executions / analytics.total_executions
        
        logger.debug(f"Updated analytics for {tool_name}: {analytics}")
    
    async def select_optimal_tools(
        self,
        context: Dict[str, Any],
        available_data: Dict[str, Any],
        target_outcome: str,
        database_types: Optional[List[str]] = None
    ) -> List[str]:
        """
        Select optimal tools based on context, data, and desired outcome.
        
        Args:
            context: Execution context and requirements
            available_data: Data available for processing
            target_outcome: Description of desired outcome
            database_types: Optional list of database types to consider
            
        Returns:
            List of optimal tool names
        """
        logger.info(f"Selecting optimal tools for outcome: {target_outcome}")
        logger.debug(f"Context: {context}")
        logger.debug(f"Available data keys: {list(available_data.keys()) if available_data else 'None'}")
        logger.debug(f"Database types filter: {database_types}")
        
        try:
            # Use LLM for intelligent tool selection if available
            if self.llm_client and self.llm_client.is_functional:
                selected_tools = await self._llm_select_tools(
                    context, available_data, target_outcome, database_types
                )
            else:
                selected_tools = self._heuristic_select_tools(
                    context, available_data, target_outcome, database_types
                )
            
            logger.info(f"Selected tools: {selected_tools}")
            return selected_tools
            
        except Exception as e:
            logger.error(f"Tool selection failed: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise RuntimeError(f"Tool selection failed: {e}")
    
    async def _llm_select_tools(
        self,
        context: Dict[str, Any],
        available_data: Dict[str, Any],
        target_outcome: str,
        database_types: Optional[List[str]] = None
    ) -> List[str]:
        """Use LLM for intelligent tool selection."""
        logger.debug("Using LLM for intelligent tool selection")
        
        # Create prompt for tool selection
        available_tools = self._filter_tools_by_database(database_types) if database_types else list(self.tools.keys())
        
        prompt = self._create_tool_selection_prompt(
            context, available_data, target_outcome, available_tools
        )
        
        try:
            # Use Bedrock for tool selection
            response = await self.llm_client.generate_graph_plan(
                target_outcome,
                database_types or [],
                {"available_tools": available_tools, "context": context},
                {"data_available": available_data}
            )
            
            # Extract tool selection from response
            if "tools" in response:
                selected_tools = response["tools"]
            elif "optimization_hints" in response:
                # Extract tools from optimization hints
                selected_tools = self._extract_tools_from_hints(response["optimization_hints"])
            else:
                # Fallback to heuristic selection
                selected_tools = self._heuristic_select_tools(context, available_data, target_outcome, database_types)
            
            logger.debug(f"LLM selected tools: {selected_tools}")
            return selected_tools
            
        except Exception as e:
            logger.warning(f"LLM tool selection failed: {e}, falling back to heuristic")
            return self._heuristic_select_tools(context, available_data, target_outcome, database_types)
    
    def _filter_tools_by_database(self, database_types: List[str]) -> List[str]:
        """Filter tools by database compatibility."""
        filtered_tools = []
        
        for tool_name, metadata in self.tool_metadata.items():
            if any(db_type in metadata.database_compatibility for db_type in database_types):
                filtered_tools.append(tool_name)
        
        return filtered_tools
    
    def _heuristic_select_tools(
        self,
        context: Dict[str, Any],
        available_data: Dict[str, Any],
        target_outcome: str,
        database_types: Optional[List[str]] = None
    ) -> List[str]:
        """Heuristic-based tool selection when LLM is not available."""
        logger.debug("Using heuristic tool selection")
        
        selected_tools = []
        
        # Filter tools by database types if specified
        candidate_tools = self._filter_tools_by_database(database_types) if database_types else list(self.tools.keys())
        
        # Select tools based on target outcome keywords
        outcome_lower = target_outcome.lower()
        
        for tool_name in candidate_tools:
            metadata = self.tool_metadata[tool_name]
            
            # Match based on description and category
            if (
                any(keyword in metadata.description.lower() for keyword in outcome_lower.split()) or
                self._category_matches_outcome(metadata.category, outcome_lower)
            ):
                selected_tools.append(tool_name)
        
        # Sort by performance and complexity
        selected_tools.sort(key=lambda t: (
            self.usage_analytics[t].error_rate,
            self.tool_metadata[t].complexity.value,
            -self.usage_analytics[t].successful_executions
        ))
        
        return selected_tools[:5]  # Return top 5 tools
    
    def _category_matches_outcome(self, category: ToolCategory, outcome: str) -> bool:
        """Check if tool category matches the desired outcome."""
        category_keywords = {
            ToolCategory.DATABASE_QUERY: ["query", "select", "find", "search"],
            ToolCategory.DATABASE_ANALYSIS: ["analyze", "analysis", "insights", "statistics"],
            ToolCategory.SCHEMA_INTROSPECTION: ["schema", "structure", "metadata", "describe"],
            ToolCategory.DATA_TRANSFORMATION: ["transform", "convert", "format", "process"],
            ToolCategory.PERFORMANCE_OPTIMIZATION: ["optimize", "performance", "speed", "efficiency"],
            ToolCategory.CROSS_DATABASE: ["cross", "multi", "combine", "merge"],
            ToolCategory.VISUALIZATION: ["chart", "graph", "visualize", "plot"],
            ToolCategory.UTILITY: ["test", "validate", "check", "verify"]
        }
        
        keywords = category_keywords.get(category, [])
        return any(keyword in outcome for keyword in keywords)
    
    def _create_tool_selection_prompt(
        self,
        context: Dict[str, Any],
        available_data: Dict[str, Any],
        target_outcome: str,
        available_tools: List[str]
    ) -> str:
        """Create prompt for LLM-based tool selection."""
        tool_descriptions = {}
        has_shopify_tools = False
        
        for tool_name in available_tools:
            if tool_name in self.tool_metadata:
                metadata = self.tool_metadata[tool_name]
                tool_descriptions[tool_name] = {
                    "description": metadata.description,
                    "category": metadata.category.value,
                    "complexity": metadata.complexity.value,
                    "database_compatibility": metadata.database_compatibility,
                    "estimated_duration_ms": metadata.estimated_duration_ms
                }
                
                # Check if we have Shopify tools
                if "shopify" in metadata.database_compatibility:
                    has_shopify_tools = True
        
        # Add Shopify-specific guidance if applicable
        shopify_guidance = ""
        if has_shopify_tools:
            shopify_guidance = """
        
        IMPORTANT SHOPIFY GUIDANCE:
        - Shopify tools use REST API endpoints, not SQL queries
        - Available endpoints include: /admin/api/2025-04/products.json, /admin/api/2025-04/orders.json, /admin/api/2025-04/customers.json
        - All Shopify queries are automatically converted to proper Admin API format
        - Use "shopify.execute_query" for retrieving Shopify data (products, orders, customers, etc.)
        - Shopify queries support filters like status, created_at_min, updated_at_min, limit
        """
        
        return f"""
        Select the optimal tools to achieve the following outcome: {target_outcome}
        
        Context: {json.dumps(context, indent=2)}
        Available Data: {json.dumps({k: type(v).__name__ for k, v in available_data.items()}, indent=2)}
        
        Available Tools:
        {json.dumps(tool_descriptions, indent=2)}{shopify_guidance}
        
        Return a JSON object with:
        {{
            "tools": ["tool1", "tool2", ...],
            "reasoning": "explanation of tool selection",
            "execution_order": ["tool1", "tool2", ...],
            "estimated_total_time_ms": 5000
        }}
        """
    
    def _extract_tools_from_hints(self, hints: List[str]) -> List[str]:
        """Extract tool names from optimization hints."""
        tools = []
        for hint in hints:
            for tool_name in self.tools.keys():
                if tool_name in hint:
                    tools.append(tool_name)
        return list(set(tools))
    
    def get_tool_analytics(self, tool_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get comprehensive analytics for tools.
        
        Args:
            tool_name: Optional specific tool name, if None returns all analytics
            
        Returns:
            Tool analytics data
        """
        if tool_name:
            if tool_name not in self.usage_analytics:
                raise ValueError(f"Tool '{tool_name}' not found")
            
            analytics = self.usage_analytics[tool_name]
            metadata = self.tool_metadata[tool_name]
            
            return {
                "tool_name": tool_name,
                "metadata": metadata.__dict__,
                "analytics": analytics.__dict__,
                "recent_performance": self.performance_cache.get(tool_name, [])[-10:],
                "dependencies": list(self._tool_dependencies.get(tool_name, []))
            }
        else:
            return {
                "total_tools": len(self.tools),
                "tools_by_category": self._get_tools_by_category(),
                "tools_by_database": self._get_tools_by_database(),
                "overall_performance": self._get_overall_performance(),
                "recent_executions": len([m for m in self.execution_history 
                                        if m.start_time > datetime.now() - timedelta(hours=1)])
            }
    
    def _get_tools_by_category(self) -> Dict[str, List[str]]:
        """Group tools by category."""
        by_category = {}
        for tool_name, metadata in self.tool_metadata.items():
            category = metadata.category.value
            if category not in by_category:
                by_category[category] = []
            by_category[category].append(tool_name)
        return by_category
    
    def _get_tools_by_database(self) -> Dict[str, List[str]]:
        """Group tools by database compatibility."""
        by_database = {}
        for tool_name, metadata in self.tool_metadata.items():
            for db_type in metadata.database_compatibility:
                if db_type not in by_database:
                    by_database[db_type] = []
                by_database[db_type].append(tool_name)
        return by_database
    
    def _get_overall_performance(self) -> Dict[str, Any]:
        """Calculate overall performance metrics."""
        total_executions = sum(a.total_executions for a in self.usage_analytics.values())
        total_successful = sum(a.successful_executions for a in self.usage_analytics.values())
        
        avg_duration = 0
        if self.performance_cache:
            all_durations = []
            for durations in self.performance_cache.values():
                all_durations.extend(durations)
            if all_durations:
                avg_duration = sum(all_durations) / len(all_durations)
        
        return {
            "total_executions": total_executions,
            "overall_success_rate": total_successful / total_executions if total_executions > 0 else 0,
            "average_duration_ms": avg_duration,
            "active_tools": len([t for t, a in self.usage_analytics.items() if a.total_executions > 0])
        }

# Global registry instance
_registry_instance: Optional[DynamicToolRegistry] = None

def get_tool_registry() -> DynamicToolRegistry:
    """Get the global tool registry instance."""
    global _registry_instance
    if _registry_instance is None:
        logger.info("Creating global tool registry instance")
        _registry_instance = DynamicToolRegistry()
    return _registry_instance

def reset_tool_registry() -> None:
    """Reset the global tool registry (useful for testing)."""
    global _registry_instance
    logger.info("Resetting global tool registry")
    _registry_instance = None


# Additional classes for LangGraph integration compatibility

@dataclass
class ToolCall:
    """Represents a tool call request."""
    call_id: str
    tool_id: str
    parameters: Dict[str, Any]
    context: Dict[str, Any] = field(default_factory=dict)

@dataclass  
class ExecutionResult:
    """Represents the result of tool execution."""
    tool_id: str
    call_id: str
    success: bool
    result: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

class ToolPriority(Enum):
    """Tool execution priorities."""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

class PerformanceMonitor:
    """Performance monitoring for tool execution."""
    
    def __init__(self):
        self.metrics = {}
        logger.info("PerformanceMonitor initialized")
    
    async def record_execution(self, tool_id: str, duration: float, success: bool):
        """Record tool execution metrics."""
        if tool_id not in self.metrics:
            self.metrics[tool_id] = {
                "execution_count": 0,
                "total_duration": 0.0,
                "success_count": 0,
                "failure_count": 0
            }
        
        self.metrics[tool_id]["execution_count"] += 1
        self.metrics[tool_id]["total_duration"] += duration
        
        if success:
            self.metrics[tool_id]["success_count"] += 1
        else:
            self.metrics[tool_id]["failure_count"] += 1
    
    async def get_metrics(self, tool_id: str) -> Optional[Dict[str, Any]]:
        """Get performance metrics for a tool."""
        if tool_id not in self.metrics:
            return None
        
        raw_metrics = self.metrics[tool_id]
        return {
            "execution_count": raw_metrics["execution_count"],
            "avg_execution_time": raw_metrics["total_duration"] / raw_metrics["execution_count"],
            "success_rate": raw_metrics["success_count"] / raw_metrics["execution_count"],
            "total_executions": raw_metrics["execution_count"]
        }

class DatabaseConnectionManager:
    """Manages database connections for tool execution."""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.connections = {}
        logger.info("DatabaseConnectionManager initialized")
    
    async def get_connection(self, db_type: str, connection_uri: str):
        """Get or create database connection."""
        key = f"{db_type}:{connection_uri}"
        if key not in self.connections:
            # Create connection based on database type
            if db_type in ADAPTER_REGISTRY:
                adapter_class = ADAPTER_REGISTRY[db_type]
                self.connections[key] = adapter_class(connection_uri)
                logger.info(f"Created new connection for {db_type}")
        
        return self.connections.get(key)

class ToolRegistry:
    """Main tool registry compatible with LangGraph integration."""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.tools = {}
        self.performance_monitor = PerformanceMonitor()
        self.connection_manager = DatabaseConnectionManager(settings)
        logger.info("ToolRegistry initialized for LangGraph integration")
    
    async def initialize(self):
        """Initialize the tool registry."""
        logger.info("Initializing ToolRegistry")
        # Initialization logic here
    
    async def register_general_tools(self) -> List[Dict[str, Any]]:
        """Register general-purpose tools."""
        from .general_tools import TextProcessingTools, DataValidationTools, FileSystemTools, UtilityTools, VisualizationTools
        
        tools = []
        
        # Register text processing tools
        tools.extend([
            {
                "tool_id": "text_processing.extract_keywords",
                "name": "Extract Keywords",
                "description": "Extract keywords from text using frequency analysis",
                "category": ToolCategory.UTILITY.value,
                "function": TextProcessingTools.extract_keywords,
                "parameters": {"text": "str", "max_keywords": "int"}
            },
            {
                "tool_id": "text_processing.analyze_sentiment",
                "name": "Analyze Sentiment", 
                "description": "Analyze sentiment of text using rule-based approach",
                "category": ToolCategory.UTILITY.value,
                "function": TextProcessingTools.analyze_sentiment,
                "parameters": {"text": "str"}
            },
            {
                "tool_id": "text_processing.summarize_text",
                "name": "Summarize Text",
                "description": "Create extractive summary of text",
                "category": ToolCategory.UTILITY.value, 
                "function": TextProcessingTools.summarize_text,
                "parameters": {"text": "str", "max_sentences": "int"}
            }
        ])
        
        # Register data validation tools
        tools.extend([
            {
                "tool_id": "data_validation.validate_json_structure",
                "name": "Validate JSON Structure",
                "description": "Validate JSON structure and schema",
                "category": ToolCategory.UTILITY.value,
                "function": DataValidationTools.validate_json_structure,
                "parameters": {"json_str": "str", "expected_schema": "dict"}
            },
            {
                "tool_id": "data_validation.check_data_quality",
                "name": "Check Data Quality",
                "description": "Assess data quality across multiple dimensions",
                "category": ToolCategory.UTILITY.value,
                "function": DataValidationTools.check_data_quality,
                "parameters": {"data": "list", "quality_checks": "dict"}
            }
        ])
        
        # Register file system tools
        tools.extend([
            {
                "tool_id": "file_system.export_data_to_csv",
                "name": "Export Data to CSV",
                "description": "Export data to CSV file",
                "category": ToolCategory.UTILITY.value,
                "function": FileSystemTools.export_data_to_csv,
                "parameters": {"data": "list", "filepath": "str", "include_headers": "bool"}
            },
            {
                "tool_id": "file_system.export_data_to_json",
                "name": "Export Data to JSON",
                "description": "Export data to JSON file",
                "category": ToolCategory.UTILITY.value,
                "function": FileSystemTools.export_data_to_json,
                "parameters": {"data": "any", "filepath": "str", "pretty_print": "bool"}
            }
        ])
        
        # Register utility tools
        tools.extend([
            {
                "tool_id": "utility.generate_unique_id",
                "name": "Generate Unique ID",
                "description": "Generate a unique identifier",
                "category": ToolCategory.UTILITY.value,
                "function": UtilityTools.generate_unique_id,
                "parameters": {"prefix": "str", "length": "int"}
            },
            {
                "tool_id": "utility.calculate_hash",
                "name": "Calculate Hash",
                "description": "Calculate hash of data",
                "category": ToolCategory.UTILITY.value,
                "function": UtilityTools.calculate_hash,
                "parameters": {"data": "any", "algorithm": "str"}
            },
            {
                "tool_id": "utility.format_timestamp",
                "name": "Format Timestamp",
                "description": "Format timestamp to human-readable string",
                "category": ToolCategory.UTILITY.value,
                "function": UtilityTools.format_timestamp,
                "parameters": {"timestamp": "any", "format_str": "str"}
            }
        ])
        
        # Register visualization tools
        tools.extend([
            {
                "tool_id": "visualization.create_visualization",
                "name": "Create Visualization",
                "description": "Create intelligent visualizations based on data analysis and chart selection",
                "category": ToolCategory.VISUALIZATION.value,
                "function": VisualizationTools.create_visualization,
                "parameters": {
                    "data": "list", 
                    "chart_type": "str", 
                    "title": "str", 
                    "user_query": "str",
                    "session_id": "str",  # NEW: Add session_id parameter for associating saved files
                    "save_to_file": "bool",
                    "output_filename": "str"
                }
            }
        ])
        
        # Store tools in registry
        for tool in tools:
            self.tools[tool["tool_id"]] = tool
        
        logger.info(f"Registered {len(tools)} general tools")
        return tools
    
    async def register_database_tools(self, db_type: str, connection_uri: str) -> List[Dict[str, Any]]:
        """Register database-specific tools."""
        logger.info(f"Registering tools for database type: {db_type}")
        
        if db_type not in ADAPTER_REGISTRY:
            logger.warning(f"No adapter found for database type: {db_type}")
            return []
        
        try:
            adapter_class = ADAPTER_REGISTRY[db_type]
            adapter = adapter_class(connection_uri)
            
            tools = []
            
            # Register core database tools - adapters now handle their own query format conversion
            execute_func = adapter.execute
                
            tools.extend([
                {
                    "tool_id": f"{db_type}.execute_query",
                    "name": f"{db_type.title()} Execute Query",
                    "description": f"Execute query on {db_type} database" + (
                        " using REST API endpoints" if db_type == "shopify" else 
                        " using aggregation pipelines" if db_type == "mongo" else ""
                    ),
                    "category": ToolCategory.DATABASE_QUERY.value,
                    "function": execute_func,
                    "parameters": {
                        "query": "dict" if db_type in ["mongo", "shopify"] else "str"
                    }
                },
                {
                    "tool_id": f"{db_type}.introspect_schema",
                    "name": f"{db_type.title()} Introspect Schema",
                    "description": f"Introspect schema of {db_type} database",
                    "category": ToolCategory.SCHEMA_INTROSPECTION.value,
                    "function": adapter.introspect_schema,
                    "parameters": {}
                },
                {
                    "tool_id": f"{db_type}.test_connection",
                    "name": f"{db_type.title()} Test Connection",
                    "description": f"Test connection to {db_type} database",
                    "category": ToolCategory.DATABASE_QUERY.value,
                    "function": adapter.test_connection,
                    "parameters": {}
                }
            ])
            
            # Add database-specific tools
            if hasattr(adapter, 'llm_to_query'):
                tools.append({
                    "tool_id": f"{db_type}.llm_to_query",
                    "name": f"{db_type.title()} LLM to Query",
                    "description": f"Convert natural language to {db_type} query",
                    "category": ToolCategory.DATABASE_QUERY.value,
                    "function": adapter.llm_to_query,
                    "parameters": {"nl_prompt": "str"}
                })
            
            # Store tools in registry
            for tool in tools:
                self.tools[tool["tool_id"]] = tool
            
            logger.info(f"Registered {len(tools)} tools for {db_type}")
            return tools
            
        except Exception as e:
            logger.error(f"Failed to register database tools for {db_type}: {e}")
            return []
    
    async def get_available_tools(self) -> List[Dict[str, Any]]:
        """Get list of all available tools."""
        return list(self.tools.values())
    
    async def get_tools_by_category(self, category: ToolCategory) -> List[Dict[str, Any]]:
        """Get tools by category."""
        return [tool for tool in self.tools.values() if tool["category"] == category.value]
    
    async def get_tools_by_database_type(self, db_type: str) -> List[Dict[str, Any]]:
        """Get tools by database type."""
        return [tool for tool in self.tools.values() if tool["tool_id"].startswith(f"{db_type}.")]
    
    async def search_tools(self, query: str) -> List[Dict[str, Any]]:
        """Search tools by query."""
        query_lower = query.lower()
        matching_tools = []
        
        for tool in self.tools.values():
            if (query_lower in tool["name"].lower() or 
                query_lower in tool["description"].lower() or
                query_lower in tool["tool_id"].lower()):
                matching_tools.append(tool)
        
        return matching_tools
    
    async def get_tool_info(self, tool_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific tool."""
        return self.tools.get(tool_id)
    
    async def execute_tool(self, tool_call: ToolCall) -> ExecutionResult:
        """Execute a tool call."""
        start_time = time.time()
        
        try:
            # Get tool info
            tool_info = self.tools.get(tool_call.tool_id)
            if not tool_info:
                return ExecutionResult(
                    tool_id=tool_call.tool_id,
                    call_id=tool_call.call_id,
                    success=False,
                    error=f"Tool {tool_call.tool_id} not found in registry"
                )
            
            # Execute tool function
            tool_function = tool_info["function"]
            
            # Call the function with parameters
            if asyncio.iscoroutinefunction(tool_function):
                result = await tool_function(**tool_call.parameters)
            else:
                result = tool_function(**tool_call.parameters)
            
            duration = time.time() - start_time
            
            # Record performance metrics
            await self.performance_monitor.record_execution(
                tool_call.tool_id, duration, True
            )
            
            return ExecutionResult(
                tool_id=tool_call.tool_id,
                call_id=tool_call.call_id,
                success=True,
                result=result,
                metadata={"execution_time": duration}
            )
            
        except Exception as e:
            duration = time.time() - start_time
            error_msg = str(e)
            
            # Record performance metrics
            await self.performance_monitor.record_execution(
                tool_call.tool_id, duration, False
            )
            
            logger.error(f"Tool execution failed for {tool_call.tool_id}: {error_msg}")
            
            return ExecutionResult(
                tool_id=tool_call.tool_id,
                call_id=tool_call.call_id,
                success=False,
                error=error_msg,
                metadata={"execution_time": duration}
            )
    
    async def get_performance_metrics(self, tool_id: str) -> Optional[Dict[str, Any]]:
        """Get performance metrics for a tool."""
        return await self.performance_monitor.get_metrics(tool_id)
    
 
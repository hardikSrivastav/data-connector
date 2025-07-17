"""
LangGraph Visualization Node

This node integrates with the existing visualization system to create charts
when the agent identifies that data should be visualized.
"""

import logging
import asyncio
import time
import pandas as pd
import os
from typing import Dict, List, Any, Optional, AsyncIterator, Tuple
from dataclasses import asdict
from datetime import datetime

from .streaming_node_base import StreamingNodeBase
from ..state import LangGraphState
from ...visualization.analyzer import DataAnalysisModule
from ...visualization.selector import ChartSelectionEngine
from ...visualization.generator import PlotlyConfigGenerator
from ...visualization.types import (
    VisualizationDataset, UserPreferences, DataAnalysisResult,
    ChartSelection, PlotlyConfig, PerformanceMetrics
)
from ...llm.client import get_llm_client

logger = logging.getLogger(__name__)

# ✅ NEW: Dedicated visualization debug logger
def setup_viz_debug_logger():
    """Setup dedicated logger for visualization debugging"""
    viz_logger = logging.getLogger('visualization_debug')
    viz_logger.setLevel(logging.DEBUG)
    
    # Create logs directory if it doesn't exist
    log_dir = os.path.join(os.path.dirname(__file__), '../../../../logs')
    os.makedirs(log_dir, exist_ok=True)
    
    # Create file handler for visualization debug log
    log_file = os.path.join(log_dir, 'visualization_debug.log')
    file_handler = logging.FileHandler(log_file, mode='a')
    file_handler.setLevel(logging.DEBUG)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - [VIZ_DEBUG] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    
    # Add handler if not already added
    if not viz_logger.handlers:
        viz_logger.addHandler(file_handler)
    
    return viz_logger

# Initialize debug logger
viz_debug_logger = setup_viz_debug_logger()

class VisualizationNode(StreamingNodeBase):
    """
    LangGraph node for intelligent chart generation and visualization.
    
    This node:
    1. Analyzes execution results to determine if visualization is beneficial
    2. Prepares data for visualization using the existing visualization system
    3. Generates appropriate chart configurations
    4. Integrates charts into the final response
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("visualization_node")
        self.config = config or {}
        
        # ✅ DEBUG: Log initialization
        viz_debug_logger.info("="*80)
        viz_debug_logger.info("VISUALIZATION NODE INITIALIZATION STARTED")
        viz_debug_logger.info(f"Config: {self.config}")
        
        # Initialize visualization system components
        try:
            self.llm_client = get_llm_client()
            viz_debug_logger.info("✅ LLM client initialized successfully")
        except Exception as e:
            viz_debug_logger.error(f"❌ Failed to initialize LLM client: {e}")
            raise
            
        try:
            self.data_analyzer = DataAnalysisModule(self.llm_client)
            viz_debug_logger.info("✅ Data analyzer initialized successfully")
        except Exception as e:
            viz_debug_logger.error(f"❌ Failed to initialize data analyzer: {e}")
            raise
            
        try:
            self.chart_selector = ChartSelectionEngine(self.llm_client)
            viz_debug_logger.info("✅ Chart selector initialized successfully")
        except Exception as e:
            viz_debug_logger.error(f"❌ Failed to initialize chart selector: {e}")
            raise
            
        try:
            self.config_generator = PlotlyConfigGenerator()
            viz_debug_logger.info("✅ Config generator initialized successfully")
        except Exception as e:
            viz_debug_logger.error(f"❌ Failed to initialize config generator: {e}")
            raise
        
        # Visualization detection keywords and patterns
        self.visualization_keywords = [
            'chart', 'graph', 'plot', 'visualize', 'visualization', 'show', 'display',
            'trend', 'pattern', 'distribution', 'comparison', 'breakdown', 'analysis',
            'dashboard', 'report', 'summary', 'overview', 'insights'
        ]
        
        self.chart_type_keywords = {
            'bar': ['bar', 'column', 'category', 'comparison', 'compare'],
            'line': ['line', 'trend', 'time', 'timeline', 'over time', 'temporal'],
            'pie': ['pie', 'percentage', 'proportion', 'share', 'breakdown'],
            'scatter': ['scatter', 'correlation', 'relationship', 'vs', 'against'],
            'histogram': ['histogram', 'distribution', 'frequency', 'bins'],
            'box': ['box', 'quartile', 'outlier', 'statistical', 'stats']
        }
        
        viz_debug_logger.info(f"✅ Visualization keywords loaded: {len(self.visualization_keywords)} total")
        viz_debug_logger.info(f"✅ Chart type keywords loaded: {list(self.chart_type_keywords.keys())}")
        viz_debug_logger.info("VISUALIZATION NODE INITIALIZATION COMPLETED")
        viz_debug_logger.info("="*80)
        
        logger.info("🎨 [VISUALIZATION_NODE] Initialized with visualization system components")
    
    async def stream(self, state: LangGraphState, **kwargs) -> AsyncIterator[Dict[str, Any]]:
        """
        Stream the visualization creation process.
        """
        session_id = state.get("session_id", "unknown")
        user_query = state.get("user_query", state.get("question", ""))
        
        # ✅ DEBUG: Log stream method entry
        viz_debug_logger.info("="*80)
        viz_debug_logger.info(f"VISUALIZATION NODE STREAM CALLED - Session: {session_id}")
        viz_debug_logger.info(f"User Query: '{user_query}'")
        viz_debug_logger.info(f"State Keys: {list(state.keys())}")
        viz_debug_logger.info(f"Kwargs: {kwargs}")
        
        # Log full state for debugging
        viz_debug_logger.debug(f"Full State Data: {state}")
        
        logger.info(f"🎨 [VISUALIZATION_NODE] [{session_id}] Starting visualization analysis")
        logger.info(f"🎨 [VISUALIZATION_NODE] [{session_id}] Query: {user_query}")
        
        start_time = time.time()
        
        try:
            # Step 1: Determine if visualization is needed
            viz_debug_logger.info("STEP 1: Checking if visualization is needed...")
            
            yield self.create_progress_chunk(
                0.1, "Analyzing if visualization is needed...", 
                {"stage": "visualization_detection"}
            )
            
            should_visualize, viz_intent = await self._should_create_visualization(
                user_query, state, session_id
            )
            
            viz_debug_logger.info(f"Should visualize: {should_visualize}")
            viz_debug_logger.info(f"Visualization intent: {viz_intent}")
            
            if not should_visualize:
                viz_debug_logger.warning("❌ NO VISUALIZATION NEEDED - Exiting early")
                viz_debug_logger.info("="*80)
                
                logger.info(f"🎨 [VISUALIZATION_NODE] [{session_id}] No visualization needed")
                yield self.create_result_chunk(
                    {"visualization_needed": False, "reason": "No visualization intent detected"},
                    state_update={"visualization_completed": True},
                    is_final=True
                )
                return
            
            viz_debug_logger.info(f"✅ VISUALIZATION NEEDED: {viz_intent}")
            logger.info(f"🎨 [VISUALIZATION_NODE] [{session_id}] Visualization needed: {viz_intent}")
            
            # Step 2: Extract and prepare data for visualization
            viz_debug_logger.info("STEP 2: Preparing data for visualization...")
            
            yield self.create_progress_chunk(
                0.3, "Preparing data for visualization...", 
                {"stage": "data_preparation", "intent": viz_intent}
            )
            
            dataset = await self._prepare_visualization_dataset(state, session_id)
            
            if not dataset or dataset.size == 0:
                viz_debug_logger.error("❌ NO SUITABLE DATA FOR VISUALIZATION")
                viz_debug_logger.info("="*80)
                
                logger.warning(f"🎨 [VISUALIZATION_NODE] [{session_id}] No suitable data for visualization")
                yield self.create_result_chunk(
                    {"visualization_needed": True, "error": "No suitable data available"},
                    state_update={"visualization_completed": True, "visualization_error": True},
                    is_final=True
                )
                return
            
            viz_debug_logger.info(f"✅ DATASET PREPARED: {dataset.size} rows, {len(dataset.columns)} columns")
            viz_debug_logger.info(f"Dataset columns: {dataset.columns}")
            viz_debug_logger.info(f"Dataset sample: {dataset.data.head().to_dict() if hasattr(dataset.data, 'head') else 'No sample available'}")
            
            logger.info(f"🎨 [VISUALIZATION_NODE] [{session_id}] Dataset prepared: {dataset.size} rows, {len(dataset.columns)} columns")
            
            # Step 3: Analyze data for visualization
            viz_debug_logger.info("STEP 3: Analyzing data characteristics...")
            
            yield self.create_progress_chunk(
                0.5, "Analyzing data characteristics...", 
                {"stage": "data_analysis", "dataset_size": dataset.size}
            )
            
            analysis_result = await self.data_analyzer.analyze_dataset(
                dataset, viz_intent, session_id
            )
            
            viz_debug_logger.info("✅ DATA ANALYSIS COMPLETED")
            viz_debug_logger.info(f"Analysis result keys: {list(asdict(analysis_result).keys()) if analysis_result else 'No result'}")
            
            logger.info(f"🎨 [VISUALIZATION_NODE] [{session_id}] Data analysis completed")
            
            # Step 4: Select optimal chart type
            viz_debug_logger.info("STEP 4: Selecting optimal chart type...")
            
            yield self.create_progress_chunk(
                0.7, "Selecting optimal chart type...", 
                {"stage": "chart_selection"}
            )
            
            user_preferences = UserPreferences(
                preferred_style=self.config.get("chart_style", "modern"),
                performance_priority=self.config.get("performance_priority", "medium"),
                interactivity_level=self.config.get("interactivity_level", "medium")
            )
            
            viz_debug_logger.info(f"User preferences: {asdict(user_preferences)}")
            
            chart_selection = await self.chart_selector.select_optimal_chart(
                analysis_result, user_preferences, session_id
            )
            
            viz_debug_logger.info(f"✅ CHART SELECTED: {chart_selection.primary_chart.chart_type}")
            viz_debug_logger.info(f"Chart selection confidence: {chart_selection.primary_chart.confidence_score}")
            
            logger.info(f"🎨 [VISUALIZATION_NODE] [{session_id}] Selected chart: {chart_selection.primary_chart.chart_type}")
            
            # Step 5: Generate chart configuration
            viz_debug_logger.info("STEP 5: Generating chart configuration...")
            
            yield self.create_progress_chunk(
                0.9, f"Generating {chart_selection.primary_chart.chart_type} chart configuration...", 
                {"stage": "chart_generation", "chart_type": chart_selection.primary_chart.chart_type}
            )
            
            chart_config = await self.config_generator.generate_config(
                chart_type=chart_selection.primary_chart.chart_type,
                dataset=dataset,
                recommendation=chart_selection.primary_chart,
                customizations=self.config.get("chart_customizations", {}),
                session_id=session_id
            )
            
            viz_debug_logger.info("✅ CHART CONFIG GENERATED")
            viz_debug_logger.info(f"Chart config type: {chart_config.type if chart_config else 'No config'}")
            
            # Step 6: Prepare final visualization result
            execution_time = time.time() - start_time
            
            visualization_result = {
                "visualization_created": True,
                "chart_config": asdict(chart_config),
                "chart_data": dataset.data.to_dict('records'),
                "chart_selection": asdict(chart_selection),
                "data_analysis": asdict(analysis_result),
                "dataset_info": {
                    "size": dataset.size,
                    "columns": dataset.columns,
                    "source_info": dataset.source_info
                },
                "performance_metrics": {
                    "execution_time": execution_time,
                    "dataset_size": dataset.size,
                    "chart_type": chart_selection.primary_chart.chart_type
                },
                "visualization_intent": viz_intent,
                "session_id": session_id
            }
            
            viz_debug_logger.info("✅ VISUALIZATION RESULT PREPARED")
            viz_debug_logger.info(f"Result keys: {list(visualization_result.keys())}")
            viz_debug_logger.info(f"Chart type: {visualization_result['performance_metrics']['chart_type']}")
            viz_debug_logger.info(f"Dataset size: {visualization_result['performance_metrics']['dataset_size']}")
            viz_debug_logger.info(f"Execution time: {execution_time:.2f}s")
            
            # Capture outputs for aggregation
            await self._capture_node_outputs(session_id, visualization_result)
            viz_debug_logger.info("✅ NODE OUTPUTS CAPTURED")
            
            # Capture final synthesis for output aggregator
            try:
                from ..output_aggregator import get_output_integrator
                output_integrator = get_output_integrator()
                aggregator = output_integrator.get_aggregator(session_id)
                
                # Create a descriptive analysis of the visualization
                chart_type = chart_selection.primary_chart.chart_type
                data_size = dataset.size
                visualization_summary = f"Successfully created {chart_type} visualization with {data_size} data points. Chart displays {', '.join(dataset.columns[:3])}{'...' if len(dataset.columns) > 3 else ''} across {len(dataset.columns)} total columns. Visualization generated in {execution_time*1000:.0f}ms with optimal chart selection based on data analysis."
                
                aggregator.capture_final_synthesis(
                    response_text=visualization_summary,
                    confidence_score=0.9,  # High confidence for successful visualization
                    sources_used=["visualization_system", "data_analysis"],
                    node_id="visualization_node",
                    synthesis_method="visualization_analysis"
                )
                
                viz_debug_logger.info("✅ FINAL SYNTHESIS CAPTURED")
                viz_debug_logger.info(f"Synthesis summary: {visualization_summary[:100]}...")
                
                logger.info(f"🎨 [VISUALIZATION_NODE] [{session_id}] Captured final synthesis for output aggregator")
                
            except Exception as e:
                viz_debug_logger.error(f"❌ FAILED TO CAPTURE FINAL SYNTHESIS: {e}")
                logger.warning(f"🎨 [VISUALIZATION_NODE] [{session_id}] Failed to capture final synthesis: {e}")
            
            logger.info(f"🎨 [VISUALIZATION_NODE] [{session_id}] Visualization completed in {execution_time:.2f}s")
            
            # ✅ DEBUG: Log the final result before yielding
            viz_debug_logger.info("🎉 YIELDING FINAL VISUALIZATION RESULT")
            viz_debug_logger.info(f"Final result type: visualization_created = {visualization_result['visualization_created']}")
            viz_debug_logger.info("="*80)
            
            yield self.create_result_chunk(
                visualization_result,
                state_update={
                    "visualization_completed": True,
                    "chart_config": chart_config,
                    "visualization_data": visualization_result
                },
                is_final=True
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            
            viz_debug_logger.error("❌ VISUALIZATION NODE ERROR")
            viz_debug_logger.error(f"Error type: {type(e).__name__}")
            viz_debug_logger.error(f"Error message: {str(e)}")
            viz_debug_logger.error(f"Execution time before error: {execution_time:.2f}s")
            viz_debug_logger.info("="*80)
            
            logger.error(f"🎨 [VISUALIZATION_NODE] [{session_id}] Error: {e}")
            
            yield self.create_result_chunk(
                {
                    "visualization_needed": True,
                    "error": str(e),
                    "execution_time": execution_time
                },
                state_update={
                    "visualization_completed": True,
                    "visualization_error": True,
                    "error_message": str(e)
                },
                is_final=True
            )
    
    async def __call__(self, state: LangGraphState, **kwargs) -> LangGraphState:
        """
        Non-streaming execution of the visualization node.
        """
        # Execute streaming version and get final result
        final_result = None
        async for chunk in self.stream(state, **kwargs):
            if chunk.get("is_final", False):
                final_result = chunk
                break
        
        # Update state with results
        if final_result and "state_update" in final_result:
            state.update(final_result["state_update"])
        
        return state
    
    async def _should_create_visualization(
        self, 
        user_query: str, 
        state: LangGraphState, 
        session_id: str
    ) -> Tuple[bool, str]:
        """
        Determine if visualization should be created based on query and results.
        """
        viz_debug_logger.info(f"🤔 ANALYZING VISUALIZATION NEED - Session: {session_id}")
        viz_debug_logger.info(f"Query: '{user_query}'")
        
        query_lower = user_query.lower()
        viz_debug_logger.info(f"Query (lowercase): '{query_lower}'")
        
        # Check for explicit visualization keywords
        explicit_viz_request = any(keyword in query_lower for keyword in self.visualization_keywords)
        viz_debug_logger.info(f"Explicit visualization request: {explicit_viz_request}")
        
        if explicit_viz_request:
            matched_keywords = [kw for kw in self.visualization_keywords if kw in query_lower]
            viz_debug_logger.info(f"Matched keywords: {matched_keywords}")
        
        # Check for data analysis context that would benefit from visualization
        has_numerical_data = self._has_numerical_results(state)
        has_multiple_records = self._has_multiple_records(state)
        has_temporal_data = self._has_temporal_data(state)
        has_categorical_data = self._has_categorical_data(state)
        
        viz_debug_logger.info(f"Data analysis context:")
        viz_debug_logger.info(f"  - Has numerical data: {has_numerical_data}")
        viz_debug_logger.info(f"  - Has multiple records: {has_multiple_records}")
        viz_debug_logger.info(f"  - Has temporal data: {has_temporal_data}")
        viz_debug_logger.info(f"  - Has categorical data: {has_categorical_data}")
        
        # Log state data for debugging
        results = state.get("results", [])
        operation_results = state.get("operation_results", {})
        viz_debug_logger.info(f"State analysis:")
        viz_debug_logger.info(f"  - Results count: {len(results) if results else 0}")
        viz_debug_logger.info(f"  - Operation results keys: {list(operation_results.keys()) if operation_results else []}")
        
        # Sample first few results for debugging
        if results and len(results) > 0:
            sample_results = results[:3] if len(results) >= 3 else results
            viz_debug_logger.info(f"  - Sample results: {sample_results}")
        
        # Determine visualization intent
        if explicit_viz_request:
            # Try to determine specific chart type from query
            intent = self._extract_chart_intent(query_lower)
            viz_debug_logger.info(f"✅ EXPLICIT VISUALIZATION REQUEST - Intent: '{intent}'")
            return True, intent
        
        # Auto-detect visualization opportunities
        if has_numerical_data and has_multiple_records:
            if has_temporal_data:
                intent = "Show trends over time"
                viz_debug_logger.info(f"✅ AUTO-DETECTED TEMPORAL VISUALIZATION - Intent: '{intent}'")
                return True, intent
            elif has_categorical_data:
                intent = "Compare categories with numerical data"
                viz_debug_logger.info(f"✅ AUTO-DETECTED CATEGORICAL COMPARISON - Intent: '{intent}'")
                return True, intent
            else:
                intent = "Visualize numerical data distribution"
                viz_debug_logger.info(f"✅ AUTO-DETECTED NUMERICAL DISTRIBUTION - Intent: '{intent}'")
                return True, intent
        
        if has_categorical_data and has_multiple_records:
            intent = "Show categorical data breakdown"
            viz_debug_logger.info(f"✅ AUTO-DETECTED CATEGORICAL BREAKDOWN - Intent: '{intent}'")
            return True, intent
        
        # No visualization needed
        viz_debug_logger.info("❌ NO VISUALIZATION NEEDED")
        viz_debug_logger.info("Reasons:")
        if not explicit_viz_request:
            viz_debug_logger.info("  - No explicit visualization keywords found")
        if not has_numerical_data:
            viz_debug_logger.info("  - No numerical data detected")
        if not has_multiple_records:
            viz_debug_logger.info("  - Not enough records for visualization")
        if not has_categorical_data and not has_temporal_data:
            viz_debug_logger.info("  - No categorical or temporal data patterns")
        
        return False, ""
    
    def _extract_chart_intent(self, query_lower: str) -> str:
        """
        Extract specific chart type intent from query.
        """
        for chart_type, keywords in self.chart_type_keywords.items():
            if any(keyword in query_lower for keyword in keywords):
                return f"Create {chart_type} chart"
        
        return "Create appropriate visualization"
    
    def _has_numerical_results(self, state: LangGraphState) -> bool:
        """Check if execution results contain numerical data."""
        results = state.get("results", [])
        operation_results = state.get("operation_results", {})
        
        # Check direct results
        if results and isinstance(results, list) and results:
            first_row = results[0] if results else {}
            if isinstance(first_row, dict):
                return any(isinstance(v, (int, float)) for v in first_row.values())
        
        # Check operation results
        for op_result in operation_results.values():
            if isinstance(op_result, dict) and "result" in op_result:
                data = op_result["result"]
                if isinstance(data, list) and data:
                    first_row = data[0] if data else {}
                    if isinstance(first_row, dict):
                        return any(isinstance(v, (int, float)) for v in first_row.values())
        
        return False
    
    def _has_multiple_records(self, state: LangGraphState) -> bool:
        """Check if there are multiple data records."""
        results = state.get("results", [])
        operation_results = state.get("operation_results", {})
        
        if results and len(results) > 1:
            return True
        
        for op_result in operation_results.values():
            if isinstance(op_result, dict) and "result" in op_result:
                data = op_result["result"]
                if isinstance(data, list) and len(data) > 1:
                    return True
        
        return False
    
    def _has_temporal_data(self, state: LangGraphState) -> bool:
        """Check if data contains temporal/date columns."""
        results = state.get("results", [])
        operation_results = state.get("operation_results", {})
        
        temporal_keywords = ['date', 'time', 'created', 'updated', 'timestamp', 'year', 'month', 'day']
        
        # Check column names in results
        if results and results:
            first_row = results[0] if results else {}
            if isinstance(first_row, dict):
                columns = list(first_row.keys())
                return any(any(keyword in col.lower() for keyword in temporal_keywords) for col in columns)
        
        return False
    
    def _has_categorical_data(self, state: LangGraphState) -> bool:
        """Check if data contains categorical columns."""
        results = state.get("results", [])
        operation_results = state.get("operation_results", {})
        
        # Check for string data that could be categorical
        if results and results:
            first_row = results[0] if results else {}
            if isinstance(first_row, dict):
                return any(isinstance(v, str) for v in first_row.values())
        
        return False
    
    async def _prepare_visualization_dataset(
        self, 
        state: LangGraphState, 
        session_id: str
    ) -> Optional[VisualizationDataset]:
        """
        Prepare a VisualizationDataset from the execution results.
        """
        # Collect all available data
        all_data = []
        source_info = {}
        
        # Get data from results
        results = state.get("results", [])
        if results and isinstance(results, list):
            all_data.extend(results)
            source_info["direct_results"] = len(results)
        
        # Get data from operation results
        operation_results = state.get("operation_results", {})
        for op_id, op_result in operation_results.items():
            if isinstance(op_result, dict) and "result" in op_result:
                data = op_result["result"]
                if isinstance(data, list):
                    all_data.extend(data)
                    source_info[f"operation_{op_id}"] = len(data)
        
        if not all_data:
            logger.warning(f"🎨 [VISUALIZATION_NODE] [{session_id}] No data available for visualization")
            return None
        
        # Convert to DataFrame
        try:
            df = pd.DataFrame(all_data)
            
            # Clean the data
            df = self._clean_dataframe(df)
            
            if df.empty:
                logger.warning(f"🎨 [VISUALIZATION_NODE] [{session_id}] DataFrame is empty after cleaning")
                return None
            
            # Create VisualizationDataset
            dataset = VisualizationDataset(
                data=df,
                columns=list(df.columns),
                metadata={
                    "session_id": session_id,
                    "total_records": len(df),
                    "data_types": {col: str(dtype) for col, dtype in df.dtypes.items()}
                },
                source_info=source_info
            )
            
            logger.info(f"🎨 [VISUALIZATION_NODE] [{session_id}] Dataset created: {dataset.size} rows, {len(dataset.columns)} columns")
            
            return dataset
            
        except Exception as e:
            logger.error(f"🎨 [VISUALIZATION_NODE] [{session_id}] Error creating dataset: {e}")
            return None
    
    def _clean_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Clean and prepare DataFrame for visualization.
        """
        # Remove completely empty columns
        df = df.dropna(axis=1, how='all')
        
        # Remove completely empty rows
        df = df.dropna(axis=0, how='all')
        
        # Convert numeric strings to numbers where possible
        for col in df.columns:
            if df[col].dtype == 'object':
                # Try to convert to numeric
                numeric_values = pd.to_numeric(df[col], errors='coerce')
                if not numeric_values.isna().all():
                    df[col] = numeric_values
                else:
                    # Try to convert to datetime
                    try:
                        datetime_values = pd.to_datetime(df[col], errors='coerce')
                        if not datetime_values.isna().all():
                            df[col] = datetime_values
                    except:
                        pass  # Keep as string/object
        
        # Reset index
        df = df.reset_index(drop=True)
        
        return df
    
    def get_node_capabilities(self) -> Dict[str, Any]:
        """Get capabilities of this visualization node."""
        return {
            "node_type": "visualization",
            "supports_streaming": True,
            "visualization_features": {
                "auto_detection": True,
                "chart_types": list(self.chart_type_keywords.keys()),
                "data_analysis": True,
                "chart_optimization": True
            },
            "supported_data_types": ["numerical", "categorical", "temporal", "text"],
            "chart_capabilities": {
                "bar_charts": True,
                "line_charts": True,
                "pie_charts": True,
                "scatter_plots": True,
                "histograms": True,
                "box_plots": True
            }
        } 
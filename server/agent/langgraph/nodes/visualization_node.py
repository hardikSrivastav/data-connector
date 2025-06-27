"""
LangGraph Visualization Node

This node integrates with the existing visualization system to create charts
when the agent identifies that data should be visualized.
"""

import logging
import asyncio
import time
import pandas as pd
from typing import Dict, List, Any, Optional, AsyncIterator, Tuple
from dataclasses import asdict

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
        
        # Initialize visualization system components
        self.llm_client = get_llm_client()
        self.data_analyzer = DataAnalysisModule(self.llm_client)
        self.chart_selector = ChartSelectionEngine(self.llm_client)
        self.config_generator = PlotlyConfigGenerator()
        
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
        
        logger.info("🎨 [VISUALIZATION_NODE] Initialized with visualization system components")
    
    async def stream(self, state: LangGraphState, **kwargs) -> AsyncIterator[Dict[str, Any]]:
        """
        Stream the visualization creation process.
        """
        session_id = state.get("session_id", "unknown")
        user_query = state.get("user_query", state.get("question", ""))
        
        logger.info(f"🎨 [VISUALIZATION_NODE] [{session_id}] Starting visualization analysis")
        logger.info(f"🎨 [VISUALIZATION_NODE] [{session_id}] Query: {user_query}")
        
        start_time = time.time()
        
        try:
            # Step 1: Determine if visualization is needed
            yield self.create_progress_chunk(
                0.1, "Analyzing if visualization is needed...", 
                {"stage": "visualization_detection"}
            )
            
            should_visualize, viz_intent = await self._should_create_visualization(
                user_query, state, session_id
            )
            
            if not should_visualize:
                logger.info(f"🎨 [VISUALIZATION_NODE] [{session_id}] No visualization needed")
                yield self.create_result_chunk(
                    {"visualization_needed": False, "reason": "No visualization intent detected"},
                    state_update={"visualization_completed": True},
                    is_final=True
                )
                return
            
            logger.info(f"🎨 [VISUALIZATION_NODE] [{session_id}] Visualization needed: {viz_intent}")
            
            # Step 2: Extract and prepare data for visualization
            yield self.create_progress_chunk(
                0.3, "Preparing data for visualization...", 
                {"stage": "data_preparation", "intent": viz_intent}
            )
            
            dataset = await self._prepare_visualization_dataset(state, session_id)
            
            if not dataset or dataset.size == 0:
                logger.warning(f"🎨 [VISUALIZATION_NODE] [{session_id}] No suitable data for visualization")
                yield self.create_result_chunk(
                    {"visualization_needed": True, "error": "No suitable data available"},
                    state_update={"visualization_completed": True, "visualization_error": True},
                    is_final=True
                )
                return
            
            logger.info(f"🎨 [VISUALIZATION_NODE] [{session_id}] Dataset prepared: {dataset.size} rows, {len(dataset.columns)} columns")
            
            # Step 3: Analyze data for visualization
            yield self.create_progress_chunk(
                0.5, "Analyzing data characteristics...", 
                {"stage": "data_analysis", "dataset_size": dataset.size}
            )
            
            analysis_result = await self.data_analyzer.analyze_dataset(
                dataset, viz_intent, session_id
            )
            
            logger.info(f"🎨 [VISUALIZATION_NODE] [{session_id}] Data analysis completed")
            
            # Step 4: Select optimal chart type
            yield self.create_progress_chunk(
                0.7, "Selecting optimal chart type...", 
                {"stage": "chart_selection"}
            )
            
            user_preferences = UserPreferences(
                preferred_style=self.config.get("chart_style", "modern"),
                performance_priority=self.config.get("performance_priority", "medium"),
                interactivity_level=self.config.get("interactivity_level", "medium")
            )
            
            chart_selection = await self.chart_selector.select_optimal_chart(
                analysis_result, user_preferences, session_id
            )
            
            logger.info(f"🎨 [VISUALIZATION_NODE] [{session_id}] Selected chart: {chart_selection.primary_chart.chart_type}")
            
            # Step 5: Generate chart configuration
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
            
            # Capture outputs for aggregation
            await self._capture_node_outputs(session_id, visualization_result)
            
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
                
                logger.info(f"🎨 [VISUALIZATION_NODE] [{session_id}] Captured final synthesis for output aggregator")
                
            except Exception as e:
                logger.warning(f"🎨 [VISUALIZATION_NODE] [{session_id}] Failed to capture final synthesis: {e}")
            
            logger.info(f"🎨 [VISUALIZATION_NODE] [{session_id}] Visualization completed in {execution_time:.2f}s")
            
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
        query_lower = user_query.lower()
        
        # Check for explicit visualization keywords
        explicit_viz_request = any(keyword in query_lower for keyword in self.visualization_keywords)
        
        # Check for data analysis context that would benefit from visualization
        has_numerical_data = self._has_numerical_results(state)
        has_multiple_records = self._has_multiple_records(state)
        has_temporal_data = self._has_temporal_data(state)
        has_categorical_data = self._has_categorical_data(state)
        
        # Determine visualization intent
        if explicit_viz_request:
            # Try to determine specific chart type from query
            intent = self._extract_chart_intent(query_lower)
            return True, intent
        
        # Auto-detect visualization opportunities
        if has_numerical_data and has_multiple_records:
            if has_temporal_data:
                return True, "Show trends over time"
            elif has_categorical_data:
                return True, "Compare categories with numerical data"
            else:
                return True, "Visualize numerical data distribution"
        
        if has_categorical_data and has_multiple_records:
            return True, "Show categorical data breakdown"
        
        # No visualization needed
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
"""
Chart Selection Engine for Visualization

Uses LLM-powered intelligent chart selection based on data analysis
"""
import logging
from typing import List, Dict, Any
from .types import DataAnalysisResult, UserPreferences, ChartSelection, ChartRecommendation, DatasetDimensionality, VariableClassification

logger = logging.getLogger(__name__)

class ChartSelectionEngine:
    """LLM-powered intelligent chart selection"""
    
    def __init__(self, llm_client):
        self.llm_client = llm_client
        
        # Setup dedicated logging
        self.logger = logging.getLogger('visualization_pipeline')
        if not self.logger.handlers:
            handler = logging.FileHandler('visualization_pipeline.log')
            handler.setLevel(logging.DEBUG)
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.DEBUG)
    
    async def select_optimal_chart(self, analysis: DataAnalysisResult, user_preferences: UserPreferences, session_id: str = "default") -> ChartSelection:
        """
        Select optimal chart type based on data analysis and user preferences
        
        Args:
            analysis: Result from data analysis
            user_preferences: User's visualization preferences
            session_id: Session identifier for logging
            
        Returns:
            ChartSelection with primary recommendation and alternatives
        """
        self.logger.info(f"[{session_id}] Starting chart selection for {analysis.dataset_size} data points")
        self.logger.debug(f"[{session_id}] Analysis input: dimensionality={analysis.dimensionality.variable_count} vars, preferences={user_preferences.__dict__}")
        
        try:
            # Step 1: Rule-based filtering
            self.logger.info(f"[{session_id}] Step 1: Filtering compatible chart types...")
            compatible_charts = self._filter_compatible_charts(analysis, session_id)
            self.logger.info(f"[{session_id}] Found {len(compatible_charts)} compatible chart types: {compatible_charts}")
            
            # Step 2: Score and rank charts
            self.logger.info(f"[{session_id}] Step 2: Scoring and ranking charts...")
            ranked_charts = self._rank_charts(compatible_charts, analysis, user_preferences, session_id)
            
            # Step 3: Create recommendations
            self.logger.info(f"[{session_id}] Step 3: Creating final recommendations...")
            primary_chart = ranked_charts[0] if ranked_charts else self._get_fallback_chart()
            alternatives = ranked_charts[1:3] if len(ranked_charts) > 1 else []
            
            selection = ChartSelection(
                primary_chart=primary_chart,
                alternatives=alternatives,
                rationale=f"Selected {primary_chart.chart_type} based on {analysis.dimensionality.variable_count} variables with {primary_chart.confidence_score:.1%} confidence",
                performance_considerations={
                    "dataset_size": analysis.dataset_size,
                    "expected_render_time": self._estimate_render_time(primary_chart.chart_type, analysis.dataset_size)
                }
            )
            
            self.logger.info(f"[{session_id}] Chart selection completed: {primary_chart.chart_type} ({primary_chart.confidence_score:.1%} confidence)")
            return selection
            
        except Exception as e:
            self.logger.error(f"[{session_id}] Error in chart selection: {str(e)}")
            self.logger.exception(f"[{session_id}] Full error traceback:")
            # Return fallback selection
            fallback_chart = self._get_fallback_chart()
            return ChartSelection(
                primary_chart=fallback_chart,
                alternatives=[],
                rationale="Error in chart selection - using fallback recommendation"
            )
    
    def _filter_compatible_charts(self, analysis: DataAnalysisResult, session_id: str) -> List[str]:
        """Filter charts based on data characteristics"""
        compatible = []
        
        # Get variable counts by type
        numeric_vars = [col for col, var_type in analysis.variable_types.items() if var_type.data_type == "continuous"]
        categorical_vars = [col for col, var_type in analysis.variable_types.items() if var_type.data_type == "categorical"]
        temporal_vars = [col for col, var_type in analysis.variable_types.items() if var_type.data_type == "temporal"]
        
        self.logger.debug(f"[{session_id}] Variable analysis: {len(numeric_vars)} numeric, {len(categorical_vars)} categorical, {len(temporal_vars)} temporal")
        
        # Single variable analysis
        if analysis.dimensionality.variable_count == 1:
            if numeric_vars:
                compatible.extend(['histogram', 'box_plot'])
            if categorical_vars:
                compatible.extend(['bar_chart', 'pie_chart', 'donut_chart'])
        
        # Two variable analysis
        elif analysis.dimensionality.variable_count == 2:
            if temporal_vars and numeric_vars:
                compatible.extend(['line_chart', 'area_chart'])
            elif categorical_vars and numeric_vars:
                compatible.extend(['bar_chart', 'column_chart', 'box_plot'])
            elif len(numeric_vars) >= 2:
                    compatible.extend(['scatter_plot', 'line_chart'])
        
        # Multi-variable analysis
        elif analysis.dimensionality.variable_count > 2:
            compatible.extend(['heatmap', 'parallel_coordinates'])
            if temporal_vars:
                compatible.extend(['line_chart', 'area_chart'])
            if categorical_vars and numeric_vars:
                compatible.extend(['grouped_bar_chart', 'stacked_bar_chart'])
        
        # Ensure we always have some options
        if not compatible:
            compatible = ['bar_chart', 'line_chart', 'scatter_plot']
        
        return compatible
    
    def _rank_charts(self, compatible_charts: List[str], analysis: DataAnalysisResult, preferences: UserPreferences, session_id: str) -> List[ChartRecommendation]:
        """Rank compatible charts based on analysis and preferences"""
        recommendations = []
        
        for chart_type in compatible_charts:
            # Base confidence score
            confidence = 0.7
            
            # Adjust based on data characteristics
            confidence += self._calculate_data_fit_score(chart_type, analysis)
            
            # Adjust based on user preferences
            confidence += self._calculate_preference_score(chart_type, preferences)
            
            # Adjust based on performance considerations
            confidence += self._calculate_performance_score(chart_type, analysis.dataset_size)
            
            # Cap confidence at 1.0
            confidence = min(confidence, 1.0)
            
            # Generate rationale
            rationale = self._generate_rationale(chart_type, analysis)
            
            # Create data mapping
            data_mapping = self._create_data_mapping(chart_type, analysis)
            
            recommendations.append(ChartRecommendation(
                chart_type=chart_type,
                confidence_score=confidence,
                rationale=rationale,
                data_mapping=data_mapping,
                performance_score=self._calculate_performance_score(chart_type, analysis.dataset_size)
            ))
        
        # Sort by confidence score
        recommendations.sort(key=lambda x: x.confidence_score, reverse=True)
        return recommendations
    
    def _calculate_data_fit_score(self, chart_type: str, analysis: DataAnalysisResult) -> float:
        """Calculate how well the chart type fits the data"""
        score = 0.0
        
        # Get variable information
        has_temporal = any(vt.data_type == "temporal" for vt in analysis.variable_types.values())
        has_numeric = any(vt.data_type == "continuous" for vt in analysis.variable_types.values())
        has_categorical = any(vt.data_type == "categorical" for vt in analysis.variable_types.values())
        
        # Chart-specific scoring
        if chart_type in ['line_chart', 'area_chart'] and has_temporal:
            score += 0.2
        elif chart_type in ['bar_chart', 'column_chart'] and has_categorical and has_numeric:
            score += 0.2
        elif chart_type == 'scatter_plot' and len([vt for vt in analysis.variable_types.values() if vt.data_type == "continuous"]) >= 2:
            score += 0.2
        elif chart_type in ['pie_chart', 'donut_chart'] and has_categorical and not has_temporal:
            score += 0.1
        
        return score
    
    def _calculate_preference_score(self, chart_type: str, preferences: UserPreferences) -> float:
        """Calculate score based on user preferences"""
        score = 0.0
        
        # Style preferences
        if preferences.preferred_style == 'modern':
            if chart_type in ['area_chart', 'scatter_plot', 'heatmap']:
                score += 0.05
        elif preferences.preferred_style == 'classic':
            if chart_type in ['bar_chart', 'line_chart', 'pie_chart']:
                score += 0.05
        
        # Performance preferences
        if preferences.performance_priority == 'high':
            if chart_type in ['bar_chart', 'line_chart']:
                score += 0.05
        
        return score
    
    def _calculate_performance_score(self, chart_type: str, dataset_size: int) -> float:
        """Calculate performance score based on dataset size"""
        if dataset_size < 1000:
            return 0.05  # All charts perform well
        elif dataset_size < 10000:
            # Some charts better for medium datasets
            if chart_type in ['line_chart', 'area_chart', 'bar_chart']:
                return 0.03
            else:
                return 0.01
        else:
            # Large datasets - favor simple charts
            if chart_type in ['line_chart', 'bar_chart']:
                return 0.02
            else:
                return -0.05  # Penalty for complex charts
    
    def _generate_rationale(self, chart_type: str, analysis: DataAnalysisResult) -> str:
        """Generate rationale for chart selection"""
        rationales = {
            'line_chart': "Ideal for showing trends over time or continuous data relationships",
            'bar_chart': "Perfect for comparing categories or discrete values",
            'scatter_plot': "Best for exploring relationships between two continuous variables",
            'pie_chart': "Good for showing proportions of a whole with few categories",
            'area_chart': "Effective for showing cumulative totals over time",
            'histogram': "Ideal for showing distribution of a single continuous variable",
            'box_plot': "Great for showing distribution summary and outliers",
            'heatmap': "Excellent for showing correlation patterns in multi-dimensional data"
        }
        
        base_rationale = rationales.get(chart_type, f"Good choice for this type of {chart_type} visualization")
        
        # Add data-specific context
        if analysis.dataset_size > 10000:
            base_rationale += f" (optimized for large dataset of {analysis.dataset_size:,} points)"
        
        return base_rationale
    
    def _create_data_mapping(self, chart_type: str, analysis: DataAnalysisResult) -> Dict[str, str]:
        """Create data mapping for the chart"""
        mapping = {}
        
        # Use the dimensionality information to map variables
        if analysis.dimensionality.x_variable:
            mapping['x'] = analysis.dimensionality.x_variable
        if analysis.dimensionality.y_variable:
            mapping['y'] = analysis.dimensionality.y_variable
        if analysis.dimensionality.primary_variable:
            mapping['primary'] = analysis.dimensionality.primary_variable
        
        # Chart-specific mappings
        if chart_type in ['pie_chart', 'donut_chart']:
            # Find categorical variable for labels and numeric for values
            categorical_var = next((col for col, vt in analysis.variable_types.items() if vt.data_type == "categorical"), None)
            numeric_var = next((col for col, vt in analysis.variable_types.items() if vt.data_type == "continuous"), None)
            
            if categorical_var:
                mapping['labels'] = categorical_var
            if numeric_var:
                mapping['values'] = numeric_var
        
        return mapping
    
    def _estimate_render_time(self, chart_type: str, dataset_size: int) -> str:
        """Estimate rendering time for the chart"""
        base_times = {
            'bar_chart': 0.1,
            'line_chart': 0.05,
            'scatter_plot': 0.2,
            'pie_chart': 0.05,
            'heatmap': 0.3,
            'histogram': 0.1
        }
        
        base_time = base_times.get(chart_type, 0.15)
        
        if dataset_size < 1000:
            multiplier = 1.0
        elif dataset_size < 10000:
            multiplier = 2.0
        else:
            multiplier = 4.0
        
        estimated_seconds = base_time * multiplier
        
        if estimated_seconds < 1:
            return "< 1 second"
        elif estimated_seconds < 5:
            return f"~{estimated_seconds:.0f} seconds"
        else:
            return f"~{estimated_seconds:.0f} seconds (consider data sampling)"
    
    def _get_fallback_chart(self) -> ChartRecommendation:
        """Return a fallback chart recommendation"""
        return ChartRecommendation(
            chart_type="bar_chart",
            confidence_score=0.5,
            rationale="Fallback recommendation - bar charts work for most data types",
            data_mapping={"x": "auto", "y": "auto"}
        ) 
"""
Plotly Chart Performance Optimizer

Optimizes Plotly chart configurations for performance based on dataset size
and chart complexity.
"""

from typing import Dict, Any, Optional
from .types import PlotlyConfig, RenderOptions

class PlotlyOptimizer:
    """Optimizes Plotly configurations for performance"""
    
    def __init__(self):
        self.optimization_thresholds = {
            'large_dataset': 10000,
            'very_large_dataset': 50000,
            'webgl_threshold': 5000
        }
    
    async def optimize(self, config: PlotlyConfig, performance_requirements: Optional[RenderOptions] = None) -> PlotlyConfig:
        """
        Optimize Plotly configuration for performance
        
        Args:
            config: Base Plotly configuration
            performance_requirements: Performance optimization settings
            
        Returns:
            Optimized Plotly configuration
        """
        optimized_config = config.copy()
        
        # Estimate data size
        data_size = self._estimate_data_size(config)
        
        # Apply size-based optimizations
        if data_size > self.optimization_thresholds['very_large_dataset']:
            optimized_config = self._apply_very_large_dataset_optimizations(optimized_config)
        elif data_size > self.optimization_thresholds['large_dataset']:
            optimized_config = self._apply_large_dataset_optimizations(optimized_config)
        
        # Apply chart-type specific optimizations
        optimized_config = self._apply_chart_type_optimizations(optimized_config, data_size)
        
        # Apply performance requirements
        if performance_requirements:
            optimized_config = self._apply_performance_requirements(optimized_config, performance_requirements)
        
        return optimized_config
    
    def _estimate_data_size(self, config: PlotlyConfig) -> int:
        """Estimate the total number of data points in the configuration"""
        total_points = 0
        
        if isinstance(config.get('data'), list):
            for trace in config['data']:
                if isinstance(trace, dict):
                    # Count points in x and y arrays
                    x_len = len(trace.get('x', []))
                    y_len = len(trace.get('y', []))
                    total_points += max(x_len, y_len)
        
        return total_points
    
    def _apply_large_dataset_optimizations(self, config: PlotlyConfig) -> PlotlyConfig:
        """Apply optimizations for large datasets (10K-50K points)"""
        # Reduce marker size for scatter plots
        if config.get('type') == 'scatter':
            if 'marker' not in config:
                config['marker'] = {}
            config['marker']['size'] = 2
        
        # Disable hover for performance
        config['hoverinfo'] = 'skip'
        
        # Use WebGL for eligible chart types
        if config.get('type') == 'scatter':
            config['type'] = 'scattergl'
        
        return config
    
    def _apply_very_large_dataset_optimizations(self, config: PlotlyConfig) -> PlotlyConfig:
        """Apply aggressive optimizations for very large datasets (>50K points)"""
        # Apply large dataset optimizations first
        config = self._apply_large_dataset_optimizations(config)
        
        # Disable animations
        if 'layout' not in config:
            config['layout'] = {}
        config['layout']['transition'] = {'duration': 0}
        
        # Further reduce visual elements
        if config.get('type') in ['scatter', 'scattergl']:
            if 'marker' not in config:
                config['marker'] = {}
            config['marker']['size'] = 1
            config['marker']['opacity'] = 0.6
        
        # Sample data if necessary (basic implementation)
        config = self._sample_data_if_needed(config)
        
        return config
    
    def _apply_chart_type_optimizations(self, config: PlotlyConfig, data_size: int) -> PlotlyConfig:
        """Apply chart-type specific performance optimizations"""
        chart_type = config.get('type', 'scatter')
        
        if chart_type == 'scatter' and data_size > self.optimization_thresholds['webgl_threshold']:
            # Use WebGL for large scatter plots
            config['type'] = 'scattergl'
        
        elif chart_type == 'line' and data_size > self.optimization_thresholds['large_dataset']:
            # Simplify line charts
            config['line'] = config.get('line', {})
            config['line']['simplify'] = True
        
        return config
    
    def _apply_performance_requirements(self, config: PlotlyConfig, requirements: RenderOptions) -> PlotlyConfig:
        """Apply specific performance requirements"""
        if requirements.get('enableStreaming'):
            # Configure for streaming data
            config['streaming'] = {
                'maxpoints': 1000,
                'token': 'streaming_token'
            }
        
        if requirements.get('responsiveMode'):
            # Enable responsive mode
            if 'layout' not in config:
                config['layout'] = {}
            config['layout']['responsive'] = True
        
        return config
    
    def _sample_data_if_needed(self, config: PlotlyConfig) -> PlotlyConfig:
        """Sample data if dataset is too large (basic implementation)"""
        # This is a basic implementation - in production you'd want more sophisticated sampling
        max_points = 10000
        
        if isinstance(config.get('data'), list):
            for i, trace in enumerate(config['data']):
                if isinstance(trace, dict):
                    x_data = trace.get('x', [])
                    y_data = trace.get('y', [])
                    
                    if len(x_data) > max_points:
                        # Simple systematic sampling
                        step = len(x_data) // max_points
                        config['data'][i]['x'] = x_data[::step]
                        if y_data:
                            config['data'][i]['y'] = y_data[::step]
        
        return config
    
    def get_performance_profile(self) -> Dict[str, Any]:
        """Get performance optimization profile"""
        return {
            'optimization_applied': True,
            'thresholds': self.optimization_thresholds,
            'optimizations': [
                'webgl_rendering',
                'marker_size_reduction',
                'hover_disable',
                'animation_disable',
                'data_sampling'
            ]
        } 
"""
Plotly Configuration Generator for Autonomous Graphing System

Generates optimized Plotly.js configurations based on chart selection
and data characteristics, including performance optimizations.
"""

import logging
import time
from typing import Dict, List, Any, Optional
from .types import (
    ChartType, PlotlyConfig, VisualizationDataset, 
    ChartRecommendation, RenderOptions
)

# Use the same chart generation logger
chart_logger = logging.getLogger('chart_generation')

class PlotlyConfigGenerator:
    """Generates Plotly.js configurations for different chart types"""
    
    def __init__(self):
        self.color_palettes = {
            'default': ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd'],
            'categorical': ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', 
                          '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf'],
            'sequential': ['#08519c', '#3182bd', '#6baed6', '#9ecae1', '#c6dbef'],
            'diverging': ['#d73027', '#f46d43', '#fdae61', '#fee08b', '#ffffbf']
        }
    
    async def generate_config(self, chart_type: ChartType, dataset: VisualizationDataset, 
                            recommendation: ChartRecommendation, 
                            customizations: Dict[str, Any] = None,
                            session_id: str = None) -> PlotlyConfig:
        """Generate complete Plotly configuration"""
        
        session_id = session_id or f"generator_{int(time.time())}"
        start_time = time.time()
        
        if customizations is None:
            customizations = {}
        
        chart_logger.info(f"[{session_id}] Starting Plotly config generation for {chart_type}")
        chart_logger.info(f"[{session_id}] Dataset: {len(dataset.data)} rows, {len(dataset.columns)} columns")
        chart_logger.debug(f"[{session_id}] Customizations: {customizations}")
        
        try:
            # Generate chart-specific configuration
            config_generator = getattr(self, f'_generate_{chart_type}_config', None)
            if not config_generator:
                chart_logger.error(f"[{session_id}] Unsupported chart type: {chart_type}")
                raise ValueError(f"Unsupported chart type: {chart_type}")
            
            chart_logger.info(f"[{session_id}] Step 1: Generating {chart_type}-specific configuration...")
            config = await config_generator(dataset, recommendation, customizations, session_id)
            chart_logger.info(f"[{session_id}] Chart-specific config generated successfully")
            
            # Apply common optimizations
            chart_logger.info(f"[{session_id}] Step 2: Applying common optimizations...")
            config = self._apply_common_optimizations(config, dataset)
            
            # Apply custom styling
            chart_logger.info(f"[{session_id}] Step 3: Applying custom styling...")
            config = self._apply_custom_styling(config, customizations)
            
            generation_time = time.time() - start_time
            chart_logger.info(f"[{session_id}] Plotly config generation completed in {generation_time:.2f}s")
            chart_logger.debug(f"[{session_id}] Generated config type: {config.type}")
            
            return config
            
        except Exception as e:
            chart_logger.error(f"[{session_id}] Error in config generation: {str(e)}")
            chart_logger.exception(f"[{session_id}] Full error traceback:")
            raise
    
    async def _generate_scatter_config(self, dataset: VisualizationDataset, 
                                     recommendation: ChartRecommendation,
                                     customizations: Dict[str, Any],
                                     session_id: str = None) -> PlotlyConfig:
        """Generate scatter plot configuration"""
        
        data_mapping = recommendation.data_mapping
        df = dataset.data
        
        # Extract x and y data
        x_col = data_mapping.get('x', df.columns[0])
        y_col = data_mapping.get('y', df.columns[1] if len(df.columns) > 1 else df.columns[0])
        
        x_data = df[x_col].tolist()
        y_data = df[y_col].tolist()
        
        # Optional color and size mapping
        color_col = data_mapping.get('color')
        size_col = data_mapping.get('size')
        
        trace = {
            'x': x_data,
            'y': y_data,
            'mode': 'markers',
            'type': 'scatter',
            'name': f'{y_col} vs {x_col}',
            'marker': {
                'size': 8,
                'color': self.color_palettes['default'][0],
                'opacity': 0.7
            }
        }
        
        # Add color mapping if specified
        if color_col and color_col in df.columns:
            color_data = df[color_col].tolist()
            trace['marker']['color'] = color_data
            trace['marker']['colorbar'] = {'title': color_col}
            trace['marker']['showscale'] = True
        
        # Add size mapping if specified
        if size_col and size_col in df.columns:
            size_data = df[size_col].tolist()
            # Normalize sizes to reasonable range
            min_size, max_size = min(size_data), max(size_data)
            if max_size > min_size:
                normalized_sizes = [
                    5 + 15 * (s - min_size) / (max_size - min_size) 
                    for s in size_data
                ]
            else:
                normalized_sizes = [10] * len(size_data)
            trace['marker']['size'] = normalized_sizes
        
        layout = {
            'title': customizations.get('title', f'{y_col} vs {x_col}'),
            'xaxis': {'title': x_col},
            'yaxis': {'title': y_col},
            'hovermode': 'closest',
            'showlegend': bool(color_col)
        }
        
        config = {
            'responsive': True,
            'displayModeBar': True,
            'modeBarButtonsToRemove': ['pan2d', 'lasso2d']
        }
        
        return PlotlyConfig(
            data=[trace],
            layout=layout,
            config=config,
            type='scatter'
        )
    
    async def _generate_line_config(self, dataset: VisualizationDataset,
                                  recommendation: ChartRecommendation,
                                  customizations: Dict[str, Any],
                                  session_id: str = None) -> PlotlyConfig:
        """Generate line chart configuration"""
        
        data_mapping = recommendation.data_mapping
        df = dataset.data
        
        x_col = data_mapping.get('x', df.columns[0])
        y_col = data_mapping.get('y', df.columns[1] if len(df.columns) > 1 else df.columns[0])
        
        # Sort by x-axis for proper line visualization
        df_sorted = df.sort_values(x_col)
        
        trace = {
            'x': df_sorted[x_col].tolist(),
            'y': df_sorted[y_col].tolist(),
            'mode': 'lines+markers',
            'type': 'scatter',
            'name': y_col,
            'line': {
                'color': self.color_palettes['default'][0],
                'width': 2
            },
            'marker': {
                'size': 6,
                'color': self.color_palettes['default'][0]
            }
        }
        
        layout = {
            'title': customizations.get('title', f'{y_col} over {x_col}'),
            'xaxis': {'title': x_col},
            'yaxis': {'title': y_col},
            'hovermode': 'x unified'
        }
        
        config = {
            'responsive': True,
            'displayModeBar': True,
            'modeBarButtonsToRemove': ['pan2d', 'lasso2d']
        }
        
        return PlotlyConfig(
            data=[trace],
            layout=layout,
            config=config,
            type='line'
        )
    
    async def _generate_bar_config(self, dataset: VisualizationDataset,
                                 recommendation: ChartRecommendation,
                                 customizations: Dict[str, Any],
                                 session_id: str = None) -> PlotlyConfig:
        """Generate bar chart configuration"""
        
        data_mapping = recommendation.data_mapping
        df = dataset.data
        
        x_col = data_mapping.get('x', df.columns[0])
        y_col = data_mapping.get('y', df.columns[1] if len(df.columns) > 1 else df.columns[0])
        
        # Group by x column and aggregate y values if needed
        if df[x_col].dtype in ['object', 'category']:
            grouped = df.groupby(x_col)[y_col].sum().reset_index()
            x_data = grouped[x_col].tolist()
            y_data = grouped[y_col].tolist()
        else:
            x_data = df[x_col].tolist()
            y_data = df[y_col].tolist()
        
        trace = {
            'x': x_data,
            'y': y_data,
            'type': 'bar',
            'name': y_col,
            'marker': {
                'color': self.color_palettes['categorical'][:len(x_data)],
                'opacity': 0.8
            }
        }
        
        layout = {
            'title': customizations.get('title', f'{y_col} by {x_col}'),
            'xaxis': {'title': x_col},
            'yaxis': {'title': y_col},
            'hovermode': 'x'
        }
        
        config = {
            'responsive': True,
            'displayModeBar': True
        }
        
        return PlotlyConfig(
            data=[trace],
            layout=layout,
            config=config,
            type='bar'
        )
    
    async def _generate_histogram_config(self, dataset: VisualizationDataset,
                                       recommendation: ChartRecommendation,
                                       customizations: Dict[str, Any],
                                       session_id: str = None) -> PlotlyConfig:
        """Generate histogram configuration"""
        
        data_mapping = recommendation.data_mapping
        df = dataset.data
        
        x_col = data_mapping.get('x', df.columns[0])
        x_data = df[x_col].dropna().tolist()
        
        trace = {
            'x': x_data,
            'type': 'histogram',
            'name': f'{x_col} Distribution',
            'marker': {
                'color': self.color_palettes['default'][0],
                'opacity': 0.7
            },
            'nbinsx': min(50, max(10, len(x_data) // 20))  # Auto bin count
        }
        
        layout = {
            'title': customizations.get('title', f'Distribution of {x_col}'),
            'xaxis': {'title': x_col},
            'yaxis': {'title': 'Frequency'},
            'hovermode': 'x'
        }
        
        config = {
            'responsive': True,
            'displayModeBar': True
        }
        
        return PlotlyConfig(
            data=[trace],
            layout=layout,
            config=config,
            type='histogram'
        )
    
    async def _generate_pie_config(self, dataset: VisualizationDataset,
                                 recommendation: ChartRecommendation,
                                 customizations: Dict[str, Any],
                                 session_id: str = None) -> PlotlyConfig:
        """Generate pie chart configuration"""
        
        data_mapping = recommendation.data_mapping
        df = dataset.data
        
        labels_col = data_mapping.get('labels', df.columns[0])
        values_col = data_mapping.get('values')
        
        if values_col and values_col in df.columns:
            # Use specified values column
            grouped = df.groupby(labels_col)[values_col].sum().reset_index()
            labels = grouped[labels_col].tolist()
            values = grouped[values_col].tolist()
        else:
            # Use count of categories
            value_counts = df[labels_col].value_counts()
            labels = value_counts.index.tolist()
            values = value_counts.values.tolist()
        
        trace = {
            'labels': labels,
            'values': values,
            'type': 'pie',
            'name': labels_col,
            'marker': {
                'colors': self.color_palettes['categorical'][:len(labels)]
            },
            'textinfo': 'label+percent',
            'textposition': 'auto'
        }
        
        layout = {
            'title': customizations.get('title', f'{labels_col} Distribution'),
            'showlegend': True
        }
        
        config = {
            'responsive': True,
            'displayModeBar': True
        }
        
        return PlotlyConfig(
            data=[trace],
            layout=layout,
            config=config,
            type='pie'
        )
    
    async def _generate_box_config(self, dataset: VisualizationDataset,
                                 recommendation: ChartRecommendation,
                                 customizations: Dict[str, Any],
                                 session_id: str = None) -> PlotlyConfig:
        """Generate box plot configuration"""
        
        data_mapping = recommendation.data_mapping
        df = dataset.data
        
        y_col = data_mapping.get('y', df.columns[0])
        x_col = data_mapping.get('x')  # Optional grouping variable
        
        if x_col and x_col in df.columns:
            # Grouped box plot
            traces = []
            for group in df[x_col].unique():
                group_data = df[df[x_col] == group][y_col].dropna().tolist()
                if group_data:  # Only add if there's data
                    trace = {
                        'y': group_data,
                        'type': 'box',
                        'name': str(group),
                        'boxpoints': 'outliers'
                    }
                    traces.append(trace)
            
            layout = {
                'title': customizations.get('title', f'{y_col} by {x_col}'),
                'xaxis': {'title': x_col},
                'yaxis': {'title': y_col},
                'boxmode': 'group'
            }
        else:
            # Single box plot
            traces = [{
                'y': df[y_col].dropna().tolist(),
                'type': 'box',
                'name': y_col,
                'boxpoints': 'outliers'
            }]
            
            layout = {
                'title': customizations.get('title', f'{y_col} Distribution'),
                'yaxis': {'title': y_col}
            }
        
        config = {
            'responsive': True,
            'displayModeBar': True
        }
        
        return PlotlyConfig(
            data=traces,
            layout=layout,
            config=config,
            type='box_plot'
        )

    async def _generate_heatmap_config(self, dataset: VisualizationDataset,
                                     recommendation: ChartRecommendation,
                                     customizations: Dict[str, Any],
                                     session_id: str = None) -> PlotlyConfig:
        """Generate heatmap configuration"""
        
        data_mapping = recommendation.data_mapping
        df = dataset.data
        
        # For heatmap, we need numeric columns
        import numpy as np
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        
        if len(numeric_cols) < 2:
            # Fallback to bar chart if not enough numeric data
            chart_logger.warning(f"Not enough numeric columns for heatmap, falling back to bar chart")
            return await self._generate_bar_config(dataset, recommendation, customizations)
        
        # Use correlation matrix for heatmap
        corr_matrix = df[numeric_cols].corr()
        
        trace = {
            'z': corr_matrix.values.tolist(),
            'x': corr_matrix.columns.tolist(),
            'y': corr_matrix.index.tolist(),
            'type': 'heatmap',
            'colorscale': 'RdBu',
            'zmid': 0,
            'showscale': True,
            'hovertemplate': '<b>%{x}</b> vs <b>%{y}</b><br>Correlation: %{z:.2f}<extra></extra>'
        }
        
        layout = {
            'title': customizations.get('title', 'Correlation Heatmap'),
            'xaxis': {'title': 'Variables', 'side': 'bottom'},
            'yaxis': {'title': 'Variables'},
            'height': max(400, len(numeric_cols) * 40),
            'width': max(400, len(numeric_cols) * 40)
        }
        
        config = {
            'responsive': True,
            'displayModeBar': True,
            'modeBarButtonsToRemove': ['pan2d', 'lasso2d']
        }
        
        return PlotlyConfig(
            data=[trace],
            layout=layout,
            config=config,
            type='heatmap'
        )
    
    def _apply_common_optimizations(self, config: PlotlyConfig, dataset: VisualizationDataset) -> PlotlyConfig:
        """Apply performance optimizations based on dataset size"""
        
        data_size = len(dataset.data)
        
        # Large dataset optimizations
        if data_size > 10000:
            # Reduce marker size for scatter plots
            for trace in config.data:
                if trace.get('type') == 'scatter' and 'marker' in trace:
                    trace['marker']['size'] = max(2, trace['marker'].get('size', 8) // 2)
            
            # Disable hover for very large datasets
            if data_size > 50000:
                config.layout['hovermode'] = False
                for trace in config.data:
                    trace['hoverinfo'] = 'skip'
        
        # Memory optimization
        config.config['staticPlot'] = data_size > 100000
        
        # Performance mode flag
        config.performance_mode = data_size > 10000
        
        return config
    
    def _apply_custom_styling(self, config: PlotlyConfig, customizations: Dict[str, Any]) -> PlotlyConfig:
        """Apply custom styling options"""
        
        # Title customization
        if 'title' in customizations:
            config.layout['title'] = customizations['title']
        
        # Color scheme customization
        if 'color_scheme' in customizations:
            color_scheme = customizations['color_scheme']
            if color_scheme in self.color_palettes:
                colors = self.color_palettes[color_scheme]
                
                for i, trace in enumerate(config.data):
                    if 'marker' in trace:
                        if isinstance(trace['marker'].get('color'), str):
                            trace['marker']['color'] = colors[i % len(colors)]
                    elif 'line' in trace:
                        trace['line']['color'] = colors[i % len(colors)]
        
        # Theme customization
        if 'theme' in customizations:
            theme = customizations['theme']
            if theme == 'dark':
                config.layout.update({
                    'paper_bgcolor': '#2d3748',
                    'plot_bgcolor': '#2d3748',
                    'font': {'color': '#f7fafc'}
                })
                
                # Update axis colors
                for axis in ['xaxis', 'yaxis']:
                    if axis in config.layout:
                        config.layout[axis].update({
                            'gridcolor': '#4a5568',
                            'linecolor': '#4a5568',
                            'tickcolor': '#4a5568'
                        })
        
        # Size customization
        if 'width' in customizations:
            config.layout['width'] = customizations['width']
        if 'height' in customizations:
            config.layout['height'] = customizations['height']
        
        return config


class PlotlyOptimizer:
    """Optimizes Plotly configurations for performance"""
    
    @staticmethod
    def optimize_for_performance(config: PlotlyConfig, options: RenderOptions) -> PlotlyConfig:
        """Apply performance optimizations"""
        
        # Data sampling for very large datasets
        if len(config.data[0].get('x', [])) > 50000:
            config = PlotlyOptimizer._apply_data_sampling(config, max_points=10000)
        
        # WebGL acceleration for large scatter plots
        for trace in config.data:
            if (trace.get('type') == 'scatter' and 
                len(trace.get('x', [])) > 5000):
                trace['type'] = 'scattergl'
        
        # Disable animations for performance
        if options.performance_mode:
            config.config['animation'] = False
            config.layout['transition'] = {'duration': 0}
        
        return config
    
    @staticmethod
    def _apply_data_sampling(config: PlotlyConfig, max_points: int) -> PlotlyConfig:
        """Sample data to reduce size while preserving distribution"""
        
        for trace in config.data:
            if 'x' in trace and 'y' in trace:
                x_data = trace['x']
                y_data = trace['y']
                
                if len(x_data) > max_points:
                    # Simple random sampling (could be improved with statistical sampling)
                    import random
                    indices = random.sample(range(len(x_data)), max_points)
                    indices.sort()
                    
                    trace['x'] = [x_data[i] for i in indices]
                    trace['y'] = [y_data[i] for i in indices]
                    
                    # Handle other data arrays
                    for key in ['marker', 'line']:
                        if key in trace and isinstance(trace[key], dict):
                            for subkey, subvalue in trace[key].items():
                                if isinstance(subvalue, list) and len(subvalue) == len(x_data):
                                    trace[key][subkey] = [subvalue[i] for i in indices]
        
        return config 
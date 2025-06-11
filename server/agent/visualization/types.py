"""
Type definitions for the visualization system
"""

from typing import Dict, List, Optional, Any, Union, Literal
from dataclasses import dataclass
from datetime import datetime
import numpy as np
import pandas as pd

# Chart types supported by the system
ChartType = Literal[
    'scatter', 'line', 'bar', 'histogram', 'box_plot', 'violin_plot',
    'pie', 'donut', 'heatmap', 'area', 'candlestick', 'parallel_coordinates',
    'radar', 'treemap', 'sankey', 'scatter_3d', 'surface'
]

# Data types for analysis
DataType = Literal['continuous', 'categorical', 'temporal', 'text', 'boolean']

# Variable roles in visualization
VariableRole = Literal['x_axis', 'y_axis', 'color', 'size', 'grouping', 'filter']

@dataclass
class VariableClassification:
    """Classification of a dataset variable"""
    data_type: DataType
    role: VariableRole
    cardinality: int
    distribution: Dict[str, Any]
    null_percentage: float

@dataclass
class DatasetDimensionality:
    """Dimensionality analysis of dataset"""
    variable_count: int
    row_count: int
    primary_variable: Optional[str]
    x_variable: Optional[str] 
    y_variable: Optional[str]
    grouping_variables: List[str]
    temporal_variables: List[str]
    
    @property
    def has_temporal(self) -> bool:
        """Check if dataset has temporal variables"""
        return len(self.temporal_variables) > 0
    
    @property
    def has_continuous(self) -> bool:
        """Check if dataset has continuous variables"""
        # This will be set by the analyzer when creating the dimensionality
        return hasattr(self, '_has_continuous') and self._has_continuous
    
    @property
    def has_categorical(self) -> bool:
        """Check if dataset has categorical variables"""
        # This will be set by the analyzer when creating the dimensionality
        return hasattr(self, '_has_categorical') and self._has_categorical

@dataclass
class StatisticalSummary:
    """Statistical summary of dataset"""
    correlations: Dict[str, Dict[str, float]]
    distributions: Dict[str, Dict[str, Any]]
    outliers: Dict[str, List[int]]
    trends: Dict[str, Dict[str, Any]]
    missing_data: Dict[str, float]

@dataclass
class VisualizationDataset:
    """Container for data to be visualized"""
    data: pd.DataFrame
    columns: List[str]
    metadata: Dict[str, Any]
    source_info: Dict[str, Any]
    
    @property
    def size(self) -> int:
        return len(self.data)

    def merge(self, other: 'VisualizationDataset') -> None:
        """Merge another dataset into this one"""
        self.data = pd.concat([self.data, other.data], ignore_index=True)
        self.columns.extend([col for col in other.columns if col not in self.columns])
        self.metadata.update(other.metadata)
        self.source_info.update(other.source_info)

@dataclass
class UserPreferences:
    """User preferences for visualization"""
    preferred_style: str = 'modern'  # modern, classic, minimal
    performance_priority: str = 'medium'  # low, medium, high
    interactivity_level: str = 'medium'  # low, medium, high

@dataclass 
class VariableType:
    """Information about a variable in the dataset"""
    data_type: str  # continuous, categorical, temporal, text
    role: str  # dimension, measure, identifier
    cardinality: int
    distribution: str

@dataclass
class Dimensionality:
    """Information about dataset dimensions"""
    variable_count: int
    primary_variable: Optional[str] = None
    x_variable: Optional[str] = None
    y_variable: Optional[str] = None

@dataclass
class DataAnalysisResult:
    """Result of data analysis for visualization"""
    dataset_size: int
    variable_types: Dict[str, VariableType]
    dimensionality: Dimensionality
    recommendations: str
    statistical_summary: Optional[Dict[str, Any]] = None
    semantic_insights: Optional[str] = None

@dataclass
class ChartRecommendation:
    """A chart recommendation with rationale"""
    chart_type: str
    confidence_score: float
    rationale: str
    data_mapping: Dict[str, str]
    performance_score: Optional[float] = None

@dataclass
class ChartSelection:
    """Result of chart selection process"""
    primary_chart: ChartRecommendation
    alternatives: List[ChartRecommendation]
    rationale: str
    performance_considerations: Optional[Dict[str, Any]] = None

@dataclass
class PlotlyConfig:
    """Plotly chart configuration"""
    data: List[Dict[str, Any]]
    layout: Dict[str, Any]
    config: Dict[str, Any]
    type: ChartType
    performance_mode: bool = False

@dataclass
class RenderOptions:
    """Chart rendering options"""
    width: int = 800
    height: int = 600
    enable_streaming: bool = False
    performance_mode: bool = False
    interactive: bool = True
    export_format: Literal['png', 'svg', 'webp', 'pdf'] = 'png'

@dataclass
class PerformanceMetrics:
    """Chart rendering performance metrics"""
    data_processing_time: float
    chart_generation_time: float
    rendering_time: float
    memory_usage: float
    bundle_size: int

# Request/Response types for API
@dataclass
class VisualizationAnalysisRequest:
    """Request for visualization analysis"""
    dataset: VisualizationDataset
    user_intent: str
    preferences: Dict[str, Any]

@dataclass
class VisualizationAnalysisResponse:
    """Response from visualization analysis"""
    analysis: DataAnalysisResult
    recommendations: ChartSelection
    estimated_render_time: float

@dataclass
class ChartGenerationRequest:
    """Request for chart generation"""
    chart_type: ChartType
    data: VisualizationDataset
    customizations: Dict[str, Any]
    performance_requirements: Dict[str, Any]

@dataclass
class ChartGenerationResponse:
    """Response from chart generation"""
    config: PlotlyConfig
    performance_profile: PerformanceMetrics
    alternative_configs: List[PlotlyConfig] 
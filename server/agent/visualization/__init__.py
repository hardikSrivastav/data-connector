"""
Autonomous Visualization Module

This module provides intelligent chart selection and configuration
capabilities for the Data Connector platform.
"""

from .types import VisualizationDataset, UserPreferences, ChartRecommendation
from .analyzer import DataAnalysisModule
from .selector import ChartSelectionEngine

__all__ = [
    'VisualizationDataset',
    'UserPreferences', 
    'ChartRecommendation',
    'DataAnalysisModule',
    'ChartSelectionEngine'
] 
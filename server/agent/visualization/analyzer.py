"""
Data Analysis Module for Visualization

Analyzes datasets to determine optimal visualization characteristics
"""
import logging
import pandas as pd
from typing import Dict, Any, Optional
from .types import (
    VisualizationDataset, DataAnalysisResult, VariableType, 
    DatasetDimensionality, VariableClassification
)

logger = logging.getLogger(__name__)

class DataAnalysisModule:
    """Analyzes datasets to determine visualization characteristics"""
    
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
    
    async def analyze_dataset(self, dataset: VisualizationDataset, user_intent: str, session_id: str = "default") -> DataAnalysisResult:
        """
        Comprehensive dataset analysis for visualization selection
        
        Args:
            dataset: The dataset to analyze
            user_intent: User's visualization intent/question
            session_id: Session identifier for logging
            
        Returns:
            DataAnalysisResult containing analysis insights
        """
        self.logger.info(f"[{session_id}] Starting dataset analysis for user intent: '{user_intent}'")
        self.logger.info(f"[{session_id}] Dataset info: {len(dataset.data)} rows, {len(dataset.columns)} columns")
        self.logger.debug(f"[{session_id}] Columns: {dataset.columns}")
        self.logger.debug(f"[{session_id}] Sample data (first 2 rows):\n{dataset.data.head(2)}")
        
        try:
            # Step 1: Basic statistical analysis
            self.logger.info(f"[{session_id}] Step 1: Computing statistical analysis...")
            stats = self._compute_basic_statistics(dataset, session_id)
            
            # Step 2: Variable type classification
            self.logger.info(f"[{session_id}] Step 2: Classifying variables...")
            variable_types = self._classify_variables(dataset, stats, session_id)
            
            # Step 3: Dimensionality assessment
            self.logger.info(f"[{session_id}] Step 3: Assessing dimensionality...")
            dimensionality = self._assess_dimensionality(dataset, variable_types, session_id)
            
            # Step 4: LLM semantic analysis (if available)
            self.logger.info(f"[{session_id}] Step 4: Running LLM semantic analysis...")
            semantic_insights = await self._llm_semantic_analysis(dataset, user_intent, session_id)
            
            # Step 5: Generate recommendations
            self.logger.info(f"[{session_id}] Step 5: Generating visualization recommendations...")
            recommendations = self._generate_recommendations(stats, variable_types, dimensionality, semantic_insights)
            
            result = DataAnalysisResult(
                dataset_size=len(dataset.data),
                variable_types=variable_types,
                dimensionality=dimensionality,
                recommendations=recommendations,
                statistical_summary=stats,
                semantic_insights=semantic_insights
            )
            
            self.logger.info(f"[{session_id}] Dataset analysis completed successfully")
            self.logger.debug(f"[{session_id}] Result: {result.dataset_size} rows, {len(result.variable_types)} variables")
            return result
            
        except Exception as e:
            self.logger.error(f"[{session_id}] Error in dataset analysis: {str(e)}")
            self.logger.exception(f"[{session_id}] Full error traceback:")
            # Return basic fallback analysis
            return DataAnalysisResult(
                dataset_size=len(dataset.data),
                variable_types={},
                dimensionality=DatasetDimensionality(
                    variable_count=len(dataset.columns),
                    row_count=len(dataset.data),
                    primary_variable=None,
                    x_variable=None,
                    y_variable=None,
                    grouping_variables=[],
                    temporal_variables=[]
                ),
                recommendations="Error analyzing dataset - using default chart recommendations",
                statistical_summary={}
            )
    
    def _compute_basic_statistics(self, dataset: VisualizationDataset, session_id: str) -> Dict[str, Any]:
        """Compute basic statistical summaries"""
        self.logger.info(f"[{session_id}] Starting statistical analysis for dataset with {len(dataset.data)} rows, {len(dataset.columns)} columns")
        
        stats = {
            "row_count": len(dataset.data),
            "column_count": len(dataset.columns),
            "column_types": {},
            "missing_values": {},
            "unique_counts": {}
        }
        
        for i, column in enumerate(dataset.columns, 1):
            self.logger.debug(f"[{session_id}] Analyzing column {i}/{len(dataset.columns)}: {column}")
            if column in dataset.data.columns:
                col_data = dataset.data[column]
                stats["column_types"][column] = str(col_data.dtype)
                stats["missing_values"][column] = col_data.isnull().sum()
                stats["unique_counts"][column] = col_data.nunique()
        
        self.logger.info(f"[{session_id}] Statistical analysis completed in 0.00s")
        return stats
    
    def _classify_variables(self, dataset: VisualizationDataset, stats: Dict[str, Any], session_id: str) -> Dict[str, VariableType]:
        """Classify variables by type and role"""
        self.logger.info(f"[{session_id}] Statistical analysis complete: {stats['row_count']} rows, {stats['column_count']} columns")
        
        classifications = {}
        
        for column in dataset.columns:
            if column not in dataset.data.columns:
                continue
                
            col_data = dataset.data[column]
            
            # Determine data type
            if pd.api.types.is_numeric_dtype(col_data):
                data_type = "continuous"
                role = "measure"
            elif pd.api.types.is_datetime64_any_dtype(col_data):
                data_type = "temporal"
                role = "dimension"
            else:
                # Check if categorical or text
                unique_ratio = col_data.nunique() / len(col_data) if len(col_data) > 0 else 0
                if unique_ratio < 0.5:
                    data_type = "categorical"
                    role = "dimension"
                else:
                    data_type = "text"
                    role = "identifier"
            
            # Calculate null percentage
            null_percentage = (col_data.isnull().sum() / len(col_data)) * 100 if len(col_data) > 0 else 0
            
            # Create classification using VariableClassification
            classifications[column] = VariableClassification(
                data_type=data_type,
                role=role,
                cardinality=col_data.nunique(),
                distribution={'type': 'discrete'},
                null_percentage=null_percentage
            )
        
        self.logger.info(f"[{session_id}] Variable classification complete: {len(classifications)} variables classified")
        self.logger.debug(f"[{session_id}] Variable classifications: {classifications}")
        return classifications
    
    def _assess_dimensionality(self, dataset: VisualizationDataset, variable_types: Dict[str, VariableClassification], session_id: str) -> DatasetDimensionality:
        """Assess the dimensional characteristics of the dataset"""
        
        # Find numeric and categorical variables
        numeric_vars = [col for col, var_type in variable_types.items() if var_type.data_type == "continuous"]
        categorical_vars = [col for col, var_type in variable_types.items() if var_type.data_type == "categorical"]
        temporal_vars = [col for col, var_type in variable_types.items() if var_type.data_type == "temporal"]
        
        # Determine primary variables for visualization
        x_variable = None
        y_variable = None
        primary_variable = None
        
        if temporal_vars:
            x_variable = temporal_vars[0]  # Time usually goes on x-axis
            if numeric_vars:
                y_variable = numeric_vars[0]  # Numeric usually goes on y-axis
        elif categorical_vars and numeric_vars:
            x_variable = categorical_vars[0]
            y_variable = numeric_vars[0]
        elif len(numeric_vars) >= 2:
            x_variable = numeric_vars[0]
            y_variable = numeric_vars[1]
        elif numeric_vars:
            primary_variable = numeric_vars[0]
        elif categorical_vars:
            primary_variable = categorical_vars[0]
        
        # Count meaningful variables (excluding identifiers)
        meaningful_vars = [col for col, var_type in variable_types.items() if var_type.role != "identifier"]
        
        dimensionality = DatasetDimensionality(
            variable_count=len(meaningful_vars),
            row_count=len(dataset.data),
            primary_variable=primary_variable,
            x_variable=x_variable,
            y_variable=y_variable,
            grouping_variables=meaningful_vars,
            temporal_variables=temporal_vars
        )
        
        # Set the computed properties
        dimensionality._has_continuous = len(numeric_vars) > 0
        dimensionality._has_categorical = len(categorical_vars) > 0
        
        self.logger.info(f"[{session_id}] Dimensionality assessment complete: {dimensionality.variable_count} variables")
        self.logger.debug(f"[{session_id}] Dimensionality: {{'variable_count': {dimensionality.variable_count}, 'row_count': {dimensionality.row_count}, 'primary_variable': '{dimensionality.primary_variable}', 'x_variable': {dimensionality.x_variable}, 'y_variable': {dimensionality.y_variable}, 'grouping_variables': {dimensionality.grouping_variables}, 'temporal_variables': {dimensionality.temporal_variables}}}")
        
        return dimensionality
    
    async def _llm_semantic_analysis(self, dataset: VisualizationDataset, user_intent: str, session_id: str) -> str:
        """Perform LLM-based semantic analysis of the dataset"""
        try:
            # Build prompt for LLM analysis
            prompt = f"""Analyze this dataset for visualization purposes:

User Intent: {user_intent}

Dataset Statistics:
- Rows: {len(dataset.data)}
- Columns: {len(dataset.columns)}
- Column Info: {dict(zip(dataset.columns, [str(dataset.data[col].dtype) for col in dataset.columns if col in dataset.data.columns]))}

Sample Data (first 3 rows):
{dataset.data.head(3).to_string()}

Please analyze the semantic meaning of this data and suggest optimal visualization approaches."""

            self.logger.debug(f"[{session_id}] Built LLM prompt: \n{prompt[:200]}...")
            
            # Check if LLM client has the generate method
            if hasattr(self.llm_client, 'generate'):
                response = await self.llm_client.generate(prompt)
                self.logger.info(f"[{session_id}] LLM analysis completed successfully")
                return response
            else:
                self.logger.error(f"[{session_id}] LLM client missing 'generate' method")
                return "LLM analysis unavailable - client does not support generate method"
                
        except Exception as e:
            self.logger.error(f"[{session_id}] Semantic analysis error: {str(e)}")
            return "LLM analysis failed - using rule-based recommendations"
    
    def _generate_recommendations(self, stats: Dict[str, Any], variable_types: Dict[str, VariableClassification], 
                                dimensionality: DatasetDimensionality, semantic_insights: str) -> str:
        """Generate enhanced visualization recommendations"""
        
        recommendations = []
        
        # Analyze variable composition
        numeric_count = sum(1 for vt in variable_types.values() if vt.data_type == "continuous")
        categorical_count = sum(1 for vt in variable_types.values() if vt.data_type == "categorical")
        temporal_count = sum(1 for vt in variable_types.values() if vt.data_type == "temporal")
        
        # Rule-based recommendations
        if dimensionality.has_temporal and numeric_count > 0:
            recommendations.append("Time-series visualization recommended (line chart or area chart)")
        elif categorical_count > 0 and numeric_count > 0:
            recommendations.append("Categorical comparison recommended (bar chart or column chart)")
        elif numeric_count >= 2:
            recommendations.append("Correlation analysis recommended (scatter plot)")
        elif categorical_count > 0:
            recommendations.append("Distribution visualization recommended (pie chart or donut chart)")
        else:
            recommendations.append("Simple distribution chart recommended")
        
        # Data size considerations
        if stats["row_count"] > 10000:
            recommendations.append("Large dataset detected - consider sampling or aggregation for performance")
        elif stats["row_count"] < 50:
            recommendations.append("Small dataset - simple chart types recommended")
        
        # Include LLM insights if available
        if semantic_insights and "LLM analysis failed" not in semantic_insights:
            recommendations.append(f"LLM insights: {semantic_insights[:100]}...")
        
        final_recommendation = "; ".join(recommendations) if recommendations else "Standard chart visualization recommended"
        return final_recommendation 
# Autonomous Graphing System: End-to-End Implementation Guide

## Executive Summary

This document outlines the complete implementation of an autonomous graphing system for the Data Connector platform. The system integrates LLM-powered chart selection with high-performance visualization rendering, providing users with intelligent, real-time data visualization capabilities within the existing canvas-based architecture.

## System Architecture Overview

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────────┐    ┌─────────────────┐
│   User Query    │───▶│  Data Analysis   │───▶│  Chart Selection    │───▶│  Visualization  │
│  (Natural Lang) │    │   & Processing   │    │   Engine (LLM)      │    │   Generation    │
└─────────────────┘    └──────────────────┘    └─────────────────────┘    └─────────────────┘
                              │                          │                          │
                              ▼                          ▼                          ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────────┐    ┌─────────────────┐
│ Cross-Database  │    │ Statistical      │    │ Chart Configuration │    │ Runtime Renderer│
│ Orchestrator    │    │ Analysis Module  │    │ & Data Transform    │    │ (Web Workers)   │
└─────────────────┘    └──────────────────┘    └─────────────────────┘    └─────────────────┘
         │                       │                          │                          │
         ▼                       ▼                          ▼                          ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────────┐    ┌─────────────────┐
│ Multiple Data   │    │ Data Insights &  │    │ Plotly.js Config    │    │ Interactive     │
│ Sources         │    │ Recommendations  │    │ Generation          │    │ Chart Display   │
└─────────────────┘    └──────────────────┘    └─────────────────────┘    └─────────────────┘
```

## Core Components Integration

### 1. Data Flow Architecture

#### 1.1 Query Processing Pipeline

**File References:**
- `server/agent/cmd/query.py` - Entry point for query processing
- `server/agent/cmd/cross_db.py` - Cross-database orchestration
- `server/agent/api/endpoints.py` - API endpoints for data retrieval

**Data Flow Sequence:**
```python
# 1. User submits natural language query through GraphingBlock
user_query = "Show me sales trends by region over the last 6 months"

# 2. Query processing in cmd/query.py
query_processor = QueryProcessor()
parsed_query = await query_processor.analyze_intent(user_query)
# Output: {
#   "intent": "trend_analysis",
#   "entities": ["sales", "region", "time_period"],
#   "time_range": "6_months",
#   "aggregation": "temporal",
#   "data_sources": ["postgres", "mongodb"]
# }

# 3. Cross-database orchestration in cmd/cross_db.py
orchestrator = CrossDatabaseOrchestrator()
execution_plan = await orchestrator.plan_query(parsed_query)
# Output: Multi-step execution plan spanning databases

# 4. Data retrieval via api/endpoints.py
data_results = await orchestrator.execute_plan(execution_plan)
# Output: Normalized dataset ready for visualization
```

#### 1.2 Data Normalization Layer

**Implementation Logic:**
```python
# server/agent/data/normalizer.py (NEW FILE)
class DataNormalizer:
    """Normalizes heterogeneous data for visualization"""
    
    def __init__(self):
        self.type_mappings = {
            'postgres': PostgresTypeMapper(),
            'mongodb': MongoTypeMapper(),
            'qdrant': VectorTypeMapper(),
            'slack': TextTypeMapper()
        }
    
    async def normalize_for_visualization(self, raw_data: dict) -> VisualizationDataset:
        """
        Convert raw database results into visualization-ready format
        
        Input: {
            'postgres': [{'region': 'North', 'sales': 1000, 'date': '2024-01-01'}, ...],
            'mongodb': [{'region': 'South', 'revenue': 1500, 'timestamp': ISODate(...)}]
        }
        
        Output: VisualizationDataset with standardized schema
        """
        normalized_data = VisualizationDataset()
        
        for source, data in raw_data.items():
            mapper = self.type_mappings[source]
            standardized = await mapper.standardize(data)
            normalized_data.merge(standardized)
        
        return normalized_data
```

### 2. GraphingBlock Component Architecture

#### 2.1 BlockEditor Integration

**File Reference:** `server/web/src/components/BlockEditor.tsx`

**Integration Points:**
```typescript
// Addition to BlockEditor.tsx - New block type handling
{block.type === 'graphing' && (
  <GraphingBlock
    block={block}
    onUpdate={onUpdate}
    isFocused={isFocused}
    workspace={workspace}
    page={page}
    onDataQuery={onAIQuery} // Reuse existing AI query infrastructure
    onChartGenerate={handleChartGeneration}
    streamingState={streamingState}
  />
)}

// New command recognition in handleContentChange
else if (currentLine.startsWith('/chart') || currentLine.startsWith('/graph')) {
  const query = currentLine.slice(6); // Remove '/chart' prefix
  setGraphingQuery(query);
  setShowGraphingInterface(true);
  setShowAIQuery(false);
}
```

**GraphingBlock State Management:**
```typescript
// server/web/src/components/GraphingBlock.tsx (NEW FILE)
interface GraphingBlockState {
  mode: 'input' | 'analyzing' | 'generating' | 'display' | 'error';
  userQuery: string;
  dataAnalysis: DataAnalysisResult | null;
  chartConfig: PlotlyConfig | null;
  chartData: ProcessedDataset | null;
  renderingState: 'idle' | 'processing' | 'complete';
  errorMessage?: string;
  suggestions: ChartSuggestion[];
}

const GraphingBlock: React.FC<GraphingBlockProps> = ({
  block, onUpdate, isFocused, onDataQuery, onChartGenerate
}) => {
  const [state, setState] = useState<GraphingBlockState>({
    mode: 'input',
    userQuery: '',
    dataAnalysis: null,
    chartConfig: null,
    chartData: null,
    renderingState: 'idle',
    suggestions: []
  });
  
  // Integration with existing streaming infrastructure
  const { streamingState } = useContext(StreamingContext);
  
  // Chart generation pipeline
  const handleGenerateChart = async (query: string) => {
    setState(prev => ({ ...prev, mode: 'analyzing' }));
    
    try {
      // Step 1: Data analysis using existing AI infrastructure
      const analysisResult = await onDataQuery(
        `analyze_for_visualization: ${query}`, 
        block.id
      );
      
      setState(prev => ({ 
        ...prev, 
        dataAnalysis: analysisResult,
        mode: 'generating' 
      }));
      
      // Step 2: Chart selection and generation
      const chartResult = await generateChart(analysisResult);
      
      setState(prev => ({
        ...prev,
        chartConfig: chartResult.config,
        chartData: chartResult.data,
        mode: 'display',
        renderingState: 'processing'
      }));
      
    } catch (error) {
      setState(prev => ({ 
        ...prev, 
        mode: 'error', 
        errorMessage: error.message 
      }));
    }
  };
  
  return (
    <div className="graphing-block">
      {state.mode === 'input' && (
        <GraphingInput 
          onSubmit={handleGenerateChart}
          suggestions={state.suggestions}
        />
      )}
      
      {state.mode === 'analyzing' && (
        <AnalysisProgress 
          streamingState={streamingState}
          stage="data_analysis"
        />
      )}
      
      {state.mode === 'generating' && (
        <ChartGenerationProgress
          dataAnalysis={state.dataAnalysis}
          stage="chart_selection"
        />
      )}
      
      {state.mode === 'display' && (
        <ChartRenderer
          config={state.chartConfig}
          data={state.chartData}
          renderingState={state.renderingState}
          onRenderComplete={() => setState(prev => ({ 
            ...prev, 
            renderingState: 'complete' 
          }))}
        />
      )}
      
      {state.mode === 'error' && (
        <ErrorDisplay 
          message={state.errorMessage}
          onRetry={() => setState(prev => ({ ...prev, mode: 'input' }))}
        />
      )}
    </div>
  );
};
```

### 3. LLM-Powered Chart Selection Engine

#### 3.1 Analysis and Selection Pipeline

**File Structure:**
```
server/agent/visualization/
├── __init__.py
├── analyzer.py          # Data analysis module
├── selector.py          # Chart selection engine
├── generator.py         # Plotly config generation
├── optimizer.py         # Performance optimization
└── templates/
    ├── analysis.tpl     # Data analysis prompts
    ├── selection.tpl    # Chart selection prompts
    └── optimization.tpl # Performance optimization prompts
```

**Data Analysis Module:**
```python
# server/agent/visualization/analyzer.py
class DataAnalysisModule:
    """Analyzes datasets to determine visualization characteristics"""
    
    def __init__(self, llm_client):
        self.llm_client = llm_client
        self.statistical_analyzer = StatisticalAnalyzer()
    
    async def analyze_dataset(self, dataset: VisualizationDataset, user_intent: str) -> DataAnalysisResult:
        """
        Comprehensive dataset analysis for visualization selection
        
        Returns DataAnalysisResult containing:
        - Data types and distributions
        - Cardinality analysis
        - Temporal patterns
        - Correlation insights
        - Visualization recommendations
        """
        
        # Statistical analysis
        stats = await self.statistical_analyzer.compute_statistics(dataset)
        
        # LLM-based semantic analysis
        analysis_prompt = self._build_analysis_prompt(dataset, user_intent, stats)
        semantic_analysis = await self.llm_client.generate(
            prompt=analysis_prompt,
            template="analysis.tpl"
        )
        
        return DataAnalysisResult(
            statistical_summary=stats,
            semantic_insights=semantic_analysis,
            variable_types=self._classify_variables(dataset),
            dimensionality=self._assess_dimensionality(dataset),
            recommendations=self._generate_recommendations(stats, semantic_analysis)
        )
    
    def _classify_variables(self, dataset: VisualizationDataset) -> dict:
        """Classify variables by type and role"""
        classifications = {}
        
        for column in dataset.columns:
            classifications[column] = {
                'data_type': self._infer_data_type(dataset[column]),
                'role': self._infer_variable_role(dataset[column]),
                'cardinality': len(dataset[column].unique()),
                'distribution': self._analyze_distribution(dataset[column])
            }
        
        return classifications
```

**Chart Selection Engine:**
```python
# server/agent/visualization/selector.py
class ChartSelectionEngine:
    """LLM-powered intelligent chart selection"""
    
    def __init__(self, llm_client):
        self.llm_client = llm_client
        self.chart_library = ChartLibrary()
    
    async def select_optimal_chart(self, analysis: DataAnalysisResult, user_preferences: dict) -> ChartSelection:
        """
        Select optimal chart type based on data analysis and user preferences
        
        Selection Logic:
        1. Rule-based filtering (eliminate incompatible charts)
        2. LLM-based ranking (semantic understanding)
        3. Performance scoring (dataset size considerations)
        4. User preference weighting
        """
        
        # Step 1: Rule-based filtering
        compatible_charts = self._filter_compatible_charts(analysis)
        
        # Step 2: LLM-based semantic selection
        selection_prompt = self._build_selection_prompt(analysis, compatible_charts, user_preferences)
        llm_recommendations = await self.llm_client.generate(
            prompt=selection_prompt,
            template="selection.tpl",
            response_format="json"
        )
        
        # Step 3: Performance scoring
        performance_scores = self._calculate_performance_scores(compatible_charts, analysis.dataset_size)
        
        # Step 4: Combined ranking
        final_ranking = self._combine_rankings(llm_recommendations, performance_scores, user_preferences)
        
        return ChartSelection(
            primary_chart=final_ranking[0],
            alternatives=final_ranking[1:3],
            rationale=llm_recommendations['reasoning'],
            performance_considerations=performance_scores[final_ranking[0]['type']]
        )
    
    def _filter_compatible_charts(self, analysis: DataAnalysisResult) -> List[ChartType]:
        """Filter charts based on data characteristics"""
        compatible = []
        
        # Single variable analysis
        if analysis.dimensionality.variable_count == 1:
            var_type = analysis.variable_types[analysis.dimensionality.primary_variable]['data_type']
            if var_type == 'continuous':
                compatible.extend(['histogram', 'box_plot', 'violin_plot'])
            elif var_type == 'categorical':
                compatible.extend(['bar_chart', 'pie_chart', 'donut_chart'])
        
        # Two variable analysis
        elif analysis.dimensionality.variable_count == 2:
            x_type = analysis.variable_types[analysis.dimensionality.x_variable]['data_type']
            y_type = analysis.variable_types[analysis.dimensionality.y_variable]['data_type']
            
            if x_type == 'continuous' and y_type == 'continuous':
                compatible.extend(['scatter_plot', 'line_chart', 'heatmap'])
            elif x_type == 'categorical' and y_type == 'continuous':
                compatible.extend(['bar_chart', 'box_plot', 'violin_plot'])
            elif x_type == 'temporal' and y_type == 'continuous':
                compatible.extend(['line_chart', 'area_chart', 'candlestick'])
        
        # Multi-variable analysis
        elif analysis.dimensionality.variable_count > 2:
            compatible.extend(['parallel_coordinates', 'radar_chart', 'treemap', 'sankey'])
        
        return compatible
```

### 4. High-Performance Visualization Rendering

#### 4.1 Web Workers Architecture

**File Structure:**
```
server/web/src/workers/
├── chart-renderer.worker.ts     # Main chart rendering worker
├── data-processor.worker.ts     # Data processing worker
├── plotly-optimizer.worker.ts   # Plotly optimization worker
└── types/
    ├── worker-messages.ts       # Message type definitions
    └── chart-config.ts          # Chart configuration types
```

**Chart Renderer Worker:**
```typescript
// server/web/src/workers/chart-renderer.worker.ts
import Plotly from 'plotly.js-dist-min';

interface RenderMessage {
  type: 'RENDER_CHART';
  payload: {
    config: PlotlyConfig;
    data: ProcessedDataset;
    containerId: string;
    options: RenderOptions;
  };
}

interface ProgressMessage {
  type: 'RENDER_PROGRESS';
  payload: {
    stage: 'data_processing' | 'chart_generation' | 'optimization' | 'rendering';
    progress: number;
    message: string;
  };
}

// Main worker thread
self.onmessage = async (event: MessageEvent<RenderMessage>) => {
  const { type, payload } = event.data;
  
  if (type === 'RENDER_CHART') {
    try {
      await renderChart(payload);
    } catch (error) {
      self.postMessage({
        type: 'RENDER_ERROR',
        payload: { error: error.message }
      });
    }
  }
};

async function renderChart(payload: RenderMessage['payload']) {
  const { config, data, containerId, options } = payload;
  
  // Stage 1: Data Processing
  self.postMessage({
    type: 'RENDER_PROGRESS',
    payload: {
      stage: 'data_processing',
      progress: 10,
      message: 'Processing dataset...'
    }
  });
  
  const processedData = await processDataForPlotly(data, config);
  
  // Stage 2: Chart Generation
  self.postMessage({
    type: 'RENDER_PROGRESS',
    payload: {
      stage: 'chart_generation',
      progress: 40,
      message: 'Generating chart configuration...'
    }
  });
  
  const plotlyConfig = await generatePlotlyConfig(config, processedData);
  
  // Stage 3: Performance Optimization
  self.postMessage({
    type: 'RENDER_PROGRESS',
    payload: {
      stage: 'optimization',
      progress: 70,
      message: 'Optimizing for performance...'
    }
  });
  
  const optimizedConfig = await optimizeForPerformance(plotlyConfig, options);
  
  // Stage 4: Rendering
  self.postMessage({
    type: 'RENDER_PROGRESS',
    payload: {
      stage: 'rendering',
      progress: 90,
      message: 'Rendering visualization...'
    }
  });
  
  // Use OffscreenCanvas for rendering in worker
  const canvas = new OffscreenCanvas(options.width, options.height);
  await Plotly.newPlot(canvas, optimizedConfig.data, optimizedConfig.layout, optimizedConfig.config);
  
  self.postMessage({
    type: 'RENDER_COMPLETE',
    payload: {
      chartId: containerId,
      imageData: canvas.transferToImageBitmap(),
      interactionData: optimizedConfig.interactionData
    }
  });
}

async function optimizeForPerformance(config: PlotlyConfig, options: RenderOptions): Promise<OptimizedConfig> {
  """
  Performance optimization strategies based on research:
  
  1. Data Sampling: For datasets > 10,000 points
  2. WebGL Rendering: For scatter plots with > 5,000 points
  3. Aggregation: For time series with > 1,000 points
  4. Selective Rendering: Show/hide based on zoom level
  """
  
  const dataSize = config.data[0].x.length;
  
  if (dataSize > 10000) {
    // Large dataset optimizations
    if (config.type === 'scatter') {
      // Use WebGL for large scatter plots
      config.mode = 'markers';
      config.marker = { ...config.marker, size: 2 };
      config.type = 'scattergl';
    } else if (config.type === 'line') {
      // Downsample line charts
      config.data = await downsampleTimeSeries(config.data, 1000);
    }
  }
  
  // Memory optimization
  if (options.enableStreaming) {
    config.streaming = {
      maxpoints: 1000,
      token: generateStreamingToken()
    };
  }
  
  return config;
}
```

#### 4.2 Runtime Environment Management

**Comparison to Lovable/ChatGPT Preview Systems:**
```typescript
// server/web/src/components/ChartRenderer.tsx
interface ChartRendererProps {
  config: PlotlyConfig;
  data: ProcessedDataset;
  renderingMode: 'inline' | 'iframe' | 'webworker';
  sandboxed?: boolean;
}

const ChartRenderer: React.FC<ChartRendererProps> = ({ 
  config, data, renderingMode = 'webworker', sandboxed = true 
}) => {
  const [renderState, setRenderState] = useState<RenderState>('initializing');
  const [chartElement, setChartElement] = useState<HTMLElement | null>(null);
  const workerRef = useRef<Worker | null>(null);
  const iframeRef = useRef<HTMLIFrameElement | null>(null);
  
  useEffect(() => {
    switch (renderingMode) {
      case 'webworker':
        renderWithWebWorker();
        break;
      case 'iframe':
        renderWithSandboxedIframe();
        break;
      case 'inline':
        renderInline();
        break;
    }
  }, [config, data, renderingMode]);
  
  const renderWithWebWorker = async () => {
    setRenderState('processing');
    
    // Create dedicated worker for chart rendering
    workerRef.current = new Worker(
      new URL('../workers/chart-renderer.worker.ts', import.meta.url),
      { type: 'module' }
    );
    
    workerRef.current.onmessage = (event) => {
      const { type, payload } = event.data;
      
      switch (type) {
        case 'RENDER_PROGRESS':
          setRenderState('rendering');
          // Update progress indicators
          break;
        case 'RENDER_COMPLETE':
          setRenderState('complete');
          // Transfer rendered chart to main thread
          displayRenderedChart(payload);
          break;
        case 'RENDER_ERROR':
          setRenderState('error');
          console.error('Chart rendering error:', payload.error);
          break;
      }
    };
    
    // Send rendering job to worker
    workerRef.current.postMessage({
      type: 'RENDER_CHART',
      payload: { config, data, containerId: generateId(), options: getRenderOptions() }
    });
  };
  
  const renderWithSandboxedIframe = () => {
    """
    Similar to how Lovable/ChatGPT show code previews:
    1. Create sandboxed iframe
    2. Inject minimal HTML with Plotly
    3. Render chart in isolated environment
    4. Enable communication via postMessage
    """
    setRenderState('processing');
    
    const iframeContent = generateIframeContent(config, data);
    
    if (iframeRef.current) {
      iframeRef.current.srcdoc = iframeContent;
      iframeRef.current.onload = () => {
        setRenderState('complete');
      };
    }
  };
  
  const generateIframeContent = (config: PlotlyConfig, data: ProcessedDataset): string => {
    return `
      <!DOCTYPE html>
      <html>
      <head>
        <script src="https://cdn.plot.ly/plotly-2.26.0.min.js"></script>
        <style>
          body { margin: 0; padding: 0; }
          #chart { width: 100%; height: 100vh; }
        </style>
      </head>
      <body>
        <div id="chart"></div>
        <script>
          const config = ${JSON.stringify(config)};
          const data = ${JSON.stringify(data)};
          
          Plotly.newPlot('chart', data, config.layout, config.options)
            .then(() => {
              parent.postMessage({ type: 'CHART_READY' }, '*');
            })
            .catch((error) => {
              parent.postMessage({ type: 'CHART_ERROR', error: error.message }, '*');
            });
          
          // Handle resize
          window.addEventListener('resize', () => {
            Plotly.Plots.resize('chart');
          });
        </script>
      </body>
      </html>
    `;
  };
  
  return (
    <div className="chart-renderer">
      {renderState === 'processing' && (
        <div className="rendering-progress">
          <Spinner />
          <p>Generating visualization...</p>
        </div>
      )}
      
      {renderingMode === 'iframe' && (
        <iframe
          ref={iframeRef}
          className="chart-iframe"
          sandbox="allow-scripts allow-same-origin"
          style={{ width: '100%', height: '400px', border: 'none' }}
        />
      )}
      
      {renderingMode === 'inline' && renderState === 'complete' && (
        <div 
          ref={setChartElement}
          className="chart-container"
          style={{ width: '100%', height: '400px' }}
        />
      )}
      
      {renderState === 'error' && (
        <div className="chart-error">
          <p>Error rendering chart. Please try again.</p>
        </div>
      )}
    </div>
  );
};
```

### 5. Performance Optimization Strategy

#### 5.1 Data-Driven Optimization

**Based on Research Findings:**

1. **Bundle Size Optimization (from acmiyaguchi.me analysis):**
```typescript
// server/web/src/lib/plotly-optimizer.ts
class PlotlyOptimizer {
  private static readonly BUNDLE_THRESHOLDS = {
    BASIC: 500, // KB - use plotly.js-basic-dist
    CARTESIAN: 1000, // KB - use plotly.js-cartesian-dist  
    FULL: 2000 // KB - use full plotly.js
  };
  
  static async selectOptimalBundle(chartTypes: string[]): Promise<PlotlyBundle> {
    const requiredFeatures = this.analyzeRequiredFeatures(chartTypes);
    
    if (this.canUseBasicBundle(requiredFeatures)) {
      return await import('plotly.js-basic-dist-min');
    } else if (this.canUseCartesianBundle(requiredFeatures)) {
      return await import('plotly.js-cartesian-dist-min');
    } else {
      return await import('plotly.js-dist-min');
    }
  }
  
  private static canUseBasicBundle(features: PlotlyFeatures): boolean {
    const basicCharts = ['scatter', 'bar', 'line', 'pie'];
    return features.chartTypes.every(type => basicCharts.includes(type)) &&
           !features.requires3D &&
           !features.requiresGL;
  }
}
```

2. **Rendering Performance (from plotly.com performance update):**
```typescript
// server/web/src/lib/performance-config.ts
class RenderingPerformanceConfig {
  static generateOptimizedConfig(dataSize: number, chartType: string): Partial<PlotlyConfig> {
    const config = {
      responsive: true,
      displayModeBar: false, // Hide toolbar for performance
      staticPlot: false
    };
    
    // Large dataset optimizations
    if (dataSize > 10000) {
      Object.assign(config, {
        staticPlot: true, // Disable interactivity for large datasets
        toImageButtonOptions: {
          format: 'webp', // Faster image format
          filename: 'chart',
          scale: 1
        }
      });
    }
    
    // Chart-specific optimizations
    if (chartType === 'scatter' && dataSize > 5000) {
      return {
        ...config,
        scattermode: 'markers',
        marker: { size: 2 }, // Smaller markers for performance
        mode: 'markers'
      };
    }
    
    return config;
  }
}
```

#### 5.2 Memory Management

```typescript
// server/web/src/hooks/useChartMemoryManagement.ts
export const useChartMemoryManagement = () => {
  const chartInstancesRef = useRef<Map<string, any>>(new Map());
  const cleanupTimeoutRef = useRef<NodeJS.Timeout>();
  
  const registerChart = (id: string, instance: any) => {
    chartInstancesRef.current.set(id, instance);
    
    // Schedule cleanup for inactive charts
    if (cleanupTimeoutRef.current) {
      clearTimeout(cleanupTimeoutRef.current);
    }
    
    cleanupTimeoutRef.current = setTimeout(() => {
      cleanupInactiveCharts();
    }, 30000); // 30 seconds
  };
  
  const cleanupInactiveCharts = () => {
    const now = Date.now();
    const INACTIVE_THRESHOLD = 5 * 60 * 1000; // 5 minutes
    
    chartInstancesRef.current.forEach((instance, id) => {
      if (now - instance.lastAccessed > INACTIVE_THRESHOLD) {
        Plotly.purge(instance.element);
        chartInstancesRef.current.delete(id);
      }
    });
  };
  
  const destroyChart = (id: string) => {
    const instance = chartInstancesRef.current.get(id);
    if (instance) {
      Plotly.purge(instance.element);
      chartInstancesRef.current.delete(id);
    }
  };
  
  useEffect(() => {
    return () => {
      // Cleanup all charts on unmount
      chartInstancesRef.current.forEach((instance) => {
        Plotly.purge(instance.element);
      });
      chartInstancesRef.current.clear();
      
      if (cleanupTimeoutRef.current) {
        clearTimeout(cleanupTimeoutRef.current);
      }
    };
  }, []);
  
  return { registerChart, destroyChart };
};
```

### 6. Integration with Existing Canvas System

#### 6.1 Canvas Block Integration

**File Reference:** `server/web/src/components/CanvasBlock.tsx`

**Enhancement Strategy:**
```typescript
// Enhanced CanvasBlock to support graphing capabilities
const CanvasBlock: React.FC<CanvasBlockProps> = ({ 
  block, onUpdate, workspace, page, onCreateCanvasPage 
}) => {
  const [canvasMode, setCanvasMode] = useState<'analysis' | 'graphing' | 'hybrid'>('analysis');
  const [graphingData, setGraphingData] = useState<GraphingData | null>(null);
  
  // Integration point for graphing within canvas
  const handleAnalysisComplete = async (analysisResult: AnalysisResult) => {
    // Check if analysis result contains visualizable data
    if (isVisualizationCandidate(analysisResult)) {
      setCanvasMode('hybrid');
      
      // Automatically suggest chart creation
      const chartSuggestions = await generateChartSuggestions(analysisResult);
      setGraphingData({
        sourceAnalysis: analysisResult,
        suggestions: chartSuggestions,
        autoGenerate: shouldAutoGenerateChart(analysisResult)
      });
    }
  };
  
  const isVisualizationCandidate = (result: AnalysisResult): boolean => {
    // Determine if analysis result should trigger visualization
    return result.data_type === 'tabular' &&
           result.row_count > 5 &&
           result.row_count < 50000 &&
           hasNumericColumns(result.schema);
  };
  
  return (
    <div className="canvas-block">
      {canvasMode === 'analysis' && (
        <AnalysisInterface 
          onAnalysisComplete={handleAnalysisComplete}
          // ... existing props
        />
      )}
      
      {canvasMode === 'graphing' && (
        <GraphingInterface
          initialData={graphingData}
          onChartCreated={handleChartCreated}
          onBackToAnalysis={() => setCanvasMode('analysis')}
        />
      )}
      
      {canvasMode === 'hybrid' && (
        <HybridCanvasInterface
          analysisResult={graphingData?.sourceAnalysis}
          chartSuggestions={graphingData?.suggestions}
          onModeSwitch={setCanvasMode}
        />
      )}
    </div>
  );
};
```

#### 6.2 Canvas Data Flow Enhancement

**Integration with existing canvas threads:**
```python
# Enhancement to server/application/routes/storage.py
class CanvasThreadDB(Base):
    # ... existing fields ...
    
    # New fields for graphing support
    visualization_config = Column(JSONB, nullable=True)  # Chart configuration
    chart_data_cache = Column(LargeBinary, nullable=True)  # Cached chart data
    auto_viz_enabled = Column(Boolean, default=True)  # Auto-visualization flag
    
    # Relationship to chart instances
    chart_instances = relationship("ChartInstanceDB", back_populates="thread", cascade="all, delete-orphan")

class ChartInstanceDB(Base):
    __tablename__ = "chart_instances"
    
    id = Column(String, primary_key=True)
    thread_id = Column(String, ForeignKey("canvas_threads.id"), nullable=False)
    chart_type = Column(String, nullable=False)  # scatter, bar, line, etc.
    chart_config = Column(JSONB, nullable=False)  # Plotly configuration
    data_source_query = Column(Text, nullable=False)  # Original query for data
    performance_metrics = Column(JSONB, nullable=True)  # Rendering performance data
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    thread = relationship("CanvasThreadDB", back_populates="chart_instances")
```

### 7. API Endpoints and Data Flow

#### 7.1 New API Endpoints

**File Reference:** `server/agent/api/endpoints.py`

**Additional Endpoints:**
```python
# Addition to endpoints.py
@router.post("/visualization/analyze")
async def analyze_for_visualization(request: VisualizationAnalysisRequest):
    """Analyze dataset and suggest optimal visualizations"""
    analyzer = DataAnalysisModule(llm_client)
    analysis_result = await analyzer.analyze_dataset(request.dataset, request.user_intent)
    
    selector = ChartSelectionEngine(llm_client)
    chart_selection = await selector.select_optimal_chart(analysis_result, request.preferences)
    
    return VisualizationAnalysisResponse(
        analysis=analysis_result,
        recommendations=chart_selection,
        estimated_render_time=estimate_render_time(analysis_result.dataset_size)
    )

@router.post("/visualization/generate")
async def generate_chart_config(request: ChartGenerationRequest):
    """Generate optimized Plotly configuration"""
    generator = PlotlyConfigGenerator()
    
    # Generate base configuration
    base_config = await generator.generate_config(
        chart_type=request.chart_type,
        data=request.data,
        customizations=request.customizations
    )
    
    # Apply performance optimizations
    optimizer = PlotlyOptimizer()
    optimized_config = await optimizer.optimize(base_config, request.performance_requirements)
    
    return ChartGenerationResponse(
        config=optimized_config,
        performance_profile=optimizer.get_performance_profile(),
        alternative_configs=generator.get_alternatives()
    )

@router.post("/visualization/render")
async def render_chart(request: ChartRenderRequest):
    """Server-side chart rendering for heavy computations"""
    if request.data_size > LARGE_DATASET_THRESHOLD:
        # Use server-side rendering for large datasets
        renderer = ServerSideRenderer()
        result = await renderer.render(request.config, request.data)
        
        return ChartRenderResponse(
            rendered_image=result.image_data,
            interaction_data=result.interaction_data,
            render_time=result.metrics.render_time
        )
    else:
        # Return configuration for client-side rendering
        return ChartRenderResponse(
            client_config=request.config,
            render_mode="client"
        )
```

### 8. Implementation Timeline and Dependencies

#### 8.1 Phase 1: Core Infrastructure (Weeks 1-2)
- Data analysis module implementation
- Chart selection engine development
- GraphingBlock component creation
- Basic Plotly integration

#### 8.2 Phase 2: Performance Optimization (Weeks 3-4)
- Web workers implementation
- Memory management systems
- Bundle optimization
- Runtime environment setup

#### 8.3 Phase 3: Canvas Integration (Week 5)
- Canvas block enhancements
- Database schema updates
- API endpoint implementation
- End-to-end testing

#### 8.4 Phase 4: Advanced Features (Week 6)
- Server-side rendering for large datasets
- Advanced chart types
- Real-time data streaming
- Performance monitoring

## Conclusion

This autonomous graphing system provides intelligent, high-performance data visualization capabilities that integrate seamlessly with the existing Data Connector architecture. By leveraging LLM-powered chart selection, Web Workers for performance, and a sophisticated canvas integration, users can generate publication-ready visualizations through natural language queries while maintaining optimal performance across datasets of varying sizes.

The system addresses the key challenges identified in the Notion research while building upon the proven architecture patterns already established in the codebase, ensuring a robust and scalable solution for enterprise data visualization needs. 
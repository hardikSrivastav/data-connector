/**
 * GraphingBlock Component - Autonomous Visualization Generation
 * 
 * Integrates with the existing block editor system to provide intelligent
 * chart generation capabilities through natural language queries.
 */

import React, { useState, useEffect } from 'react';
import { Spinner } from './ui/Spinner';
import { ChartRenderer } from './ChartRenderer';
import type { Block, ChartSuggestion, DataAnalysisResult, PlotlyConfig, ProcessedDataset } from '../types';

// Enhanced logging utility for frontend
const createLogger = (sessionId: string) => ({
  info: (message: string, data?: any) => {
    console.log(`🔵 [${sessionId}] ${message}`, data || '');
  },
  error: (message: string, error?: any) => {
    console.error(`🔴 [${sessionId}] ${message}`, error || '');
  },
  warning: (message: string, data?: any) => {
    console.warn(`🟠 [${sessionId}] ${message}`, data || '');
  },
  debug: (message: string, data?: any) => {
    console.debug(`🟡 [${sessionId}] ${message}`, data || '');
  },
  time: (label: string) => {
    console.time(`⏱️ [${sessionId}] ${label}`);
  },
  timeEnd: (label: string) => {
    console.timeEnd(`⏱️ [${sessionId}] ${label}`);
  }
});

// Types for the GraphingBlock
interface GraphingBlockProps {
  block: Block;
  onUpdate: (id: string, updates: Partial<Block>) => void;
  onAIQuery: (query: string, blockId: string) => Promise<any>;
  isFocused: boolean;
  workspace?: any;
  page?: any;
  streamingState?: any;
}

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
  block,
  onUpdate,
  isFocused,
  onAIQuery,
  workspace,
  page,
  streamingState
}) => {
  // Create session ID for logging
  const [sessionId] = useState(() => `chart_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`);
  const logger = createLogger(sessionId);
  
  const [state, setState] = useState<GraphingBlockState>({
    mode: 'input',
    userQuery: '',
    dataAnalysis: null,
    chartConfig: null,
    chartData: null,
    renderingState: 'idle',
    suggestions: []
  });

  // Log component initialization and restore persisted chart
  useEffect(() => {
    logger.info('=== GRAPHING BLOCK INITIALIZED ===');
    logger.info('Block ID:', block.id);
    logger.info('Block type:', block.type);
    logger.info('Is focused:', isFocused);
    logger.debug('Full block data:', block);
    
    // Check if there's persisted chart data
    const persistedData = block.properties?.graphingData;
    if (persistedData && persistedData.chartConfig && persistedData.chartData) {
      logger.info('📄 Found persisted chart data, restoring chart...');
      logger.info('📄 Persisted query:', persistedData.query);
      logger.info('📄 Chart type:', persistedData.chartConfig.type);
      logger.info('📄 Last generated:', persistedData.lastGenerated);
      
      // Restore the chart state
      setState(prev => ({
        ...prev,
        mode: 'display',
        userQuery: persistedData.query,
        chartConfig: persistedData.chartConfig,
        chartData: persistedData.chartData,
        renderingState: 'complete'
      }));
      
      logger.info('✅ Chart restored from persistence');
    } else {
      logger.info('📄 No persisted chart data found, showing input form');
    }
  }, []);

  // Log state changes
  useEffect(() => {
    logger.info(`Frontend state changed to: ${state.mode}`);
    if (state.mode === 'error' && state.errorMessage) {
      logger.error('Frontend error state:', state.errorMessage);
    }
  }, [state.mode]);

  // Chart generation pipeline - Enhanced Direct Connection
  const handleGenerateChart = async (query: string) => {
    const sessionId = Date.now().toString();
    
    logger.info(`[${sessionId}] === ENHANCED DIRECT CHART GENERATION STARTED ===`);
    logger.info(`[${sessionId}] User query: "${query}"`);
    logger.info(`[${sessionId}] Using direct visualization API approach`);
    logger.time(`[${sessionId}] Total chart generation`);
    
    setState(prev => ({ ...prev, mode: 'analyzing', userQuery: query }));
    
    try {
      // Primary approach: Use direct visualization endpoint with proper agent base URL
      logger.info(`[${sessionId}] Step 1: Calling direct visualization endpoint...`);
      logger.time(`[${sessionId}] Direct API call`);
      
      // Get the proper agent base URL from environment variables
      const agentBaseUrl = import.meta.env.VITE_AGENT_BASE_URL || 'http://localhost:8787';
      const apiUrl = `${agentBaseUrl}/api/agent/visualization/query`;
      
      logger.info(`[${sessionId}] API URL: ${apiUrl}`);
      
      const response = await fetch(apiUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          query: query,
          chart_preferences: {
            style: 'modern',
            title: `Chart for: ${query}`
          },
          auto_generate: true,
          performance_mode: false
        })
      });
      
      logger.timeEnd(`[${sessionId}] Direct API call`);
      logger.info(`[${sessionId}] Direct API response status: ${response.status}`);
      
      if (!response.ok) {
        throw new Error(`Direct API failed with status ${response.status}`);
      }
      
      const result = await response.json();
      
      logger.info(`[${sessionId}] Step 2: Processing direct API response...`);
      logger.info(`[${sessionId}] API Success: ${result.success}`);
      logger.info(`[${sessionId}] Data summary:`, result.data_summary);
      logger.info(`[${sessionId}] Chart config present: ${!!result.chart_config}`);
      logger.info(`[${sessionId}] Backend session ID: ${result.session_id}`);
      
      if (result.success) {
        logger.info(`[${sessionId}] ✅ Direct API call successful`);
        
                 setState(prev => ({ 
           ...prev, 
           dataAnalysis: {
             dataset_size: result.data_summary?.row_count || 0,
             variable_types: result.data_summary?.data_types || {},
             dimensionality: {
               variable_count: result.data_summary?.column_count || 0,
               primary_variable: result.data_summary?.columns?.[0]
             },
             statistical_summary: result.data_summary,
             semantic_insights: { success: true, session_id: result.session_id }
           },
           mode: 'generating' 
         }));
        
        // Extract and process chart information
        const chartInfo = {
          type: result.chart_config?.type || 'bar',
          data: result.chart_data || [],
          config: result.chart_config,
          performance: result.performance_metrics,
          suggestions: result.suggestions || []
        };
        
        logger.info(`[${sessionId}] Chart type: ${chartInfo.type}`);
        logger.info(`[${sessionId}] Data points: ${chartInfo.data.length}`);
        logger.info(`[${sessionId}] Performance: ${chartInfo.performance?.total_time}s`);
        
        // Format chart configuration for display
        const chartResult = {
          config: {
            type: chartInfo.type,
            data: chartInfo.config?.data || [],
            layout: chartInfo.config?.layout || {
              title: `${chartInfo.type.charAt(0).toUpperCase() + chartInfo.type.slice(1)} Chart`,
              margin: { l: 50, r: 50, t: 50, b: 50 }
            },
            config: chartInfo.config?.config || { responsive: true }
          },
          data: chartInfo.data
        };
        
        logger.info(`[${sessionId}] Final chart config:`, chartResult.config);
        
        setState(prev => ({
          ...prev,
          chartConfig: chartResult.config,
          chartData: chartResult.data,
          mode: 'display',
          renderingState: 'processing'
        }));
        
        // Update block with chart data
        const updatedBlock = {
          content: `Chart: ${query}`,
          properties: {
            ...block.properties,
            graphingData: {
              query,
              chartConfig: chartResult.config,
              chartData: chartResult.data,
              lastGenerated: new Date(),
              sessionId: result.session_id,
              approach: 'direct_api'
            }
          }
        };
        
        onUpdate(block.id, updatedBlock);
        
        logger.timeEnd(`[${sessionId}] Total chart generation`);
        logger.info(`[${sessionId}] === ENHANCED DIRECT CHART GENERATION COMPLETED ===`);
        
        return; // Success - exit early
      }
      
      // If direct API didn't succeed, fall through to fallback
      throw new Error(result.error_message || 'Direct API returned success=false');
      
    } catch (directError) {
      logger.timeEnd(`[${sessionId}] Direct API call`);
      logger.warning(`[${sessionId}] Direct API failed: ${directError.message}`);
      logger.info(`[${sessionId}] Attempting fallback to original AI query approach...`);
      
      try {
        // Fallback approach: Use existing AI infrastructure
        logger.time(`[${sessionId}] Fallback API call`);
      
      const analysisResult = await onAIQuery(
        `analyze_for_visualization: ${query}`, 
        block.id
      );
      
        logger.timeEnd(`[${sessionId}] Fallback API call`);
        logger.info(`[${sessionId}] Fallback result type:`, typeof analysisResult);
        logger.info(`[${sessionId}] Fallback result keys:`, analysisResult ? Object.keys(analysisResult) : 'null');
      
      setState(prev => ({ 
        ...prev, 
        dataAnalysis: analysisResult,
        mode: 'generating' 
      }));
      
        // Process fallback result
        let chartResult;
        if (analysisResult?.visualization_data) {
          logger.info(`[${sessionId}] ✅ Found visualization_data in fallback response`);
          chartResult = {
            config: {
              type: analysisResult.visualization_data.chart_type,
              data: analysisResult.visualization_data.dataset || [],
              layout: analysisResult.visualization_data.chart_config?.layout || {},
              ...analysisResult.visualization_data.chart_config
            },
            data: analysisResult.visualization_data.dataset || []
          };
        } else {
          logger.warning(`[${sessionId}] No visualization_data in fallback, using basic config`);
          chartResult = {
            config: { 
              type: 'bar', 
              data: [], 
              layout: { title: 'Fallback Chart' } 
            },
            data: []
          };
        }
      
      setState(prev => ({
        ...prev,
        chartConfig: chartResult.config,
        chartData: chartResult.data,
        mode: 'display',
        renderingState: 'processing'
      }));
      
        // Update block with fallback data
      const updatedBlock = {
        content: `Chart: ${query}`,
        properties: {
          ...block.properties,
          graphingData: {
            query,
            chartConfig: chartResult.config,
            chartData: chartResult.data,
              lastGenerated: new Date(),
              approach: 'fallback_ai_query'
            }
        }
      };
      
      onUpdate(block.id, updatedBlock);
        
        logger.timeEnd(`[${sessionId}] Total chart generation`);
        logger.info(`[${sessionId}] === FALLBACK CHART GENERATION COMPLETED ===`);
        
      } catch (fallbackError) {
        logger.timeEnd(`[${sessionId}] Total chart generation`);
        logger.error(`[${sessionId}] === CHART GENERATION COMPLETELY FAILED ===`);
        logger.error(`[${sessionId}] Direct error:`, directError.message);
        logger.error(`[${sessionId}] Fallback error:`, fallbackError.message);
      
      setState(prev => ({ 
        ...prev, 
        mode: 'error', 
          errorMessage: `Both approaches failed. Direct: ${directError.message}. Fallback: ${fallbackError.message}`
      }));
      }
    }
  };

  return (
    <div className="graphing-block p-4 border border-gray-200 rounded-lg space-y-4">
      {state.mode === 'input' && (
        <GraphingInput 
          onSubmit={handleGenerateChart}
          suggestions={state.suggestions}
          placeholder="Describe the chart you want to create..."
          isFocused={isFocused}
        />
      )}
      
      {state.mode === 'analyzing' && (
        <AnalysisProgress 
          streamingState={streamingState}
          stage="data_analysis"
          query={state.userQuery}
        />
      )}
      
      {state.mode === 'generating' && (
        <ChartGenerationProgress
          dataAnalysis={state.dataAnalysis}
          stage="chart_selection"
        />
      )}
      
      {state.mode === 'display' && (
        <ChartDisplay
          config={state.chartConfig}
          data={state.chartData}
          renderingState={state.renderingState}
          userQuery={state.userQuery}
          onRenderComplete={() => setState(prev => ({ 
            ...prev, 
            renderingState: 'complete' 
          }))}
          onCreateNew={() => setState(prev => ({ 
            ...prev, 
            mode: 'input', 
            renderingState: 'idle',
            userQuery: '',
            chartConfig: null,
            chartData: null
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

// Inline components to avoid import issues
const GraphingInput: React.FC<{
  onSubmit: (query: string) => void;
  suggestions: ChartSuggestion[];
  placeholder: string;
  isFocused: boolean;
}> = ({ onSubmit, suggestions, placeholder, isFocused }) => {
  const [query, setQuery] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim()) {
      onSubmit(query.trim());
    }
  };

  return (
    <div className="graphing-input">
      <form onSubmit={handleSubmit} className="space-y-3">
        <div>
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={placeholder}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            autoFocus={isFocused}
          />
        </div>
        <div className="flex space-x-2">
          <button
            type="submit"
            disabled={!query.trim()}
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Generate Chart
          </button>
        </div>
      </form>
      
      {suggestions.length > 0 && (
        <div className="mt-3 space-y-1">
          <p className="text-sm text-gray-600">Suggestions:</p>
          {suggestions.slice(0, 3).map((suggestion, index) => (
            <button
              key={index}
              onClick={() => setQuery(suggestion.query)}
              className="block text-left text-sm text-blue-600 hover:text-blue-800 underline"
            >
              {suggestion.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
};

const AnalysisProgress: React.FC<{
  streamingState: any;
  stage: string;
  query: string;
}> = ({ streamingState, stage, query }) => {
  const [sessionId] = useState(() => `analysis_${Date.now()}`);
  const logger = createLogger(sessionId);
  
  useEffect(() => {
    logger.info('=== ANALYSIS PROGRESS COMPONENT RENDERED ===');
    logger.info('Query being analyzed:', query);
    logger.info('Current stage:', stage);
    logger.debug('Streaming state:', streamingState);
  }, [stage, query]);

  return (
    <div className="analysis-progress p-4 bg-blue-50 rounded-lg">
      <div className="flex items-center space-x-3">
        <Spinner />
        <div>
          <p className="font-medium text-blue-900">Analyzing your data...</p>
          <p className="text-sm text-blue-700">Query: {query}</p>
          <p className="text-xs text-blue-600">Stage: {stage}</p>
          {streamingState && (
            <p className="text-xs text-blue-500">
              Status: {streamingState.status || 'processing'}
            </p>
          )}
        </div>
      </div>
    </div>
  );
};

const ChartGenerationProgress: React.FC<{
  dataAnalysis: DataAnalysisResult | null;
  stage: string;
}> = ({ dataAnalysis, stage }) => {
  return (
    <div className="chart-generation-progress p-4 bg-green-50 rounded-lg">
      <div className="flex items-center space-x-3">
        <Spinner />
        <div>
          <p className="font-medium text-green-900">Generating your chart...</p>
          <p className="text-xs text-green-600">Stage: {stage}</p>
        </div>
      </div>
    </div>
  );
};

const ChartDisplay: React.FC<{
  config: PlotlyConfig | null;
  data: ProcessedDataset | null;
  renderingState: string;
  userQuery: string;
  onRenderComplete: () => void;
  onCreateNew: () => void;
}> = ({ config, data, renderingState, userQuery, onRenderComplete, onCreateNew }) => {
  const [sessionId] = useState(() => `render_${Date.now()}`);
  const logger = createLogger(sessionId);
  
  useEffect(() => {
    logger.info('=== CHART DISPLAY COMPONENT RENDERED ===');
    logger.info('Rendering state:', renderingState);
    logger.info('Has config:', !!config);
    logger.info('Has data:', !!data);
    if (config) {
      logger.debug('Chart config type:', config.type);
      logger.debug('Chart config data length:', config.data?.length || 0);
    }
    if (data) {
      logger.debug('Chart data keys:', Object.keys(data));
    }
  }, [renderingState, config, data]);

  if (!config) {
    logger.error('❌ No chart configuration available for rendering');
    return (
      <div className="chart-display p-4 bg-red-50 rounded-lg">
        <p className="text-red-700">❌ No chart configuration available</p>
      </div>
    );
  }

  if (!data) {
    logger.error('❌ No chart data available for rendering');
    return (
      <div className="chart-display p-4 bg-red-50 rounded-lg">
        <p className="text-red-700">❌ No chart data available</p>
      </div>
    );
  }

  // Prepare config and data for ChartRenderer component
  const chartConfig = {
    type: config.type,
    data: config.data || [],
    layout: config.layout || {},
    config: config.config || { responsive: true, displayModeBar: true },
    mode: config.mode,
    marker: config.marker
  };

  // Convert data to expected format for ChartRenderer
  const chartData = {
    data: Array.isArray(data) ? data : (data.data || []),
    columns: data.columns || (Array.isArray(data) && data.length > 0 ? Object.keys(data[0]) : []),
    metadata: data.metadata || {}
  };

  return (
    <div className="chart-display space-y-4">
      {/* Processing indicator - only show when processing, not when complete */}
      {renderingState === 'processing' && (
        <div className="p-3 bg-yellow-50 rounded-lg border border-yellow-200">
          <div className="flex items-center space-x-3">
            <Spinner />
            <div>
              <p className="text-yellow-700 font-medium">🎨 Rendering chart...</p>
              <p className="text-xs text-yellow-600">Chart type: {config.type}</p>
              <p className="text-xs text-yellow-600">Preparing Plotly.js visualization...</p>
            </div>
          </div>
        </div>
      )}
      
      {/* Chart container - always visible with proper spacing */}
      <div className="chart-container bg-white border border-gray-200 rounded-lg overflow-hidden">
        <div className="chart-wrapper p-4">
          <ChartRenderer
            config={chartConfig}
            data={chartData}
            renderingMode="inline"
            height={400}
            onRenderComplete={() => {
              logger.info('🎨 Chart rendering completed, transitioning to complete state');
              onRenderComplete();
            }}
            onRenderError={(error) => {
              logger.error('Chart rendering failed:', error);
            }}
          />
        </div>
        
        {/* Chart metadata footer - only show when complete */}
      {renderingState === 'complete' && (
          <div className="chart-footer px-4 py-3 bg-gray-50 border-t border-gray-200">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-4 text-sm text-gray-600">
                <span>Query: "{userQuery}"</span>
                <span>•</span>
                <span>Data: {chartData?.data?.length || 0} points</span>
                <span>•</span>
                <span>Rendered: {new Date().toLocaleTimeString()}</span>
              </div>
              <button
                onClick={onCreateNew}
                className="px-3 py-1 text-sm bg-blue-50 text-blue-600 rounded hover:bg-blue-100 transition-colors"
              >
                Create New Chart
              </button>
          </div>
            
            {/* Debug info - collapsed by default */}
          <details className="mt-2">
              <summary className="text-xs text-gray-400 cursor-pointer hover:text-gray-600">Debug info</summary>
              <pre className="mt-2 text-xs bg-white p-2 rounded border max-h-32 overflow-auto">
                {JSON.stringify({ config: chartConfig, data: chartData }, null, 2)}
            </pre>
          </details>
        </div>
      )}
      </div>
    </div>
  );
};

const ErrorDisplay: React.FC<{
  message?: string;
  onRetry: () => void;
}> = ({ message, onRetry }) => {
  return (
    <div className="error-display p-4 bg-red-50 rounded-lg">
      <div className="flex items-center justify-between">
        <div>
          <p className="font-medium text-red-900">Error generating chart</p>
          {message && <p className="text-sm text-red-700">{message}</p>}
        </div>
        <button
          onClick={onRetry}
          className="px-3 py-1 bg-red-600 text-white rounded-md hover:bg-red-700 text-sm"
        >
          Try Again
        </button>
      </div>
    </div>
  );
};

export { GraphingBlock }; 
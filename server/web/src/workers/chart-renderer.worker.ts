/**
 * Chart Renderer Web Worker
 * Handles heavy Plotly.js operations off the main thread to prevent UI blocking
 */

// Note: Plotly import removed as it's not needed in worker for data processing
// The worker only processes data and sends optimized config back to main thread

interface RenderMessage {
  type: 'RENDER_CHART';
  payload: {
    config: any;
    data: any;
    containerId: string;
    options: {
      width?: number;
      height?: number;
      performanceMode?: boolean;
    };
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

interface CompleteMessage {
  type: 'RENDER_COMPLETE';
  payload: {
    chartId: string;
    success: boolean;
    renderTime: number;
  };
}

interface ErrorMessage {
  type: 'RENDER_ERROR';
  payload: {
    error: string;
    stage: string;
  };
}

// Main worker message handler
self.onmessage = async (event: MessageEvent<RenderMessage>) => {
  console.log('🎯 Worker received message:', event.data);
  
  const { type, payload } = event.data;
  
  if (type === 'RENDER_CHART') {
    try {
      console.log('🎯 Worker starting chart processing...');
      await renderChart(payload);
    } catch (error) {
      console.error('🎯 Worker error in renderChart:', error);
      const errorMessage: ErrorMessage = {
        type: 'RENDER_ERROR',
        payload: { 
          error: error instanceof Error ? error.message : 'Unknown error',
          stage: 'chart_processing'
        }
      };
      self.postMessage(errorMessage);
    }
  } else {
    console.log('🎯 Worker received unknown message type:', type);
  }
};

// Add global error handler for worker
self.onerror = (error) => {
  console.error('🎯 Worker global error:', error);
  const errorMessage: ErrorMessage = {
    type: 'RENDER_ERROR',
    payload: { 
      error: typeof error === 'string' ? error : (error instanceof ErrorEvent ? error.message : 'Worker global error'),
      stage: 'worker_initialization'
    }
  };
  self.postMessage(errorMessage);
};

async function renderChart(payload: RenderMessage['payload']) {
  const startTime = Date.now();
  const { config, data, containerId, options } = payload;
  
  try {
    // Stage 1: Data Processing
    postProgress('data_processing', 10, 'Processing dataset...');
    const processedData = await processDataForPlotly(data, config);
    
    // Stage 2: Chart Generation
    postProgress('chart_generation', 40, 'Generating chart configuration...');
    const plotlyConfig = await generatePlotlyConfig(config, processedData);
    
    // Stage 3: Performance Optimization
    postProgress('optimization', 70, 'Optimizing for performance...');
    const optimizedConfig = await optimizeForPerformance(plotlyConfig, options);
    
    // Stage 4: Rendering Preparation
    postProgress('rendering', 90, 'Preparing visualization...');
    
    // Instead of actual rendering in worker (which has DOM limitations),
    // send optimized config back to main thread
    const renderTime = Date.now() - startTime;
    
    const completeMessage: CompleteMessage = {
      type: 'RENDER_COMPLETE',
      payload: {
        chartId: containerId,
        success: true,
        renderTime
      }
    };
    
    // Transfer the optimized config back to main thread
    self.postMessage({
      ...completeMessage,
      optimizedConfig
    });
    
  } catch (error) {
    const errorMessage: ErrorMessage = {
      type: 'RENDER_ERROR',
      payload: {
        error: error instanceof Error ? error.message : 'Chart processing failed',
        stage: 'processing'
      }
    };
    self.postMessage(errorMessage);
  }
}

function postProgress(stage: ProgressMessage['payload']['stage'], progress: number, message: string) {
  const progressMessage: ProgressMessage = {
    type: 'RENDER_PROGRESS',
    payload: { stage, progress, message }
  };
  self.postMessage(progressMessage);
}

async function processDataForPlotly(data: any, config: any) {
  // Simulate data processing time
  await new Promise(resolve => setTimeout(resolve, 100));
  
  // Data conversion logic
  const chartData = data.data || [];
  const columns = data.columns || [];
  
  if (chartData.length === 0 || columns.length === 0) {
    return generateSampleData(config.type);
  }
  
  return convertDataByChartType(chartData, columns, config.type);
}

async function generatePlotlyConfig(config: any, processedData: any) {
  // Simulate config generation time
  await new Promise(resolve => setTimeout(resolve, 50));
  
  return {
    data: processedData,
    layout: {
      ...config.layout,
      autosize: true,
      margin: { l: 40, r: 40, t: 40, b: 40 }
    },
    config: {
      responsive: true,
      displayModeBar: true,
      ...config.config
    }
  };
}

async function optimizeForPerformance(plotlyConfig: any, options: any) {
  // Simulate optimization time
  await new Promise(resolve => setTimeout(resolve, 50));
  
  const dataSize = plotlyConfig.data[0]?.x?.length || 0;
  
  // Performance optimizations for large datasets
  if (dataSize > 10000) {
    if (plotlyConfig.data[0].type === 'scatter') {
      // Use WebGL for large scatter plots
      plotlyConfig.data[0].type = 'scattergl';
      plotlyConfig.data[0].marker = { 
        ...plotlyConfig.data[0].marker, 
        size: 2 
      };
    }
  }
  
  // Memory optimization
  if (options.performanceMode) {
    plotlyConfig.config.staticPlot = true;
    plotlyConfig.config.displayModeBar = false;
  }
  
  return plotlyConfig;
}

function generateSampleData(chartType: string) {
  switch (chartType) {
    case 'scatter':
      return [{
        x: Array.from({ length: 10 }, (_, i) => i),
        y: Array.from({ length: 10 }, () => Math.random() * 100),
        type: 'scatter',
        mode: 'markers',
        name: 'Sample Data'
      }];
    case 'bar':
      return [{
        x: ['A', 'B', 'C', 'D', 'E'],
        y: [20, 14, 23, 25, 22],
        type: 'bar',
        name: 'Sample Data'
      }];
    case 'line':
      return [{
        x: Array.from({ length: 10 }, (_, i) => i),
        y: Array.from({ length: 10 }, () => Math.random() * 100),
        type: 'scatter',
        mode: 'lines+markers',
        name: 'Sample Data'
      }];
    default:
      return [{
        x: [1, 2, 3, 4],
        y: [10, 11, 12, 13],
        type: 'scatter',
        mode: 'markers'
      }];
  }
}

function convertDataByChartType(chartData: any[], columns: string[], chartType: string) {
  switch (chartType) {
    case 'bar':
      return [{
        x: chartData.map(row => row[columns[0]] || row.x || row.category || ''),
        y: chartData.map(row => row[columns[1]] || row.y || row.value || 0),
        type: 'bar',
        name: columns[1] || 'Values'
      }];
    case 'line':
      return [{
        x: chartData.map(row => row[columns[0]] || row.x || row.date || ''),
        y: chartData.map(row => row[columns[1]] || row.y || row.value || 0),
        type: 'scatter',
        mode: 'lines+markers',
        name: columns[1] || 'Values'
      }];
    case 'scatter':
      return [{
        x: chartData.map(row => row[columns[0]] || row.x || 0),
        y: chartData.map(row => row[columns[1]] || row.y || 0),
        type: 'scatter',
        mode: 'markers',
        name: 'Data Points'
      }];
    default:
      return [{
        x: chartData.map((_, index) => index),
        y: chartData.map(row => Object.values(row)[0] || 0),
        type: 'scatter',
        mode: 'markers',
        name: 'Data'
      }];
  }
} 
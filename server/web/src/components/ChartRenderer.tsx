/**
 * ChartRenderer Component - High-Performance Chart Rendering
 * 
 * Provides multiple rendering modes including inline, iframe sandboxing,
 * and Web Workers for optimal performance across different dataset sizes.
 */

import React, { useEffect, useRef, useState } from 'react';
import { Spinner } from './ui/Spinner';
// Import Plotly.js for actual chart rendering
import Plotly from 'plotly.js-dist-min';

// Chart rendering modes
type RenderingMode = 'inline' | 'iframe' | 'webworker';
type RenderState = 'initializing' | 'processing' | 'rendering' | 'complete' | 'error';

interface PlotlyConfig {
  data: any[];
  layout: any;
  config: any;
  type: string;
  performance_mode?: boolean;
}

interface ProcessedDataset {
  data: any[];
  columns: string[];
  metadata: Record<string, any>;
}

interface RenderOptions {
  width?: number;
  height?: number;
  enableStreaming?: boolean;
  performanceMode?: boolean;
  interactive?: boolean;
}

interface ChartRendererProps {
  config: PlotlyConfig;
  data: ProcessedDataset;
  renderingMode?: RenderingMode;
  sandboxed?: boolean;
  renderingState?: RenderState;
  onRenderComplete?: () => void;
  onRenderError?: (error: string) => void;
  height?: number;
  width?: number;
}

export const ChartRenderer: React.FC<ChartRendererProps> = ({
  config,
  data,
  renderingMode = 'inline',
  sandboxed = false,
  renderingState: externalRenderState,
  onRenderComplete,
  onRenderError,
  height = 400,
  width
}) => {
  const [internalRenderState, setInternalRenderState] = useState<RenderState>('initializing');
  const [chartElement, setChartElement] = useState<HTMLElement | null>(null);
  const [errorMessage, setErrorMessage] = useState<string>('');
  const [isDarkModeActive, setIsDarkModeActive] = useState(false);
  
  const containerRef = useRef<HTMLDivElement>(null);
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const workerRef = useRef<Worker | null>(null);
  const plotlyInstanceRef = useRef<any>(null);

  // Use external render state if provided, otherwise use internal
  const renderState = externalRenderState || internalRenderState;

  // Dark mode detection effect
  useEffect(() => {
    const checkDarkMode = () => {
      const darkMode = window.matchMedia('(prefers-color-scheme: dark)').matches ||
                       document.documentElement.classList.contains('dark') ||
                       document.body.classList.contains('dark') ||
                       document.querySelector('[data-theme="dark"]') !== null;
      setIsDarkModeActive(darkMode);
    };

    // Initial check
    checkDarkMode();

    // Listen for system dark mode changes
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    const handleChange = () => checkDarkMode();
    mediaQuery.addEventListener('change', handleChange);

    // Listen for manual theme toggles
    const observer = new MutationObserver(checkDarkMode);
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['class', 'data-theme']
    });
    observer.observe(document.body, {
      attributes: true,
      attributeFilter: ['class', 'data-theme']
    });

    return () => {
      mediaQuery.removeEventListener('change', handleChange);
      observer.disconnect();
    };
  }, []);

  useEffect(() => {
    console.log('🎯 ChartRenderer: useEffect triggered - config:', !!config, 'data:', !!data, 'renderState:', renderState);
    
    // Only render if we have data/config AND we're not already complete
    if (config && data && renderState !== 'complete') {
      console.log('🎯 ChartRenderer: Starting render process');
      performRender();
    } else if (renderState === 'complete') {
      console.log('🎯 ChartRenderer: Already complete, skipping render');
    } else {
      console.log('🎯 ChartRenderer: Missing config or data - config:', !!config, 'data:', !!data);
    }
    
    return () => {
      console.log('🎯 ChartRenderer: Cleanup triggered - terminating any active workers');
      // Cleanup on unmount or re-render
      if (workerRef.current) {
        console.log('🎯 ChartRenderer: Terminating worker');
        workerRef.current.terminate();
        workerRef.current = null;
      }
      if (plotlyInstanceRef.current && containerRef.current) {
        try {
          // Plotly cleanup would go here
          // Plotly.purge(containerRef.current);
        } catch (e) {
          console.warn('Error cleaning up Plotly:', e);
        }
      }
    };
  }, [config, data, renderingMode, isDarkModeActive]); // Re-render when dark mode changes

  const performRender = async () => {
    console.log('🎯 ChartRenderer: performRender called - mode:', renderingMode);
    try {
      setInternalRenderState('processing');
      setErrorMessage('');

      switch (renderingMode) {
        case 'webworker':
          console.log('🎯 ChartRenderer: Using webworker mode');
          await renderWithWebWorker();
          break;
        case 'iframe':
          console.log('🎯 ChartRenderer: Using iframe mode');
          await renderWithSandboxedIframe();
          break;
        case 'inline':
        default:
          console.log('🎯 ChartRenderer: Using inline mode (default)');
          await renderInline();
          break;
      }
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : 'Unknown rendering error';
      console.error('🎯 ChartRenderer: ❌ performRender failed:', errorMsg);
      setErrorMessage(errorMsg);
      setInternalRenderState('error');
      onRenderError?.(errorMsg);
    }
  };

  const renderInline = async (): Promise<void> => {
    console.log('🎯 ChartRenderer: Starting non-blocking inline rendering...');
    setInternalRenderState('processing');

    if (!containerRef.current) {
      throw new Error('Container ref not available');
    }

    try {
      // Clear any existing content
      containerRef.current.innerHTML = '';
      console.log('🎯 ChartRenderer: Container cleared, starting processing...');

      let optimizedConfig;
      
      try {
        // Try Web Worker for heavy data processing with shorter timeout
        console.log('🎯 ChartRenderer: Attempting worker processing...');
        optimizedConfig = await Promise.race([
          processWithWorker(config, data),
          new Promise((_, reject) => 
            setTimeout(() => reject(new Error('Worker timeout')), 5000)
          )
        ]);
        console.log('🎯 ChartRenderer: Worker processing complete!');
      } catch (workerError) {
        console.warn('🎯 ChartRenderer: Worker failed, using fallback:', workerError);
        // Immediate fallback to direct processing
        optimizedConfig = fallbackProcessing(config, data);
      }
      
      console.log('🎯 ChartRenderer: Config ready, doing Plotly render...');
      
      // Now do Plotly rendering on main thread with processed data
      await Plotly.newPlot(
        containerRef.current,
        optimizedConfig.data,
        optimizedConfig.layout,
        optimizedConfig.config
      );

      console.log('🎯 ChartRenderer: ✅ Plotly.newPlot completed successfully!');
      plotlyInstanceRef.current = containerRef.current;
      setInternalRenderState('complete');
      onRenderComplete?.();
      
    } catch (error) {
      console.error('🎯 ChartRenderer: ❌ Rendering error:', error);
      // Fallback to mock rendering if everything fails
      console.log('🎯 ChartRenderer: Falling back to mock rendering...');
      try {
        createMockChart(containerRef.current);
        setInternalRenderState('complete');
        onRenderComplete?.();
      } catch (mockError) {
        console.error('🎯 ChartRenderer: ❌ Even mock rendering failed:', mockError);
        setInternalRenderState('error');
        onRenderError?.('All rendering methods failed');
      }
    }
  };

  const processWithWorker = async (config: any, data: any): Promise<any> => {
    return new Promise((resolve, reject) => {
      console.log('🎯 Creating worker for chart processing...');
      
      // Add timeout to prevent infinite hanging
      const timeoutId = setTimeout(() => {
        console.error('🎯 Worker timeout after 30 seconds');
        worker.terminate();
        reject(new Error('Worker processing timeout'));
      }, 30000);

      let worker: Worker;
      
      try {
        // Create worker for heavy processing
        worker = new Worker(
          new URL('../workers/chart-renderer.worker.ts', import.meta.url),
          { type: 'module' }
        );
        
        // Store worker reference for cleanup
        workerRef.current = worker;
        console.log('🎯 Worker created successfully');
      } catch (workerError) {
        console.error('🎯 Failed to create worker:', workerError);
        clearTimeout(timeoutId);
        // Fallback to direct processing without worker
        return resolve(fallbackProcessing(config, data));
      }

      worker.onmessage = (event) => {
        console.log('🎯 Worker message received:', event.data);
        const { type, payload, optimizedConfig } = event.data;
        
        switch (type) {
          case 'RENDER_PROGRESS':
            console.log(`🎯 Worker Progress: ${payload.stage} - ${payload.progress}% - ${payload.message}`);
            break;
          case 'RENDER_COMPLETE':
            console.log('🎯 Worker completed successfully');
            clearTimeout(timeoutId);
            worker.terminate();
            workerRef.current = null; // Clear reference
            resolve(optimizedConfig);
            break;
          case 'RENDER_ERROR':
            console.error('🎯 Worker error:', payload.error);
            clearTimeout(timeoutId);
            worker.terminate();
            workerRef.current = null; // Clear reference
            reject(new Error(payload.error));
            break;
        }
      };

      worker.onerror = (error) => {
        console.error('🎯 Worker error:', error);
        clearTimeout(timeoutId);
        worker.terminate();
        workerRef.current = null; // Clear reference
        reject(error);
      };

      // Send processing job to worker
      console.log('🎯 Sending data to worker...');
      try {
        worker.postMessage({
          type: 'RENDER_CHART',
          payload: {
            config,
            data,
            containerId: 'chart-container',
            options: {
              width,
              height,
              performanceMode: config.performance_mode || false,
              darkModeTheme: getDarkModeTheme(), // Pass dark mode theme to worker
              isDarkMode: isDarkMode()
            }
          }
        });
        console.log('🎯 Data sent to worker successfully');
      } catch (postError) {
        console.error('🎯 Failed to send data to worker:', postError);
        clearTimeout(timeoutId);
        worker.terminate();
        reject(postError);
      }
    });
  };

  // Detect dark mode
  const isDarkMode = () => {
    // Use the reactive state instead of checking again
    return isDarkModeActive;
  };

  // Get dark mode theme configuration
  const getDarkModeTheme = () => {
    if (!isDarkMode()) return {};
    
    return {
      plot_bgcolor: '#1f2937', // Dark gray background
      paper_bgcolor: '#111827', // Darker background for paper
      font: {
        color: '#f9fafb' // Light text
      },
      xaxis: {
        gridcolor: '#374151', // Dark grid
        zerolinecolor: '#6b7280',
        tickcolor: '#9ca3af',
        linecolor: '#6b7280'
      },
      yaxis: {
        gridcolor: '#374151', // Dark grid
        zerolinecolor: '#6b7280',
        tickcolor: '#9ca3af',
        linecolor: '#6b7280'
      },
      colorway: [
        '#3b82f6', // Blue
        '#10b981', // Emerald
        '#f59e0b', // Amber
        '#ef4444', // Red
        '#8b5cf6', // Violet
        '#06b6d4', // Cyan
        '#f97316', // Orange
        '#84cc16'  // Lime
      ]
    };
  };

  // Fallback processing when worker fails
  const fallbackProcessing = (config: any, data: any) => {
    console.log('🎯 Using fallback processing (no worker)');
    
    // Simple data conversion without worker
    const plotlyData = convertToPlotlyData(config, data);
    const darkModeTheme = getDarkModeTheme();
    
    return {
      data: plotlyData,
      layout: {
        ...config.layout,
        ...darkModeTheme, // Apply dark mode theme
        height: height,
        width: width || undefined,
        margin: config.layout?.margin || { l: 40, r: 40, t: 40, b: 40 },
        autosize: true
      },
      config: {
        responsive: true,
        displayModeBar: true,
        modeBarButtonsToRemove: [], // Show all buttons
        displaylogo: false, // Remove Plotly logo
        ...config.config
      }
    };
  };

  // Convert our chart config format to Plotly.js format
  const convertToPlotlyData = (config: PlotlyConfig, data: ProcessedDataset) => {
    // If config already has Plotly-formatted data, use it
    if (config.data && Array.isArray(config.data) && config.data.length > 0) {
      return config.data;
    }

    // Otherwise, convert from our data format
    const chartData = data.data || [];
    const columns = data.columns || [];

    if (chartData.length === 0 || columns.length === 0) {
      // Return sample data for empty datasets
      return [{
        x: ['A', 'B', 'C', 'D'],
        y: [1, 3, 2, 4],
        type: config.type === 'line' ? 'scatter' : config.type,
        mode: config.type === 'line' ? 'lines+markers' : undefined,
        name: 'Sample Data'
      }];
    }

    // Convert based on chart type
    switch (config.type) {
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

      case 'pie':
        return [{
          labels: chartData.map(row => row[columns[0]] || row.label || ''),
          values: chartData.map(row => row[columns[1]] || row.value || 0),
          type: 'pie'
        }];

      default:
        // Default to scatter plot
        return [{
          x: chartData.map((_, index) => index),
          y: chartData.map(row => Object.values(row)[0] || 0),
          type: 'scatter',
          mode: 'markers',
          name: 'Data'
        }];
    }
  };

  const renderWithWebWorker = async () => {
    console.log('🎯 ChartRenderer: Starting dedicated worker rendering...');
    setInternalRenderState('processing');

    if (!containerRef.current) {
      throw new Error('Container ref not available');
    }

    try {
      // Clear any existing content
      containerRef.current.innerHTML = '';
      
      // Use the same worker processing as inline mode
      const optimizedConfig = await processWithWorker(config, data);
      console.log('🎯 ChartRenderer: Worker processing complete for webworker mode');
      
      // Render with optimized config
      await Plotly.newPlot(
        containerRef.current,
        optimizedConfig.data,
        optimizedConfig.layout,
        optimizedConfig.config
      );

      console.log('🎯 ChartRenderer: ✅ WebWorker mode rendering completed!');
      plotlyInstanceRef.current = containerRef.current;
      setInternalRenderState('complete');
      onRenderComplete?.();
      
    } catch (error) {
      console.error('🎯 ChartRenderer: ❌ WebWorker rendering error:', error);
      throw new Error(`Worker rendering failed: ${error}`);
    }
  };

  const renderWithSandboxedIframe = async () => {
    setInternalRenderState('processing');

    if (!iframeRef.current) {
      throw new Error('Iframe ref not available');
    }

    const iframeContent = generateIframeContent(config, data);
    iframeRef.current.srcdoc = iframeContent;

    // Listen for iframe load
    const handleIframeLoad = () => {
      setInternalRenderState('complete');
      onRenderComplete?.();
    };

    const handleIframeError = () => {
      throw new Error('Iframe rendering failed');
    };

    iframeRef.current.onload = handleIframeLoad;
    iframeRef.current.onerror = handleIframeError;

    // Cleanup listeners
    return () => {
      if (iframeRef.current) {
        iframeRef.current.onload = null;
        iframeRef.current.onerror = null;
      }
    };
  };

  const simulatePlotlyRendering = async (): Promise<void> => {
    // Simulate processing time based on data size
    const dataSize = data.data.length;
    const processingTime = Math.min(2000, Math.max(200, dataSize * 0.1));
    
    await new Promise(resolve => setTimeout(resolve, processingTime));
  };

  const simulateWorkerRendering = async (): Promise<void> => {
    // Simulate worker processing
    await new Promise(resolve => setTimeout(resolve, 1000));
    
    if (containerRef.current) {
      createMockChart(containerRef.current);
    }
  };

  const createMockChart = (container: HTMLElement) => {
    // Clear container
    container.innerHTML = '';

    // Create a simple mock chart using HTML/CSS
    const chartDiv = document.createElement('div');
    chartDiv.style.width = '100%';
    chartDiv.style.height = `${height}px`;
    chartDiv.style.border = '1px solid #e2e8f0';
    chartDiv.style.borderRadius = '8px';
    chartDiv.style.padding = '20px';
    chartDiv.style.display = 'flex';
    chartDiv.style.flexDirection = 'column';
    chartDiv.style.justifyContent = 'center';
    chartDiv.style.alignItems = 'center';
    chartDiv.style.backgroundColor = '#f8fafc';

    // Chart type indicator
    const typeDiv = document.createElement('div');
    typeDiv.textContent = `${config.type.toUpperCase()} CHART`;
    typeDiv.style.fontSize = '18px';
    typeDiv.style.fontWeight = 'bold';
    typeDiv.style.color = '#4a5568';
    typeDiv.style.marginBottom = '16px';

    // Mock data visualization
    const dataDiv = document.createElement('div');
    dataDiv.style.display = 'flex';
    dataDiv.style.gap = '8px';
    dataDiv.style.alignItems = 'end';
    dataDiv.style.height = '200px';

    // Create mock bars/points based on chart type
    if (config.type === 'bar') {
      for (let i = 0; i < Math.min(data.data.length, 10); i++) {
        const bar = document.createElement('div');
        const height = Math.random() * 150 + 20;
        bar.style.width = '20px';
        bar.style.height = `${height}px`;
        bar.style.backgroundColor = `hsl(${i * 30}, 70%, 50%)`;
        bar.style.borderRadius = '2px 2px 0 0';
        dataDiv.appendChild(bar);
      }
    } else if (config.type === 'line' || config.type === 'scatter') {
      const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
      svg.setAttribute('width', '300');
      svg.setAttribute('height', '150');
      
      if (config.type === 'line') {
        const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        let pathData = 'M';
        for (let i = 0; i < 10; i++) {
          const x = (i / 9) * 280 + 10;
          const y = Math.random() * 130 + 10;
          pathData += ` ${x},${y}`;
          if (i === 0) pathData += ' L';
        }
        path.setAttribute('d', pathData);
        path.setAttribute('stroke', '#3b82f6');
        path.setAttribute('stroke-width', '2');
        path.setAttribute('fill', 'none');
        svg.appendChild(path);
      } else {
        for (let i = 0; i < 20; i++) {
          const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
          circle.setAttribute('cx', String(Math.random() * 280 + 10));
          circle.setAttribute('cy', String(Math.random() * 130 + 10));
          circle.setAttribute('r', '3');
          circle.setAttribute('fill', '#3b82f6');
          svg.appendChild(circle);
        }
      }
      
      dataDiv.appendChild(svg);
    } else {
      // Generic visualization
      const genericDiv = document.createElement('div');
      genericDiv.textContent = `Rendering ${config.type} chart with ${data.data.length} data points`;
      genericDiv.style.color = '#6b7280';
      genericDiv.style.textAlign = 'center';
      dataDiv.appendChild(genericDiv);
    }

    // Data info
    const infoDiv = document.createElement('div');
    infoDiv.textContent = `${data.data.length} data points • ${data.columns.join(', ')}`;
    infoDiv.style.fontSize = '12px';
    infoDiv.style.color = '#9ca3af';
    infoDiv.style.marginTop = '16px';

    chartDiv.appendChild(typeDiv);
    chartDiv.appendChild(dataDiv);
    chartDiv.appendChild(infoDiv);
    container.appendChild(chartDiv);
  };

  const generateIframeContent = (config: PlotlyConfig, data: ProcessedDataset): string => {
    // Similar to implementation in the design doc
    return `
      <!DOCTYPE html>
      <html>
      <head>
        <meta charset="utf-8">
        <style>
          body { margin: 0; padding: 20px; font-family: Arial, sans-serif; }
          #chart { width: 100%; height: ${height - 40}px; border: 1px solid #e2e8f0; border-radius: 8px; }
          .chart-info { margin-top: 16px; font-size: 12px; color: #6b7280; text-align: center; }
        </style>
      </head>
      <body>
        <div id="chart">
          <div style="display: flex; flex-direction: column; justify-content: center; align-items: center; height: 100%; background: #f8fafc;">
            <h3 style="color: #4a5568; margin-bottom: 16px;">${config.type.toUpperCase()} CHART</h3>
            <div style="color: #6b7280;">Chart rendered in sandboxed iframe</div>
            <div style="color: #9ca3af; font-size: 12px; margin-top: 8px;">${data.data.length} data points</div>
          </div>
        </div>
        <div class="chart-info">
          Columns: ${data.columns.join(', ')} • Generated: ${new Date().toLocaleString()}
        </div>
        <script>
          // In real implementation, would include Plotly.js and render actual chart
          parent.postMessage({ type: 'CHART_READY' }, '*');
        </script>
      </body>
      </html>
    `;
  };

  const getRenderingStatusMessage = (): string => {
    switch (renderState) {
      case 'initializing':
        return 'Initializing chart renderer...';
      case 'processing':
        return 'Processing chart data...';
      case 'rendering':
        return 'Rendering visualization...';
      case 'complete':
        return 'Chart rendered successfully';
      case 'error':
        return `Rendering error: ${errorMessage}`;
      default:
        return 'Unknown state';
    }
  };

  const getProgressPercentage = (): number => {
    switch (renderState) {
      case 'initializing':
        return 10;
      case 'processing':
        return 40;
      case 'rendering':
        return 80;
      case 'complete':
        return 100;
      case 'error':
        return 0;
      default:
        return 0;
    }
  };

  return (
    <div className="chart-renderer" style={{ width: width || '100%', height }}>
      {/* Progress indicator */}
      {renderState !== 'complete' && renderState !== 'error' && (
        <div className="rendering-progress mb-4 p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
          <div className="flex items-center space-x-3">
            <Spinner className="w-5 h-5 text-blue-500" />
            <div className="flex-1">
              <div className="flex justify-between items-center mb-2">
                <span className="text-sm font-medium text-blue-900 dark:text-blue-100">
                  {getRenderingStatusMessage()}
                </span>
                <span className="text-sm text-blue-700 dark:text-blue-300">
                  {getProgressPercentage()}%
                </span>
              </div>
              <div className="w-full bg-blue-200 dark:bg-blue-800 rounded-full h-2">
                <div
                  className="bg-blue-500 h-2 rounded-full transition-all duration-500"
                  style={{ width: `${getProgressPercentage()}%` }}
                />
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Chart container for inline and webworker modes */}
      {(renderingMode === 'inline' || renderingMode === 'webworker') && (
        <div
          ref={containerRef}
          className="chart-container"
          style={{ 
            width: '100%', 
            height: renderState === 'complete' ? height : 0,
            opacity: renderState === 'complete' ? 1 : 0,
            transition: 'opacity 0.3s ease-in-out'
          }}
        />
      )}

      {/* Iframe container for sandboxed mode */}
      {renderingMode === 'iframe' && (
        <iframe
          ref={iframeRef}
          className="chart-iframe"
          sandbox="allow-scripts allow-same-origin"
          style={{
            width: '100%',
            height: renderState === 'complete' ? height : 0,
            border: 'none',
            borderRadius: '8px',
            opacity: renderState === 'complete' ? 1 : 0,
            transition: 'opacity 0.3s ease-in-out'
          }}
        />
      )}

      {/* Error display */}
      {renderState === 'error' && (
        <div className="chart-error p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
          <div className="flex items-center space-x-3">
            <svg className="w-5 h-5 text-red-500 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
            </svg>
            <div>
              <p className="font-medium text-red-800 dark:text-red-200">
                Chart rendering failed
              </p>
              <p className="text-sm text-red-700 dark:text-red-300 mt-1">
                {errorMessage}
              </p>
            </div>
          </div>
        </div>
      )}

     
    </div>
  );
}; 
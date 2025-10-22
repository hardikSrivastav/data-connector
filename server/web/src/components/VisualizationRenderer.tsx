import React from 'react';
import Plot from 'react-plotly.js';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { BarChart3, PieChart, LineChart, TrendingUp, Activity } from 'lucide-react';

interface VisualizationData {
  chart_config: {
    data: any[];
    layout: any;
    config?: any;
    type?: string;
  };
  visualization_data?: {
    dataset_info?: {
      size: number;
      columns: string[];
    };
    performance_metrics?: {
      chart_type: string;
      data_points: number;
    };
    analysis_summary?: {
      chart_type: string;
      rationale: string;
    };
  };
  chart_summary?: {
    type: string;
    title: string;
    data_points: number;
  };
  metadata?: {
    generated_at: string;
    chart_type: string;
    data_points: number;
    user_query: string;
  };
}

interface VisualizationRendererProps {
  data: VisualizationData;
  title?: string;
  className?: string;
}

const getChartIcon = (chartType: string) => {
  switch (chartType?.toLowerCase()) {
    case 'bar':
      return <BarChart3 className="h-4 w-4" />;
    case 'pie':
      return <PieChart className="h-4 w-4" />;
    case 'line':
      return <LineChart className="h-4 w-4" />;
    case 'scatter':
      return <TrendingUp className="h-4 w-4" />;
    case 'histogram':
    case 'heatmap':
      return <Activity className="h-4 w-4" />;
    default:
      return <BarChart3 className="h-4 w-4" />;
  }
};

const getChartTypeColor = (chartType: string) => {
  switch (chartType?.toLowerCase()) {
    case 'bar':
      return 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300';
    case 'pie':
      return 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300';
    case 'line':
      return 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-300';
    case 'scatter':
      return 'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-300';
    case 'histogram':
      return 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300';
    case 'heatmap':
      return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300';
    default:
      return 'bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-300';
  }
};

export const VisualizationRenderer: React.FC<VisualizationRendererProps> = ({
  data,
  title,
  className = ''
}) => {
  const { chart_config, visualization_data, chart_summary, metadata } = data;

  if (!chart_config || !chart_config.data) {
    return (
      <Card className={`w-full ${className}`}>
        <CardContent className="p-6">
          <div className="text-center text-gray-500 dark:text-gray-400">
            <BarChart3 className="h-8 w-8 mx-auto mb-2 opacity-50" />
            <p>No visualization data available</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  // Extract chart information
  const chartType = chart_config.type || 
                   visualization_data?.performance_metrics?.chart_type || 
                   chart_summary?.type || 
                   metadata?.chart_type || 
                   'unknown';

  const chartTitle = title || 
                    chart_config.layout?.title || 
                    chart_summary?.title || 
                    'Visualization';

  const dataPoints = visualization_data?.dataset_info?.size || 
                    visualization_data?.performance_metrics?.data_points || 
                    chart_summary?.data_points || 
                    metadata?.data_points || 
                    0;

  const userQuery = metadata?.user_query;
  const rationale = visualization_data?.analysis_summary?.rationale;

  // Prepare Plotly configuration with responsive defaults
  const plotConfig = {
    responsive: true,
    displayModeBar: true,
    modeBarButtonsToRemove: ['pan2d', 'lasso2d', 'select2d'],
    displaylogo: false,
    ...chart_config.config
  };

  // Ensure layout is responsive
  const plotLayout = {
    ...chart_config.layout,
    autosize: true,
    margin: { l: 50, r: 50, t: 50, b: 50 },
    paper_bgcolor: 'transparent',
    plot_bgcolor: 'transparent',
    font: {
      color: 'currentColor'
    }
  };

  return (
    <Card className={`w-full ${className}`}>
      <CardHeader className="pb-4">
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <CardTitle className="text-lg font-semibold flex items-center gap-2">
              {getChartIcon(chartType)}
              {chartTitle}
            </CardTitle>
            {userQuery && (
              <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                Query: {userQuery}
              </p>
            )}
          </div>
          <div className="flex gap-2">
            <Badge 
              variant="secondary" 
              className={getChartTypeColor(chartType)}
            >
              {chartType.toUpperCase()}
            </Badge>
            {dataPoints > 0 && (
              <Badge variant="outline">
                {dataPoints} points
              </Badge>
            )}
          </div>
        </div>
        {rationale && (
          <p className="text-sm text-gray-600 dark:text-gray-400 mt-2">
            {rationale}
          </p>
        )}
      </CardHeader>
      <CardContent className="p-0">
        <div className="w-full h-96 p-4">
          <Plot
            data={chart_config.data}
            layout={plotLayout}
            config={plotConfig}
            style={{ width: '100%', height: '100%' }}
            className="w-full h-full"
            useResizeHandler={true}
          />
        </div>
        {visualization_data?.dataset_info?.columns && (
          <div className="px-4 pb-4">
            <details className="text-sm">
              <summary className="cursor-pointer text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200">
                Dataset Info ({visualization_data.dataset_info.columns.length} columns)
              </summary>
              <div className="mt-2 flex flex-wrap gap-1">
                {visualization_data.dataset_info.columns.map((column, index) => (
                  <Badge key={index} variant="outline" className="text-xs">
                    {column}
                  </Badge>
                ))}
              </div>
            </details>
          </div>
        )}
      </CardContent>
    </Card>
  );
};
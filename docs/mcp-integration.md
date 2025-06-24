# MCP Integration for Frontend Tools

## Overview

This implementation provides a comprehensive Model Context Protocol (MCP) integration that enables LLMs to create rich interactive components like charts and canvases directly in the frontend. The system consists of local MCP servers that expose frontend capabilities as tools that can be called by language models.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     LLM Client                              │
│  (Calls tools to create charts, canvases, etc.)            │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│                 MCPManager                                  │
│  • Coordinates all MCP servers                             │
│  • Routes tool calls to appropriate servers                │
│  • Builds tool context for LLM                            │
└─────────────────────┬───────────────────────────────────────┘
                      │
        ┌─────────────┼─────────────┐
        │             │             │
┌───────▼────┐ ┌──────▼─────┐ ┌─────▼──────┐
│ChartRenderer│ │CanvasBlock │ │ TextTools  │
│   Server    │ │   Server   │ │   Server   │
└─────────────┘ └────────────┘ └────────────┘
```

## Components

### 1. MCPManager
Central coordinator that manages all MCP servers and tool execution.

```typescript
import { MCPManager } from '@/lib/mcp';

const mcpManager = new MCPManager({
  enableLocalServers: true,
  enableRemoteServers: false,
  enabledLocalServers: ['chart-renderer', 'canvas-block', 'text-tools']
});

await mcpManager.initialize();
```

### 2. ChartRenderer Server
Creates interactive chart visualizations.

**Available Tools:**
- `create_bar_chart`: Bar charts with customizable styling
- `create_line_chart`: Line charts for time series data
- `create_pie_chart`: Pie charts for categorical data
- `create_scatter_plot`: Scatter plots with optional trendlines
- `create_multi_series_chart`: Charts with multiple data series

**Example Usage:**
```typescript
const chartResult = await mcpManager.executeTool('create_bar_chart', {
  data: [
    { x: 'Jan', y: 100 },
    { x: 'Feb', y: 150 },
    { x: 'Mar', y: 120 }
  ],
  title: 'Monthly Sales',
  xAxisLabel: 'Month',
  yAxisLabel: 'Sales ($)',
  color: '#3b82f6'
});
```

### 3. CanvasBlock Server
Creates analysis canvases for data exploration and insights.

**Available Tools:**
- `create_canvas_analysis`: Comprehensive analysis with data and insights
- `create_data_canvas`: Data-focused canvas for tabular information
- `update_canvas_analysis`: Update existing canvas with new analysis
- `create_summary_canvas`: Summary canvas with key points and metrics
- `create_insight_canvas`: Insights canvas with categorized findings

**Example Usage:**
```typescript
const canvasResult = await mcpManager.executeTool('create_canvas_analysis', {
  threadName: 'Q1 Sales Analysis',
  originalQuery: 'Analyze Q1 sales performance',
  analysis: 'Q1 showed strong growth...',
  data: {
    headers: ['Month', 'Sales', 'Growth'],
    rows: [['Jan', 10000, '5%'], ['Feb', 12000, '20%']]
  },
  insights: ['Mobile sales up 40%', 'New customers +25%']
});
```

## Integration with ToolRegistry

The MCP system integrates seamlessly with the existing ToolRegistry:

```typescript
import { ToolRegistry } from '@/lib/tools/tool-registry';

const toolRegistry = new ToolRegistry();

// Initialize with MCP integration
await toolRegistry.initializeWithMCP({
  enableLocalServers: true,
  enabledLocalServers: ['chart-renderer', 'canvas-block']
});

// Execute tools through registry (checks local tools first, then MCP)
const result = await toolRegistry.executeTool('create_bar_chart', chartData);

// Get comprehensive tool context for LLM
const toolContext = toolRegistry.buildToolContext();
```

## Tool Context for LLM

The system automatically builds a comprehensive tool context that can be included in LLM prompts:

```typescript
const context = mcpManager.buildToolContext();
```

**Example Output:**
```
Available tools for creating rich responses:

## Frontend Tools (Local MCP Servers)

### chart-renderer
- **create_bar_chart**: Create a bar chart visualization with customizable styling
- **create_line_chart**: Create a line chart for time series or continuous data
- **create_pie_chart**: Create a pie chart for categorical data distribution
- **create_scatter_plot**: Create a scatter plot with optional trendline
- **create_multi_series_chart**: Create charts with multiple data series

### canvas-block
- **create_canvas_analysis**: Create a comprehensive analysis canvas with data and insights
- **create_data_canvas**: Create a data-focused canvas for tabular information
- **update_canvas_analysis**: Update an existing canvas with new analysis
- **create_summary_canvas**: Create a summary canvas with key points and metrics
- **create_insight_canvas**: Create an insights canvas with categorized findings

Usage: Call these functions to generate different types of blocks, then format your response with the appropriate block tags like <chartBlock>, <canvasBlock>, etc.
```

## Block Creation Flow

1. **LLM receives user query**: "Create a chart showing monthly sales"
2. **LLM calls tool**: `create_bar_chart({ data: [...], title: "Monthly Sales" })`
3. **MCP system executes**: ChartRenderer creates chart configuration
4. **Result returned**: Chart configuration with metadata
5. **LLM formats response**: Includes `<chartBlock>` with chart data
6. **Frontend renders**: BlockRouter processes chartBlock and renders visualization

## Error Handling

The system includes comprehensive error handling:

```typescript
try {
  const result = await mcpManager.executeTool('create_chart', invalidData);
} catch (error) {
  // Errors include:
  // - tool_not_found: Tool doesn't exist
  // - validation_error: Input validation failed
  // - execution_error: Tool execution failed
  // - mcp_execution_error: MCP-specific errors
}
```

## Performance Features

- **Parallel execution**: Multiple tools can be executed simultaneously
- **Caching**: Tool mappings cached for quick lookup
- **Lazy initialization**: Servers only initialized when needed
- **Resource cleanup**: Proper cleanup of all resources

## Configuration Options

```typescript
interface MCPManagerConfig {
  enableRemoteServers?: boolean;    // Connect to remote MCP servers
  remoteServerUrl?: string;         // Remote server URL
  enableLocalServers?: boolean;     // Enable local frontend servers
  enabledLocalServers?: string[];   // Which local servers to enable
}
```

## Development and Testing

Run the comprehensive test suite:

```bash
npx tsx server/web/src/scripts/test-mcp-integration.ts
```

The test covers:
- MCPManager initialization
- Chart tool execution (bar, line, pie charts)
- Canvas tool execution (analysis, data, insights)
- Tool discovery and context building
- ToolRegistry integration
- Performance testing
- Resource cleanup

## Future Enhancements

1. **Additional Tool Servers**:
   - Table manipulation tools
   - Code execution tools
   - Embed block tools
   - File upload/processing tools

2. **Enhanced Features**:
   - Tool permissions and rate limiting
   - Real-time tool discovery updates
   - Tool versioning and compatibility
   - Advanced error recovery

3. **Integration Improvements**:
   - React component integration
   - Real-time collaboration
   - Tool usage analytics
   - Performance monitoring

## Usage in Production

1. **Initialize MCP system** during application startup
2. **Include tool context** in LLM prompts
3. **Process tool calls** from LLM responses
4. **Render blocks** using existing BlockRouter system
5. **Handle errors** gracefully with fallbacks

This MCP integration provides a powerful foundation for creating rich, interactive content through natural language interactions with LLMs. 
# LLM Frontend Tools: Dynamic Tool Discovery & Part-Based Response Architecture

## Overview

This document outlines the implementation of a dynamic tool discovery system that allows our LLM to intelligently choose and utilize frontend components (ChartRenderer, BlockTypeSelector, etc.) through function calls, then return structured, streamable responses using XML-like part tags.

## Architecture Philosophy

Instead of hardcoded routing logic that forces specific tools at specific times, we implement:

1. **Dynamic Tool Registry**: LLM discovers available tools through MCP (Model Context Protocol)
2. **Function-Based Tool Calling**: LLM uses function calls to generate different types of blocks
3. **Part-Based Response Structure**: LLM returns XML-tagged parts that frontend parses and routes
4. **Instant Streaming**: All responses are instantly streamable and transparent

## Core Flow

```
User Query → LLM Tool Discovery → Function Calls → Structured Response → Frontend Parsing
     ↓              ↓                   ↓                ↓                  ↓
"Analyze sales" → [text, chart] → create_chart() → <chartBlock>...</chartBlock> → ChartRenderer
```

## Part-Based Response Structure

### Response Format

```xml
<textBlock>Here's the analysis of your sales data...</textBlock>
<chartBlock>{"type": "bar", "data": [...], "config": {...}}</chartBlock>
<canvasBlock>Let's dive deeper into the implications...</canvasBlock>
```

### Supported Block Types

| Block Type | Purpose | Content Format |
|------------|---------|----------------|
| `<textBlock>` | Narrative explanations | Plain text/markdown |
| `<chartBlock>` | Data visualizations | JSON config for ChartRenderer |
| `<canvasBlock>` | Interactive analysis | Canvas thread data |
| `<codeBlock>` | Code examples | Language + code content |
| `<tableBlock>` | Structured data | Table configuration |
| `<imageBlock>` | Generated images | Image data/URLs |
| `<embedBlock>` | External content | Embed configurations |

### Streaming Implementation

```typescript
// Frontend parsing during streaming
const parseStreamChunk = (chunk: string) => {
  const blockPattern = /<(\w+Block)>(.*?)<\/\1>/gs;
  const matches = chunk.matchAll(blockPattern);
  
  for (const match of matches) {
    const [fullMatch, blockType, content] = match;
    routeToRenderer(blockType, content);
  }
};

const routeToRenderer = (blockType: string, content: string) => {
  switch (blockType) {
    case 'chartBlock':
      return <ChartRenderer config={JSON.parse(content)} />;
    case 'canvasBlock':
      return <CanvasBlock data={JSON.parse(content)} />;
    case 'textBlock':
      return <TextRenderer content={content} />;
    // ... other block types
  }
};
```

## Tool Storage & Discovery Architecture

### MCP Server Registry

Each frontend component becomes an MCP Server exposing its capabilities:

```typescript
// ChartRenderer MCP Server
class ChartRendererServer implements MCPServer {
  name = "chart-renderer";
  version = "1.0.0";
  
  tools = [
    {
      name: "create_bar_chart",
      description: "Create a bar chart visualization",
      inputSchema: {
        type: "object",
        properties: {
          data: { type: "array" },
          xAxis: { type: "string" },
          yAxis: { type: "string" },
          title: { type: "string" }
        }
      }
    },
    {
      name: "create_line_chart",
      description: "Create a line chart for time series data",
      inputSchema: { /* ... */ }
    }
    // ... other chart types
  ];
  
  async executeTool(name: string, args: any) {
    switch (name) {
      case "create_bar_chart":
        return this.generateBarChartConfig(args);
      // ... other implementations
    }
  }
}
```

### Central Tool Registry

```typescript
// server/web/src/lib/tools/registry.ts
class ToolRegistry {
  private servers = new Map<string, MCPServer>();
  
  registerServer(server: MCPServer) {
    this.servers.set(server.name, server);
  }
  
  async getAvailableTools(): Promise<ToolDescription[]> {
    const allTools = [];
    for (const server of this.servers.values()) {
      allTools.push(...server.tools.map(tool => ({
        ...tool,
        server: server.name
      })));
    }
    return allTools;
  }
  
  async executeTool(serverName: string, toolName: string, args: any) {
    const server = this.servers.get(serverName);
    if (!server) throw new Error(`Server ${serverName} not found`);
    return await server.executeTool(toolName, args);
  }
}
```

### Dynamic Tool Discovery

```typescript
// LLM Context Enhancement
class LLMToolContext {
  constructor(private registry: ToolRegistry) {}
  
  async buildToolContext(): Promise<string> {
    const tools = await this.registry.getAvailableTools();
    
    return `
Available tools for creating rich responses:

${tools.map(tool => `
**${tool.name}** (${tool.server})
Description: ${tool.description}
Input: ${JSON.stringify(tool.inputSchema, null, 2)}
`).join('\n')}

Usage: Call these functions to generate different types of blocks, then format your response with the appropriate block tags.
`;
  }
}
```

## Implementation Strategy

### Phase 1: Core Infrastructure

1. **Tool Registry Setup**
   ```typescript
   // server/web/src/lib/tools/
   ├── registry.ts          # Central tool registry
   ├── mcp-server.ts        # MCP server interface
   └── discovery.ts         # Tool discovery logic
   ```

2. **Block Type Definitions**
   ```typescript
   // server/web/src/types/blocks.ts
   export interface BlockPart {
     type: 'textBlock' | 'chartBlock' | 'canvasBlock' | /* ... */;
     content: string;
     metadata?: Record<string, any>;
   }
   ```

3. **Response Parser**
   ```typescript
   // server/web/src/lib/parsing/response-parser.ts
   export class ResponseParser {
     parsePartResponse(response: string): BlockPart[]
     streamParse(chunk: string): Partial<BlockPart>[]
   }
   ```

### Phase 2: MCP Server Implementation

1. **ChartRenderer MCP Server**
   ```typescript
   // server/web/src/components/ChartRenderer/mcp-server.ts
   export class ChartRendererMCPServer implements MCPServer {
     // Implementation for chart creation tools
   }
   ```

2. **Canvas MCP Server**
   ```typescript
   // server/web/src/components/CanvasBlock/mcp-server.ts
   export class CanvasMCPServer implements MCPServer {
     // Implementation for canvas analysis tools
   }
   ```

3. **Block Type Selector MCP Server**
   ```typescript
   // server/web/src/components/BlockTypeSelector/mcp-server.ts
   export class BlockTypeMCPServer implements MCPServer {
     // Implementation for different block creation tools
   }
   ```

### Phase 3: LLM Integration

1. **Enhanced LLM Client**
   ```python
   # server/agent/llm/enhanced-client.py
   class EnhancedLLMClient:
       def __init__(self, tool_registry: ToolRegistry):
           self.tool_registry = tool_registry
           
       async def generate_with_tools(self, prompt: str) -> AsyncIterator[str]:
           # Build tool context
           tool_context = await self.tool_registry.build_context()
           
           # Enhanced prompt with tool descriptions
           enhanced_prompt = f"""
           {tool_context}
           
           User Request: {prompt}
           
           Instructions:
           1. Analyze what types of output would best serve this request
           2. Use the available tools to generate appropriate content
           3. Format your response using the block tags: <textBlock>, <chartBlock>, etc.
           4. Ensure all content is wrapped in appropriate block tags
           """
           
           # Stream response with tool calling
           async for chunk in self.stream_with_functions(enhanced_prompt):
               yield chunk
   ```

2. **Function Call Handler**
   ```typescript
   // server/web/src/lib/llm/function-handler.ts
   export class FunctionCallHandler {
     constructor(private registry: ToolRegistry) {}
     
     async handleFunctionCall(call: FunctionCall): Promise<string> {
       const result = await this.registry.executeTool(
         call.server,
         call.function,
         call.arguments
       );
       
       // Convert result to appropriate block format
       return this.formatAsBlock(call.function, result);
     }
   }
   ```

### Phase 4: Frontend Integration

1. **Enhanced AIQuerySelector**
   ```typescript
   // server/web/src/components/AIQuerySelector.tsx
   const AIQuerySelector = () => {
     const handleQuery = async (query: string) => {
       const response = await llmClient.generateWithTools(query);
       
       // Parse streaming response into blocks
       for await (const chunk of response) {
         const parts = responseParser.streamParse(chunk);
         parts.forEach(part => {
           if (part.type && part.content) {
             renderBlock(part);
           }
         });
       }
     };
   };
   ```

2. **Block Router Component**
   ```typescript
   // server/web/src/components/BlockRouter.tsx
   const BlockRouter = ({ blockPart }: { blockPart: BlockPart }) => {
     switch (blockPart.type) {
       case 'chartBlock':
         return <ChartRenderer config={JSON.parse(blockPart.content)} />;
       case 'canvasBlock':
         return <CanvasBlock data={JSON.parse(blockPart.content)} />;
       case 'textBlock':
         return <TextRenderer content={blockPart.content} />;
       default:
         return <div>Unknown block type: {blockPart.type}</div>;
     }
   };
   ```

## Integration with Existing Architecture

### StreamingStatusBlock Enhancement

```typescript
// server/web/src/components/StreamingStatusBlock.tsx
const StreamingStatusBlock = ({ streamingState }: Props) => {
  const [parsedBlocks, setParsedBlocks] = useState<BlockPart[]>([]);
  
  useEffect(() => {
    if (streamingState.chunks) {
      const newBlocks = responseParser.parsePartResponse(
        streamingState.chunks.join('')
      );
      setParsedBlocks(newBlocks);
    }
  }, [streamingState.chunks]);
  
  return (
    <div className="streaming-response">
      {parsedBlocks.map((block, index) => (
        <BlockRouter key={index} blockPart={block} />
      ))}
      {streamingState.isStreaming && <StreamingIndicator />}
    </div>
  );
};
```

### PageEditor Integration

```typescript
// server/web/src/components/PageEditor.tsx
const PageEditor = () => {
  const handleToolResponse = (response: string) => {
    const blocks = responseParser.parsePartResponse(response);
    
    blocks.forEach(blockPart => {
      // Create new block for each part
      const blockId = generateBlockId();
      const block = createBlockFromPart(blockPart, blockId);
      onAddBlock(block);
    });
  };
};
```

## Auxiliary Focus Areas

### 1. Performance Optimization

- **Streaming Efficiency**: Minimize parsing overhead during streaming
- **Tool Registry Caching**: Cache tool descriptions and capabilities
- **Block Rendering**: Optimize re-renders with React.memo and useMemo
- **Memory Management**: Clean up unused tool servers and parsed blocks

### 2. Error Handling & Resilience

- **Tool Failure Handling**: Graceful degradation when tools fail
- **Malformed Response Recovery**: Parser error handling for invalid XML
- **Network Resilience**: Retry logic for tool server communication
- **Validation**: Input/output validation for all tool calls

### 3. Developer Experience

- **Tool Development Kit**: Easy framework for creating new MCP servers
- **Debug Tools**: Visualization of tool discovery and function calls
- **Testing Framework**: Unit tests for tool registry and response parsing
- **Documentation**: Auto-generated docs from tool schemas

### 4. Security & Validation

- **Tool Permissions**: Access control for sensitive tools
- **Input Sanitization**: Validate all tool inputs and outputs
- **Rate Limiting**: Prevent abuse of expensive tools
- **Audit Logging**: Track tool usage and function calls

### 5. Extensibility

- **Plugin Architecture**: Easy registration of new tool types
- **Custom Block Types**: Framework for adding new block renderers  
- **Tool Composition**: Ability to chain multiple tools together
- **Configuration**: Runtime configuration of tool availability

## Migration Strategy

### Phase 1: Parallel Implementation
- Implement new system alongside existing CanvasBlock
- Add feature flag to toggle between old and new responses
- Test with subset of queries

### Phase 2: Gradual Rollout
- Enable for specific query types (e.g., data analysis)
- Monitor performance and user satisfaction
- Iterate based on feedback

### Phase 3: Full Migration
- Migrate all query types to new system
- Remove old CanvasBlock-only responses
- Optimize based on usage patterns

## Success Metrics

- **Tool Discovery Accuracy**: % of queries that select appropriate tools
- **Response Time**: Latency from query to first block render
- **User Satisfaction**: Preference for multi-block vs single-block responses
- **System Reliability**: Uptime and error rates for tool registry
- **Developer Adoption**: Number of new tools added by team

This architecture provides a foundation for intelligent, multi-modal LLM responses while maintaining the flexibility to add new tools and block types without modifying core routing logic. 
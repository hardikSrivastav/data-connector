# LangGraph Integration for Ceneca

This module provides enhanced database querying capabilities through LangGraph orchestration while preserving all existing Ceneca functionality.

## Overview

The LangGraph integration adds advanced workflow orchestration to Ceneca's multi-tier LLM infrastructure:

- **AWS Bedrock** as primary LLM (Claude-3 Sonnet)
- **Anthropic** and **OpenAI** as intelligent fallbacks
- **Dynamic graph construction** based on query complexity
- **Enhanced parallelism** (up to 16 concurrent operations vs previous 4)
- **Hybrid operation** - preserves existing trivial routing performance
- **Real-time streaming** with progress tracking

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                 LangGraph Integration                       │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────┐ │
│  │ Routing Engine  │  │ Graph Builder   │  │ Streaming    │ │
│  │ • Complexity    │  │ • Dynamic       │  │ • Real-time  │ │
│  │   Analysis      │  │   Construction  │  │   Progress   │ │
│  │ • Smart         │  │ • Optimization  │  │ • Error      │ │
│  │   Fallbacks     │  │ • Templates     │  │   Recovery   │ │
│  └─────────────────┘  └─────────────────┘  └──────────────┘ │
├─────────────────────────────────────────────────────────────┤
│                    LLM Tier (Enhanced)                     │
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────┐ │
│  │ AWS Bedrock     │  │ Anthropic       │  │ OpenAI       │ │
│  │ (Primary)       │  │ (Fallback 1)    │  │ (Fallback 2) │ │
│  │ Claude-3 Sonnet │  │ Claude-3 Sonnet │  │ GPT-4 Turbo  │ │
│  └─────────────────┘  └─────────────────┘  └──────────────┘ │
├─────────────────────────────────────────────────────────────┤
│              Preserved Existing Infrastructure             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────┐ │
│  │ Trivial Routing │  │ Planning Agent  │  │ Database     │ │
│  │ (200-500ms)     │  │ (Enhanced)      │  │ Connectors   │ │
│  └─────────────────┘  └─────────────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## Installation

1. Install dependencies:
```bash
pip install -r server/agent/langgraph/requirements.txt
```

2. Configure AWS credentials for Bedrock:
```bash
export AWS_REGION=us-east-1
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
```

3. Set up fallback API keys (optional but recommended):
```bash
export ANTHROPIC_API_KEY=your_anthropic_key
export OPENAI_API_KEY=your_openai_key
```

## Quick Start

### Basic Usage

```python
from server.agent.langgraph.integration import LangGraphIntegrationOrchestrator

# Initialize the orchestrator
orchestrator = LangGraphIntegrationOrchestrator({
    "complexity_threshold": 5,
    "use_langgraph_for_complex": True
})

# Process a query (automatic routing based on complexity)
result = await orchestrator.process_query(
    question="Analyze customer purchase patterns across our databases",
    session_id="session_123",
    databases_available=["postgres", "mongodb", "qdrant"]
)

print(f"Used workflow: {result['execution_metadata']['routing_method']}")
print(f"Results: {result['final_result']}")
```

### Force LangGraph for Testing

```python
# Force LangGraph usage regardless of complexity
result = await orchestrator.process_query(
    question="Simple customer count",
    session_id="test_session",
    force_langgraph=True
)
```

### Stream Progress Updates

```python
async def stream_callback(chunk):
    if chunk.get("type") == "progress":
        print(f"Progress: {chunk['progress']:.1f}% - {chunk['message']}")
    elif chunk.get("type") == "result":
        print(f"Result: {chunk['result_data']}")

result = await orchestrator.process_query(
    question="Complex multi-database analysis",
    session_id="stream_session",
    stream_callback=stream_callback
)
```

## Configuration

The integration is controlled by `config.yaml`:

### Key Settings

- **complexity_threshold**: Queries above this complexity (1-10) use LangGraph
- **max_parallel_operations**: Enhanced from 4 to 16 concurrent operations
- **preserve_trivial_routing**: Keep fast routing for simple queries
- **enable_optimization**: Use LLM-driven graph optimization

### LLM Fallback Chain

1. **AWS Bedrock** (Claude-3 Sonnet) - Primary choice
2. **Anthropic** (Claude-3 Sonnet) - First fallback
3. **OpenAI** (GPT-4 Turbo) - Second fallback

Each has circuit breaker protection for automatic failover.

## Performance Optimization

### Automatic Routing

The system automatically routes queries based on complexity:

- **Complexity 1-5**: Traditional workflow (preserves 200-500ms performance)
- **Complexity 6-7**: Hybrid workflow (LangGraph orchestration + existing components)
- **Complexity 8-10**: Full LangGraph workflow (advanced parallelism)

### Enhanced Parallelism

- **Database pools**: Optimized concurrency per database type
- **Intelligent batching**: Groups operations by complexity and dependencies
- **Adaptive resource management**: Dynamically adjusts parallelism

### Performance Monitoring

```python
# Get integration status
status = orchestrator.get_integration_status()
print(f"Executions: Traditional={status['execution_statistics']['traditional_executions']}")
print(f"Executions: LangGraph={status['execution_statistics']['langgraph_executions']}")

# Analyze performance for optimization
optimization = await orchestrator.optimize_future_queries()
print(f"Recommendations: {optimization['recommendations']}")
```

## Migration Strategy

### Phase 1: Hybrid Operation (Current)

```python
# Enable hybrid mode - LangGraph for complex queries only
orchestrator = LangGraphIntegrationOrchestrator({
    "complexity_threshold": 5,
    "preserve_trivial_routing": True
})
```

### Phase 2: Gradual Migration

```python
# Lower threshold to route more queries to LangGraph
orchestrator = LangGraphIntegrationOrchestrator({
    "complexity_threshold": 3,  # More queries use LangGraph
    "preserve_trivial_routing": True
})
```

### Phase 3: Full Migration Assessment

```python
# Check migration readiness
migration_status = await orchestrator.migrate_to_full_langgraph()
if migration_status["migration_ready"]:
    print("Ready for full LangGraph migration!")
    print(f"Readiness score: {migration_status['readiness_score']}/100")
```

## Components

### State Management (`state.py`)
- **HybridStateManager**: Bridges LangGraph TypedDict with existing sessions
- **LangGraphState**: Typed state for graph operations
- **Persistent storage**: Maintains state across graph execution

### Streaming (`streaming.py`)
- **StreamingGraphCoordinator**: Real-time progress updates
- **Error propagation**: Graceful error handling with recovery
- **Performance tracking**: Node-level timing and metrics

### Nodes (`nodes/`)
- **MetadataCollectionNode**: Enhanced schema discovery
- **PlanningNode**: Wraps existing PlanningAgent with streaming
- **ExecutionNode**: Enhanced parallelism (16 vs 4 operations)

### Graph Builder (`graphs/builder.py`)
- **Dynamic construction**: Builds optimal graphs based on query analysis
- **Template system**: Pre-optimized graphs for common patterns
- **LLM optimization**: Uses AI to optimize graph structure

### Bedrock Client (`graphs/bedrock_client.py`)
- **Primary LLM**: AWS Bedrock Claude-3 Sonnet
- **Circuit breakers**: Automatic failover to Anthropic/OpenAI
- **Specialized prompts**: Optimized for graph operations

## Error Handling

The integration includes comprehensive error handling:

### Circuit Breaker Pattern
```python
# Automatic failover when a client fails
client_status = orchestrator.llm_client.get_client_status()
print(f"Bedrock status: {client_status['circuit_breakers']['bedrock']['status']}")
```

### Graceful Degradation
- LangGraph failures → Hybrid workflow
- Hybrid failures → Traditional workflow
- All failures → Cached results or meaningful error messages

### Retry Logic
- Exponential backoff for transient failures
- Smart retry based on error type
- Circuit breaker reset after timeout

## Monitoring and Debugging

### Enable Debug Logging
```python
import logging
logging.getLogger("server.agent.langgraph").setLevel(logging.DEBUG)
```

### Performance Tracking
```python
# Get detailed execution stats
stats = orchestrator.execution_stats
print(f"Performance improvements: {len(stats['performance_improvements'])}")

# Analyze method performance
for record in stats['performance_improvements'][-5:]:
    print(f"{record['method']}: {record['execution_time']:.2f}s (complexity: {record['complexity']})")
```

## Development

### Running Tests
```bash
cd server/agent/langgraph
python -m pytest tests/ -v
```

### Adding Custom Nodes
```python
from server.agent.langgraph.streaming import StreamingNodeBase

class CustomAnalysisNode(StreamingNodeBase):
    def __init__(self):
        super().__init__("custom_analysis")
    
    async def stream(self, state, **kwargs):
        # Your custom logic with streaming
        yield self.create_progress_chunk(50, "Custom analysis in progress")
        # ... analysis logic ...
        yield self.create_result_chunk({"analysis": "completed"})
```

### Extending Graph Templates
```python
# Add custom template to graph builder
orchestrator.graph_builder.graph_templates["custom_template"] = {
    "nodes": [...],
    "edges": [...],
    "complexity": 7,
    "estimated_time": 60
}
```

## Troubleshooting

### Common Issues

1. **AWS Bedrock Access Denied**
   - Check AWS credentials and region
   - Verify Bedrock model access permissions

2. **High Latency**
   - Check complexity threshold (might be routing simple queries to LangGraph)
   - Verify database connection pools

3. **Circuit Breaker Open**
   - Check LLM API status
   - Review error logs for failure patterns

### Configuration Validation
```python
# Verify configuration
status = orchestrator.get_integration_status()
if not status["integration_active"]:
    print("Integration not properly configured")
    print(f"Component status: {status['components_status']}")
```

## Contributing

When extending the LangGraph integration:

1. **Preserve existing functionality** - never break traditional workflows
2. **Add streaming support** - all new components should support progress updates
3. **Include error handling** - implement circuit breaker patterns
4. **Document performance impact** - measure and document any changes
5. **Follow the hybrid pattern** - allow gradual adoption

## Support

For questions or issues:
1. Check the logs: `logs/langgraph_integration.log`
2. Review configuration: `config.yaml`
3. Monitor status: `orchestrator.get_integration_status()`
4. Analyze performance: `orchestrator.optimize_future_queries()` 
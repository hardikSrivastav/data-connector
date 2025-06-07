# Streaming Implementation Guide: End-to-End Real-Time Query Processing

## Overview

This document provides a comprehensive implementation guide for adding streaming capabilities to Ceneca's query processing pipeline. The goal is to enable real-time progress updates as queries move through the system, from initial processing to final analysis delivery.

## Current Architecture Analysis

### Existing Components Requiring Streaming Versions

#### 1. LLM Client Layer (`server/agent/llm/client.py`)
**Current Methods Requiring Streaming:**
- `generate_sql()` - Lines 156-180 (OpenAI client)
- `generate_mongodb_query()` - Lines 182-220 (OpenAI client) 
- `analyze_results()` - Lines 222-260 (OpenAI client)
- `orchestrate_analysis()` - Lines 262-400 (OpenAI client)
- Corresponding methods in `AnthropicClient` class - Lines 600-900

#### 2. Query Engine Layer (`server/agent/db/execute.py`)
**Current Methods Requiring Streaming:**
- `process_ai_query()` - Lines 680-778 (main entry point)
- `execute_cross_database_query()` - Lines 280-450 (CrossDatabaseQueryEngine)
- `execute_single_database_query()` - Lines 180-279 (CrossDatabaseQueryEngine)
- Individual database execution methods:
  - `_execute_postgres_query()` - Lines 452-490
  - `_execute_mongodb_query()` - Lines 492-530
  - `_execute_qdrant_query()` - Lines 532-570
  - `_execute_slack_query()` - Lines 572-610

#### 3. API Endpoints Layer (`server/agent/api/endpoints.py`)
**Current Endpoints Requiring Streaming:**
- `/query` endpoint - Lines 82-130
- `/cross-database-query` endpoint - Lines 132-200
- `/classify` endpoint - Lines 202-230

#### 4. Frontend Layer (`server/web/src/components/AIQuerySelector.tsx`)
**Current Component Requiring Streaming:**
- `handleSubmit()` method - Lines 95-102
- `onQuerySubmit` prop handling - Lines 20-25
- Loading state management - Lines 40-50

---

## Phase 1: LLM Client Streaming Foundation

### 1.1 OpenAI Client Streaming Methods

**New Methods to Create:**
- `generate_sql_stream(prompt: str) -> AsyncIterator[Dict[str, Any]]`
- `generate_mongodb_query_stream(prompt: str) -> AsyncIterator[Dict[str, Any]]`
- `analyze_results_stream(rows: List[Dict], is_vector_search: bool) -> AsyncIterator[Dict[str, Any]]`
- `orchestrate_analysis_stream(question: str, db_type: str) -> AsyncIterator[Dict[str, Any]]`

**Implementation Steps:**

1. **Create Base Streaming Interface**
   - Reference: Modify `LLMClient` base class (Lines 15-100 in `client.py`)
   - Add abstract streaming methods that all client implementations must provide
   - Define streaming response event types: `status`, `partial_content`, `complete`, `error`

2. **Implement OpenAI Streaming**
   - Reference: Extend `OpenAIClient` class (Lines 100-600 in `client.py`)
   - Use OpenAI's `stream=True` parameter in `client.chat.completions.create()`
   - Yield progressive token chunks as they arrive from OpenAI
   - Handle partial JSON parsing for structured responses (SQL, MongoDB queries)

3. **Implement Anthropic Streaming**
   - Reference: Extend `AnthropicClient` class (Lines 600-900 in `client.py`)
   - Use Anthropic's streaming API capabilities
   - Maintain consistent event format across providers

4. **Add Streaming Response Format**
   - Create standardized streaming event structure:
     - `{"type": "status", "message": "Generating SQL query..."}`
     - `{"type": "partial_sql", "content": "SELECT * FROM"}`
     - `{"type": "sql_complete", "sql": "SELECT * FROM users WHERE..."}`
     - `{"type": "analysis_chunk", "text": "The data shows..."}`

### 1.2 Template-Specific Streaming

**Templates Requiring Streaming Support:**
- `nl2sql.tpl` - Referenced in `_execute_postgres_query()` (Line 465)
- `mongo_query.tpl` - Referenced in `_execute_mongodb_query()` (Line 507)
- `vector_search.tpl` - Referenced in `_execute_qdrant_query()` (Line 547)
- Cross-database planning templates in orchestration

**Implementation Steps:**

1. **Progressive Template Processing**
   - Stream template rendering progress for complex schemas
   - Yield status updates as schema chunks are processed
   - Provide early indication of which databases will be queried

2. **Incremental Query Building**
   - For complex cross-database queries, stream the planning process
   - Show users which operations are being planned in real-time
   - Indicate dependencies between operations as they're determined

---

## Phase 2: Query Engine Streaming Pipeline

### 2.1 Main Query Processing Stream

**Primary Method to Enhance:**
- `process_ai_query()` in `execute.py` (Lines 680-778)

**Implementation Steps:**

1. **Create Streaming Entry Point**
   - New method: `process_ai_query_stream()`
   - Yield classification progress: `{"type": "classifying", "message": "Determining relevant databases..."}`
   - Stream database selection results: `{"type": "databases_selected", "databases": ["postgres", "mongodb"]}`

2. **Schema Search Streaming**
   - Reference: Schema searcher initialization (Lines 690-695)
   - Stream schema loading progress: `{"type": "schema_loading", "database": "postgres", "progress": 0.6}`
   - Yield relevant schema chunks as they're found: `{"type": "schema_chunks", "chunks": [...]}`

3. **Query Generation Streaming**
   - Stream LLM query generation progress by calling streaming LLM methods
   - Yield partial queries as they're generated
   - Show validation progress for generated queries

### 2.2 Cross-Database Query Streaming

**Primary Method to Enhance:**
- `execute_cross_database_query()` in `execute.py` (Lines 280-450)

**Implementation Steps:**

1. **Planning Phase Streaming**
   - Reference: Cross-database agent execution (Lines 320-330)
   - Stream plan generation: `{"type": "planning", "step": "Analyzing query dependencies"}`
   - Yield plan validation results: `{"type": "plan_validated", "operations": 3, "estimated_time": "30s"}`

2. **Parallel Execution Streaming**
   - Stream individual database operation progress
   - Yield results as each database operation completes
   - Show aggregation progress when combining results

3. **Result Aggregation Streaming**
   - Reference: Result processing (Lines 380-420)
   - Stream join operations: `{"type": "aggregating", "step": "Joining postgres and mongodb results"}`
   - Yield partial aggregated results as they become available

### 2.3 Individual Database Streaming

**Methods to Enhance:**
- `_execute_postgres_query()` (Lines 452-490)
- `_execute_mongodb_query()` (Lines 492-530)
- `_execute_qdrant_query()` (Lines 532-570)

**Implementation Steps:**

1. **Query Execution Streaming**
   - Stream database connection status
   - Yield query execution progress for long-running queries
   - Stream partial results as they're fetched from databases

2. **Result Processing Streaming**
   - Stream data transformation progress
   - Yield analysis generation progress when `analyze=True`
   - Show result formatting and validation steps

---

## Phase 3: API Endpoints Streaming Infrastructure

### 3.1 FastAPI Streaming Endpoints

**Current Endpoints to Enhance:**
- `/query` endpoint (Lines 82-130 in `endpoints.py`)
- `/cross-database-query` endpoint (Lines 132-200 in `endpoints.py`)

**Implementation Steps:**

1. **Create Streaming Endpoints**
   - New endpoints: `/query/stream`, `/cross-database-query/stream`
   - Use FastAPI's `StreamingResponse` with `media_type="text/event-stream"`
   - Implement Server-Sent Events (SSE) format for browser compatibility

2. **Event Stream Format**
   - Structure: `data: {"type": "status", "message": "Processing..."}\n\n`
   - Handle client reconnection with event IDs
   - Implement proper error streaming and connection cleanup

3. **Session Management for Streaming**
   - Reference: Session handling in query methods (Lines 100-120)
   - Track streaming sessions for progress monitoring
   - Allow clients to retrieve partial progress if connection drops

### 3.2 Response Format Standardization

**Implementation Steps:**

1. **Unified Streaming Event Schema**
   - Define event types: `status`, `schema_loaded`, `sql_generated`, `partial_results`, `analysis_chunk`, `complete`, `error`
   - Ensure consistent format across all streaming endpoints
   - Add metadata like timestamps, session IDs, and progress percentages

2. **Error Handling in Streams**
   - Stream error events without breaking the connection
   - Provide recovery suggestions in error messages
   - Implement graceful degradation to non-streaming responses

3. **Progress Tracking**
   - Add progress indicators: `{"type": "progress", "step": 3, "total": 7, "percentage": 43}`
   - Estimate completion times based on query complexity
   - Provide detailed status for long-running operations

---

## Phase 4: Frontend Streaming Integration

### 4.1 AIQuerySelector Component Enhancement

**Current Component to Enhance:**
- `AIQuerySelector.tsx` (Lines 1-164)

**Implementation Steps:**

1. **Replace HTTP Fetch with EventSource**
   - Remove current `fetch()` call in `handleSubmit()` (Lines 95-102)
   - Implement EventSource for Server-Sent Events consumption
   - Handle streaming connection lifecycle (connect, message, error, close)

2. **Progressive UI Updates**
   - Show real-time status updates in the loading state
   - Display partial SQL as it's generated in a code block
   - Stream results into table components as rows arrive
   - Update analysis text progressively as it's generated

3. **Enhanced Loading States**
   - Replace simple loading spinner with detailed progress indicators
   - Show current operation: "Searching schema...", "Generating query...", "Executing..."
   - Display progress bars for multi-step operations
   - Add estimated time remaining based on operation complexity

### 4.2 Result Display Components

**Components to Create/Enhance:**
- Progressive result table component
- Streaming SQL code display
- Real-time analysis text component

**Implementation Steps:**

1. **Streaming Result Table**
   - Display table headers immediately when available
   - Add rows progressively as they arrive from the stream
   - Show loading indicators for pending rows
   - Handle large result sets with virtual scrolling

2. **Progressive SQL Display**
   - Show SQL generation in real-time with syntax highlighting
   - Display query validation status as it's checked
   - Indicate query execution progress with timing information

3. **Live Analysis Text**
   - Stream analysis text with typewriter effect
   - Show analysis generation progress
   - Handle markdown formatting in real-time updates

---

## Phase 5: Advanced Streaming Features

### 5.1 Connection Management

**Implementation Steps:**

1. **Reconnection Logic**
   - Implement automatic reconnection with exponential backoff
   - Resume streaming from last known position using event IDs
   - Cache partial results during connection interruptions

2. **Client-Side State Management**
   - Maintain streaming state across component re-renders
   - Handle browser tab focus/blur events to pause/resume streams
   - Implement client-side caching of streaming data

3. **Performance Optimization**
   - Implement streaming response compression where possible
   - Add client-side buffering for smooth UI updates
   - Optimize event processing to prevent UI blocking

### 5.2 Multi-Session Support

**Implementation Steps:**

1. **Concurrent Stream Management**
   - Support multiple simultaneous streaming queries
   - Implement query queuing for resource management
   - Add session priority handling for important queries

2. **Resource Monitoring**
   - Track streaming resource usage
   - Implement backpressure handling for slow clients
   - Add server-side stream timeout management

---

## Implementation Checklist by File

### LLM Client Layer (`server/agent/llm/client.py`)
- [ ] Add streaming abstract methods to `LLMClient` base class
- [ ] Implement `generate_sql_stream()` in `OpenAIClient`
- [ ] Implement `generate_mongodb_query_stream()` in `OpenAIClient`
- [ ] Implement `analyze_results_stream()` in `OpenAIClient`
- [ ] Add corresponding streaming methods to `AnthropicClient`
- [ ] Create streaming response event schema
- [ ] Add partial JSON parsing for structured responses

### Query Engine Layer (`server/agent/db/execute.py`)
- [ ] Create `process_ai_query_stream()` method
- [ ] Add `execute_cross_database_query_stream()` method
- [ ] Implement streaming versions of individual database execution methods
- [ ] Add progress tracking for schema loading and validation
- [ ] Implement result aggregation streaming
- [ ] Add error handling for streaming operations

### API Endpoints Layer (`server/agent/api/endpoints.py`)
- [ ] Create `/query/stream` endpoint with `StreamingResponse`
- [ ] Create `/cross-database-query/stream` endpoint
- [ ] Implement Server-Sent Events format
- [ ] Add streaming session management
- [ ] Implement proper error handling in streams
- [ ] Add connection cleanup and timeout handling

### Frontend Layer (`server/web/src/components/AIQuerySelector.tsx`)
- [ ] Replace `fetch()` with `EventSource` implementation
- [ ] Add progressive UI update handlers
- [ ] Implement streaming connection management
- [ ] Create enhanced loading states with progress indicators
- [ ] Add reconnection logic with exponential backoff
- [ ] Implement client-side streaming state management

### Supporting Components
- [ ] Create streaming result display components
- [ ] Add progressive SQL syntax highlighting
- [ ] Implement live analysis text rendering
- [ ] Add streaming performance monitoring
- [ ] Create streaming session storage and recovery

---

## Testing Strategy

### Unit Testing
- Test each streaming method in isolation with mock data streams
- Verify event format consistency across all streaming components
- Test error handling and connection recovery scenarios

### Integration Testing
- Test complete streaming pipeline from frontend to database
- Verify real-time updates across different query types
- Test concurrent streaming sessions and resource management

### Performance Testing
- Measure streaming latency and throughput
- Test with large result sets and complex queries
- Verify memory usage during long-running streams

---

## Deployment Considerations

### Infrastructure Requirements
- Ensure load balancer supports Server-Sent Events
- Configure appropriate timeout values for streaming connections
- Add monitoring for streaming endpoint performance

### Scaling Considerations
- Plan for horizontal scaling of streaming endpoints
- Implement session affinity for streaming connections
- Add resource limits for streaming operations

This implementation guide provides the foundation for adding comprehensive streaming capabilities to Ceneca while maintaining the existing synchronous API for compatibility. 
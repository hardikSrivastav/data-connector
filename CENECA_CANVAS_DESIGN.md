# Ceneca Canvas: Data Analysis Operating System

**Vision**: Transform data analysis from isolated queries into collaborative, iterative analytical workspaces that preserve context, enable exploration, and scale insights across teams.

## 🎯 Core Concept: Living Tiles + Analysis Threads

Ceneca Canvas combines the best of:
- **Notion's modular canvas approach** for workspace organization
- **Git's branching model** for version control and iteration tracking
- **ChatGPT's deep research flow** for progressive analysis with real-time updates
- **Figma's collaborative workspace model** for team coordination (future)

---

## 🎨 The Canvas System

### Main Canvas View
The primary workspace where all analytical work lives as **"Living Tiles"** - dynamic previews of analysis threads that update in real-time. Each tile represents an analysis thread with its current end-object (table, graph, insight summary).

**Git-Style Iteration**:
- Each analysis thread follows Git conventions
- Commands use Git terminology (`branch`, `commit`, `merge`, `diff`)
- Version history shows analytical evolution
- Easy rollback to previous analysis states

### Canvas Block Integration
- Canvas is activated via `/` command in any block (similar to Notion)
- Functions as a hybrid: **subpage + image-preview**
- **New dedicated block type**: `canvas` with specialized rendering
- **Collapsed state**: Rich thumbnail showing tables, summaries, stats, and graphs
- **Expanded state**: Full interactive canvas with thread details
- **Complete independence**: Canvas operates separately from other blocks
- Stored as special block type in existing database schema

---

## 🧵 Analysis Threads (Claude-Style Artifacts)

### Thread Lifecycle
1. **User initiates** via AIQuerySelector.tsx with customizable complexity
2. **Backend orchestrates** through classifier.py → endpoints.py → execute.py
3. **Real-time streaming**: WebSocket connection delivers detailed progress updates
4. **Progressive updates**: Every AI step instantly relayed ("Connecting to database...", "Running SQL query...", "Processing 1,247 rows...", "Generating analysis...")
5. **End-object creation**: Table, graph, or analysis summary
6. **Git-style commits** capture each iteration

### Thread Structure
```
Thread Branch: "customer-revenue-analysis"
├── Commit 1: Initial query → Basic table
├── Commit 2: Add time dimension → Time series
├── Commit 3: Segment by region → Comparative analysis
└── HEAD: Final insight summary
```

### Thread Naming Strategy
- **Auto-generation**: User query → descriptive name ("Show me revenue data" → "Revenue Data Analysis")
- **User editable**: Click to rename any thread at any time
- **Intelligent parsing**: Extract key entities and actions from natural language queries
- **Fallback naming**: "Analysis [timestamp]" if parsing fails

### User Control Levels
Users can specify in AIQuerySelector.tsx:
- **Quick Analysis**: Single query, basic insights
- **Deep Research**: Multi-step orchestrated analysis
- **Custom**: User-defined complexity and steps

---

## 📊 Living Tiles Design

### Tile States
1. **Preview Mode** (Default)
   - Rich thumbnail with major tables preview
   - Key statistics and summary overlay
   - Visual graphs/charts (when enabled)
   - Thread status indicator
   - Click to expand

2. **Expanded Mode**
   - Full analysis interface
   - Thread history sidebar with Git-style navigation
   - Real-time progress streaming during processing
   - Interactive data exploration

### Canvas Block Type
```typescript
interface CanvasBlock extends Block {
  type: 'canvas';
  content: string; // Thread name/title
  properties: {
    threadId: string;
    isExpanded: boolean;
    previewData: {
      summary: string;
      keyStats: Array<{label: string, value: string}>;
      tablePreview: Array<Record<string, any>>;
      chartPreview?: ChartData; // Future feature
    };
    currentCommit: string;
    status: 'idle' | 'running' | 'completed' | 'failed';
    
    // State persistence
    scrollPosition?: number;
    viewState?: {
      sortColumn?: string;
      sortDirection?: 'asc' | 'desc';
      appliedFilters?: Record<string, any>;
    };
  };
}
```

### Performance Optimizations
- **Lazy loading**: Preview data loads when block comes into viewport
- **Local caching**: Preview thumbnails cached as images in browser
- **Row limiting**: Preview tables show maximum 5 rows with "...and X more" indicator
- **Virtualization**: Large data tables use virtual scrolling in expanded mode
- **Smart updates**: Only re-render changed portions of canvas blocks

### Tile Types Based on End-Objects
- **Data Table Tiles**: Spreadsheet-like interface with sorting/filtering
- **Insight Summary Tiles**: AI-generated analysis with key findings
- **Query Builder Tiles**: SQL/query interface with results
- **Visualization Tiles**: Charts, graphs, heatmaps (future)

---

## 🏗️ Technical Architecture

### Real-Time Streaming System
- **Separate WebSocket service** running independently for diagnosis and scaling
- **Progress categories** without verbosity levels:
  - **Technical logs**: "Executing SQL: SELECT customers.id, SUM(orders.total)..."
  - **User-friendly messages**: "Analyzing customer purchasing patterns..."
  - **Error details**: Full error context with actionable suggestions
- **Detailed progress updates** streaming every AI operation:
  - "Analyzing query intent..."
  - "Connecting to PostgreSQL database..."
  - "Executing SQL: SELECT customers.id, SUM(orders.total)..."
  - "Processing 1,247 rows..."
  - "Generating statistical analysis..."
  - "Creating summary insights..."
- **Partial result streaming** as data becomes available
- **Error handling** with real-time error messages

### Canvas State Management
Canvas blocks implement **three-way data storage** identical to normal blocks:
1. **Local state**: Immediate responsiveness for user interactions
2. **IndexedDB**: Offline persistence and fast loading
3. **PostgreSQL**: Server-side persistence and collaboration (future)

**Auto-save features**:
- Expanded/collapsed state preservation
- Scroll position memory within expanded canvases
- User interactions (sorts, filters, selections) persistence
- Real-time sync with existing useStorageManager.ts infrastructure

### Current System Integration
- **Single-database, single-user focus** (as per endpoints.py + execute.py)
- **No cross-database complexity initially**
- **Canvas complete independence** from other blocks/pages
- **New canvas tables** in storage.py with clean separation

### Database Schema Extension
```sql
-- New tables for canvas functionality
CREATE TABLE canvas_threads (
    id VARCHAR PRIMARY KEY,
    workspace_id VARCHAR REFERENCES workspaces(id),
    page_id VARCHAR REFERENCES pages(id),
    block_id VARCHAR REFERENCES blocks(id),
    name VARCHAR NOT NULL,
    status VARCHAR DEFAULT 'idle', -- 'idle', 'running', 'completed', 'failed'
    query_text TEXT,
    complexity_level VARCHAR DEFAULT 'quick', -- 'quick', 'deep', 'custom'
    auto_generated_name BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE analysis_commits (
    id VARCHAR PRIMARY KEY,
    thread_id VARCHAR REFERENCES canvas_threads(id),
    commit_message VARCHAR NOT NULL,
    query_text TEXT,
    result_data JSONB,
    analysis_summary TEXT,
    preview_data JSONB, -- For thumbnail generation
    performance_metrics JSONB, -- Query time, row count, etc.
    parent_commit VARCHAR REFERENCES analysis_commits(id),
    is_head BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE progress_logs (
    id VARCHAR PRIMARY KEY,
    thread_id VARCHAR REFERENCES canvas_threads(id),
    message TEXT NOT NULL,
    step_type VARCHAR, -- 'query', 'processing', 'analysis', 'error'
    category VARCHAR DEFAULT 'user-friendly', -- 'technical', 'user-friendly', 'error'
    timestamp TIMESTAMP DEFAULT NOW()
);

CREATE TABLE canvas_cache (
    id VARCHAR PRIMARY KEY,
    thread_id VARCHAR REFERENCES canvas_threads(id),
    cache_key VARCHAR NOT NULL,
    cache_data BYTEA, -- Cached thumbnail images
    cache_type VARCHAR, -- 'thumbnail', 'preview_data'
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### Component Flow
1. **BlockEditor.tsx** → Handles `/canvas` activation and renders canvas blocks
2. **AIQuerySelector.tsx** → User defines analysis complexity and initiates query
3. **WebSocket Service** → Manages real-time communication with backend
4. **Backend streaming** → endpoints.py streams progress through WebSocket
5. **PageEditor.tsx** → Renders canvas blocks with special preview/expand formatting

---

## 🚀 Implementation Strategy

### Progressive Enhancement Approach
**Phase 1: Minimal Viable Canvas**
1. Basic canvas block with simple text preview
2. WebSocket streaming infrastructure
3. Simple expand/collapse functionality
4. Integration with existing query flow

**Phase 2: Rich Previews**
1. Enhanced preview data generation
2. Performance optimizations (lazy loading, caching)
3. Auto-generated thread naming
4. State persistence

**Phase 3: Git-Style Features**
1. Commit history visualization
2. Diff views between analysis versions
3. Branching and merging capabilities
4. Advanced navigation

### Error Handling Strategy
- **Partial failure recovery**: Save partial results if analysis fails mid-stream
- **Retry mechanisms**: Auto-retry transient failures with exponential backoff
- **Error classification**: Network, SQL, AI, and user errors with specific handling
- **Graceful degradation**: Fall back to basic mode if streaming fails
- **User actionable errors**: Clear error messages with suggested solutions

### Canvas Discovery Features
- **Recent canvases panel**: Quick access in sidebar to recently used analyses
- **Search functionality**: Full-text search across canvas threads and results
- **Smart suggestions**: Recommend similar analyses based on current context
- **Quick patterns**: Common analysis templates for rapid deployment

### Performance Monitoring
Built-in performance tracking for speed optimization:
- **Time to first byte**: WebSocket message latency tracking
- **Analysis completion times**: Performance by complexity level and query type
- **User engagement metrics**: Time spent in expanded view, interaction patterns
- **Database query performance**: Query execution time and optimization suggestions
- **Cache hit rates**: Effectiveness of local caching strategies

---

## 🚀 Implementation Phases

### Phase 1: Foundation (Current Focus)
- ✅ Canvas block type in BlockEditor.tsx
- ✅ Database schema for threads, commits, and progress logs
- ✅ Separate WebSocket service infrastructure
- ✅ Integration with existing endpoints.py workflow
- ✅ Basic preview/expand functionality
- ✅ Three-way state management integration

### Phase 2: Rich Experience
- Enhanced preview data with performance optimizations
- Thread naming intelligence and edit functionality
- Cache management and thumbnail generation
- Error handling and recovery mechanisms
- Canvas discovery and search features

### Phase 3: Advanced Analytics
- Visualization tiles with charts/graphs
- Advanced statistical analysis
- Git-style navigation and diff views
- Performance monitoring dashboard
- Enhanced preview thumbnails

---

## 🎯 Key Design Principles

1. **Real-Time Transparency**: Every AI operation visible to user
2. **Speed First**: WebSocket streaming for immediate feedback
3. **Git Mental Model**: Familiar version control concepts
4. **Progressive Disclosure**: Rich previews, detailed expansion
5. **Complete Independence**: Canvas operates without external dependencies
6. **Context Preservation**: Every analysis step saved and referenceable
7. **Performance Obsession**: Sub-500ms response times for all interactions

---

## 🔄 User Experience Flow

### Creating Analysis
1. Type `/canvas` in any block
2. Canvas block appears with AIQuerySelector
3. User specifies query and complexity level
4. WebSocket streams detailed progress in real-time
5. Rich preview materializes with tables, stats, and summary
6. Auto-generated thread name appears (user can edit immediately)
7. Click to expand for full interactive analysis

### Iterating Analysis
1. Click on existing canvas tile
2. Submit refinement query
3. New commit created in thread with Git-style tracking
4. WebSocket streams new analysis progress
5. Tile updates with latest end-object
6. Complete history preserved with diff navigation

### Reviewing Work
1. Canvas overview shows all active threads as rich tiles
2. Preview shows key tables, statistics, and summaries
3. Click any tile for detailed expanded view
4. Browse commit history with Git-style interface
5. Compare different analysis approaches with diff views
6. Search and discover related analyses

---

## 📈 Success Metrics

- **Time to First Insight**: < 30 seconds for simple queries
- **Real-Time Engagement**: Users see progress within 500ms
- **Analysis Depth**: Multi-step investigations in single workspace
- **Context Retention**: Zero lost work, complete audit trail
- **User Adoption**: Natural integration with existing Notion-like workflow
- **Performance**: 95th percentile response times under 2 seconds
- **Reliability**: 99.9% uptime for WebSocket streaming service

---

*This design document represents Ceneca's evolution from a data query tool to a comprehensive Data Analysis Operating System that preserves context, enables collaboration, and scales insights across organizations.*
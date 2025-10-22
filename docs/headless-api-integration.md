# Headless API Integration for Ceneca

## Overview

This document outlines the design considerations, patterns, and implementation requirements for allowing companies to integrate Ceneca's query capabilities into their own applications through a headless API approach, rather than redirecting users to Ceneca's full web interface.

## Table of Contents

1. [Integration Patterns](#integration-patterns)
2. [Headless API Pattern Deep Dive](#headless-api-pattern-deep-dive)
3. [Critical Concerns](#critical-concerns)
4. [Ceneca's Schema Infrastructure Advantage](#cenecas-schema-infrastructure-advantage)
5. [Versioning Strategy](#versioning-strategy)
6. [Implementation Requirements](#implementation-requirements)
7. [API Endpoints](#api-endpoints)
8. [SDK Interface](#sdk-interface)

---

## Integration Patterns

There are six primary patterns for integrating Ceneca into external applications:

### 1. Embedded Widget Pattern
**Best for:** Quick wins, specific use cases  
**Integration Effort:** Low (1-2 days)  
**Flexibility:** Medium  

Companies install a self-contained React component via NPM:

```bash
npm install @ceneca/query-widget
```

```jsx
<CenecaQueryWidget 
  databases={['postgres', 'mongodb']}
  theme="dark"
  onResult={handleData}
  authToken={user.token}
/>
```

**Real-world analogy:** Stripe's Payment Element

### 2. Headless API Pattern ⭐ (Focus of this doc)
**Best for:** Custom UIs, full control  
**Integration Effort:** Medium (1 week)  
**Flexibility:** Highest  

Companies use Ceneca's query engine via SDK/API but build their own UI.

```javascript
import { CenecaClient } from '@ceneca/sdk';

const ceneca = new CenecaClient({
  host: 'ceneca.company.com',
  apiKey: process.env.CENECA_API_KEY
});

const result = await ceneca.query("Total sales this month");
```

**Real-world analogy:** Algolia's Search API

### 3. Micro-Frontend Module
**Best for:** Enterprise portals  
**Integration Effort:** High (2-3 weeks)  
**Flexibility:** High  

Ceneca loads as a standalone module using Webpack Module Federation:

```javascript
import('https://cdn.ceneca.com/v2/ceneca-module.js')
  .then(CenecaModule => {
    CenecaModule.mount('#ceneca-mount-point', {
      theme: theirTheme,
      auth: theirAuthToken
    });
  });
```

**Real-world analogy:** Shopify Admin Extensions

### 4. iframe Embed
**Best for:** Legacy apps, strict CSP policies  
**Integration Effort:** Low (1 day)  
**Flexibility:** Low  

Simple iframe with postMessage communication:

```html
<iframe 
  src="ceneca.company.com/query"
  style="width:600px; height:800px"
/>
```

**Real-world analogy:** Intercom Chat Widget

### 5. Data Hook Pattern
**Best for:** Modern React/Vue apps  
**Integration Effort:** Low (2-3 days)  
**Flexibility:** High  

React hooks/Vue composables that expose Ceneca's capabilities:

```javascript
import { useCenecaQuery } from '@ceneca/react';

function Dashboard() {
  const { data, isLoading, error } = useCenecaQuery({
    query: "Top 10 products by revenue",
    databases: ['shopify', 'stripe'],
    refreshInterval: 60000
  });
  
  return <CustomChart data={data.rows} />;
}
```

**Real-world analogy:** TanStack Query (React Query)

### 6. CLI/Build-Time Integration
**Best for:** Static dashboards, generated components  
**Integration Effort:** Medium (1 week)  
**Flexibility:** Low  

Generate optimized components during build:

```bash
ceneca generate-components --queries=./queries.yaml
```

**Real-world analogy:** Prisma Client Generation

---

## Headless API Pattern Deep Dive

The headless API pattern provides maximum flexibility by giving companies complete control over the UI while leveraging Ceneca's cross-database query capabilities.

### Architecture

```
Company's Frontend (React/Vue/Angular)
        ↓
   @ceneca/sdk
        ↓
   REST/GraphQL API + WebSocket
        ↓
Ceneca Server (self-hosted on company infrastructure)
        ↓
Company's Databases (Postgres, MongoDB, etc.)
```

### Example Integration

```javascript
// Installation
npm install @ceneca/sdk

// Initialize client
import { CenecaClient } from '@ceneca/sdk';

const ceneca = new CenecaClient({
  host: 'their-internal-ceneca.company.com',
  apiKey: process.env.CENECA_API_KEY
});

// Simple query
const result = await ceneca.query("Total sales this month");
console.log(result.rows); // Array of data

// Streaming query
ceneca.streamQuery("Show customer distribution", {
  onChunk: (chunk) => updateProgressBar(chunk),
  onComplete: (final) => showFinalResults(final),
  onError: (error) => handleError(error)
});

// Get available databases
const databases = await ceneca.listDatabases();

// Get schema information
const schema = await ceneca.getDatabaseSchema('postgres');
```

---

## Critical Concerns

### 1. Streaming is Hard (And Companies Will Get It Wrong)

**Problem:**  
Ceneca's backend streams results via SSE/WebSocket (see `agent-client.ts` and `PageEditor.tsx`). Most companies aren't experienced with handling streaming APIs properly.

**What will happen:**
```javascript
// ❌ Their first attempt (WILL BREAK):
const result = await ceneca.query("Show sales data");
console.log(result); // They expect complete data immediately

// Reality: Query takes 15 seconds, streams 50 chunks
// Their app times out, shows loading forever, or crashes
```

**Solution:**  
SDK must make streaming feel synchronous by default:

```javascript
// ✅ SDK handles streaming internally:
const result = await ceneca.query("Show sales data", {
  timeout: 30000, // Auto-fail after 30s
  onProgress: (chunk) => {
    // Optional callback for real-time updates
  }
});
// Returns complete result when done

// OR explicit streaming mode:
for await (const chunk of ceneca.streamQuery("...")) {
  console.log(chunk); // Progressive updates
}
```

**Support burden:** Expect tickets like "Query stuck at 80%" due to unhandled stream interruptions.

---

### 2. Authentication Token Management

**Problem:**  
Ceneca uses Okta enterprise auth. Companies need to:
- Generate API tokens for their users
- Refresh tokens when expired
- Revoke tokens on logout
- Handle multi-tenant isolation

**What will go wrong:**
```javascript
// ❌ Common mistake #1: Hardcoded tokens in frontend
const ceneca = new CenecaClient({
  apiKey: 'sk_live_abc123...' // EXPOSED in browser DevTools
});

// ❌ Common mistake #2: Sharing tokens across users
// User A queries User B's data because token isn't user-scoped

// ❌ Common mistake #3: Not refreshing tokens
// Token expires mid-query → silent failures
```

**Solution:**  
SDK with built-in token lifecycle management:

```javascript
// ✅ Proper implementation:
const ceneca = new CenecaClient({
  tokenProvider: async () => {
    // They call their backend to get fresh token
    const token = await theirBackend.getCenecaToken(currentUser.id);
    return token;
  },
  onTokenExpired: () => {
    // SDK automatically calls tokenProvider again
  }
});
```

**Requirements:**
- Short-lived tokens (15-30 min) with refresh mechanism
- Token scoping per user + database access
- SDK auto-refresh built-in
- Clear documentation on token lifecycle

**Security risk:** Database breaches if companies hardcode production tokens in client-side code.

---

### 3. Query Cost Explosions

**Problem:**  
Companies don't understand cross-database query complexity. Innocent-looking queries can hammer the backend.

**What will happen:**
```javascript
// Innocent query from their frontend:
ceneca.query("Show me every customer purchase ever");

// Behind the scenes in Ceneca:
// → Postgres: SELECT * FROM customers (10M rows)
// → MongoDB: aggregate on orders (50M documents)
// → Join in memory
// → Result: 200GB of data, 5 minutes of compute
```

**Concerns:**
1. **Infrastructure costs** - Who pays for compute/memory?
2. **Database load** - Companies might DDoS their own databases
3. **Rate limiting** - How to throttle without breaking their app?

**Solution:**  
SDK with built-in limits and early validation:

```javascript
// SDK with limits:
const ceneca = new CenecaClient({
  limits: {
    maxRowsPerQuery: 100000,
    maxExecutionTime: 60000, // 60s
    maxConcurrentQueries: 5
  }
});

// Query fails fast with actionable error:
try {
  await ceneca.query("huge query");
} catch (err) {
  if (err.code === 'QUERY_TOO_LARGE') {
    // Show: "Please narrow your query to < 100k rows"
    console.log(err.suggestion); // "Try adding date filters"
  }
}

// Estimation before execution:
const estimate = await ceneca.estimateQuery("All orders");
console.log(estimate);
// { estimatedRows: 2400000, estimatedSizeMB: 340 }
// User can decide whether to proceed
```

**Risk:** Dev team tests with 100 rows locally, production has 100M rows → outage on day 1.

---

### 4. Error Handling is Ambiguous

**Problem:**  
When a query fails, whose fault is it?
- Ceneca's parsing?
- Their database being down?
- Bad credentials?
- Invalid question?
- Network timeout?

**What will happen:**
```javascript
// Their code:
try {
  const result = await ceneca.query("Show sales");
} catch (err) {
  console.log(err); // "Query failed"
  // Now what? Retry? Show error? Call support?
}
```

**Solution:**  
Structured error codes with actionable guidance:

```typescript
class CenecaError extends Error {
  code: string;
  retryable: boolean;
  details: any;
  suggestion?: string;
}

// Example errors:
{
  code: 'DATABASE_UNREACHABLE',
  retryable: true,
  details: { database: 'postgres', host: 'db.company.com' },
  suggestion: 'Check database connection and credentials'
}

{
  code: 'QUERY_PARSING_FAILED',
  retryable: false,
  details: { 
    question: "show stuff",
    reason: "Ambiguous query - multiple interpretations possible"
  },
  suggestion: "Try: 'Show total sales this month'"
}

{
  code: 'INSUFFICIENT_PERMISSIONS',
  retryable: false,
  details: { 
    requiredPermission: 'read:sales_data',
    userPermissions: ['read:public_data']
  },
  suggestion: 'Contact your administrator to request sales_data access'
}

{
  code: 'SCHEMA_CHANGED',
  retryable: true,
  details: {
    database: 'postgres',
    table: 'customers',
    column: 'email_address',
    status: 'column_not_found',
    possibleRenames: ['contact_email', 'user_email']
  },
  suggestion: 'Schema may have changed. Reindexing in progress.'
}
```

**Support burden:** Without structured errors, 50% of support time will be debugging "it doesn't work" → usually wrong credentials.

---

### 5. Versioning Nightmares

**Problem:**  
SDK version vs. company's self-hosted Ceneca server version vs. API compatibility.

**Scenario:**
```
Company installs: @ceneca/sdk@2.5.0
Company deploys: Ceneca Server v2.3.0 (self-hosted)

SDK calls: /api/v2/query with parameter "force_langgraph"
Server v2.3.0 doesn't recognize it → silent failure or crash
```

**Solution:**  
Server version detection in SDK with compatibility checking:

```javascript
// SDK checks server compatibility on connect:
const ceneca = new CenecaClient({ host: '...' });

await ceneca.connect(); 
// Throws if incompatible:
// CenecaError: Server v2.1.0 incompatible with SDK v2.5.0
//              Please upgrade server to >= v2.3.0
//              Or downgrade SDK: npm install @ceneca/sdk@2.3.x

// Feature detection:
if (ceneca.supports('adaptive_streaming')) {
  // Use new feature
} else {
  // Fallback behavior
}
```

**Requirements:**
- Strict semantic versioning
- Server exposes version in health endpoint
- SDK checks compatibility on initialization
- Backward compatibility for at least 2 major versions
- Feature flags for gradual rollout

**Risk:** Company updates SDK, self-hosted instance breaks, can't roll back because code depends on new SDK features.

---

### 6. No UI = No Context

**Problem:**  
Ceneca's web UI provides:
- Visual query building
- Reasoning chain display (`ReasoningChain.tsx`, `StreamingStatusBlock.tsx`)
- Database schema exploration
- Result previews with charts

With headless API, **they lose all this context**.

**What will happen:**
```javascript
// Their simple UI:
<input 
  placeholder="Ask a question" 
  onChange={(e) => handleQuery(e.target.value)}
/>

// User types: "Show me the data"
// Ceneca: "Which data? From which database?"
// But their UI has no way to show database picker...

// User types: "Sales by region"
// Ceneca streams 50 reasoning steps
// But their UI just shows a loading spinner...
```

**Solution:**  
Additional SDK methods to help them build context:

```javascript
// Help them build context:
const databases = await ceneca.listDatabases();
// Show user which DBs are available

const suggestions = await ceneca.suggestQuestions(userInput);
// Autocomplete as they type

const explanation = await ceneca.explainQuery(question);
// Show what Ceneca will do before running

// Include reasoning chain in streaming:
ceneca.streamQuery(question, {
  includeReasoningChain: true,
  onReasoningStep: (step) => {
    // step: { type: 'sql_query', query: '...', source: 'postgres' }
    // step: { type: 'tool_call', tool: 'aggregate', status: 'success' }
    showProgressToUser(step);
  }
});
```

**Support burden:** Users blame company's implementation ("your dashboard sucks") when Ceneca gave unclear results.

---

### 7. Schema Changes Break Everything

**Problem:**  
Company adds/removes database columns → queries that worked yesterday fail today.

**What will happen:**
```javascript
// Query that worked last week:
ceneca.query("Show customer emails");
// ✅ Returns: customers.email_address

// DBA renames column: email_address → contact_email

// Same query now:
ceneca.query("Show customer emails");
// ❌ Error: Column 'email_address' not found
```

**Solution (Ceneca already has this!):**  
See [Ceneca's Schema Infrastructure Advantage](#cenecas-schema-infrastructure-advantage) below.

---

### 8. Result Size Unpredictability

**Problem:**  
Don't know if a query returns 10 rows or 10 million until it runs.

**What will happen:**
```javascript
// Query: "All orders"
const result = await ceneca.query("All orders");

// Returns: 2GB JSON array
// Browser: 💥 Out of memory crash
```

**Solution:**  
Pagination and lazy loading by default:

```javascript
// Auto-paginated:
const results = ceneca.query("All orders", {
  pageSize: 1000 // Returns 1000 at a time
});

for await (const page of results) {
  console.log(page.rows); // 1000 rows
  console.log(page.hasMore); // true/false
  console.log(page.total); // Total count (if available)
  
  // They can stop early if needed
  if (foundWhatINeed) break;
}

// Size estimation before running:
const estimate = await ceneca.estimateQuery("All orders");
console.log(estimate);
// { estimatedRows: 2400000, estimatedSizeMB: 340 }

if (estimate.estimatedSizeMB > 100) {
  showWarning("This query will return ~340MB of data. Continue?");
}
```

**Risk:** Mobile app tries to load full result → crash → 1-star reviews.

---

## Ceneca's Schema Infrastructure Advantage

Ceneca already has a **powerful schema monitoring infrastructure** that solves many of the schema change concerns. This is a massive competitive advantage.

### Existing Infrastructure

Located in `server/agent/`:
- `performance/schema_monitor.py` - Detects schema changes via hash comparison
- `performance/schema_watcher.py` - Background daemon for continuous monitoring
- `db/registry/` - Multi-instance schema registry with SQLite storage
- `db/registry/introspect_worker.py` - Schema introspection across database types
- `db/registry/integrations.py` - Database connection and metadata management

### How It Works

```python
# From schema_monitor.py
async def get_schema_hash(self) -> str:
    """Generate hash of current database schema"""
    schema_metadata = await get_schema_metadata(
        conn_uri=self.conn_uri, 
        db_type=self.db_type
    )
    schema_json = json.dumps(schema_metadata, sort_keys=True)
    return hashlib.sha256(schema_json.encode()).hexdigest()

async def check_and_reindex(self, force: bool = False):
    """Check for schema changes and trigger reindexing"""
    current_hash = await self.get_schema_hash()
    stored_hash = self.get_stored_hash()
    
    if current_hash != stored_hash or force:
        # Schema changed - rebuild index
        await build_and_save_index_for_db(db_type=self.db_type)
        self.store_hash(current_hash)
        return True, f"Schema changed, reindexed {self.db_type}"
    
    return False, "No schema changes detected"
```

### Background Monitoring

```python
# From schema_watcher.py
async def watch_schema(interval: int = 300):  # 5 minutes
    """Continuously watch for schema changes"""
    monitor = SchemaMonitor(check_interval=0)
    
    while True:
        updated, message = await monitor.check_and_reindex()
        if updated:
            logger.info(f"Schema updated: {message}")
        await asyncio.sleep(interval)
```

### Why This is Gold for Headless API

**Automatic schema drift detection:**
- Company adds new column `customer_tier` to database
- Schema watcher detects change automatically  
- Ceneca reindexes without manual intervention
- **Their API calls keep working** with new schema

**Multi-instance support:**
- Track multiple database instances independently
- Different schemas per environment (prod, staging, dev)
- Independent refresh intervals per database

**Background operation:**
- Runs as daemon/systemd service
- Doesn't interrupt active queries
- Zero maintenance burden on company's dev team

### What Headless API Should Expose

Based on existing infrastructure, SDK should provide:

```javascript
// Get schema status (reads from schema_registry.db)
const status = await ceneca.getSchemaStatus();
console.log(status);
// {
//   databases: [
//     {
//       name: 'postgres',
//       lastSchemaChange: '2025-10-06T14:30:00Z',
//       lastReindex: '2025-10-06T14:31:00Z',
//       status: 'healthy',
//       tables: 42,
//       schemaHash: 'a3f2e1b...'
//     },
//     {
//       name: 'mongodb',
//       lastSchemaChange: '2025-10-05T09:15:00Z',
//       lastReindex: '2025-10-05T09:16:00Z',
//       status: 'healthy',
//       collections: 18,
//       schemaHash: 'b7c4d9e...'
//     }
//   ]
// }

// List databases (uses integrations.py)
const databases = await ceneca.listDatabases();

// Get schema details (uses introspect_worker.py)
const schema = await ceneca.getDatabaseSchema('postgres');

// Subscribe to schema change events
ceneca.subscribeToSchemaChanges((change) => {
  console.log(`Schema changed in ${change.database}`);
  console.log(`Reindex status: ${change.reindexStatus}`);
  // Notify users or refresh queries
});

// Force reindex (triggers schema_monitor.check_and_reindex(force=True))
await ceneca.forceReindex('postgres');
```

### Use Cases

**1. Debugging**
```javascript
// Query failing? Check if schema changed recently
const status = await ceneca.getSchemaStatus();
const recentChanges = status.databases.filter(
  db => Date.now() - new Date(db.lastSchemaChange) < 3600000 // Last hour
);

if (recentChanges.length > 0) {
  showMessage("Database schema changed recently. Please retry your query.");
}
```

**2. Proactive Notifications**
```javascript
// Alert devs when schema changes
ceneca.subscribeToSchemaChanges((change) => {
  slack.notify(`⚠️ Database schema changed: ${change.database}
    Tables affected: ${change.tablesAffected}
    Reindex status: ${change.reindexStatus}
    Queries may need to be updated.`);
});
```

**3. Query Validation**
```javascript
// Check if column exists before querying
const schema = await ceneca.getDatabaseSchema('postgres');
const customerTable = schema.tables.find(t => t.name === 'customers');

if (!customerTable.columns.includes('email_address')) {
  // Column doesn't exist - suggest alternatives
  const similar = findSimilarColumns(customerTable.columns, 'email_address');
  showSuggestion(`Column 'email_address' not found. Did you mean: ${similar.join(', ')}?`);
}
```

---

## Versioning Strategy

There are two types of versioning to handle:

### 1. Data Schema Versioning
**Problem:** Customer's database schema changes (columns added/renamed/removed)  
**Solution:** ✅ Already solved by Ceneca's schema monitoring infrastructure (see above)

### 2. API Contract Versioning
**Problem:** SDK version vs. Ceneca Server version compatibility  
**Solution:** Needs to be implemented

### API Contract Versioning Implementation

#### Server Side: Health Endpoint

Add version information to existing health check:

```python
# In server/agent/endpoints.py

@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "version": "2.8.0",  # Server version
        "api_version": "v2",  # API contract version
        "supported_features": [
            "basic_query",
            "streaming",
            "multi_database",
            "schema_introspection",
            "reasoning_chain",
            "chart_generation",
            # "adaptive_streaming"  ← Not in v2.8.0 yet
        ],
        "min_sdk_version": "2.5.0",  # Minimum compatible SDK
        "max_sdk_version": "2.99.99",  # Maximum compatible SDK
        "schema_monitoring": {
            "enabled": True,
            "supported_databases": ["postgres", "mongodb", "mysql", "qdrant"]
        }
    }
```

#### Client Side: Compatibility Check

SDK checks compatibility on initialization:

```typescript
// In @ceneca/sdk

interface VersionInfo {
  version: string;
  apiVersion: string;
  supportedFeatures: string[];
  minSdkVersion: string;
  maxSdkVersion: string;
}

class CenecaClient {
  private supportedFeatures: Set<string> = new Set();
  private serverVersion: string = '';
  
  async connect() {
    // Fetch server version info
    const health = await fetch(`${this.host}/api/health`)
      .then(r => r.json()) as VersionInfo;
    
    const sdkVersion = '2.8.0';  // From package.json
    this.serverVersion = health.version;
    
    // Check compatibility
    if (!this.isCompatible(sdkVersion, health.minSdkVersion, health.maxSdkVersion)) {
      throw new CenecaError({
        code: 'VERSION_INCOMPATIBLE',
        message: `SDK version ${sdkVersion} incompatible with server ${health.version}`,
        suggestion: health.version > sdkVersion
          ? `Please upgrade SDK: npm install @ceneca/sdk@${health.version}`
          : `Please upgrade Ceneca server to >= v${sdkVersion} or downgrade SDK: npm install @ceneca/sdk@${health.version}`,
        retryable: false
      });
    }
    
    // Store supported features
    this.supportedFeatures = new Set(health.supportedFeatures);
    
    console.log(`Connected to Ceneca ${health.version} (API ${health.apiVersion})`);
  }
  
  supports(feature: string): boolean {
    return this.supportedFeatures.has(feature);
  }
  
  async query(question: string, options: QueryOptions = {}) {
    // Only use features the server supports
    if (options.streamingMode === 'adaptive' && 
        !this.supports('adaptive_streaming')) {
      console.warn(
        'Server does not support adaptive streaming. ' +
        'Falling back to standard streaming.'
      );
      options.streamingMode = 'standard';
    }
    
    // Continue with query...
  }
  
  private isCompatible(sdk: string, min: string, max: string): boolean {
    // Semantic version comparison
    return this.compareVersions(sdk, min) >= 0 && 
           this.compareVersions(sdk, max) <= 0;
  }
}
```

### Version Matrix

| Server Version | Compatible SDK Versions | Breaking Changes |
|----------------|------------------------|------------------|
| v2.8.x | 2.5.x - 2.10.x | None |
| v2.9.x | 2.7.x - 2.12.x | None |
| v3.0.x | 3.0.x - 3.5.x | New auth system, streaming protocol changed |
| v3.1.x | 3.0.x - 3.8.x | None |

### Semantic Versioning Rules

**Server:**
- **Major version** (3.0.0): Breaking API changes
- **Minor version** (2.9.0): New features, backward compatible
- **Patch version** (2.8.1): Bug fixes only

**SDK:**
- Follows same semantic versioning
- Must support at least 2 minor versions back
- Gracefully degrades when features unavailable

---

## Implementation Requirements

### Minimum Viable SDK

The SDK must provide:

```typescript
class CenecaClient {
  // ===== Connection Management =====
  connect(): Promise<void>
  disconnect(): Promise<void>
  health(): Promise<HealthStatus>
  getServerVersion(): Promise<VersionInfo>
  supports(feature: string): boolean
  
  // ===== Core Querying =====
  query(question: string, options?: QueryOptions): Promise<Result>
  streamQuery(question: string, callbacks: StreamCallbacks): AsyncIterable<Chunk>
  estimateQuery(question: string): Promise<QueryEstimate>
  cancelQuery(queryId: string): Promise<void>
  retryQuery(queryId: string): Promise<Result>
  
  // ===== Context & Discovery =====
  listDatabases(): Promise<Database[]>
  getDatabaseSchema(database: string): Promise<Schema>
  getSchemaStatus(): Promise<SchemaStatus>
  suggestQuestions(partial: string): Promise<string[]>
  explainQuery(question: string): Promise<Explanation>
  
  // ===== Schema Monitoring =====
  subscribeToSchemaChanges(callback: SchemaChangeCallback): Subscription
  forceReindex(database?: string): Promise<ReindexResult>
  
  // ===== Error Recovery =====
  getQueryLogs(queryId: string): Promise<Log[]>
  getLastError(): CenecaError | null
  
  // ===== Events =====
  on(event: string, handler: Function): void
  off(event: string, handler: Function): void
}
```

### Core Types

```typescript
interface QueryOptions {
  databases?: string[];  // Specific databases to query
  timeout?: number;  // Max execution time (ms)
  pageSize?: number;  // Pagination size
  includeReasoningChain?: boolean;
  streamingMode?: 'standard' | 'adaptive';
  onProgress?: (progress: number) => void;
}

interface Result {
  queryId: string;
  rows: Array<Record<string, any>>;
  columns: Column[];
  totalRows: number;
  executionTime: number;
  databases: string[];  // Which DBs were queried
  reasoningChain?: ReasoningStep[];
  visualization?: ChartConfig;
  hasMore: boolean;
}

interface StreamCallbacks {
  onChunk: (chunk: Chunk) => void;
  onComplete: (result: Result) => void;
  onError: (error: CenecaError) => void;
  onReasoningStep?: (step: ReasoningStep) => void;
}

interface QueryEstimate {
  estimatedRows: number;
  estimatedSizeMB: number;
  estimatedTimeSeconds: number;
  databases: string[];
  confidence: 'low' | 'medium' | 'high';
}

interface SchemaStatus {
  databases: Array<{
    name: string;
    type: string;  // 'postgres', 'mongodb', etc.
    lastSchemaChange: string;  // ISO timestamp
    lastReindex: string;
    status: 'healthy' | 'reindexing' | 'error';
    tables: number;
    schemaHash: string;
  }>;
}

interface CenecaError extends Error {
  code: string;
  retryable: boolean;
  details: any;
  suggestion?: string;
}
```

### Authentication Patterns

```typescript
// Pattern 1: Token Provider (Recommended)
const ceneca = new CenecaClient({
  host: 'ceneca.company.com',
  tokenProvider: async () => {
    // Fetch fresh token from company's backend
    const response = await fetch('/api/auth/ceneca-token');
    const { token } = await response.json();
    return token;
  },
  onTokenExpired: async () => {
    // SDK will call tokenProvider again
  }
});

// Pattern 2: Static API Key (Less secure, simpler)
const ceneca = new CenecaClient({
  host: 'ceneca.company.com',
  apiKey: process.env.CENECA_API_KEY  // Server-side only!
});

// Pattern 3: OAuth Flow
const ceneca = new CenecaClient({
  host: 'ceneca.company.com',
  auth: {
    type: 'oauth',
    clientId: 'company-app-id',
    redirectUri: 'https://company.com/auth/callback'
  }
});
```

---

## API Endpoints

### New Endpoints Required

#### 1. Version & Compatibility
```
GET /api/health
Response: {
  status: "healthy",
  version: "2.8.0",
  apiVersion: "v2",
  supportedFeatures: [...],
  minSdkVersion: "2.5.0",
  maxSdkVersion: "2.99.99"
}
```

#### 2. Schema Status
```
GET /api/schema/status
Response: {
  databases: [
    {
      name: "postgres",
      type: "postgres",
      lastSchemaChange: "2025-10-06T14:30:00Z",
      lastReindex: "2025-10-06T14:31:00Z",
      status: "healthy",
      tables: 42,
      schemaHash: "a3f2e1b..."
    }
  ]
}
```

#### 3. Database List
```
GET /api/databases
Response: {
  databases: [
    {
      id: "postgres-prod",
      name: "Production Database",
      type: "postgres",
      status: "connected",
      tables: 42,
      permissions: ["read", "write"]
    }
  ]
}
```

#### 4. Database Schema
```
GET /api/databases/{database_id}/schema
Response: {
  database: "postgres-prod",
  tables: [
    {
      name: "customers",
      columns: [
        { name: "id", type: "integer", nullable: false },
        { name: "email", type: "varchar", nullable: false },
        { name: "created_at", type: "timestamp", nullable: false }
      ],
      rowCount: 1500000
    }
  ]
}
```

#### 5. Query Estimation
```
POST /api/query/estimate
Body: {
  question: "Show all customer orders"
}
Response: {
  estimatedRows: 2400000,
  estimatedSizeMB: 340,
  estimatedTimeSeconds: 12,
  databases: ["postgres", "mongodb"],
  confidence: "high"
}
```

#### 6. Query Suggestions
```
GET /api/query/suggest?q=show+sales
Response: {
  suggestions: [
    "Show total sales this month",
    "Show sales by product",
    "Show sales by region",
    "Show sales trends"
  ]
}
```

#### 7. Query Explanation
```
POST /api/query/explain
Body: {
  question: "Show top customers by revenue"
}
Response: {
  explanation: "This query will...",
  steps: [
    "Query customers table from postgres",
    "Query orders table from postgres",
    "Join and aggregate by customer",
    "Sort by total revenue descending",
    "Return top 10 results"
  ],
  databases: ["postgres"],
  estimatedTime: "2-5 seconds"
}
```

#### 8. Force Reindex
```
POST /api/schema/reindex
Body: {
  database: "postgres",  // Optional, reindex all if omitted
  force: true
}
Response: {
  success: true,
  database: "postgres",
  tablesReindexed: 42,
  timeMs: 3420,
  newSchemaHash: "b8d3f2c..."
}
```

#### 9. Schema Change Events (WebSocket)
```
WS /api/schema/events
Message format:
{
  type: "schema_changed",
  database: "postgres",
  timestamp: "2025-10-06T14:30:00Z",
  changes: [
    {
      table: "customers",
      column: "email_address",
      action: "renamed",
      newName: "contact_email"
    }
  ],
  reindexStatus: "in_progress"
}
```

### Leveraging Existing Infrastructure

Most of these endpoints can be built on top of existing code:

| New Endpoint | Existing Code to Use |
|--------------|---------------------|
| `/api/schema/status` | `db/registry/registry.py`, `schema_registry.db` |
| `/api/databases` | `db/registry/integrations.py` |
| `/api/databases/{id}/schema` | `db/registry/introspect_worker.py` |
| `/api/schema/reindex` | `performance/schema_monitor.py::check_and_reindex()` |
| `/api/schema/events` | `performance/schema_watcher.py` (add webhook support) |

---

## SDK Interface

### Complete TypeScript Definition

```typescript
// @ceneca/sdk/index.ts

export class CenecaClient {
  constructor(options: CenecaClientOptions);
  
  // Connection
  connect(): Promise<void>;
  disconnect(): Promise<void>;
  health(): Promise<HealthStatus>;
  getServerVersion(): Promise<VersionInfo>;
  supports(feature: string): boolean;
  
  // Querying
  query(question: string, options?: QueryOptions): Promise<Result>;
  streamQuery(question: string, callbacks: StreamCallbacks): AsyncIterable<Chunk>;
  estimateQuery(question: string): Promise<QueryEstimate>;
  explainQuery(question: string): Promise<Explanation>;
  suggestQuestions(partial: string): Promise<string[]>;
  
  // Query Management
  cancelQuery(queryId: string): Promise<void>;
  retryQuery(queryId: string): Promise<Result>;
  getQueryLogs(queryId: string): Promise<Log[]>;
  getQueryHistory(options?: HistoryOptions): Promise<Query[]>;
  
  // Databases
  listDatabases(): Promise<Database[]>;
  getDatabaseSchema(database: string): Promise<Schema>;
  testDatabaseConnection(database: string): Promise<ConnectionTest>;
  
  // Schema Monitoring
  getSchemaStatus(): Promise<SchemaStatus>;
  subscribeToSchemaChanges(callback: SchemaChangeCallback): Subscription;
  forceReindex(database?: string): Promise<ReindexResult>;
  
  // Events
  on(event: ClientEvent, handler: EventHandler): void;
  off(event: ClientEvent, handler: EventHandler): void;
  
  // Error Recovery
  getLastError(): CenecaError | null;
  retry<T>(fn: () => Promise<T>, options?: RetryOptions): Promise<T>;
}

// Types
export interface CenecaClientOptions {
  host: string;
  tokenProvider?: () => Promise<string>;
  apiKey?: string;
  auth?: AuthConfig;
  limits?: LimitConfig;
  onTokenExpired?: () => void | Promise<void>;
  onError?: (error: CenecaError) => void;
}

export interface QueryOptions {
  databases?: string[];
  timeout?: number;
  pageSize?: number;
  includeReasoningChain?: boolean;
  streamingMode?: 'standard' | 'adaptive';
  onProgress?: (progress: number) => void;
}

export interface Result {
  queryId: string;
  rows: Array<Record<string, any>>;
  columns: Column[];
  totalRows: number;
  executionTime: number;
  databases: string[];
  reasoningChain?: ReasoningStep[];
  visualization?: ChartConfig;
  hasMore: boolean;
}

export interface StreamCallbacks {
  onChunk: (chunk: Chunk) => void;
  onComplete: (result: Result) => void;
  onError: (error: CenecaError) => void;
  onReasoningStep?: (step: ReasoningStep) => void;
}

export interface SchemaStatus {
  databases: Array<{
    name: string;
    type: string;
    lastSchemaChange: string;
    lastReindex: string;
    status: 'healthy' | 'reindexing' | 'error';
    tables: number;
    schemaHash: string;
  }>;
}

export interface CenecaError extends Error {
  code: string;
  retryable: boolean;
  details: any;
  suggestion?: string;
}

export type ClientEvent = 
  | 'connected'
  | 'disconnected'
  | 'query_started'
  | 'query_completed'
  | 'query_failed'
  | 'schema_changed'
  | 'error';

export type SchemaChangeCallback = (change: SchemaChange) => void;

export interface Subscription {
  unsubscribe(): void;
}
```

### React Hooks Package

```typescript
// @ceneca/react

export function useCenecaQuery(
  question: string,
  options?: QueryOptions
): {
  data: Result | null;
  isLoading: boolean;
  error: CenecaError | null;
  refetch: () => void;
}

export function useCenecaStream(
  question: string,
  options?: QueryOptions
): {
  chunks: Chunk[];
  isStreaming: boolean;
  progress: number;
  error: CenecaError | null;
  cancel: () => void;
}

export function useCenecaDatabases(): {
  databases: Database[];
  isLoading: boolean;
  error: CenecaError | null;
}

export function useCenecaSchema(database: string): {
  schema: Schema | null;
  isLoading: boolean;
  error: CenecaError | null;
}

export function useCenecaSchemaStatus(): {
  status: SchemaStatus | null;
  isLoading: boolean;
  error: CenecaError | null;
  subscribe: (callback: SchemaChangeCallback) => () => void;
}
```

---

## Documentation Requirements

For successful headless API adoption, documentation must include:

### 1. Quick Start Guide
- Installation steps
- Basic authentication setup
- First query example
- Common patterns

### 2. Authentication Guide
- All authentication methods
- Token lifecycle management
- Security best practices
- Multi-user scenarios

### 3. Error Handling Guide
- Complete error code reference
- Retry strategies
- Debugging tips
- Support escalation paths

### 4. Performance Guide
- Rate limits and quotas
- Query optimization tips
- Pagination best practices
- Cost estimation

### 5. Schema Management Guide
- How schema monitoring works
- Handling schema changes
- Reindexing strategies
- Multi-environment setups

### 6. Migration Guides
- Version upgrade paths
- Breaking changes
- Deprecation timeline
- Rollback procedures

### 7. API Reference
- Complete endpoint documentation
- Request/response examples
- SDK method reference
- TypeScript definitions

### 8. Example Applications
- React dashboard
- Vue analytics app
- Node.js backend integration
- Mobile app (React Native)

---

## Support Burden Expectations

Based on headless API integration patterns, expect these support questions **weekly**:

| Question Category | Frequency | Typical Cause |
|-------------------|-----------|---------------|
| "Why is my query slow?" | High | Joining too many databases, no pagination |
| "I get 'unauthorized'" | High | Token expired, no refresh logic |
| "Results are wrong" | Medium | Database schema changed |
| "Works locally, not production" | Medium | Different DB credentials/schema |
| "Can I query X?" | Medium | Unsupported database type or feature |
| "How do I...?" | High | Missing SDK method or unclear docs |
| "Query stuck/timeout" | Medium | Stream not handled properly |
| "Out of memory" | Low | Trying to load huge result set |

### Mitigation Strategies

1. **Comprehensive Error Messages** - Include suggestions in every error
2. **Interactive Debugger** - SDK method to diagnose issues: `ceneca.diagnose()`
3. **Example Code Library** - Cover all common patterns
4. **Health Check Dashboard** - Web UI showing system status
5. **Telemetry (opt-in)** - Automatic error reporting to catch issues early

---

## Timeline & Effort Estimates

### Phase 1: Core Headless API (3-4 weeks)
- Add version endpoints to existing server
- Build basic SDK (query, stream, list databases)
- Implement authentication flow
- Create TypeScript types
- Write core documentation

### Phase 2: Schema Exposure (1-2 weeks)
- Expose schema status endpoint (uses existing registry)
- Add schema change webhooks to schema_watcher
- Implement SDK schema methods
- Add schema documentation

### Phase 3: Advanced Features (2-3 weeks)
- Query estimation
- Query suggestions
- Reasoning chain streaming
- React hooks package
- Advanced error handling

### Phase 4: Polish & Launch (2 weeks)
- Complete documentation
- Example applications
- Performance testing
- Beta user feedback
- Public launch

**Total: 8-11 weeks for complete headless API**

---

## Success Metrics

Track these to measure headless API adoption:

1. **SDK Downloads** - NPM installs per week
2. **Active Integrations** - Unique companies using the SDK
3. **Query Volume** - Queries per day via headless API
4. **Error Rates** - % of queries that fail
5. **Support Ticket Volume** - Tickets per 100 active users
6. **Time to First Query** - How quickly companies integrate
7. **Feature Adoption** - Which SDK methods are most used
8. **Version Distribution** - SDK versions in use

---

## Conclusion

The headless API pattern offers maximum flexibility for companies wanting to integrate Ceneca's cross-database querying into their own applications. With Ceneca's existing schema monitoring infrastructure, we have a **significant competitive advantage** in handling one of the hardest problems: schema drift.

**Key Success Factors:**
1. Make streaming "just work" with sensible defaults
2. Build bulletproof authentication and token management
3. Provide structured, actionable error messages
4. Expose schema monitoring capabilities via clean APIs
5. Maintain strict version compatibility
6. Create comprehensive documentation and examples

**Next Steps:**
1. Review and approve this design document
2. Prioritize which integration patterns to build first
3. Create detailed API specifications
4. Begin Phase 1 implementation
5. Recruit beta users for early feedback



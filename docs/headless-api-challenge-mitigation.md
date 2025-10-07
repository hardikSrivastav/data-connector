# Headless API Challenge Mitigation

## Overview

This document outlines **minimal, practical solutions** to the 8 critical concerns identified in the headless API integration design. The focus is on approaches that require minimal development effort while providing maximum value to integrating companies.

---

## Challenge #1: Streaming is Hard (And Companies Will Get It Wrong)

### The Problem

Ceneca's backend streams results via SSE/WebSocket. Most companies integrating via headless API aren't experienced with streaming and will expect synchronous, complete results.

### Minimal Solution: Single Callback Pattern

**Decision:** Make streaming the default, but expose it through a single, simple callback interface.

### Implementation

#### Step 1: Normalize Events (30 minutes)

Create a simple event wrapper:

```typescript
// In SDK: src/types.ts
export type StreamEvent = 
  | { type: 'status'; timestamp: string; data: { message: string; progress?: number } }
  | { type: 'reasoning'; timestamp: string; data: { step: string; details: any } }
  | { type: 'sql_query'; timestamp: string; data: { query: string; source: string } }
  | { type: 'data'; timestamp: string; data: { rows: any[]; columns: string[] } }
  | { type: 'visualization'; timestamp: string; data: { chartConfig: any } }
  | { type: 'complete'; timestamp: string; data: { result: any } }
  | { type: 'error'; timestamp: string; data: { message: string; code: string } };

function normalizeEvent(type: string, data: any): StreamEvent {
  return {
    type: type as any,
    timestamp: new Date().toISOString(),
    data
  };
}
```

#### Step 2: Single Callback Interface (1-2 hours)

Wrap existing `agent-client.ts` streaming:

```typescript
// In SDK: src/client.ts
export interface QueryOptions {
  onStream?: (event: StreamEvent) => void;
  timeout?: number;
  databases?: string[];
}

export class CenecaClient {
  async query(question: string, options?: QueryOptions): Promise<Result> {
    // If no callback provided, buffer everything internally
    if (!options?.onStream) {
      return this.bufferQuery(question, options);
    }
    
    // Stream to user via single callback
    return this.streamQuery(question, options);
  }
  
  private async streamQuery(question: string, options: QueryOptions): Promise<Result> {
    return this.agentClient.streamQuery(question, {
      onChunk: (chunk) => {
        options.onStream?.(normalizeEvent('data', chunk));
      },
      onStatus: (status) => {
        options.onStream?.(normalizeEvent('status', status));
      },
      onComplete: (result) => {
        options.onStream?.(normalizeEvent('complete', result));
        return result;
      },
      onError: (error) => {
        options.onStream?.(normalizeEvent('error', error));
        throw error;
      }
    });
  }
  
  private async bufferQuery(question: string, options?: QueryOptions): Promise<Result> {
    // No callback = wait for completion and return final result
    let finalResult: Result;
    
    await this.agentClient.streamQuery(question, {
      onComplete: (result) => {
        finalResult = result;
      },
      onError: (error) => {
        throw error;
      }
    });
    
    return finalResult!;
  }
}
```

#### Step 3: Optional Helper for Easier Routing (30 minutes)

Provide a utility to make event handling cleaner:

```typescript
// In SDK: src/utils.ts
export function createStreamHandler(handlers: {
  status?: (data: any) => void;
  reasoning?: (data: any) => void;
  sql_query?: (data: any) => void;
  data?: (data: any) => void;
  visualization?: (data: any) => void;
  complete?: (data: any) => void;
  error?: (data: any) => void;
}) {
  return (event: StreamEvent) => {
    const handler = handlers[event.type];
    if (handler) {
      handler(event.data);
    }
  };
}
```

### Usage Examples

#### Simple: Just Show Progress

```javascript
import { CenecaClient } from '@ceneca/sdk';

const ceneca = new CenecaClient({ host: 'ceneca.company.com' });

await ceneca.query("Show sales data", {
  onStream: (event) => {
    if (event.type === 'status') {
      updateProgressBar(event.data.message);
    }
    if (event.type === 'complete') {
      showResults(event.data);
    }
  }
});
```

#### With Helper Function

```javascript
import { CenecaClient, createStreamHandler } from '@ceneca/sdk';

const ceneca = new CenecaClient({ host: 'ceneca.company.com' });

await ceneca.query("Show sales by region", {
  onStream: createStreamHandler({
    status: (data) => console.log('Status:', data.message),
    data: (data) => appendToTable(data.rows),
    complete: (data) => hideSpinner(),
    error: (data) => showError(data.message)
  })
});
```

#### No Streaming (Buffered)

```javascript
// No callback = SDK buffers everything
const result = await ceneca.query("Show sales data");
console.log(result.rows); // Complete result

// User never sees streaming, but it happened behind the scenes
```

#### Show Everything (Debugging)

```javascript
await ceneca.query("Show sales data", {
  onStream: (event) => {
    console.log(`[${event.type}]`, event.data);
  }
});
```

### Documentation Template

```markdown
## Streaming Queries

Ceneca streams query results in real-time, providing progress updates, reasoning steps, and data as it's processed.

### Basic Usage

```javascript
await ceneca.query("Your question here", {
  onStream: (event) => {
    // Handle different event types
    switch(event.type) {
      case 'status':
        console.log('Progress:', event.data.message);
        break;
      case 'data':
        displayData(event.data.rows);
        break;
      case 'complete':
        console.log('Query finished!');
        break;
      case 'error':
        console.error('Error:', event.data.message);
        break;
    }
  }
});
```

### Event Types

| Type | Description | Data Format |
|------|-------------|-------------|
| `status` | Progress updates | `{ message: string, progress?: number }` |
| `reasoning` | Reasoning chain steps | `{ step: string, details: any }` |
| `sql_query` | SQL queries executed | `{ query: string, source: string }` |
| `data` | Result data chunks | `{ rows: any[], columns: string[] }` |
| `visualization` | Chart configurations | `{ chartConfig: any }` |
| `complete` | Query finished | `{ result: Result }` |
| `error` | Error occurred | `{ message: string, code: string }` |

### Without Streaming (Buffered Mode)

If you don't need real-time updates, omit the `onStream` callback:

```javascript
const result = await ceneca.query("Your question");
// Returns complete result after streaming finishes
```
```

### Implementation Effort

| Task | Time | Difficulty |
|------|------|-----------|
| Create `StreamEvent` type | 30 min | Easy |
| Wrap existing callbacks into `onStream` | 1 hour | Easy |
| Add buffer-if-no-callback logic | 1 hour | Easy |
| Create `createStreamHandler` helper | 30 min | Easy |
| Write documentation | 1 hour | Easy |
| **Total** | **4 hours** | **Easy** |

### Why This Works

1. **Minimal code**: Wraps existing streaming infrastructure
2. **Single pattern**: Users learn one callback interface
3. **Flexible**: Users handle events they care about, ignore others
4. **Future-proof**: New event types can be added without API changes
5. **Optional buffering**: Users who don't want streaming don't see it
6. **Leverages existing work**: No changes to backend required

---

## Challenge #2: Authentication Token Management

### The Problem

Companies will:
- Hardcode tokens in frontend (security risk)
- Forget to refresh expired tokens
- Share tokens across users (data leak)
- Not scope tokens properly

### Minimal Solution: Token Provider Pattern

**Decision:** Force companies to implement token refresh logic by requiring a `tokenProvider` function.

### Implementation

#### Server Side: Token Endpoint (1 hour)

Add token generation to existing auth system:

```python
# In server/agent/endpoints.py

@app.post("/api/auth/token")
async def generate_api_token(
    user_id: str = Depends(get_current_user),
    expires_in: int = 1800  # 30 minutes default
):
    """Generate short-lived API token for headless API access"""
    token = create_jwt_token(
        user_id=user_id,
        expires_in=expires_in,
        scopes=["query", "schema:read"]
    )
    
    return {
        "token": token,
        "expires_in": expires_in,
        "expires_at": datetime.utcnow() + timedelta(seconds=expires_in)
    }
```

#### SDK Side: Token Provider (2 hours)

```typescript
// In SDK: src/client.ts

export interface AuthConfig {
  // Option 1: Dynamic token provider (recommended)
  tokenProvider?: () => Promise<string>;
  
  // Option 2: Static API key (server-side only)
  apiKey?: string;
  
  // Callbacks
  onTokenExpired?: () => void | Promise<void>;
}

export class CenecaClient {
  private currentToken: string | null = null;
  private tokenExpiresAt: Date | null = null;
  
  constructor(private config: {
    host: string;
    auth: AuthConfig;
  }) {}
  
  private async getToken(): Promise<string> {
    // Static API key
    if (this.config.auth.apiKey) {
      return this.config.auth.apiKey;
    }
    
    // Token provider
    if (this.config.auth.tokenProvider) {
      // Check if current token is still valid
      if (this.currentToken && this.tokenExpiresAt && this.tokenExpiresAt > new Date()) {
        return this.currentToken;
      }
      
      // Get fresh token
      this.currentToken = await this.config.auth.tokenProvider();
      this.tokenExpiresAt = new Date(Date.now() + 25 * 60 * 1000); // 25 min (5 min buffer)
      
      return this.currentToken;
    }
    
    throw new CenecaError({
      code: 'AUTH_NOT_CONFIGURED',
      message: 'No authentication method configured',
      suggestion: 'Provide either tokenProvider or apiKey'
    });
  }
  
  async query(question: string, options?: QueryOptions): Promise<Result> {
    try {
      const token = await this.getToken();
      
      return await this.executeQuery(question, token, options);
    } catch (error) {
      if (error.code === 'TOKEN_EXPIRED') {
        // Token expired mid-query, refresh and retry
        this.currentToken = null;
        this.config.auth.onTokenExpired?.();
        
        const newToken = await this.getToken();
        return await this.executeQuery(question, newToken, options);
      }
      throw error;
    }
  }
}
```

### Usage Examples

#### Recommended: Token Provider (Frontend)

```javascript
const ceneca = new CenecaClient({
  host: 'ceneca.company.com',
  auth: {
    tokenProvider: async () => {
      // Fetch fresh token from their backend
      const response = await fetch('/api/auth/ceneca-token', {
        credentials: 'include'  // Send user's session cookie
      });
      const { token } = await response.json();
      return token;
    },
    onTokenExpired: () => {
      console.log('Token expired, fetching new one...');
    }
  }
});

// SDK automatically manages token refresh
const result = await ceneca.query("Show sales");
```

#### Static API Key (Backend Only)

```javascript
// ONLY for server-side Node.js code
const ceneca = new CenecaClient({
  host: 'ceneca.company.com',
  auth: {
    apiKey: process.env.CENECA_API_KEY  // From environment, never in frontend
  }
});
```

### Company Backend Implementation

Companies need to implement token generation:

```javascript
// Their backend: /api/auth/ceneca-token
app.get('/api/auth/ceneca-token', async (req, res) => {
  const userId = req.session.userId;
  
  // Call Ceneca's token endpoint
  const response = await fetch('https://ceneca.company.com/api/auth/token', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${CENECA_SERVICE_ACCOUNT_KEY}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      user_id: userId,
      expires_in: 1800  // 30 minutes
    })
  });
  
  const { token, expires_in } = await response.json();
  res.json({ token, expires_in });
});
```

### Documentation Template

```markdown
## Authentication

Ceneca SDK uses short-lived tokens for security. You must provide a `tokenProvider` function that fetches fresh tokens.

### Setup

1. Implement a backend endpoint that generates Ceneca tokens:

```javascript
// Your backend
app.get('/api/auth/ceneca-token', async (req, res) => {
  const userId = req.session.userId;
  
  const response = await fetch('https://ceneca.your-domain.com/api/auth/token', {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${CENECA_SERVICE_KEY}` },
    body: JSON.stringify({ user_id: userId })
  });
  
  res.json(await response.json());
});
```

2. Configure SDK with token provider:

```javascript
const ceneca = new CenecaClient({
  host: 'ceneca.your-domain.com',
  auth: {
    tokenProvider: async () => {
      const response = await fetch('/api/auth/ceneca-token');
      const { token } = await response.json();
      return token;
    }
  }
});
```

### Security Best Practices

✅ **DO:**
- Implement `tokenProvider` for frontend apps
- Store API keys in environment variables (backend only)
- Use short-lived tokens (15-30 minutes)
- Scope tokens per user

❌ **DON'T:**
- Hardcode tokens in frontend code
- Share API keys across users
- Use long-lived tokens in browser apps
- Commit tokens to version control
```

### Implementation Effort

| Task | Time | Difficulty |
|------|------|-----------|
| Add token generation endpoint | 1 hour | Easy |
| Implement token provider in SDK | 2 hours | Medium |
| Add auto-refresh logic | 1 hour | Medium |
| Write documentation & examples | 1 hour | Easy |
| **Total** | **5 hours** | **Medium** |

### Why This Works

1. **Forces best practices**: Companies can't use SDK without implementing token refresh
2. **Automatic refresh**: SDK handles token expiration transparently
3. **Flexible**: Supports both dynamic tokens and static API keys
4. **Secure by default**: No way to accidentally expose tokens in frontend
5. **User-scoped**: Each user gets their own token with appropriate permissions

---

## Challenge #3: Query Cost Explosions

### The Problem

Companies will write innocent-looking queries that hammer the backend:
- "Show all customer purchases" → 50M rows
- No pagination → 2GB result
- No timeouts → 10 minute query

### Minimal Solution: Built-in Limits + Warnings

**Decision:** Add sensible defaults with clear error messages when limits are hit.

### Implementation

#### SDK Side: Default Limits (1 hour)

```typescript
// In SDK: src/client.ts

export interface LimitConfig {
  maxRowsPerQuery?: number;      // Default: 100,000
  maxExecutionTime?: number;      // Default: 60 seconds
  maxConcurrentQueries?: number;  // Default: 5
  pageSize?: number;              // Default: 1,000
}

export class CenecaClient {
  private readonly limits: Required<LimitConfig>;
  private activeQueries = 0;
  
  constructor(config: {
    host: string;
    auth: AuthConfig;
    limits?: LimitConfig;
  }) {
    this.limits = {
      maxRowsPerQuery: config.limits?.maxRowsPerQuery ?? 100_000,
      maxExecutionTime: config.limits?.maxExecutionTime ?? 60_000,
      maxConcurrentQueries: config.limits?.maxConcurrentQueries ?? 5,
      pageSize: config.limits?.pageSize ?? 1_000
    };
  }
  
  async query(question: string, options?: QueryOptions): Promise<Result> {
    // Check concurrent query limit
    if (this.activeQueries >= this.limits.maxConcurrentQueries) {
      throw new CenecaError({
        code: 'TOO_MANY_CONCURRENT_QUERIES',
        message: `Maximum ${this.limits.maxConcurrentQueries} concurrent queries allowed`,
        suggestion: 'Wait for existing queries to complete or increase limit',
        retryable: true
      });
    }
    
    this.activeQueries++;
    
    try {
      // Set timeout
      const timeout = options?.timeout ?? this.limits.maxExecutionTime;
      const timeoutPromise = new Promise((_, reject) => {
        setTimeout(() => {
          reject(new CenecaError({
            code: 'QUERY_TIMEOUT',
            message: `Query exceeded ${timeout}ms timeout`,
            suggestion: 'Try narrowing your query or increasing timeout',
            retryable: true
          }));
        }, timeout);
      });
      
      // Race between query and timeout
      const result = await Promise.race([
        this.executeQuery(question, options),
        timeoutPromise
      ]) as Result;
      
      // Check row limit
      if (result.totalRows > this.limits.maxRowsPerQuery) {
        throw new CenecaError({
          code: 'RESULT_TOO_LARGE',
          message: `Query returned ${result.totalRows} rows (limit: ${this.limits.maxRowsPerQuery})`,
          suggestion: 'Add date filters or pagination to narrow results',
          details: {
            totalRows: result.totalRows,
            limit: this.limits.maxRowsPerQuery,
            excessRows: result.totalRows - this.limits.maxRowsPerQuery
          },
          retryable: false
        });
      }
      
      return result;
    } finally {
      this.activeQueries--;
    }
  }
}
```

#### Server Side: Query Estimation (2 hours)

Add estimation endpoint:

```python
# In server/agent/endpoints.py

@app.post("/api/query/estimate")
async def estimate_query(
    request: EstimateRequest,
    user_id: str = Depends(get_current_user)
):
    """Estimate query size and execution time before running"""
    
    # Parse query intent
    analysis = await analyze_query(request.question)
    
    # Estimate from schema metadata
    estimated_rows = 0
    databases = []
    
    for table in analysis.tables:
        table_meta = await get_table_metadata(table.database, table.name)
        estimated_rows += table_meta.row_count
        databases.append(table.database)
    
    # Apply filters (rough estimation)
    if analysis.has_date_filter:
        estimated_rows = estimated_rows * 0.1  # Assume 10% of data
    if analysis.has_other_filters:
        estimated_rows = estimated_rows * 0.3
    
    estimated_size_mb = (estimated_rows * 100) / (1024 * 1024)  # Rough: 100 bytes/row
    estimated_time_seconds = max(2, estimated_rows / 10000)  # Rough: 10k rows/sec
    
    return {
        "estimated_rows": int(estimated_rows),
        "estimated_size_mb": round(estimated_size_mb, 2),
        "estimated_time_seconds": round(estimated_time_seconds, 1),
        "databases": list(set(databases)),
        "confidence": "high" if analysis.has_specific_filters else "low"
    }
```

#### SDK: Pre-Query Estimation (1 hour)

```typescript
// In SDK: src/client.ts

export class CenecaClient {
  async estimateQuery(question: string): Promise<QueryEstimate> {
    const token = await this.getToken();
    
    const response = await fetch(`${this.config.host}/api/query/estimate`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ question })
    });
    
    return await response.json();
  }
  
  async queryWithEstimate(question: string, options?: QueryOptions): Promise<Result> {
    // Estimate first
    const estimate = await this.estimateQuery(question);
    
    // Warn if large
    if (estimate.estimatedRows > 50_000) {
      console.warn(
        `⚠️  Large query detected: ~${estimate.estimatedRows.toLocaleString()} rows, ` +
        `~${estimate.estimatedSizeMB}MB, ~${estimate.estimatedTimeSeconds}s`
      );
    }
    
    // Auto-paginate if too large
    if (estimate.estimatedRows > this.limits.maxRowsPerQuery) {
      return this.queryWithPagination(question, options);
    }
    
    return this.query(question, options);
  }
}
```

### Usage Examples

#### With Estimation

```javascript
// Check before running
const estimate = await ceneca.estimateQuery("Show all customer orders");

console.log(`Estimated: ${estimate.estimatedRows} rows, ${estimate.estimatedSizeMB}MB`);

if (estimate.estimatedRows > 100000) {
  const proceed = confirm(`This will return ${estimate.estimatedRows} rows. Continue?`);
  if (!proceed) return;
}

const result = await ceneca.query("Show all customer orders");
```

#### Auto-Estimate Mode

```javascript
// SDK automatically estimates and warns
const result = await ceneca.queryWithEstimate("Show all customer orders");
// Console: ⚠️ Large query detected: ~2,400,000 rows, ~340MB, ~12s
```

#### Custom Limits

```javascript
const ceneca = new CenecaClient({
  host: 'ceneca.company.com',
  auth: { tokenProvider: getToken },
  limits: {
    maxRowsPerQuery: 50_000,     // Stricter limit
    maxExecutionTime: 30_000,     // 30 seconds max
    maxConcurrentQueries: 3
  }
});
```

### Error Messages

```typescript
// When hitting limits:
{
  code: 'RESULT_TOO_LARGE',
  message: 'Query returned 2,400,000 rows (limit: 100,000)',
  suggestion: 'Add date filters or pagination to narrow results. Try: "Show customer orders from last month"',
  details: {
    totalRows: 2400000,
    limit: 100000,
    excessRows: 2300000
  },
  retryable: false
}

{
  code: 'QUERY_TIMEOUT',
  message: 'Query exceeded 60000ms timeout',
  suggestion: 'Try narrowing your query with filters or increase timeout in SDK config',
  retryable: true
}
```

### Implementation Effort

| Task | Time | Difficulty |
|------|------|-----------|
| Add default limits to SDK | 1 hour | Easy |
| Implement timeout logic | 1 hour | Easy |
| Create estimation endpoint | 2 hours | Medium |
| Add SDK estimation methods | 1 hour | Easy |
| Write error messages & docs | 1 hour | Easy |
| **Total** | **6 hours** | **Medium** |

### Why This Works

1. **Safe defaults**: Companies can't accidentally DDoS themselves
2. **Clear errors**: When limits hit, they know exactly what to do
3. **Proactive warnings**: Estimation helps them avoid problems
4. **Configurable**: Companies can adjust limits for their use case
5. **No backend changes**: Uses existing query infrastructure

---

## Challenge #4: Error Handling is Ambiguous

### The Problem

When a query fails, it's unclear **whose fault it is** and **what to do about it**:

**Common failure scenarios:**
- Ceneca couldn't parse the question
- Database is unreachable
- Database credentials expired
- Column doesn't exist (schema changed)
- User lacks permissions
- Network timeout
- Query syntax error

**What companies see without structure:**
```javascript
try {
  const result = await ceneca.query("Show sales");
} catch (err) {
  console.log(err); // "Query failed"
  // Now what? Retry? Show error? Call support?
  // Is it temporary? Permanent? User's fault?
}
```

### Minimal Solution: Structured Error Codes

**Decision:** Implement standardized error codes with clear guidance on how to handle each error type.

### Implementation

#### Step 1: Error Class Definition (1 hour)

```typescript
// In SDK: src/errors.ts

export class CenecaError extends Error {
  code: string;
  retryable: boolean;
  suggestion?: string;
  details?: any;
  timestamp: string;
  
  constructor(params: {
    code: string;
    message: string;
    retryable: boolean;
    suggestion?: string;
    details?: any;
  }) {
    super(params.message);
    this.name = 'CenecaError';
    this.code = params.code;
    this.retryable = params.retryable;
    this.suggestion = params.suggestion;
    this.details = params.details;
    this.timestamp = new Date().toISOString();
    
    // Maintain proper stack trace
    if (Error.captureStackTrace) {
      Error.captureStackTrace(this, CenecaError);
    }
  }
  
  toJSON() {
    return {
      name: this.name,
      code: this.code,
      message: this.message,
      retryable: this.retryable,
      suggestion: this.suggestion,
      details: this.details,
      timestamp: this.timestamp
    };
  }
}

// Error code constants for easy reference
export const ErrorCodes = {
  // Authentication errors (4xx-style)
  AUTH_NOT_CONFIGURED: 'AUTH_NOT_CONFIGURED',
  TOKEN_EXPIRED: 'TOKEN_EXPIRED',
  INVALID_TOKEN: 'INVALID_TOKEN',
  INSUFFICIENT_PERMISSIONS: 'INSUFFICIENT_PERMISSIONS',
  
  // Database errors (5xx-style)
  DATABASE_UNREACHABLE: 'DATABASE_UNREACHABLE',
  DATABASE_AUTH_FAILED: 'DATABASE_AUTH_FAILED',
  DATABASE_TIMEOUT: 'DATABASE_TIMEOUT',
  
  // Query errors (4xx-style)
  QUERY_PARSING_FAILED: 'QUERY_PARSING_FAILED',
  QUERY_AMBIGUOUS: 'QUERY_AMBIGUOUS',
  QUERY_TIMEOUT: 'QUERY_TIMEOUT',
  INVALID_QUERY: 'INVALID_QUERY',
  
  // Schema errors
  COLUMN_NOT_FOUND: 'COLUMN_NOT_FOUND',
  TABLE_NOT_FOUND: 'TABLE_NOT_FOUND',
  SCHEMA_CHANGED: 'SCHEMA_CHANGED',
  SCHEMA_REINDEX_IN_PROGRESS: 'SCHEMA_REINDEX_IN_PROGRESS',
  
  // Limit errors
  RESULT_TOO_LARGE: 'RESULT_TOO_LARGE',
  TOO_MANY_CONCURRENT_QUERIES: 'TOO_MANY_CONCURRENT_QUERIES',
  RATE_LIMIT_EXCEEDED: 'RATE_LIMIT_EXCEEDED',
  
  // System errors (5xx-style)
  NETWORK_ERROR: 'NETWORK_ERROR',
  SERVER_ERROR: 'SERVER_ERROR',
  SERVICE_UNAVAILABLE: 'SERVICE_UNAVAILABLE',
  
  // Unknown
  UNKNOWN_ERROR: 'UNKNOWN_ERROR'
} as const;
```

#### Step 2: Error Factory Functions (1 hour)

Create helpers to generate consistent errors:

```typescript
// In SDK: src/errors.ts

export const createError = {
  // Authentication errors
  authNotConfigured: () => new CenecaError({
    code: ErrorCodes.AUTH_NOT_CONFIGURED,
    message: 'No authentication method configured',
    retryable: false,
    suggestion: 'Provide either tokenProvider or apiKey in CenecaClient config'
  }),
  
  tokenExpired: () => new CenecaError({
    code: ErrorCodes.TOKEN_EXPIRED,
    message: 'Authentication token has expired',
    retryable: true,
    suggestion: 'Token will be automatically refreshed. If issue persists, check your tokenProvider implementation'
  }),
  
  insufficientPermissions: (details: { required: string; current: string[] }) => new CenecaError({
    code: ErrorCodes.INSUFFICIENT_PERMISSIONS,
    message: `You do not have permission to access this data`,
    retryable: false,
    suggestion: 'Contact your administrator to request access',
    details
  }),
  
  // Database errors
  databaseUnreachable: (database: string, host?: string) => new CenecaError({
    code: ErrorCodes.DATABASE_UNREACHABLE,
    message: `Cannot connect to ${database} database`,
    retryable: true,
    suggestion: 'Check database connection and credentials. Database may be temporarily down.',
    details: { database, host }
  }),
  
  databaseAuthFailed: (database: string) => new CenecaError({
    code: ErrorCodes.DATABASE_AUTH_FAILED,
    message: `Authentication failed for ${database} database`,
    retryable: false,
    suggestion: 'Verify database credentials in Ceneca configuration',
    details: { database }
  }),
  
  // Query errors
  queryParsingFailed: (question: string, reason?: string) => new CenecaError({
    code: ErrorCodes.QUERY_PARSING_FAILED,
    message: 'Could not understand the query',
    retryable: false,
    suggestion: reason || 'Try rephrasing your question more specifically',
    details: { question, reason }
  }),
  
  queryAmbiguous: (question: string, suggestions: string[]) => new CenecaError({
    code: ErrorCodes.QUERY_AMBIGUOUS,
    message: 'Query has multiple possible interpretations',
    retryable: false,
    suggestion: `Try being more specific. For example: ${suggestions.slice(0, 3).join(' OR ')}`,
    details: { question, suggestions }
  }),
  
  queryTimeout: (timeout: number) => new CenecaError({
    code: ErrorCodes.QUERY_TIMEOUT,
    message: `Query exceeded ${timeout}ms timeout`,
    retryable: true,
    suggestion: 'Try narrowing your query with date filters or increase timeout in SDK config',
    details: { timeout }
  }),
  
  // Schema errors
  columnNotFound: (column: string, table: string, similarColumns?: string[]) => new CenecaError({
    code: ErrorCodes.COLUMN_NOT_FOUND,
    message: `Column "${column}" not found in ${table} table`,
    retryable: true,
    suggestion: similarColumns?.length 
      ? `Schema may have changed. Did you mean: ${similarColumns.join(', ')}?`
      : 'Schema may have changed. Check available columns or wait for reindexing to complete.',
    details: { column, table, similarColumns }
  }),
  
  tableNotFound: (table: string, database: string, similarTables?: string[]) => new CenecaError({
    code: ErrorCodes.TABLE_NOT_FOUND,
    message: `Table "${table}" not found in ${database}`,
    retryable: true,
    suggestion: similarTables?.length
      ? `Did you mean: ${similarTables.join(', ')}?`
      : 'Verify table name or check database schema',
    details: { table, database, similarTables }
  }),
  
  schemaChanged: (database: string, reindexing: boolean) => new CenecaError({
    code: ErrorCodes.SCHEMA_CHANGED,
    message: `Database schema for ${database} has changed`,
    retryable: true,
    suggestion: reindexing 
      ? 'Reindexing in progress. Please retry in a few moments.'
      : 'Schema update detected. Triggering reindex...',
    details: { database, reindexing }
  }),
  
  // Limit errors
  resultTooLarge: (totalRows: number, limit: number) => new CenecaError({
    code: ErrorCodes.RESULT_TOO_LARGE,
    message: `Query returned ${totalRows.toLocaleString()} rows (limit: ${limit.toLocaleString()})`,
    retryable: false,
    suggestion: 'Add date filters or pagination to narrow results. Example: "Show orders from last month"',
    details: { totalRows, limit, excessRows: totalRows - limit }
  }),
  
  tooManyConcurrentQueries: (limit: number) => new CenecaError({
    code: ErrorCodes.TOO_MANY_CONCURRENT_QUERIES,
    message: `Maximum ${limit} concurrent queries allowed`,
    retryable: true,
    suggestion: 'Wait for existing queries to complete or increase limit in SDK config',
    details: { limit }
  }),
  
  // System errors
  networkError: (originalError: Error) => new CenecaError({
    code: ErrorCodes.NETWORK_ERROR,
    message: 'Network error occurred',
    retryable: true,
    suggestion: 'Check your internet connection and try again',
    details: { originalError: originalError.message }
  }),
  
  serverError: (statusCode?: number, details?: any) => new CenecaError({
    code: ErrorCodes.SERVER_ERROR,
    message: 'Server error occurred',
    retryable: true,
    suggestion: 'If issue persists, contact support',
    details: { statusCode, ...details }
  })
};
```

#### Step 3: Server-Side Error Responses (2 hours)

Standardize error responses from backend:

```python
# In server/agent/errors.py

from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel

class ErrorCode(str, Enum):
    # Authentication
    AUTH_NOT_CONFIGURED = "AUTH_NOT_CONFIGURED"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    INVALID_TOKEN = "INVALID_TOKEN"
    INSUFFICIENT_PERMISSIONS = "INSUFFICIENT_PERMISSIONS"
    
    # Database
    DATABASE_UNREACHABLE = "DATABASE_UNREACHABLE"
    DATABASE_AUTH_FAILED = "DATABASE_AUTH_FAILED"
    DATABASE_TIMEOUT = "DATABASE_TIMEOUT"
    
    # Query
    QUERY_PARSING_FAILED = "QUERY_PARSING_FAILED"
    QUERY_AMBIGUOUS = "QUERY_AMBIGUOUS"
    QUERY_TIMEOUT = "QUERY_TIMEOUT"
    INVALID_QUERY = "INVALID_QUERY"
    
    # Schema
    COLUMN_NOT_FOUND = "COLUMN_NOT_FOUND"
    TABLE_NOT_FOUND = "TABLE_NOT_FOUND"
    SCHEMA_CHANGED = "SCHEMA_CHANGED"
    SCHEMA_REINDEX_IN_PROGRESS = "SCHEMA_REINDEX_IN_PROGRESS"
    
    # Limits
    RESULT_TOO_LARGE = "RESULT_TOO_LARGE"
    TOO_MANY_CONCURRENT_QUERIES = "TOO_MANY_CONCURRENT_QUERIES"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    
    # System
    NETWORK_ERROR = "NETWORK_ERROR"
    SERVER_ERROR = "SERVER_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"

class ErrorResponse(BaseModel):
    code: str
    message: str
    retryable: bool
    suggestion: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    timestamp: str

class CenecaAPIError(Exception):
    """Base exception for Ceneca API errors"""
    def __init__(
        self,
        code: ErrorCode,
        message: str,
        retryable: bool,
        suggestion: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.code = code
        self.message = message
        self.retryable = retryable
        self.suggestion = suggestion
        self.details = details or {}
        super().__init__(message)
    
    def to_response(self) -> ErrorResponse:
        from datetime import datetime
        return ErrorResponse(
            code=self.code.value,
            message=self.message,
            retryable=self.retryable,
            suggestion=self.suggestion,
            details=self.details,
            timestamp=datetime.utcnow().isoformat()
        )
```

```python
# In server/agent/endpoints.py

from fastapi import HTTPException
from fastapi.responses import JSONResponse
from .errors import CenecaAPIError, ErrorCode, ErrorResponse

@app.exception_handler(CenecaAPIError)
async def ceneca_error_handler(request, exc: CenecaAPIError):
    """Handle Ceneca-specific errors"""
    return JSONResponse(
        status_code=500 if exc.code == ErrorCode.SERVER_ERROR else 400,
        content=exc.to_response().dict()
    )

# Example usage in endpoints
@app.post("/api/query")
async def query_endpoint(request: QueryRequest):
    try:
        result = await execute_query(request.question)
        return result
    except DatabaseConnectionError as e:
        raise CenecaAPIError(
            code=ErrorCode.DATABASE_UNREACHABLE,
            message=f"Cannot connect to {e.database} database",
            retryable=True,
            suggestion="Check database connection and credentials",
            details={"database": e.database, "host": e.host}
        )
    except ColumnNotFoundError as e:
        # Find similar columns
        similar = find_similar_columns(e.column, e.table)
        raise CenecaAPIError(
            code=ErrorCode.COLUMN_NOT_FOUND,
            message=f'Column "{e.column}" not found in {e.table}',
            retryable=True,
            suggestion=f"Did you mean: {', '.join(similar)}?" if similar else "Schema may have changed",
            details={"column": e.column, "table": e.table, "similarColumns": similar}
        )
```

#### Step 4: SDK Error Handling (1 hour)

Parse and throw structured errors in SDK:

```typescript
// In SDK: src/client.ts

export class CenecaClient {
  private async makeRequest<T>(
    endpoint: string,
    options: RequestInit
  ): Promise<T> {
    try {
      const response = await fetch(`${this.config.host}${endpoint}`, options);
      
      // Success
      if (response.ok) {
        return await response.json();
      }
      
      // Parse error response
      const errorData = await response.json().catch(() => ({}));
      
      // Structured error from server
      if (errorData.code) {
        throw new CenecaError({
          code: errorData.code,
          message: errorData.message || 'An error occurred',
          retryable: errorData.retryable ?? false,
          suggestion: errorData.suggestion,
          details: errorData.details
        });
      }
      
      // Fallback for unstructured errors
      throw createError.serverError(response.status, { 
        statusText: response.statusText 
      });
      
    } catch (error) {
      // Network error
      if (error instanceof TypeError) {
        throw createError.networkError(error);
      }
      
      // Re-throw CenecaError
      if (error instanceof CenecaError) {
        throw error;
      }
      
      // Unknown error
      throw new CenecaError({
        code: ErrorCodes.UNKNOWN_ERROR,
        message: error.message || 'An unknown error occurred',
        retryable: false,
        details: { originalError: error }
      });
    }
  }
}
```

### Usage Examples

#### Basic Error Handling

```javascript
try {
  const result = await ceneca.query("Show sales data");
  console.log(result);
} catch (error) {
  if (error instanceof CenecaError) {
    console.error(`Error [${error.code}]: ${error.message}`);
    
    if (error.suggestion) {
      console.log(`Suggestion: ${error.suggestion}`);
    }
    
    if (error.retryable) {
      console.log('This error is retryable');
    }
  }
}
```

#### Handle Specific Error Codes

```javascript
import { CenecaClient, CenecaError, ErrorCodes } from '@ceneca/sdk';

try {
  const result = await ceneca.query("Show customer emails");
} catch (error) {
  if (!(error instanceof CenecaError)) throw error;
  
  switch (error.code) {
    case ErrorCodes.COLUMN_NOT_FOUND:
      // Schema changed - show user suggestions
      const similar = error.details.similarColumns;
      showError(`Column not found. Did you mean: ${similar.join(', ')}?`);
      break;
      
    case ErrorCodes.DATABASE_UNREACHABLE:
      // Database down - show maintenance message
      showMaintenanceMessage('Database temporarily unavailable');
      break;
      
    case ErrorCodes.INSUFFICIENT_PERMISSIONS:
      // Permission issue - redirect to access request
      redirectToAccessRequest(error.details.required);
      break;
      
    case ErrorCodes.QUERY_TIMEOUT:
      // Timeout - offer to retry with filters
      offerRetryWithFilters();
      break;
      
    default:
      // Generic error handler
      showError(error.message, error.suggestion);
  }
}
```

#### Automatic Retry Logic

```javascript
async function queryWithRetry(question: string, maxRetries = 3) {
  let lastError;
  
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      return await ceneca.query(question);
    } catch (error) {
      lastError = error;
      
      // Only retry if error is retryable
      if (error instanceof CenecaError && error.retryable) {
        console.log(`Attempt ${attempt} failed, retrying...`);
        
        // Exponential backoff
        await new Promise(resolve => 
          setTimeout(resolve, Math.pow(2, attempt) * 1000)
        );
        continue;
      }
      
      // Not retryable - throw immediately
      throw error;
    }
  }
  
  throw lastError;
}
```

#### React Error Boundary

```javascript
import { CenecaError, ErrorCodes } from '@ceneca/sdk';

function CenecaErrorDisplay({ error }: { error: CenecaError }) {
  return (
    <div className="error-card">
      <div className="error-header">
        <Icon name={error.retryable ? 'warning' : 'error'} />
        <h3>{error.message}</h3>
      </div>
      
      {error.suggestion && (
        <div className="error-suggestion">
          <strong>Suggestion:</strong> {error.suggestion}
        </div>
      )}
      
      {error.details && (
        <details className="error-details">
          <summary>Technical Details</summary>
          <pre>{JSON.stringify(error.details, null, 2)}</pre>
        </details>
      )}
      
      {error.retryable && (
        <button onClick={() => retry()}>
          Try Again
        </button>
      )}
      
      <div className="error-code">
        Error Code: {error.code}
      </div>
    </div>
  );
}
```

### Error Code Reference Table

| Code | Retryable | Common Cause | Suggestion |
|------|-----------|--------------|------------|
| `AUTH_NOT_CONFIGURED` | No | SDK initialized without auth | Add tokenProvider or apiKey |
| `TOKEN_EXPIRED` | Yes | Token lifetime exceeded | Automatic refresh, check tokenProvider |
| `INSUFFICIENT_PERMISSIONS` | No | User lacks data access | Contact administrator |
| `DATABASE_UNREACHABLE` | Yes | DB down or network issue | Check connection, may be temporary |
| `DATABASE_AUTH_FAILED` | No | Wrong DB credentials | Verify credentials in config |
| `QUERY_PARSING_FAILED` | No | Ambiguous question | Rephrase more specifically |
| `QUERY_AMBIGUOUS` | No | Multiple interpretations | Use suggested clarifications |
| `QUERY_TIMEOUT` | Yes | Query too slow | Add filters or increase timeout |
| `COLUMN_NOT_FOUND` | Yes | Schema changed | Check similar columns or reindex |
| `TABLE_NOT_FOUND` | Yes | Schema changed | Verify table name |
| `SCHEMA_CHANGED` | Yes | DB schema updated | Wait for reindex to complete |
| `RESULT_TOO_LARGE` | No | Too many rows | Add date filters or pagination |
| `TOO_MANY_CONCURRENT_QUERIES` | Yes | Rate limit hit | Wait or increase limit |
| `NETWORK_ERROR` | Yes | Connection failed | Check internet connection |
| `SERVER_ERROR` | Yes | Backend issue | Retry or contact support |

### Documentation Template

```markdown
## Error Handling

Ceneca SDK provides structured error handling with specific error codes and actionable suggestions.

### Basic Usage

```javascript
try {
  const result = await ceneca.query("Your question");
} catch (error) {
  if (error instanceof CenecaError) {
    console.error(`[${error.code}] ${error.message}`);
    
    // Show suggestion to user
    if (error.suggestion) {
      alert(error.suggestion);
    }
    
    // Retry if appropriate
    if (error.retryable) {
      // Implement retry logic
    }
  }
}
```

### Error Properties

Every `CenecaError` includes:

- **`code`**: Machine-readable error code (e.g., `'COLUMN_NOT_FOUND'`)
- **`message`**: Human-readable error message
- **`retryable`**: Whether retrying might succeed
- **`suggestion`**: Actionable guidance (optional)
- **`details`**: Additional context for debugging (optional)
- **`timestamp`**: When the error occurred

### Common Patterns

**Handle specific errors:**
```javascript
if (error.code === ErrorCodes.COLUMN_NOT_FOUND) {
  const similar = error.details.similarColumns;
  // Show alternatives to user
}
```

**Automatic retry:**
```javascript
if (error.retryable) {
  await new Promise(r => setTimeout(r, 2000));
  return await ceneca.query(question); // Retry
}
```

**Log for debugging:**
```javascript
console.log(JSON.stringify(error.toJSON(), null, 2));
```

### Error Codes

See [Error Code Reference](#error-code-reference-table) for complete list.
```

### Implementation Effort

| Task | Time | Difficulty |
|------|------|-----------|
| Create error class & constants | 1 hour | Easy |
| Implement error factory functions | 1 hour | Easy |
| Add server-side error responses | 2 hours | Medium |
| Update SDK to parse/throw errors | 1 hour | Easy |
| Update all endpoints to use errors | 3 hours | Medium |
| Write documentation & examples | 2 hours | Easy |
| **Total** | **10 hours** | **Medium** |

### Why This Works

1. **Clear communication**: Companies know exactly what went wrong
2. **Actionable**: Every error includes guidance on next steps
3. **Programmatic handling**: Error codes enable smart retry logic
4. **Debuggable**: Details provide context for troubleshooting
5. **Consistent**: All errors follow same structure
6. **Retryable flag**: SDK can automatically retry appropriate errors
7. **Future-proof**: New error codes can be added without breaking changes

---

## Challenge #5: Versioning Nightmares

### The Problem

**SDK version vs. company's self-hosted Ceneca server version incompatibility:**

**What will happen:**
```
Company installs: @ceneca/sdk@2.5.0
Company deploys: Ceneca Server v2.3.0 (self-hosted in their infrastructure)

SDK tries to use new feature:
ceneca.query("...", { streaming_mode: 'adaptive' }) // Added in v2.5.0

Server v2.3.0:
❌ Doesn't recognize 'streaming_mode' → silent failure or crash
```

**Why this is tricky:**
1. Companies self-host Ceneca, so they control upgrade timing
2. Developers might `npm update` SDK without upgrading server
3. Server upgrades require infrastructure changes (Docker, K8s)
4. No enforcement mechanism for version alignment

### Minimal Solution: Semantic Version Ranges with Warnings

**Decision:** Use version range checking with warning behavior. SDK supports 2-3 minor versions back (6-9 months for quarterly stable releases).

### Backward Compatibility Policy

**SDK supports 2-3 minor versions back:**
- Companies have 6-9 months to upgrade self-hosted servers
- Provides flexibility without breaking integrations
- Aligns with quarterly stable release cadence

**Example:**
```
SDK v2.8.0 (Q4 2025) supports:
  ✅ Server v2.5.0 (Q1 2025)
  ✅ Server v2.6.0 (Q2 2025)
  ✅ Server v2.7.0 (Q3 2025)
  ✅ Server v2.8.0 (Q4 2025)
  
  ⚠️  Server v2.4.0 (Q4 2024) - Warn but try to work
  ❌ Server v2.3.0 or older - Refuse to connect
```

### Semantic Versioning Rules

**Minor versions (2.5 → 2.6):** No breaking changes
- New features only
- SDK v2.6 works with server v2.5
- Server v2.6 works with SDK v2.5

**Major versions (2.x → 3.0):** Breaking changes allowed
- Can change auth system, API structure, etc.
- Requires coordinated upgrade
- SDK v3.0 might NOT work with server v2.x

**Patch versions (2.5.0 → 2.5.1):** Bug fixes only
- Always compatible
- No new features

### Implementation

#### Step 1: Server Health Endpoint with Version Info (1 hour)

Add version information to health endpoint:

```python
# In server/agent/endpoints.py

# Read version from package.json or version file
def get_server_version():
    """Read current server version"""
    try:
        with open('version.txt', 'r') as f:
            return f.read().strip()
    except:
        return "2.0.0"  # Fallback

@app.get("/api/health")
async def health_check():
    """Health check with version information"""
    server_version = get_server_version()
    major, minor, patch = server_version.split('.')
    
    return {
        "status": "healthy",
        "version": server_version,
        "api_version": "v2",
        "supported_features": [
            "basic_query",
            "streaming",
            "multi_database",
            "schema_introspection",
            "reasoning_chain",
            "chart_generation",
            # Add new features as they're released
            # "adaptive_streaming",  # Example: added in v2.9.0
        ],
        "compatibility": {
            "min_sdk_version": f"{major}.{max(0, int(minor) - 3)}.0",  # 3 versions back
            "max_sdk_version": f"{major}.{int(minor) + 2}.99"  # 2 versions forward
        },
        "schema_monitoring": {
            "enabled": True,
            "supported_databases": ["postgres", "mongodb", "mysql", "qdrant"]
        },
        "timestamp": datetime.utcnow().isoformat()
    }
```

Example response:
```json
{
  "status": "healthy",
  "version": "2.7.0",
  "api_version": "v2",
  "supported_features": [
    "basic_query",
    "streaming",
    "multi_database",
    "schema_introspection"
  ],
  "compatibility": {
    "min_sdk_version": "2.4.0",
    "max_sdk_version": "2.9.99"
  },
  "timestamp": "2025-10-06T15:30:00Z"
}
```

#### Step 2: SDK Version Checking (2 hours)

```typescript
// In SDK: src/version.ts

import packageJson from '../package.json';

export const SDK_VERSION = packageJson.version;

export interface VersionInfo {
  version: string;
  apiVersion: string;
  supportedFeatures: string[];
  compatibility: {
    minSdkVersion: string;
    maxSdkVersion: string;
  };
}

export function parseVersion(version: string): [number, number, number] {
  const parts = version.split('.').map(Number);
  return [parts[0], parts[1], parts[2]];
}

export function compareVersions(v1: string, v2: string): number {
  const [major1, minor1, patch1] = parseVersion(v1);
  const [major2, minor2, patch2] = parseVersion(v2);
  
  if (major1 !== major2) return major1 - major2;
  if (minor1 !== minor2) return minor1 - minor2;
  return patch1 - patch2;
}

export function isVersionInRange(
  version: string,
  minVersion: string,
  maxVersion: string
): boolean {
  return (
    compareVersions(version, minVersion) >= 0 &&
    compareVersions(version, maxVersion) <= 0
  );
}

export enum CompatibilityStatus {
  COMPATIBLE = 'compatible',
  WARNING = 'warning',
  INCOMPATIBLE = 'incompatible'
}

export interface CompatibilityCheck {
  status: CompatibilityStatus;
  message: string;
  serverVersion: string;
  sdkVersion: string;
  suggestion?: string;
}

export function checkCompatibility(
  serverInfo: VersionInfo
): CompatibilityCheck {
  const sdkVersion = SDK_VERSION;
  const { version: serverVersion, compatibility } = serverInfo;
  
  // Check if SDK is in supported range
  if (isVersionInRange(sdkVersion, compatibility.minSdkVersion, compatibility.maxSdkVersion)) {
    return {
      status: CompatibilityStatus.COMPATIBLE,
      message: `SDK v${sdkVersion} is compatible with server v${serverVersion}`,
      serverVersion,
      sdkVersion
    };
  }
  
  // SDK too old
  if (compareVersions(sdkVersion, compatibility.minSdkVersion) < 0) {
    return {
      status: CompatibilityStatus.INCOMPATIBLE,
      message: `SDK v${sdkVersion} is too old for server v${serverVersion}`,
      serverVersion,
      sdkVersion,
      suggestion: `Please upgrade SDK to v${compatibility.minSdkVersion} or newer: npm install @ceneca/sdk@^${compatibility.minSdkVersion}`
    };
  }
  
  // SDK too new - warn but allow
  if (compareVersions(sdkVersion, compatibility.maxSdkVersion) > 0) {
    return {
      status: CompatibilityStatus.WARNING,
      message: `SDK v${sdkVersion} is newer than server v${serverVersion} expects`,
      serverVersion,
      sdkVersion,
      suggestion: `Some features may not work. Consider upgrading server to v${sdkVersion} or downgrade SDK: npm install @ceneca/sdk@${serverVersion}`
    };
  }
  
  // Should never reach here
  return {
    status: CompatibilityStatus.INCOMPATIBLE,
    message: `Version compatibility check failed`,
    serverVersion,
    sdkVersion
  };
}
```

#### Step 3: SDK Client with Version Validation (2 hours)

```typescript
// In SDK: src/client.ts

import { checkCompatibility, CompatibilityStatus, SDK_VERSION } from './version';
import { createError, ErrorCodes } from './errors';

export class CenecaClient {
  private serverInfo: VersionInfo | null = null;
  private supportedFeatures: Set<string> = new Set();
  private connected: boolean = false;
  
  constructor(private config: {
    host: string;
    auth: AuthConfig;
    limits?: LimitConfig;
    strictVersionCheck?: boolean;  // Default: false (warn mode)
  }) {}
  
  async connect(): Promise<void> {
    // Fetch server health/version info
    const response = await fetch(`${this.config.host}/api/health`);
    
    if (!response.ok) {
      throw createError.serverError(response.status, {
        message: 'Could not fetch server version information'
      });
    }
    
    this.serverInfo = await response.json();
    this.supportedFeatures = new Set(this.serverInfo.supportedFeatures);
    
    // Check version compatibility
    const compatibility = checkCompatibility(this.serverInfo);
    
    // Handle incompatibility
    if (compatibility.status === CompatibilityStatus.INCOMPATIBLE) {
      throw new CenecaError({
        code: ErrorCodes.VERSION_INCOMPATIBLE,
        message: compatibility.message,
        retryable: false,
        suggestion: compatibility.suggestion,
        details: {
          sdkVersion: compatibility.sdkVersion,
          serverVersion: compatibility.serverVersion,
          minRequired: this.serverInfo.compatibility.minSdkVersion,
          maxSupported: this.serverInfo.compatibility.maxSdkVersion
        }
      });
    }
    
    // Handle warning
    if (compatibility.status === CompatibilityStatus.WARNING) {
      if (this.config.strictVersionCheck) {
        // Strict mode: treat warnings as errors
        throw new CenecaError({
          code: ErrorCodes.VERSION_MISMATCH,
          message: compatibility.message,
          retryable: false,
          suggestion: compatibility.suggestion,
          details: {
            sdkVersion: compatibility.sdkVersion,
            serverVersion: compatibility.serverVersion
          }
        });
      } else {
        // Warn mode: log warning and continue
        console.warn(
          `⚠️  Ceneca Version Warning: ${compatibility.message}\n` +
          `   ${compatibility.suggestion || ''}`
        );
      }
    }
    
    // Success
    console.log(
      `✅ Connected to Ceneca v${this.serverInfo.version} (SDK v${SDK_VERSION})`
    );
    
    this.connected = true;
  }
  
  supports(feature: string): boolean {
    if (!this.connected) {
      throw new Error('Client not connected. Call connect() first.');
    }
    return this.supportedFeatures.has(feature);
  }
  
  getServerVersion(): string {
    if (!this.connected || !this.serverInfo) {
      throw new Error('Client not connected. Call connect() first.');
    }
    return this.serverInfo.version;
  }
  
  async query(question: string, options?: QueryOptions): Promise<Result> {
    if (!this.connected) {
      throw new Error('Client not connected. Call connect() first.');
    }
    
    // Feature-specific handling
    if (options?.streamingMode === 'adaptive') {
      if (!this.supports('adaptive_streaming')) {
        console.warn(
          '⚠️  Adaptive streaming not supported by server. ' +
          'Falling back to standard streaming.'
        );
        options.streamingMode = 'standard';
      }
    }
    
    // Continue with query...
    return this.executeQuery(question, options);
  }
}
```

#### Step 4: Add Error Codes for Versioning (30 minutes)

```typescript
// Add to SDK: src/errors.ts

export const ErrorCodes = {
  // ... existing codes ...
  
  // Version errors
  VERSION_INCOMPATIBLE: 'VERSION_INCOMPATIBLE',
  VERSION_MISMATCH: 'VERSION_MISMATCH'
} as const;

export const createError = {
  // ... existing error creators ...
  
  versionIncompatible: (details: {
    sdkVersion: string;
    serverVersion: string;
    minRequired: string;
    maxSupported: string;
  }) => new CenecaError({
    code: ErrorCodes.VERSION_INCOMPATIBLE,
    message: `SDK v${details.sdkVersion} is incompatible with server v${details.serverVersion}`,
    retryable: false,
    suggestion: details.sdkVersion < details.minRequired
      ? `Upgrade SDK: npm install @ceneca/sdk@^${details.minRequired}`
      : `Upgrade server to v${details.minRequired} or newer`,
    details
  })
};
```

### Usage Examples

#### Basic Connection with Version Check

```javascript
import { CenecaClient } from '@ceneca/sdk';

const ceneca = new CenecaClient({
  host: 'ceneca.company.com',
  auth: { tokenProvider: getToken }
});

try {
  await ceneca.connect();
  // ✅ Connected to Ceneca v2.7.0 (SDK v2.8.0)
  
  const result = await ceneca.query("Show sales");
} catch (error) {
  if (error.code === 'VERSION_INCOMPATIBLE') {
    console.error(error.message);
    console.log(error.suggestion);
    // SDK v2.8.0 is incompatible with server v2.3.0
    // Upgrade server to v2.5.0 or newer
  }
}
```

#### Feature Detection

```javascript
await ceneca.connect();

// Check if server supports specific feature
if (ceneca.supports('adaptive_streaming')) {
  console.log('Using adaptive streaming');
  await ceneca.query("...", { streamingMode: 'adaptive' });
} else {
  console.log('Using standard streaming');
  await ceneca.query("...");
}

// Get server version
console.log(`Server version: ${ceneca.getServerVersion()}`);
```

#### Strict Version Checking

```javascript
// Enable strict mode - warnings become errors
const ceneca = new CenecaClient({
  host: 'ceneca.company.com',
  auth: { tokenProvider: getToken },
  strictVersionCheck: true  // Fail on any version mismatch
});

try {
  await ceneca.connect();
} catch (error) {
  if (error.code === 'VERSION_MISMATCH') {
    // Even warnings will throw in strict mode
    handleVersionMismatch(error);
  }
}
```

#### Auto-Reconnect on Server Upgrade

```javascript
const ceneca = new CenecaClient({ ... });

// Initial connection
await ceneca.connect();

// Periodically check if server was upgraded
setInterval(async () => {
  try {
    const response = await fetch(`${host}/api/health`);
    const info = await response.json();
    
    const currentVersion = ceneca.getServerVersion();
    if (info.version !== currentVersion) {
      console.log(`Server upgraded: ${currentVersion} → ${info.version}`);
      
      // Reconnect to refresh compatibility
      await ceneca.connect();
    }
  } catch (error) {
    console.error('Failed to check server version:', error);
  }
}, 60000); // Check every minute
```

### Version Compatibility Matrix

| SDK Version | Compatible Server Versions | Status |
|-------------|---------------------------|---------|
| 2.8.0 | 2.5.0 - 2.10.x | ✅ Supported |
| 2.8.0 | 2.4.0 | ⚠️ Warning (works but outdated) |
| 2.8.0 | 2.3.0 or older | ❌ Incompatible |
| 2.5.0 | 2.5.0 - 2.7.x | ✅ Supported |
| 2.5.0 | 2.8.0 | ⚠️ Warning (newer features unavailable) |
| 3.0.0 | 2.x.x | ❌ Major version incompatible |

### Release Process

#### For SDK Releases:

1. Update `package.json` version
2. Document breaking changes in CHANGELOG.md
3. Update minimum server version if needed
4. Tag release: `git tag v2.8.0`
5. Publish: `npm publish`

#### For Server Releases:

1. Update `version.txt` or equivalent
2. Update `supported_features` list in health endpoint
3. Update `min_sdk_version` and `max_sdk_version`
4. Tag release: `git tag server-v2.8.0`
5. Build and publish Docker image

### Documentation Template

```markdown
## Version Compatibility

Ceneca SDK and Server follow semantic versioning. SDK versions are compatible with server versions within a defined range.

### Current Compatibility

SDK v2.8.0 supports servers v2.5.0 - v2.10.x

### Checking Compatibility

The SDK automatically checks version compatibility on connection:

```javascript
const ceneca = new CenecaClient({ host: '...' });
await ceneca.connect();
// ✅ Connected to Ceneca v2.7.0 (SDK v2.8.0)
```

### Version Errors

**`VERSION_INCOMPATIBLE`**: SDK and server versions are too far apart
- Upgrade SDK or server as suggested

**`VERSION_MISMATCH`**: Versions work but are outside optimal range
- Only in strict mode
- Consider upgrading for best experience

### Feature Detection

Check if server supports specific features:

```javascript
if (ceneca.supports('adaptive_streaming')) {
  // Use new feature
}
```

### Upgrade Guidelines

**Minor version updates** (2.7 → 2.8): Safe to upgrade, backward compatible

**Major version updates** (2.x → 3.0): Review breaking changes, coordinate upgrades

**Recommended**: Keep SDK and server within 2-3 minor versions of each other.
```

### Implementation Effort

| Task | Time | Difficulty |
|------|------|-----------|
| Add version info to health endpoint | 1 hour | Easy |
| Implement version parsing/comparison | 1 hour | Easy |
| Add compatibility checking logic | 2 hours | Medium |
| Update SDK client with validation | 2 hours | Medium |
| Add version error codes | 30 min | Easy |
| Write tests for version logic | 2 hours | Medium |
| Write documentation | 1.5 hours | Easy |
| **Total** | **10 hours** | **Medium** |

### Why This Works

1. **Fails fast**: Companies know immediately if versions are incompatible
2. **Clear guidance**: Error messages explain exactly what to upgrade
3. **Flexible**: Warn mode allows working with slight mismatches
4. **Feature detection**: Graceful degradation for new SDK with old server
5. **Self-documenting**: Health endpoint shows compatibility range
6. **Long support window**: 6-9 months gives companies time to upgrade
7. **Future-proof**: Can add features without breaking old clients

---

## Challenge #6: No UI = No Context

### The Problem

Ceneca's web UI provides valuable context that companies lose with headless API:

**What Ceneca's UI shows:**
- Reasoning chain display (`ReasoningChain.tsx`, `StreamingStatusBlock.tsx`)
- Database schema exploration
- Result previews with automatic charts
- SQL queries that were executed
- Execution timing and performance metrics

**What companies build with headless API:**
```javascript
// Their simple implementation
<input placeholder="Ask a question" onChange={handleQuery} />
<button onClick={submit}>Search</button>
{loading && <Spinner />}
{data && <Table data={data} />}
```

**Problems this creates:**

1. **User doesn't know what's happening**
   - Shows loading spinner for 30 seconds
   - No indication if querying postgres vs mongodb
   - No idea how many steps remain

2. **Ambiguous queries fail silently**
   - User types: "Show me the data"
   - Ceneca: "Which data? From which database?"
   - Their UI: Just shows error, no guidance

3. **Users can't discover what was queried**
   - Don't know which databases were used
   - Don't know which tables/columns were accessed
   - Missing context about data source

4. **Results lack context**
   - Just raw data in table
   - No indication which databases were queried
   - Missing performance metrics

### Minimal Solution: Context in API Response + Real-Time Streaming

**Decisions:**
1. **Minimal context by default** - Include only essential context, keep payloads small
2. **No UI components** - Companies build their own UI, we provide the data
3. **Stream reasoning chain in real-time** - Via existing streaming infrastructure
4. **Schema info in query response** - Include schema for tables actually queried
5. **No autocomplete/suggestions** - Not worth complexity for MVP

### Implementation

#### Step 1: Enhanced Query Response Structure (1 hour)

Update query response to include context:

```typescript
// In SDK: src/types.ts

export interface QueryResult {
  // Core data
  queryId: string;
  rows: Array<Record<string, any>>;
  columns: Column[];
  totalRows: number;
  
  // Execution context (minimal by default)
  context: {
    databases_queried: string[];
    execution_time_ms: number;
    timestamp: string;
  };
  
  // Schema info for queried tables
  schema_used?: {
    [database: string]: {
      [table: string]: {
        columns: Array<{
          name: string;
          type: string;
          nullable: boolean;
        }>;
      };
    };
  };
  
  // Optional detailed context (opt-in)
  details?: {
    sql_queries?: Array<{
      database: string;
      query: string;
      execution_time_ms: number;
      rows_returned: number;
    }>;
    performance?: {
      rows_scanned: number;
      databases_accessed: number;
      cache_hit: boolean;
    };
  };
}
```

#### Step 2: Server-Side Response Enhancement (2 hours)

Update query endpoint to include context:

```python
# In server/agent/endpoints.py

@app.post("/api/query")
async def query_endpoint(request: QueryRequest):
    start_time = time.time()
    
    # Execute query (existing logic)
    result = await execute_query(request.question)
    
    # Collect context
    execution_time = (time.time() - start_time) * 1000
    
    # Get schema for tables that were used
    schema_used = {}
    for db in result.databases_queried:
        schema_used[db] = {}
        for table in result.tables_accessed.get(db, []):
            table_schema = await get_table_schema(db, table)
            schema_used[db][table] = {
                "columns": [
                    {
                        "name": col.name,
                        "type": col.type,
                        "nullable": col.nullable
                    }
                    for col in table_schema.columns
                ]
            }
    
    # Build response with context
    response = {
        "queryId": result.query_id,
        "rows": result.rows,
        "columns": result.columns,
        "totalRows": len(result.rows),
        "context": {
            "databases_queried": result.databases_queried,
            "execution_time_ms": round(execution_time, 2),
            "timestamp": datetime.utcnow().isoformat()
        },
        "schema_used": schema_used
    }
    
    # Include detailed context if requested
    if request.include_details:
        response["details"] = {
            "sql_queries": [
                {
                    "database": q.database,
                    "query": q.query,
                    "execution_time_ms": q.execution_time_ms,
                    "rows_returned": q.rows_returned
                }
                for q in result.sql_queries
            ],
            "performance": {
                "rows_scanned": result.rows_scanned,
                "databases_accessed": len(result.databases_queried),
                "cache_hit": result.cache_hit
            }
        }
    
    return response
```

#### Step 3: Real-Time Reasoning Chain Streaming (Already Exists!)

Leverage existing streaming infrastructure from Challenge #1:

```typescript
// In SDK: Already implemented via onStream callback

await ceneca.query("Show sales data", {
  onStream: (event) => {
    // Reasoning chain events already stream
    if (event.type === 'reasoning') {
      updateReasoningUI(event.data.step, event.data.details);
    }
    
    // SQL query events
    if (event.type === 'sql_query') {
      showSQLQuery(event.data.query, event.data.source);
    }
    
    // Status events
    if (event.type === 'status') {
      updateProgress(event.data.message, event.data.progress);
    }
  }
});
```

**No additional work needed** - reasoning chain already streams via existing infrastructure!

#### Step 4: SDK Helper for Optional Details (30 minutes)

```typescript
// In SDK: src/client.ts

export interface QueryOptions {
  onStream?: (event: StreamEvent) => void;
  timeout?: number;
  databases?: string[];
  
  // NEW: Include detailed context
  includeDetails?: boolean;  // Default: false (minimal)
}

export class CenecaClient {
  async query(question: string, options?: QueryOptions): Promise<QueryResult> {
    const response = await this.makeRequest('/api/query', {
      method: 'POST',
      body: JSON.stringify({
        question,
        include_details: options?.includeDetails || false
      })
    });
    
    return response as QueryResult;
  }
}
```

### Usage Examples

#### Minimal Context (Default)

```javascript
const result = await ceneca.query("Show customer orders");

console.log(result);
// {
//   queryId: "q_abc123",
//   rows: [...],
//   columns: [...],
//   totalRows: 1234,
//   context: {
//     databases_queried: ['postgres', 'mongodb'],
//     execution_time_ms: 2340,
//     timestamp: '2025-10-06T15:30:00Z'
//   },
//   schema_used: {
//     postgres: {
//       customers: {
//         columns: [
//           { name: 'id', type: 'integer', nullable: false },
//           { name: 'email', type: 'varchar', nullable: false }
//         ]
//       },
//       orders: {
//         columns: [
//           { name: 'id', type: 'integer', nullable: false },
//           { name: 'customer_id', type: 'integer', nullable: false },
//           { name: 'total', type: 'decimal', nullable: false }
//         ]
//       }
//     }
//   }
// }
```

#### Display Context in UI

```javascript
const result = await ceneca.query("Show sales by region");

// Show which databases were used
const dbBadges = result.context.databases_queried.map(db => 
  `<span class="badge">${db}</span>`
);

// Show execution time
const timing = `Executed in ${result.context.execution_time_ms}ms`;

// Show schema info (for debugging or "data source" display)
const tables = Object.entries(result.schema_used).flatMap(([db, tables]) =>
  Object.keys(tables).map(table => `${db}.${table}`)
);
console.log(`Data from: ${tables.join(', ')}`);
// "Data from: postgres.sales, postgres.regions"
```

#### With Detailed Context (Opt-In)

```javascript
const result = await ceneca.query("Show sales", {
  includeDetails: true  // Get SQL queries and performance metrics
});

// Display SQL queries that were executed
result.details.sql_queries.forEach(q => {
  console.log(`[${q.database}] ${q.query}`);
  console.log(`  → ${q.rows_returned} rows in ${q.execution_time_ms}ms`);
});

// Show performance metrics
console.log(`Scanned ${result.details.performance.rows_scanned} rows`);
console.log(`Queried ${result.details.performance.databases_accessed} databases`);
```

#### Real-Time Reasoning Chain

```javascript
// Show reasoning steps as they happen
const reasoningSteps = [];

const result = await ceneca.query("Show top customers", {
  onStream: (event) => {
    if (event.type === 'reasoning') {
      reasoningSteps.push(event.data.step);
      updateReasoningUI(reasoningSteps);
      // UI shows:
      // ✓ Analyzing query...
      // ✓ Identifying databases...
      // ⏳ Executing SQL query on postgres...
    }
    
    if (event.type === 'sql_query') {
      showSQLInUI(event.data.query, event.data.source);
      // UI shows expandable SQL queries as they execute
    }
    
    if (event.type === 'status') {
      updateProgressBar(event.data.progress);
      // UI shows: "Step 3 of 5: Aggregating results..."
    }
  }
});
```

#### Build "Data Source" Display

```javascript
function DataSourceInfo({ result }) {
  return (
    <div className="data-source-info">
      <h4>Data Source</h4>
      
      {/* Show which databases */}
      <div className="databases">
        {result.context.databases_queried.map(db => (
          <span key={db} className="badge">{db}</span>
        ))}
      </div>
      
      {/* Show tables and columns */}
      <details>
        <summary>Tables Used</summary>
        {Object.entries(result.schema_used).map(([db, tables]) => (
          <div key={db}>
            <strong>{db}</strong>
            <ul>
              {Object.entries(tables).map(([table, schema]) => (
                <li key={table}>
                  {table} ({schema.columns.length} columns)
                  <ul>
                    {schema.columns.map(col => (
                      <li key={col.name}>
                        {col.name}: {col.type}
                      </li>
                    ))}
                  </ul>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </details>
      
      {/* Show performance */}
      <div className="performance">
        <small>Executed in {result.context.execution_time_ms}ms</small>
      </div>
    </div>
  );
}
```

### Example: Complete Query UI with Context

```javascript
import { CenecaClient } from '@ceneca/sdk';

function QueryInterface() {
  const [query, setQuery] = useState('');
  const [result, setResult] = useState(null);
  const [reasoning, setReasoning] = useState([]);
  const [sqlQueries, setSqlQueries] = useState([]);
  const [progress, setProgress] = useState(0);
  const [isLoading, setIsLoading] = useState(false);

  const handleQuery = async () => {
    setIsLoading(true);
    setReasoning([]);
    setSqlQueries([]);
    
    try {
      const result = await ceneca.query(query, {
        includeDetails: true,  // Get SQL queries
        onStream: (event) => {
          // Real-time updates
          if (event.type === 'reasoning') {
            setReasoning(prev => [...prev, event.data.step]);
          }
          if (event.type === 'sql_query') {
            setSqlQueries(prev => [...prev, event.data]);
          }
          if (event.type === 'status') {
            setProgress(event.data.progress || 0);
          }
        }
      });
      
      setResult(result);
    } catch (error) {
      console.error(error);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div>
      <input 
        value={query} 
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Ask a question..."
      />
      <button onClick={handleQuery}>Query</button>
      
      {isLoading && (
        <div className="loading">
          <ProgressBar value={progress} />
          
          {/* Show reasoning steps */}
          <div className="reasoning">
            {reasoning.map((step, i) => (
              <div key={i}>✓ {step}</div>
            ))}
          </div>
          
          {/* Show SQL queries as they execute */}
          {sqlQueries.map((q, i) => (
            <details key={i}>
              <summary>[{q.source}] Query {i + 1}</summary>
              <pre>{q.query}</pre>
            </details>
          ))}
        </div>
      )}
      
      {result && (
        <div>
          {/* Data source info */}
          <div className="metadata">
            <span>Queried: {result.context.databases_queried.join(', ')}</span>
            <span>Time: {result.context.execution_time_ms}ms</span>
            <span>Rows: {result.totalRows}</span>
          </div>
          
          {/* Tables used */}
          <details>
            <summary>Schema Info</summary>
            {Object.entries(result.schema_used).map(([db, tables]) => (
              <div key={db}>
                <strong>{db}</strong>
                <ul>
                  {Object.keys(tables).map(table => (
                    <li key={table}>{table}</li>
                  ))}
                </ul>
              </div>
            ))}
          </details>
          
          {/* Results table */}
          <table>
            <thead>
              <tr>
                {result.columns.map(col => (
                  <th key={col}>{col}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {result.rows.map((row, i) => (
                <tr key={i}>
                  {result.columns.map(col => (
                    <td key={col}>{row[col]}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
```

### Documentation Template

```markdown
## Query Context

Ceneca query responses include context about data sources and execution.

### Default Context

Every query includes:

```javascript
{
  rows: [...],
  context: {
    databases_queried: ['postgres'],
    execution_time_ms: 234,
    timestamp: '2025-10-06T15:30:00Z'
  },
  schema_used: {
    postgres: {
      customers: {
        columns: [
          { name: 'id', type: 'integer', nullable: false },
          { name: 'email', type: 'varchar', nullable: false }
        ]
      }
    }
  }
}
```

### Detailed Context (Opt-In)

For debugging or advanced UIs, request detailed context:

```javascript
const result = await ceneca.query("...", {
  includeDetails: true
});

// Includes SQL queries and performance metrics
result.details.sql_queries.forEach(q => {
  console.log(`[${q.database}] ${q.query}`);
});
```

### Real-Time Reasoning

Stream reasoning steps as they happen:

```javascript
await ceneca.query("...", {
  onStream: (event) => {
    if (event.type === 'reasoning') {
      console.log(event.data.step);
      // "Analyzing query..."
      // "Querying postgres..."
      // "Aggregating results..."
    }
  }
});
```

### Use Cases

**Show data source:**
```javascript
const sources = result.context.databases_queried.join(', ');
console.log(`Data from: ${sources}`);
```

**Display execution time:**
```javascript
console.log(`Query took ${result.context.execution_time_ms}ms`);
```

**Show which tables were accessed:**
```javascript
const tables = Object.entries(result.schema_used)
  .flatMap(([db, tables]) => 
    Object.keys(tables).map(t => `${db}.${t}`)
  );
console.log(`Tables: ${tables.join(', ')}`);
```
```

### Implementation Effort

| Task | Time | Difficulty |
|------|------|-----------|
| Update response type definitions | 30 min | Easy |
| Add schema collection to query flow | 1 hour | Easy |
| Update server response structure | 2 hours | Medium |
| Add `includeDetails` option to SDK | 30 min | Easy |
| Write documentation & examples | 2 hours | Easy |
| **Total** | **6 hours** | **Easy** |

### Why This Works

1. **Minimal by default**: Small payloads, fast responses
2. **Progressive enhancement**: Companies can show as much context as they want
3. **Leverages existing streaming**: Reasoning chain already streams (Challenge #1)
4. **Schema discovery built-in**: No separate API calls needed
5. **Context-aware**: Only includes schema for tables actually used
6. **Flexible**: Companies build UI that fits their design
7. **Debuggable**: Detailed mode helps troubleshoot issues

---

## Challenge #7: Schema Changes Break Everything

### The Problem

Database schema changes break queries that worked yesterday:
- DBA renames column: `email_address` → `contact_email`
- Query fails: `Column 'email_address' not found`

### Solution: Already Solved! ✅

This challenge is **already addressed** by Ceneca's existing infrastructure:

**Schema monitoring system** (`server/agent/performance/schema_monitor.py`):
- Automatically detects schema changes via hash comparison
- Triggers reindexing when changes detected
- Runs continuously in background

**Schema watcher** (`server/agent/performance/schema_watcher.py`):
- Background daemon monitoring all databases
- No manual intervention required
- Companies' queries keep working after automatic reindex

**Schema registry** (`server/agent/db/registry/`):
- Tracks schema state for all database instances
- Multi-instance support for dev/staging/prod
- Provides schema status via API

### What Headless API Needs

The existing infrastructure already works. Just expose it via API:

**From Challenge #6**: Schema info already included in query responses
**From Challenge #4**: `SCHEMA_CHANGED` error code already defined
**From headless-api-integration.md**: API endpoints already designed:
- `GET /api/schema/status` - Get schema status
- `POST /api/schema/reindex` - Force reindex
- `WS /api/schema/events` - Schema change notifications

### Implementation Status

**Already implemented:**
- ✅ Schema change detection
- ✅ Automatic reindexing
- ✅ Multi-database support
- ✅ Background monitoring

**Needs for headless API (covered in other challenges):**
- ✅ Schema status endpoint (Challenge #6)
- ✅ Error handling for schema issues (Challenge #4)
- ✅ Include schema in responses (Challenge #6)

**Total additional work needed:** ~0 hours (already solved by existing infrastructure)

---

## Challenge #8: Result Size Unpredictability

### The Problem

Companies don't know if a query returns 10 rows or 10 million until it runs.

**What will happen:**

```javascript
// Query that looks innocent
const result = await ceneca.query("Show all customer orders");

// Returns: 2.4 million rows, 2GB JSON payload
// Browser: 💥 Out of memory crash
```

**Scenarios:**

1. **Mobile app crashes** - Tries to load 500MB result
2. **Endless scrolling** - User gets 100,000 rows, no way to find specific data
3. **Wasted bandwidth** - Queries 1M rows, only looks at first 50
4. **Dev vs Production mismatch** - 100 rows in dev, 10M in production

### Minimal Solution: Transparent Pagination with Estimation

**Decisions:**
1. **Transparent pagination** - SDK handles it automatically
2. **Medium page size** - Default 10,000 rows (covers most use cases)
3. **Auto-paginate in background** - Seamless experience
4. **Use estimation** - Warn before executing large queries (from Challenge #3)

### Implementation

#### Step 1: Paginated Response Type (30 minutes)

```typescript
// In SDK: src/types.ts

export interface PaginatedResult {
  queryId: string;
  rows: Array<Record<string, any>>;
  columns: Column[];
  
  // Pagination info
  page: number;           // Current page (1-indexed)
  pageSize: number;       // Rows per page
  totalRows: number;      // Total rows available
  totalPages: number;     // Total pages available
  hasMore: boolean;       // More pages available
  
  // Context (from Challenge #6)
  context: {
    databases_queried: string[];
    execution_time_ms: number;
    timestamp: string;
  };
  
  schema_used?: { ... };
  details?: { ... };
}
```

#### Step 2: SDK with Transparent Pagination (2 hours)

```typescript
// In SDK: src/client.ts

export interface QueryOptions {
  onStream?: (event: StreamEvent) => void;
  timeout?: number;
  databases?: string[];
  includeDetails?: boolean;
  
  // NEW: Pagination options
  pageSize?: number;      // Default: 10,000
  maxPages?: number;      // Max pages to auto-fetch (default: 1)
  autoPaginate?: boolean; // Fetch all pages automatically (default: false)
}

export class CenecaClient {
  private readonly defaultPageSize = 10_000;
  
  async query(
    question: string, 
    options?: QueryOptions
  ): Promise<PaginatedResult> {
    const pageSize = options?.pageSize ?? this.defaultPageSize;
    
    // Estimate query size first (from Challenge #3)
    const estimate = await this.estimateQuery(question);
    
    // Warn if result will be large
    if (estimate.estimatedRows > pageSize) {
      console.warn(
        `⚠️  Query will return ~${estimate.estimatedRows.toLocaleString()} rows ` +
        `(showing first ${pageSize.toLocaleString()}). ` +
        `Use pagination to access more.`
      );
    }
    
    // Execute with pagination
    const result = await this.makeRequest<PaginatedResult>('/api/query', {
      method: 'POST',
      body: JSON.stringify({
        question,
        page: 1,
        page_size: pageSize,
        include_details: options?.includeDetails
      })
    });
    
    // Auto-paginate if requested
    if (options?.autoPaginate && result.hasMore) {
      return this.fetchAllPages(question, result, options);
    }
    
    return result;
  }
  
  async getPage(
    question: string,
    page: number,
    options?: QueryOptions
  ): Promise<PaginatedResult> {
    const pageSize = options?.pageSize ?? this.defaultPageSize;
    
    return this.makeRequest<PaginatedResult>('/api/query', {
      method: 'POST',
      body: JSON.stringify({
        question,
        page,
        page_size: pageSize
      })
    });
  }
  
  private async fetchAllPages(
    question: string,
    firstPage: PaginatedResult,
    options?: QueryOptions
  ): Promise<PaginatedResult> {
    const maxPages = options?.maxPages ?? Infinity;
    const allRows = [...firstPage.rows];
    
    let currentPage = 1;
    let result = firstPage;
    
    // Fetch remaining pages
    while (result.hasMore && currentPage < maxPages) {
      currentPage++;
      result = await this.getPage(question, currentPage, options);
      allRows.push(...result.rows);
      
      // Progress callback
      if (options?.onStream) {
        options.onStream({
          type: 'status',
          timestamp: new Date().toISOString(),
          data: {
            message: `Fetching page ${currentPage}/${result.totalPages}`,
            progress: Math.round((currentPage / result.totalPages) * 100)
          }
        });
      }
    }
    
    return {
      ...result,
      rows: allRows,
      page: currentPage,
      hasMore: result.hasMore && currentPage >= maxPages
    };
  }
  
  // Helper: Async iterator for manual pagination
  async *queryPages(
    question: string,
    options?: QueryOptions
  ): AsyncGenerator<PaginatedResult> {
    let page = 1;
    let hasMore = true;
    
    while (hasMore) {
      const result = await this.getPage(question, page, options);
      yield result;
      
      hasMore = result.hasMore;
      page++;
    }
  }
}
```

#### Step 3: Server-Side Pagination (2 hours)

```python
# In server/agent/endpoints.py

from pydantic import BaseModel

class QueryRequest(BaseModel):
    question: str
    page: int = 1
    page_size: int = 10_000
    include_details: bool = False

@app.post("/api/query")
async def query_endpoint(request: QueryRequest):
    # Execute query (gets all matching rows)
    result = await execute_query(request.question)
    
    # Calculate pagination
    total_rows = len(result.rows)
    total_pages = math.ceil(total_rows / request.page_size)
    
    # Get requested page
    start_idx = (request.page - 1) * request.page_size
    end_idx = start_idx + request.page_size
    page_rows = result.rows[start_idx:end_idx]
    
    return {
        "queryId": result.query_id,
        "rows": page_rows,
        "columns": result.columns,
        "page": request.page,
        "pageSize": request.page_size,
        "totalRows": total_rows,
        "totalPages": total_pages,
        "hasMore": request.page < total_pages,
        "context": {
            "databases_queried": result.databases_queried,
            "execution_time_ms": result.execution_time_ms,
            "timestamp": datetime.utcnow().isoformat()
        },
        "schema_used": result.schema_used
    }
```

### Usage Examples

#### Default: First Page Only

```javascript
// Returns first 10,000 rows automatically
const result = await ceneca.query("Show all customer orders");

console.log(result.rows.length);        // 10,000
console.log(result.totalRows);          // 2,400,000
console.log(result.hasMore);            // true
console.log(result.totalPages);         // 240

// Warning logged:
// ⚠️ Query will return ~2,400,000 rows (showing first 10,000)
```

#### Get Specific Page

```javascript
// Get page 2
const page2 = await ceneca.getPage("Show all orders", 2);

// Get page 5 with custom page size
const page5 = await ceneca.getPage("Show all orders", 5, {
  pageSize: 5000
});
```

#### Manual Pagination UI

```javascript
function PaginatedTable({ query }) {
  const [currentPage, setCurrentPage] = useState(1);
  const [result, setResult] = useState(null);

  useEffect(() => {
    ceneca.getPage(query, currentPage).then(setResult);
  }, [currentPage]);

  return (
    <div>
      <table>
        {/* Render result.rows */}
      </table>
      
      <div className="pagination">
        <button 
          disabled={currentPage === 1}
          onClick={() => setCurrentPage(p => p - 1)}
        >
          Previous
        </button>
        
        <span>
          Page {result?.page} of {result?.totalPages}
          ({result?.totalRows.toLocaleString()} total rows)
        </span>
        
        <button 
          disabled={!result?.hasMore}
          onClick={() => setCurrentPage(p => p + 1)}
        >
          Next
        </button>
      </div>
    </div>
  );
}
```

#### Auto-Paginate (Fetch All)

```javascript
// Fetch all pages automatically (use with caution!)
const result = await ceneca.query("Show all orders", {
  autoPaginate: true,
  maxPages: 10,  // Safety limit
  onStream: (event) => {
    if (event.type === 'status') {
      updateProgress(event.data.message);
      // "Fetching page 3/10"
    }
  }
});

console.log(result.rows.length);  // 100,000 (10 pages × 10,000)
```

#### Async Iterator (Memory Efficient)

```javascript
// Process pages one at a time (memory efficient)
for await (const page of ceneca.queryPages("Show all orders")) {
  processRows(page.rows);
  
  console.log(`Processed page ${page.page}/${page.totalPages}`);
  
  // Stop early if needed
  if (foundWhatINeed) break;
}
```

#### Infinite Scroll

```javascript
function InfiniteScrollTable({ query }) {
  const [pages, setPages] = useState([]);
  const [currentPage, setCurrentPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);

  const loadMore = async () => {
    const result = await ceneca.getPage(query, currentPage);
    setPages(prev => [...prev, ...result.rows]);
    setHasMore(result.hasMore);
    setCurrentPage(p => p + 1);
  };

  return (
    <div>
      <table>
        {pages.map((row, i) => (
          <tr key={i}>{/* render row */}</tr>
        ))}
      </table>
      
      {hasMore && (
        <button onClick={loadMore}>Load More</button>
      )}
    </div>
  );
}
```

#### With Estimation Warning

```javascript
// Before running expensive query
const estimate = await ceneca.estimateQuery("Show all customer data");

if (estimate.estimatedRows > 100000) {
  const proceed = confirm(
    `This query will return ~${estimate.estimatedRows.toLocaleString()} rows. ` +
    `Continue? (This may take ${estimate.estimatedTimeSeconds}s)`
  );
  
  if (!proceed) return;
}

const result = await ceneca.query("Show all customer data", {
  pageSize: 5000  // Smaller pages for large queries
});
```

#### Custom Page Size

```javascript
// For large displays: bigger pages
const result = await ceneca.query("Show orders", {
  pageSize: 50000  // 50k rows per page
});

// For mobile: smaller pages
const result = await ceneca.query("Show orders", {
  pageSize: 100  // Only 100 rows
});
```

### Documentation Template

```markdown
## Pagination

Ceneca automatically paginates large query results to prevent memory issues.

### Default Behavior

Queries return the first 10,000 rows by default:

```javascript
const result = await ceneca.query("Show all orders");

console.log(result.rows.length);  // 10,000
console.log(result.totalRows);    // 2,400,000
console.log(result.hasMore);      // true
```

### Get More Pages

**Specific page:**
```javascript
const page2 = await ceneca.getPage("Show all orders", 2);
```

**All pages automatically:**
```javascript
const result = await ceneca.query("Show orders", {
  autoPaginate: true,
  maxPages: 10  // Safety limit
});
```

**Async iterator (memory efficient):**
```javascript
for await (const page of ceneca.queryPages("Show orders")) {
  processRows(page.rows);
  if (done) break;
}
```

### Custom Page Size

```javascript
const result = await ceneca.query("Show orders", {
  pageSize: 5000  // 5k rows per page
});
```

### Result Properties

- `rows`: Array of data for current page
- `page`: Current page number (1-indexed)
- `pageSize`: Rows per page
- `totalRows`: Total rows across all pages
- `totalPages`: Total number of pages
- `hasMore`: Whether more pages available

### Best Practices

**Mobile apps:** Use smaller page sizes (100-1000)
```javascript
{ pageSize: 500 }
```

**Desktop dashboards:** Default (10,000) works well

**Background processing:** Use async iterator
```javascript
for await (const page of ceneca.queryPages("...")) { ... }
```

**Large exports:** Use autoPaginate with progress
```javascript
{
  autoPaginate: true,
  maxPages: 100,
  onStream: (e) => showProgress(e)
}
```
```

### Implementation Effort

| Task | Time | Difficulty |
|------|------|-----------|
| Add pagination to response types | 30 min | Easy |
| Implement SDK pagination logic | 2 hours | Medium |
| Add server-side pagination | 2 hours | Medium |
| Integrate with estimation (Challenge #3) | 1 hour | Easy |
| Add async iterator helper | 1 hour | Medium |
| Write documentation & examples | 1.5 hours | Easy |
| **Total** | **8 hours** | **Medium** |

### Why This Works

1. **Safe by default**: 10k row limit prevents crashes
2. **Transparent**: Companies don't need to think about pagination for small queries
3. **Flexible**: Multiple ways to access more data
4. **Memory efficient**: Can process huge datasets page by page
5. **Warned**: Estimation alerts before executing expensive queries
6. **Configurable**: Page size adjustable per query
7. **Progressive**: Start simple, add pagination only when needed

---

## All Challenges Complete! ✅

All 8 challenges have been addressed with minimal, practical solutions.

---

## Summary

This document addresses all 8 critical challenges for headless API integration with **minimal, practical solutions**.

### Complete Challenge Overview

| Challenge | Solution | Implementation Time | Difficulty |
|-----------|----------|-------------------|-----------|
| **1. Streaming** | Single callback pattern, buffered fallback | 4 hours | Easy |
| **2. Authentication** | Token provider pattern, auto-refresh | 5 hours | Medium |
| **3. Query Cost** | Built-in limits, estimation, warnings | 6 hours | Medium |
| **4. Error Handling** | Structured error codes, suggestions | 10 hours | Medium |
| **5. Versioning** | Semantic ranges, 6-9 month support | 10 hours | Medium |
| **6. No UI Context** | Minimal context in responses, streaming | 6 hours | Easy |
| **7. Schema Changes** | Already solved by existing infrastructure | 0 hours | N/A |
| **8. Result Size** | Transparent pagination, 10k default | 8 hours | Medium |
| **Total** | | **49 hours** | **~2 weeks** |

### Key Design Principles

Each solution prioritizes:
1. **Sensible defaults** - Works well out of the box
2. **Clear errors** - Actionable error messages
3. **Configurability** - Companies can adjust to their needs
4. **Future-proof** - Can be extended without breaking changes
5. **Leverage existing** - Use Ceneca's current infrastructure
6. **Minimal overhead** - Small payloads, fast responses

### What Companies Get

**Out of the box:**
- ✅ Streaming with progress updates
- ✅ Automatic token refresh
- ✅ Safe query limits (10k rows, 60s timeout)
- ✅ Structured errors with suggestions
- ✅ Version compatibility checking
- ✅ Context about data sources
- ✅ Automatic schema sync
- ✅ Transparent pagination

**With minimal configuration:**
- Custom limits and timeouts
- Detailed SQL queries and performance metrics
- Manual pagination controls
- Strict version enforcement
- Auto-paginate for large datasets

**Advanced capabilities:**
- Async iterators for memory-efficient processing
- Real-time reasoning chain display
- Schema change notifications
- Query estimation before execution

### Integration Complexity

**For Companies:**
- **Simple integration**: 2-3 days (basic queries, default settings)
- **Production-ready**: 1 week (error handling, pagination, auth)
- **Advanced features**: 2-3 weeks (custom UI, all context displayed)

**For Ceneca:**
- **MVP**: 2 weeks (all 8 challenges addressed)
- **Polish**: 1 week (testing, documentation, examples)
- **Total**: 3 weeks to production-ready headless API

### Support Burden Mitigation

These solutions minimize support burden through:
- **Self-documenting errors** - Every error includes what to do
- **Proactive warnings** - Estimate size before executing
- **Automatic recovery** - Token refresh, schema reindex
- **Clear documentation** - Comprehensive examples for all patterns
- **Progressive disclosure** - Start simple, add complexity as needed

### Next Steps

1. **Review** this document with engineering team
2. **Prioritize** challenges based on customer demand
3. **Implement** in phases (can be done incrementally)
4. **Beta test** with 2-3 friendly customers
5. **Iterate** based on feedback
6. **Launch** with comprehensive documentation


# Slack MCP Connection and Query System Integration

This document outlines the approach for integrating Slack as a queryable data source within the Data Connector system, leveraging the existing adapter-orchestrator architecture.

## 1. Overview

The integration enables users to query Slack data using natural language through the same CLI interface that's used for database queries. This allows for insights across both communication data (Slack) and structured data (databases) within a single system.

## 2. Architecture

### 2.1 Components

The integration consists of these key components:

1. **Slack Adapter**: Implements the `DBAdapter` interface for Slack data
2. **Slack Schema Model**: Represents Slack's structure as queryable "schema" metadata
3. **Authentication Flow**: Session-based OAuth flow for CLI users
4. **MCP Client**: Client for the MCP server that manages Slack API access
5. **Query Templates**: LLM prompts for translating natural language to Slack queries

### 2.2 Data Model

Slack data will be modeled as:

```
Workspace
└── Channels
    └── Messages
        └── Threads
            └── Replies
```

This document-oriented structure maps naturally to Slack's organization and allows for semantic querying.

## 3. Authentication Flow

### 3.1 Session-Based CLI Authentication

The authentication flow is designed to be seamless for CLI users:

1. User runs `data-connector slack auth`
2. CLI generates a temporary session ID
3. Browser opens to `https://server.com/api/auth/slack/authorize?session=XYZ123`
4. User completes OAuth in browser
5. Server associates credentials with session
6. CLI retrieves and stores credentials locally
7. Future CLI commands use stored credentials automatically

This removes the need for users to manually enter or know their user_id or workspace_id.

### 3.2 Credential Storage

User credentials will be stored in:
- `~/.data-connector/slack_credentials.json`

Contents will include:
```json
{
  "user_id": 123,
  "workspaces": [
    {
      "id": 456,
      "team_id": "T12345",
      "name": "Acme Corp",
      "is_default": true
    }
  ]
}
```

### 3.3 Server-Side Sessions

The MCP server will maintain temporary sessions to connect browser-based authentication with CLI clients:

1. Store session ID with expiration (30 minutes)
2. Associate session with OAuth state
3. Upon successful OAuth, link credentials to session
4. Provide API endpoint for CLI to retrieve credentials using session ID

## 4. Schema Introspection and Indexing

### 4.1 Slack "Schema" Definition

The Slack adapter will introspect and create schema metadata including:

1. **Workspace Information**:
   - Team name
   - Member count
   - Available channels

2. **Channel Metadata**:
   - Channel name and purpose
   - Member count
   - Message volume statistics
   - Creation date

3. **Usage Statistics**:
   - Active channels
   - Message distribution
   - Conversation patterns

### 4.2 Schema Indexing Process

The indexing process will:
1. Connect to Slack via MCP
2. Fetch workspace, channel, and user metadata
3. Create schema document chunks
4. Embed chunks using the same embedding approach as database schemas
5. Store in FAISS index for semantic search

### 4.3 Update Frequency

Schema metadata will be updated:
- Every 6 hours automatically
- On-demand when requested via `--refresh` flag
- Limited to configured history timeframe (default 30 days, up to 90 for enterprise)

## 5. Query Execution

### 5.1 Query Pipeline

1. User submits natural language query via CLI with `--type slack`
2. System retrieves relevant Slack schema chunks
3. LLM translates query to appropriate Slack API calls
4. Adapter executes calls through MCP server
5. Results are formatted and returned

### 5.2 Query Capabilities

The system will support queries like:

- "How many channels do I have in my workspace?"
- "Show me the most active channels in the last week"
- "How many messages are in the #general channel?"
- "What are the top 5 users by message count?"
- "Show me all messages containing 'data analysis' in the #project-alpha channel"

### 5.3 Handling Large Results

For large result sets:
- Implement pagination for message history queries
- Enforce reasonable limits (e.g., 1000 messages)
- Provide options for date range filtering

## 6. Integration with Existing CLI

### 6.1 CLI Extensions

The `query.py` CLI will be extended with:

```
data-connector query --type slack "How many messages in #general?"
data-connector slack auth  # New command for authentication
data-connector slack list-workspaces  # List available workspaces
data-connector slack refresh  # Force schema refresh
```

### 6.2 Configuration Options

New options in `config.yaml`:

```yaml
# Slack Configuration
slack:
  mcp_url: http://localhost:8500  # MCP server URL
  history_days: 30  # Conversation history to index (30-90)
  update_frequency: 6  # Hours between schema updates
```

## 7. Security Considerations

- All tokens stored encrypted
- User credentials stored only on client machine
- Communication with MCP server over TLS
- Workspace isolation to prevent cross-tenant access
- Audit logging of all Slack data access

## 8. Implementation Plan

1. Implement Slack adapter (`slack.py`)
2. Create session-based auth flow in MCP
3. Implement schema introspection for Slack
4. Update CLI with authentication command
5. Create Slack-specific query templates
6. Test basic metadata queries
7. Add advanced querying capabilities

## 9. Limitations and Considerations

- Slack API rate limits may affect query performance for large workspaces
- Historical data beyond configured limit will not be queryable
- User must have appropriate permissions in the Slack workspace
- Channel history requires either bot membership or user token with appropriate scopes 
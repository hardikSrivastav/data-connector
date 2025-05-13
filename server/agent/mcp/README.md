# Slack MCP Server

This component provides a Multi-Channel Provider (MCP) implementation for Slack, allowing the data connector agent to communicate with Slack workspaces via OAuth authentication.

## Features

- OAuth-based authentication for Slack workspaces
- Secure token storage in PostgreSQL
- Multi-tenant support for multiple users and workspaces
- JWT-based API authentication
- Slack tools for:
  - Listing channels
  - Fetching message history
  - Getting thread replies
  - Posting messages
  - Getting user information

## Setup

### Prerequisites

- Docker and Docker Compose
- PostgreSQL
- Python 3.11+

### Installation

1. Install dependencies:
   ```bash
   cd server/agent/mcp
   pip install -r requirements.txt
   ```

2. Configure environment variables:
   Create a `.env` file in the `server/agent/mcp` directory with the following variables:

   ```
   # Server settings
   MCP_HOST=0.0.0.0
   MCP_PORT=8500
   MCP_DEBUG=true
   MCP_DEV_MODE=true

   # Auth database settings
   MCP_DB_HOST=postgres-mcp
   MCP_DB_PORT=5432
   MCP_DB_NAME=slackoauth
   MCP_DB_USER=slackoauth
   MCP_DB_PASSWORD=slackoauth

   # URL settings
   MCP_API_BASE_URL=http://localhost:8500
   MCP_WEB_APP_URL=http://localhost:3000
   MCP_CORS_ORIGINS=["*"]

   # Slack settings
   MCP_SLACK_CLIENT_ID=your_slack_client_id
   MCP_SLACK_CLIENT_SECRET=your_slack_client_secret
   MCP_SLACK_SIGNING_SECRET=your_slack_signing_secret

   # Security settings
   MCP_SECRET_KEY=your_secret_key
   MCP_TOKEN_EXPIRY_HOURS=1
   ```

3. Start the server:

   Using Docker Compose:
   ```bash
   docker-compose up mcp-server
   ```

   Or manually:
   ```bash
   cd server
   python -m agent.mcp.server
   ```

### Slack App Configuration

1. Create a Slack App at https://api.slack.com/apps
2. Configure OAuth:
   - Add the following scopes: `channels:read`, `groups:read`, `im:read`, `mpim:read`, `channels:history`, `groups:history`, `im:history`, `mpim:history`, `users:read`, `chat:write`
   - Set the redirect URL to `http://your-server-url:8500/api/auth/slack/callback`
3. Install the app to your workspace
4. Copy the Client ID, Client Secret, and Signing Secret to your `.env` file

## Usage

### Client Usage

The MCP client provides an easy interface for interacting with Slack:

```python
from server.agent.mcp.client import MCPClient

# Create client
client = MCPClient("http://localhost:8500")

# Authenticate
client.authenticate("user_id", "workspace_id")

# List channels
channels = client.list_channels()

# Get channel history
messages = client.get_channel_history("channel_id", limit=50)

# Get thread replies
replies = client.get_thread_replies("channel_id", "thread_ts")

# Post message
client.post_message("channel_id", "Hello from the agent!")

# Post reply to a thread
client.post_message("channel_id", "This is a reply", thread_ts="thread_ts")

# Get user info
user = client.get_user_info("user_id")
```

### API Endpoints

- `GET /api/auth/slack/authorize` - Start OAuth flow
- `GET /api/auth/slack/callback` - OAuth callback
- `GET /api/auth/slack/workspaces/{user_id}` - Get user workspaces
- `POST /api/tools/token` - Generate API token
- `POST /api/tools/invoke` - Invoke Slack tools

## Docker Setup

The MCP server and its PostgreSQL database are configured in `docker-compose.yml`. To start only the MCP components:

```bash
docker-compose up mcp-server postgres-mcp
```

### Troubleshooting

If you encounter module import errors:

1. Check that the Python path is properly set:
   ```
   export PYTHONPATH=/path/to/server
   ```

2. Make sure all `__init__.py` files are present in the directory structure:
   ```
   server/
   ├── __init__.py
   └── agent/
       ├── __init__.py
       └── mcp/
           ├── __init__.py
           └── ...
   ```

## Security

- JWT tokens for API authentication
- Encrypted token storage in the database
- CSRF protection for OAuth flow
- Token rotation support 
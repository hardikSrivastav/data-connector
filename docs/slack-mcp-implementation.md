# On-Prem Slack MCP Integration: Enterprise OAuth Implementation

This document provides a complete, end-to-end OAuth-based implementation for integrating Slack with your data connector, enabling corporate users to securely connect and analyze their Slack workspace data alongside database information through a seamless SSO experience.

---

## 1. Central Slack App Configuration (Admin Only)

As the administrator of the data connector platform, you'll need to create a central Slack app that all your users can connect to.

1. **Create the Platform App**

   * Go to [https://api.slack.com/apps](https://api.slack.com/apps) → **Create New App** → **From scratch**.
   * Name your app (e.g., `Data Connector`) and select your development workspace.

2. **Configure App Manifest**
   Under **Settings → App Manifest**, import this YAML snippet and save:

   ```yaml
   display_information:
     name: Data Connector
     description: Connect your Slack workspace to your data analysis platform
     background_color: "#4A154B"
   features:
     bot_user:
       display_name: Data Connector
       always_online: true
   oauth_config:
     redirect_urls:
       - https://your-platform-domain.com/api/oauth/slack/callback
     scopes:
       bot:
         - channels:read
         - groups:read
         - im:read
         - mpim:read
         - channels:history
         - groups:history
         - im:history
         - mpim:history
         - users:read
         - chat:write
   settings:
     org_deploy_enabled: true
     socket_mode_enabled: false
     token_rotation_enabled: true
   ```

3. **App Distribution Settings**
   
   * Go to **Settings → Manage Distribution**
   * Enable **Remove Hard Coded Information**
   * Enable **Activate Public Distribution**
   * Save changes

4. **Record Credentials**

   * Go to **Basic Information**
   * Under **App Credentials**, record your:
     * `Client ID`
     * `Client Secret`
     * `Signing Secret`

---

## 2. Multi-Tenant MCP Server Implementation with FastAPI

This section shows how to build a FastAPI-based MCP server that supports multiple organizations using OAuth, token storage, and tenant isolation.

### 2.1. Dedicated Database for OAuth Storage

We'll use a dedicated PostgreSQL database (separate from client databases) to store OAuth tokens and user-workspace relationships:

```yaml
# docker-compose.yml addition
  auth-postgres:
    image: postgres:16
    ports:
      - "6500:5432"
    environment:
      - POSTGRES_USER=slackoauth
      - POSTGRES_PASSWORD=slackoauth
      - POSTGRES_DB=slackoauth
    volumes:
      - auth-postgres-data:/var/lib/postgresql/data
    container_name: data-connector-auth-postgres
    networks:
      - connector-network

volumes:
  auth-postgres-data:
```

### 2.2. Project Structure

```
server/agent/mcp/
├── __init__.py                 # Package initialization
├── models/
│   ├── __init__.py
│   ├── oauth.py                # Pydantic models for OAuth
│   └── workspace.py            # Workspace data models
├── api/
│   ├── __init__.py
│   ├── auth.py                 # OAuth endpoints
│   └── tools.py                # MCP tool endpoints
├── db/
│   ├── __init__.py
│   ├── models.py               # SQLAlchemy models
│   └── crud.py                 # Database operations
├── client.py                   # MCP client for agent usage
├── server.py                   # FastAPI application
├── security.py                 # Token encryption/JWT
└── config.py                   # MCP configuration
```

### 2.3. Database Models for OAuth Storage

```python
# server/agent/mcp/db/models.py
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text, Table
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import datetime
import json

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    name = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    
    # SSO information if needed
    sso_provider = Column(String(50), nullable=True)
    sso_id = Column(String(255), nullable=True)
    
    # Relationships
    workspaces = relationship("SlackWorkspace", secondary="user_workspaces", back_populates="users")

class SlackWorkspace(Base):
    __tablename__ = "slack_workspaces"
    
    id = Column(Integer, primary_key=True)
    team_id = Column(String(50), unique=True, nullable=False)
    team_name = Column(String(255), nullable=False)
    bot_user_id = Column(String(50), nullable=False)
    bot_token = Column(Text, nullable=False)  # Encrypted xoxb token
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    last_used = Column(DateTime, nullable=True)
    
    # For token rotation
    access_token_expires_at = Column(DateTime, nullable=True)
    refresh_token = Column(Text, nullable=True)
    
    # Relationships
    users = relationship("User", secondary="user_workspaces", back_populates="workspaces")

class UserWorkspace(Base):
    __tablename__ = "user_workspaces"
    
    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    workspace_id = Column(Integer, ForeignKey("slack_workspaces.id"), primary_key=True)
    added_at = Column(DateTime, default=datetime.datetime.utcnow)
    is_admin = Column(Boolean, default=False)
    
    # Authorized scopes as JSON
    authorized_scopes = Column(Text, nullable=True)
    
    def get_scopes(self):
        if self.authorized_scopes:
            return json.loads(self.authorized_scopes)
        return []
```

### 2.4. OAuth Flow Implementation with FastAPI

```python
# server/agent/mcp/api/auth.py
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
import secrets
from typing import Optional
import json

from ..db import crud, models
from ..db.database import get_db
from ..models.oauth import OAuthState, OAuthToken
from ..security import create_jwt_token
from ..config import settings

router = APIRouter()

@router.get("/slack/authorize")
async def slack_authorize(request: Request, db: Session = Depends(get_db)):
    """Start the OAuth flow by redirecting to Slack"""
    # Get user from session
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    # Generate and store state
    state = secrets.token_urlsafe(32)
    oauth_state = OAuthState(state=state, user_id=user_id)
    crud.create_oauth_state(db, oauth_state)
    
    # Store state in session for validation on callback
    request.session["slack_oauth_state"] = state
    
    # Generate authorization URL
    from slack_sdk.oauth import AuthorizeUrlGenerator
    
    authorize_url_generator = AuthorizeUrlGenerator(
        client_id=settings.SLACK_CLIENT_ID,
        scopes=settings.SLACK_SCOPES,
        redirect_uri=f"{settings.API_BASE_URL}/api/oauth/slack/callback"
    )
    
    url = authorize_url_generator.generate(state)
    return RedirectResponse(url)

@router.get("/slack/callback")
async def slack_callback(
    code: str, 
    state: str, 
    request: Request, 
    db: Session = Depends(get_db)
):
    """Handle the OAuth callback from Slack"""
    # Verify state
    expected_state = request.session.get("slack_oauth_state")
    
    if not state or state != expected_state:
        raise HTTPException(status_code=400, detail="Invalid state parameter")
    
    # Clear state from session
    request.session.pop("slack_oauth_state", None)
    
    # Get user_id from state
    user_id = crud.get_user_id_from_state(db, state)
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid state or expired")
    
    # Exchange code for token
    from slack_sdk.web import WebClient
    client = WebClient()
    
    try:
        response = client.oauth_v2_access(
            client_id=settings.SLACK_CLIENT_ID,
            client_secret=settings.SLACK_CLIENT_SECRET,
            code=code,
            redirect_uri=f"{settings.API_BASE_URL}/api/oauth/slack/callback"
        )
        token_data = response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error exchanging code: {str(e)}")
    
    # Get the user
    user = crud.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if workspace already exists
    team_id = token_data["team"]["id"]
    workspace = crud.get_workspace_by_team_id(db, team_id)
    
    if not workspace:
        # Create new workspace record
        workspace = models.SlackWorkspace(
            team_id=team_id,
            team_name=token_data["team"]["name"],
            bot_user_id=token_data["bot_user_id"],
            bot_token=token_data["access_token"]  # Will be encrypted in service layer
        )
        workspace = crud.create_workspace(db, workspace)
    
    # Link user to workspace if not already linked
    user_workspace = crud.get_user_workspace(db, user_id, workspace.id)
    if not user_workspace:
        scopes = token_data.get("scope", "").split(",")
        crud.create_user_workspace(db, user_id, workspace.id, scopes)
    
    # Redirect to success page
    return RedirectResponse(url=f"{settings.WEB_APP_URL}/slack/success?team={team_id}")
```

### 2.5. Multi-Tenant MCP Server Implementation

```python
# server/agent/mcp/api/tools.py
from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any, Optional
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db.database import get_db
from ..db import crud
from ..security import verify_jwt_token, JWTData
from ..models.slack import SlackToolRequest

router = APIRouter()

class ToolRequest(BaseModel):
    tool: str
    parameters: Optional[Dict[str, Any]] = {}

class ToolResponse(BaseModel):
    result: Dict[str, Any]

@router.post("/invoke", response_model=ToolResponse)
async def invoke(
    request: ToolRequest,
    token_data: JWTData = Depends(verify_jwt_token),
    db: Session = Depends(get_db)
):
    """MCP invoke endpoint for Slack tools"""
    # Get workspace from token data
    workspace = crud.get_workspace(db, token_data.workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    # Create Slack client with workspace's bot token
    slack = WebClient(token=workspace.bot_token)
    
    try:
        if request.tool == "slack_list_channels":
            res = slack.conversations_list(limit=1000)
            channels = [{"id": c["id"], "name": c["name"]} for c in res["channels"]]
            return ToolResponse(result={"channels": channels})

        elif request.tool == "slack_get_channel_history":
            channel_id = request.parameters.get("channel_id")
            if not channel_id:
                raise HTTPException(status_code=400, detail="Missing channel_id parameter")
                
            limit = request.parameters.get("limit", 50)
            res = slack.conversations_history(channel=channel_id, limit=limit)
            return ToolResponse(result={"messages": res["messages"]})

        elif request.tool == "slack_get_thread_replies":
            channel_id = request.parameters.get("channel_id")
            thread_ts = request.parameters.get("thread_ts")
            
            if not channel_id or not thread_ts:
                raise HTTPException(
                    status_code=400, 
                    detail="Missing required parameters: channel_id and thread_ts"
                )
                
            res = slack.conversations_replies(channel=channel_id, ts=thread_ts)
            return ToolResponse(result={"replies": res["messages"]})
            
        elif request.tool == "slack_post_message":
            channel_id = request.parameters.get("channel_id")
            text = request.parameters.get("text")
            
            if not channel_id or not text:
                raise HTTPException(
                    status_code=400, 
                    detail="Missing required parameters: channel_id and text"
                )
            
            # Optional thread parameter
            message_params = {
                "channel": channel_id,
                "text": text
            }
            
            thread_ts = request.parameters.get("thread_ts")
            if thread_ts:
                message_params["thread_ts"] = thread_ts
                
            res = slack.chat_postMessage(**message_params)
            return ToolResponse(result={"message": res["message"]})

        else:
            raise HTTPException(status_code=400, detail=f"Unknown tool: {request.tool}")

    except SlackApiError as e:
        raise HTTPException(status_code=500, detail=f"Slack API error: {e.response['error']}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Token generation endpoint
class TokenRequest(BaseModel):
    user_id: int
    workspace_id: int

class TokenResponse(BaseModel):
    token: str
    expires_at: int

@router.post("/token", response_model=TokenResponse)
async def generate_token(
    request: TokenRequest,
    db: Session = Depends(get_db)
):
    """Generate a JWT token for client use"""
    # Verify user has access to this workspace
    user_workspace = crud.get_user_workspace(db, request.user_id, request.workspace_id)
    if not user_workspace:
        raise HTTPException(status_code=403, detail="User does not have access to this workspace")
    
    # Generate and return token
    from datetime import datetime, timedelta
    
    token, expires_at = create_jwt_token(
        user_id=request.user_id,
        workspace_id=request.workspace_id,
        expiry=datetime.utcnow() + timedelta(hours=1)
    )
    
    return TokenResponse(token=token, expires_at=expires_at)
```

### 2.6. FastAPI Application Setup

```python
# server/agent/mcp/server.py
from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from sqlalchemy.orm import Session

from .db.database import engine, Base, get_db
from .api import auth, tools
from .config import settings

# Create FastAPI app
app = FastAPI(
    title="Data Connector MCP Server",
    description="Slack MCP Server for Data Connector",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create database tables
Base.metadata.create_all(bind=engine)

# Include routers
app.include_router(auth.router, prefix="/api/oauth", tags=["oauth"])
app.include_router(tools.router, prefix="/api/mcp", tags=["mcp"])

# Health check endpoint
@app.get("/health", tags=["system"])
async def health_check(db: Session = Depends(get_db)):
    """Check if the server is healthy"""
    # Check if database is connected
    try:
        db.execute("SELECT 1")
        db_status = "connected"
    except Exception:
        db_status = "disconnected"
    
    return {
        "status": "healthy",
        "database": db_status,
        "version": "1.0.0"
    }

# Main entrypoint
def start():
    """Start the FastAPI server using uvicorn"""
    uvicorn.run(
        "server.agent.mcp.server:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )

if __name__ == "__main__":
    start()
```

---

## 3. Client Integration with Data Analysis Agent

This section details how to integrate the OAuth-based Slack MCP server with your existing data analysis agent.

### 3.1. Add Slack Adapter to Your Engine

Create a new adapter for Slack in your database adapters directory:

```python
# server/agent/db/adapters/slack.py
import requests
import json
import jwt
from typing import Dict, List, Any, Optional
from .base import BaseDBAdapter
import logging

class SlackAdapter(BaseDBAdapter):
    """Adapter for Slack MCP integration"""
    
    def __init__(self, uri: str, **kwargs):
        super().__init__(uri)
        self.mcp_base_url = uri.rstrip('/')
        self.workspace_id = kwargs.get('workspace_id')
        self.user_id = kwargs.get('user_id')
        self.token = kwargs.get('token')
        
        # If no token provided, request one
        if not self.token and self.workspace_id and self.user_id:
            self._request_token()
            
    def _request_token(self):
        """Request a token from the MCP server"""
        try:
            response = requests.post(
                f"{self.mcp_base_url}/api/mcp/token",
                json={
                    'user_id': self.user_id,
                    'workspace_id': self.workspace_id
                }
            )
            response.raise_for_status()
            self.token = response.json().get('token')
        except Exception as e:
            logging.error(f"Failed to get MCP token: {str(e)}")
            raise RuntimeError(f"Failed to authenticate with Slack MCP server: {str(e)}")
    
    async def test_connection(self) -> bool:
        """Test connection to the Slack workspace"""
        if not self.token:
            return False
            
        try:
            headers = {'Authorization': f'Bearer {self.token}'}
            response = requests.post(
                f"{self.mcp_base_url}/api/mcp/invoke",
                json={'tool': 'slack_list_channels'},
                headers=headers
            )
            return response.status_code == 200
        except Exception:
            return False
    
    async def execute(self, query_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Execute a Slack MCP tool call"""
        if isinstance(query_data, str):
            # Try to parse as JSON
            try:
                query_data = json.loads(query_data)
            except json.JSONDecodeError:
                # It's not JSON, so it's probably a tool name
                query_data = {'tool': query_data}
        
        # Ensure it has tool field
        if 'tool' not in query_data:
            raise ValueError("Query must include 'tool' field")
            
        tool = query_data.get('tool')
        params = query_data.get('parameters', {})
        
        try:
            headers = {'Authorization': f'Bearer {self.token}'}
            response = requests.post(
                f"{self.mcp_base_url}/api/mcp/invoke",
                json={'tool': tool, 'parameters': params},
                headers=headers
            )
            response.raise_for_status()
            
            result = response.json().get('result', {})
            
            # Different tools return different data structures
            if tool == 'slack_list_channels':
                return result.get('channels', [])
            elif tool == 'slack_get_channel_history':
                return result.get('messages', [])
            elif tool == 'slack_get_thread_replies':
                return result.get('replies', [])
            elif tool == 'slack_post_message':
                return [result.get('message', {})]
            else:
                return [result]
                
        except Exception as e:
            logging.error(f"Slack MCP error: {str(e)}")
            raise RuntimeError(f"Failed to execute Slack tool '{tool}': {str(e)}")
    
    async def llm_to_query(self, query_text: str, **kwargs) -> Dict[str, Any]:
        """Convert natural language to Slack query"""
        # This would normally be implemented using your LLM client
        from agent.llm.client import get_llm_client
        
        llm = get_llm_client()
        schema_chunks = kwargs.get('schema_chunks', [])
        
        # Render a template for Slack queries
        prompt = llm.render_template(
            "slack_query.tpl",
            user_question=query_text,
            schema_chunks=schema_chunks
        )
        
        # Generate a query that specifies which Slack tool to use
        slack_query = await llm.generate_slack_query(prompt)
        
        try:
            # Parse the LLM response as JSON
            return json.loads(slack_query)
        except json.JSONDecodeError:
            # If it's not valid JSON, create a default query
            return {"tool": "slack_list_channels"}
```

### 3.2. Register the New Adapter in `__init__.py`

```python
# server/agent/db/adapters/__init__.py
from .base import BaseDBAdapter
from .postgres import PostgresAdapter
from .mongo import MongoDBAdapter
from .qdrant import QdrantAdapter
from .slack import SlackAdapter

# Map of db_type to adapter class
ADAPTER_MAP = {
    'postgres': PostgresAdapter,
    'postgresql': PostgresAdapter,
    'mongodb': MongoDBAdapter,
    'qdrant': QdrantAdapter,
    'slack': SlackAdapter
}

def get_adapter(db_type: str) -> BaseDBAdapter:
    """Factory function to get the appropriate adapter"""
    adapter_class = ADAPTER_MAP.get(db_type.lower())
    if not adapter_class:
        raise ValueError(f"Unsupported database type: {db_type}")
    
    return adapter_class
```

### 3.3. Add Slack-Specific Prompt Template

Create a new template for Slack queries:

```python
# server/agent/prompts/slack_query.tpl
You are an AI assistant with access to a Slack workspace.

I'll provide you with a question, and you need to determine which Slack API tool to use and what parameters to include.

Available tools:
- slack_list_channels: List all channels in the workspace
- slack_get_channel_history: Get message history from a channel (params: channel_id, limit)
- slack_get_thread_replies: Get all replies in a thread (params: channel_id, thread_ts)
- slack_post_message: Post a message to a channel (params: channel_id, text, thread_ts)

User's question: {{ user_question }}

Please return a JSON object with the tool name and parameters. For example:
{
  "tool": "slack_get_channel_history",
  "parameters": {
    "channel_id": "C012345",
    "limit": 50
  }
}
```

### 3.4. Update CLI to Support Slack Commands

Add Slack command support to your `query.py` CLI.

---

## 4. Orchestrating Combined Data Analysis

This section demonstrates how to combine Slack data with database insights for comprehensive analysis through your orchestrator.

### 4.1. Update Orchestrator for Multi-Source Analysis

Extend your existing orchestrator to support multi-source queries that combine Slack and database data.

---

## 5. Security & Best Practices

* **Token Encryption**: Store Slack tokens encrypted in the database (not in plaintext)
* **Token Rotation**: Implement automated token refresh using Slack's rotation API
* **Per-User ACLs**: Limit access to only workspaces explicitly authorized by each user
* **API Rate Limiting**: Implement intelligent backoff to avoid Slack API rate limits
* **Audit Logging**: Log all MCP operations for security and compliance
* **Token Validation**: Verify token scopes before every request
* **Cross-Tenant Isolation**: Ensure complete isolation between different customers
* **Regular Security Scans**: Set up automated vulnerability scanning

---

With this comprehensive implementation, your data connector platform allows users to seamlessly:

1. Log in with their corporate SSO
2. Authorize access to their Slack workspace with a single click
3. Query and analyze data across both databases and Slack conversations
4. Generate insights that combine structured and communication data
5. Share findings back to relevant Slack channels

All of this happens with enterprise-grade security and without requiring users to manage API tokens or complex configuration files.

# Template Editor Service Architecture

## Overview

This document outlines the architecture for an intelligent file template editing service that provides AI-powered customization of authentication file templates while maintaining system integrity and reproducibility.

## Design Concept

**Core Mission**: An intelligent agent that takes generic auth file templates and customizes them based on user requirements through guided information gathering and validated edits.

### Template Structure

The service operates on three core auth file templates:
- **Config file** (`auth.config.js/ts`) - Main authentication configuration
- **Environment file** (`.env.template`) - Environment variables and secrets
- **Middleware file** (`auth.middleware.js/ts`) - Authentication logic implementation

## File Replication System

### Three-Tier File System Architecture

```
/templates/
  ├── auth-v1.2.0/
  │   ├── auth.config.template
  │   ├── .env.template
  │   └── auth.middleware.template
  └── auth-v1.1.0/ (previous versions)

/workspaces/
  ├── user-session-abc123/
  │   ├── metadata.json
  │   ├── auth.config.js
  │   ├── .env.example
  │   └── auth.middleware.js
  └── user-session-def456/

/completed/
  ├── user-123-timestamp/
  └── user-456-timestamp/
```

### Moving Parts

**1. Template Manager**
- Maintains immutable template versions
- Handles template versioning and rollbacks
- Provides template metadata and validation schemas

**2. Session Manager**
- Creates isolated workspaces for each user session
- Manages session lifecycle and cleanup
- Tracks editing progress and state

**3. Replication Service**
- Copies templates to user workspaces
- Applies file transformations (rename .template extensions)
- Maintains template-to-instance mapping

**4. AI Editor Agent**
- Operates within user workspace only
- Cannot access template directories
- Validates edits against template schema

**5. Validation Engine**
- Ensures edited files conform to template structure
- Checks for required placeholders being filled
- Validates against template's JSON schema

## Information Acquisition Flow

### Smart Inference First
The agent analyzes existing project files to understand:
- Framework being used (React, Node.js, etc.)
- Existing auth patterns in codebase
- Package.json dependencies for auth libraries
- Database connections and user models

### Structured Questionnaire
Based on analysis, ask targeted questions:
```
"I see you're using Express with JWT. Do you want:
1. Local authentication with bcrypt
2. OAuth integration (Google, GitHub, etc.)
3. Both approaches?"
```

## Tool Call Pattern

### Read-Analyze-Edit Pattern
1. `Read` existing project files for context
2. `Glob` to find related auth files
3. `Grep` to identify auth patterns
4. `Edit` or `MultiEdit` to modify templates
5. `Read` again to verify changes

### Example Tool Calls
```
- Read("package.json") → understand dependencies
- Grep("passport|jwt|auth", "**/*.js") → find auth patterns  
- Edit("auth.config.template", old_string="{{AUTH_METHOD}}", new_string="jwt")
- MultiEdit("auth.middleware.template", [
    {old_string: "{{SECRET_KEY}}", new_string: process.env.JWT_SECRET},
    {old_string: "{{ALGORITHM}}", new_string: "HS256"}
  ])
```

## Replication Flow

### Session Initialization
1. User requests auth setup
2. System creates unique workspace: `/workspaces/session-{uuid}`
3. Template files copied to workspace with metadata:
   ```json
   {
     "templateVersion": "auth-v1.2.0",
     "templateHash": "sha256:abc123...",
     "createdAt": "2024-01-01T00:00:00Z",
     "placeholders": ["{{AUTH_METHOD}}", "{{SECRET_KEY}}"]
   }
   ```

### File Isolation
```
Original Template (READ-ONLY):
/templates/auth-v1.2.0/auth.config.template

User Workspace (READ-WRITE):
/workspaces/session-abc123/auth.config.js
```

## Reproducibility Guarantees

### 1. Template Immutability
- Template files are read-only after creation
- Changes require new version with migration path
- Template hash verification prevents tampering

### 2. Structural Validation
- JSON Schema defines template structure
- AI edits validated against schema before applying
- Required sections cannot be removed

### 3. Change Tracking
```json
{
  "templateVersion": "auth-v1.2.0",
  "changes": [
    {
      "placeholder": "{{AUTH_METHOD}}",
      "originalValue": "{{AUTH_METHOD}}",
      "newValue": "jwt",
      "timestamp": "2024-01-01T00:15:00Z"
    }
  ]
}
```

### 4. Diff-Based Validation
- Track what changed vs. what remained
- Ensure core structure preservation
- Flag significant deviations for review

## Service Integration Architecture

### Microservice Boundaries

```
Main Application:
├── Frontend (React/Next.js)
├── Main Backend (your existing DB)
└── Main Auth System

Template Editor Service:
├── Editor Frontend Module
├── Editor Backend (separate DB)
├── AI Agent Infrastructure
└── File System Manager
```

### Integration Patterns

**1. Frontend Integration**
```javascript
// Your main app
<MainApp>
  <TemplateEditor 
    onComplete={handleTemplateComplete}
    userContext={currentUser}
    projectId={projectId}
  />
</MainApp>
```

**2. API Gateway Pattern**
```
/api/main/* → Your existing backend
/api/templates/* → Template editor service
/api/ai-agent/* → AI agent infrastructure
```

**3. Event-Driven Communication**
```javascript
// Events flowing between services
MainApp → TemplateService: "user-initiated-template"
TemplateService → MainApp: "template-completed"
TemplateService → MainApp: "template-failed"
```

## Database Separation

### Isolated Data Stores
```
Main Database:
├── users
├── projects  
├── your_business_logic
└── template_references (foreign keys only)

Template Database:
├── template_versions
├── user_sessions
├── workspace_metadata
├── edit_history
└── validation_schemas
```

### Cross-Service References
```json
// In your main DB
{
  "projectId": "proj-123",
  "templateSessionId": "session-abc123",  // Reference only
  "templateStatus": "completed"
}

// In template DB
{
  "sessionId": "session-abc123",
  "externalProjectId": "proj-123",  // Reference back
  "userId": "user-456"
}
```

## AI Agent Infrastructure

### Separate Agent Environment
```
Agent Infrastructure:
├── Agent Runtime (Docker/K8s)
├── Tool Registry
├── Session Management
├── File System (isolated)
└── Security Sandbox
```

### Agent Communication
```javascript
// Your app triggers agent work
POST /api/ai-agent/sessions
{
  "sessionId": "session-abc123",
  "templateVersion": "auth-v1.2.0",
  "userContext": {...}
}

// Agent reports back
WebSocket: /api/ai-agent/sessions/session-abc123/events
{
  "type": "question",
  "question": "Which OAuth providers?",
  "options": ["google", "github", "auth0"]
}
```

## Security & Isolation

### Authentication Flow
```
1. User authenticated in main app
2. Main app generates JWT for template service
3. Template service validates JWT against main app
4. Agent operates with scoped permissions
```

### Data Access Controls
```javascript
// Agent can only access its workspace
const agentPermissions = {
  read: [`/workspaces/${sessionId}/*`],
  write: [`/workspaces/${sessionId}/*`],
  forbidden: ['/templates/*', '/other-sessions/*']
};
```

## Deployment Strategies

### 1. Sidecar Pattern
```yaml
# docker-compose.yml
services:
  main-app:
    build: ./main-app
  template-service:
    build: ./template-service
  ai-agent:
    build: ./ai-agent
  shared-redis:
    image: redis
```

### 2. Embedded Module
```javascript
// Package as npm module
npm install @yourcompany/template-editor

// Integrate in your app
import { TemplateEditor } from '@yourcompany/template-editor';
```

### 3. Micro-frontend
```javascript
// Module federation
const TemplateEditor = React.lazy(() => 
  import('templateService/TemplateEditor')
);
```

## Data Flow Architecture

### Request Flow
```
User Action → Main Frontend → Main Backend → Template Service → AI Agent
                     ↓
              Update Main DB ← Template Complete ← Agent Complete
```

### State Management
```javascript
// Shared state bus
const eventBus = {
  'template:started': (data) => updateMainAppState(data),
  'template:progress': (data) => updateProgress(data),
  'template:completed': (data) => downloadFiles(data)
};
```

## Validation System

### Multi-layer Validation
1. **Syntax Validation**: Ensure valid JavaScript/JSON syntax
2. **Schema Validation**: Check required fields are populated
3. **Security Validation**: Warn about hardcoded secrets, weak configurations
4. **Integration Validation**: Verify compatibility with existing codebase

### Editing Flow
1. **Template Analysis** → Parse placeholders and dependencies
2. **Context Gathering** → Analyze existing project structure
3. **Information Collection** → Interactive, targeted questioning
4. **Template Population** → Replace placeholders with validated values
5. **Integration Check** → Ensure compatibility with existing code
6. **User Review** → Present changes for approval
7. **File Generation** → Create final auth files

## System Prompt Design

```
You are an Auth File Editor Agent. Your role is to:

CORE MISSION: Transform generic auth templates into production-ready files

ANALYSIS PHASE:
- Read existing project files to understand architecture
- Identify auth patterns and dependencies
- Infer user needs from codebase context

INFORMATION GATHERING:
- Ask targeted questions based on analysis
- Provide smart defaults when possible
- Explain implications of choices

VALIDATION RULES:
- Never hardcode secrets in files
- Ensure all placeholders are filled
- Validate syntax and security practices
- Check integration compatibility

EDITING CONSTRAINTS:
- Only modify template files provided
- Preserve existing code structure
- Use MultiEdit for related changes
- Verify all edits before completion

ERROR HANDLING:
- If validation fails, explain issue and ask for correction
- Provide specific guidance on fixes needed
- Never proceed with invalid configurations
```

## Configuration Management

### Environment Separation
```
Main App Config:
MAIN_DB_URL=postgresql://main-db
TEMPLATE_SERVICE_URL=http://template-service
AI_AGENT_URL=http://ai-agent

Template Service Config:
TEMPLATE_DB_URL=postgresql://template-db
MAIN_APP_URL=http://main-app
AI_AGENT_URL=http://ai-agent
```

## Error Handling & Rollback

### Cross-Service Error Handling
```javascript
try {
  await templateService.createSession(projectId);
} catch (error) {
  // Rollback in main app
  await mainApp.updateProject(projectId, { templateStatus: 'failed' });
  throw error;
}
```

### Health Checks
```
/health/main-app → Main app status
/health/template-service → Template service status  
/health/ai-agent → Agent infrastructure status
```

## Quality Assurance

### Template Drift Prevention
- Automatic diff reports showing template vs. final files
- Percentage similarity score (e.g., 85% structural similarity)
- Mandatory fields that cannot be modified
- Optional customization zones clearly marked

### Rollback Mechanism
- Any edit can be reverted to template state
- Workspace can be reset to clean template copy
- Version upgrade path for existing customizations

## Key Design Principles

1. **Intelligence Over Burden**: The agent does heavy lifting through codebase analysis rather than asking users to provide every detail
2. **Validation-First**: Every edit is validated against multiple criteria before application
3. **Context-Aware**: Decisions are made based on existing project structure and patterns
4. **Incremental Verification**: Each step is validated before proceeding to the next
5. **Clean Separation**: Services maintain clear boundaries while enabling seamless interplay
6. **Reproducibility**: Template integrity is maintained while allowing flexible customization

This architecture ensures template integrity while providing flexible customization within controlled boundaries and seamless integration with existing applications.
# Template Editor Service

An AI-powered template editing service that provides intelligent customization of authentication file templates.

## Quick Start

1. **Set up environment variables**:
   ```bash
   cp .env.example .env
   # Edit .env and add your Anthropic API key
   ```

2. **Run with Docker**:
   ```bash
   docker-compose up --build
   ```

3. **Access the application**:
   - Frontend: http://localhost:8500
   - Backend API: http://localhost:8501
   - API Documentation: http://localhost:8501/docs

## Architecture

- **Frontend**: React TypeScript (port 8500)
- **Backend**: FastAPI Python (port 8501)
- **Database**: SQLite
- **AI**: Anthropic Claude API
- **Deployment**: Docker containers

## Features

- 🤖 AI-powered template customization
- 🔒 Workspace isolation for each user session
- 📝 Template version management
- ✅ Multi-layer validation (syntax, schema, security)
- 🔄 Real-time chat interface with AI agent
- 📊 Change tracking and diff visualization

## Development

See `/docs/template-editor-service-architecture.md` for detailed architecture documentation.

## Environment Variables

- `ANTHROPIC_API_KEY`: Your Anthropic API key
- `DATABASE_URL`: SQLite database path (default: sqlite:///./app.db)
- `CORS_ORIGINS`: Allowed CORS origins (default: http://localhost:8500)
#!/usr/bin/env python3
"""
Simple HTTP Server for Agent API
Provides HTTP access to the agent endpoints with CORS support
"""

import uvicorn
import sys
import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Add server path
sys.path.insert(0, str(Path(__file__).parent))

# Import agent router
from agent.api.endpoints import router as agent_router
from application.routes.storage import router as storage_router

def create_app() -> FastAPI:
    """Create FastAPI application with agent endpoints"""
    
    app = FastAPI(
        title="Ceneca Data Connector Agent",
        description="HTTP API for data processing and query execution",
        version="1.0.0"
    )

    # Add CORS middleware for web client access
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",  # React dev server
            "http://localhost:5173",  # Vite dev server
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5173",
            "*"  # For now, allow all origins in development
        ],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(agent_router, prefix="/api/agent", tags=["agent"])
    app.include_router(storage_router, tags=["storage"])  # storage_router already has /api prefix

    @app.get("/health")
    async def health_check():
        """Health check endpoint"""
        return {"status": "healthy", "service": "ceneca-agent"}

    return app

def main():
    """Start the HTTP server"""
    try:
        print("🚀 Starting Ceneca Agent HTTP Server...")
        print("📊 Agent API: http://localhost:8787/api/agent")
        print("📝 API Documentation: http://localhost:8787/docs")
        print("🌐 Web Client can connect to: http://localhost:8787")
        print()
        
        app = create_app()
        
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=8787,
            reload=True,  # Auto-reload on code changes in development
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\n👋 Agent server stopped by user")
    except Exception as e:
        print(f"❌ Error starting agent server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 
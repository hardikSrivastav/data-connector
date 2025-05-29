#!/usr/bin/env python3
"""
FastAPI Server Runner for Notion Clone
Runs the API server on port 8787
"""

import uvicorn
import os
import sys
from pathlib import Path

# Add the server directory to Python path
server_dir = Path(__file__).parent
sys.path.insert(0, str(server_dir))

# Set environment variables if not already set
os.environ.setdefault("DATABASE_URL", "postgresql://notion_user:notion_password@localhost:5432/notion_clone")
os.environ.setdefault("ENVIRONMENT", "development")

def main():
    """Run the FastAPI server"""
    try:
        print("🚀 Starting Notion Clone API server on port 8787...")
        print(f"📊 Database URL: {os.environ.get('DATABASE_URL')}")
        print(f"🌍 Environment: {os.environ.get('ENVIRONMENT')}")
        print("📝 API Documentation: http://localhost:8787/docs")
        print("⚡ Web Client should connect to: http://localhost:8787")
        print()
        
        uvicorn.run(
            "application:create_app",
            factory=True,
            host="0.0.0.0",
            port=8787,
            reload=True,  # Auto-reload on code changes
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\n👋 Server stopped by user")
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 
#!/usr/bin/env python3
"""
FastAPI Server Runner for Notion Clone
Runs the API server on port 8787
"""

import uvicorn
import os
import sys
import subprocess
import time
from pathlib import Path

# Add the server directory to Python path
server_dir = Path(__file__).parent
sys.path.insert(0, str(server_dir))

# Set environment variables if not already set
os.environ.setdefault("DATABASE_URL", "postgresql://notion_user:notion_password@localhost:5432/notion_clone")
os.environ.setdefault("ENVIRONMENT", "development")

def ensure_postgres_running():
    """Ensure PostgreSQL Docker container is running"""
    container_name = "ceneca-storage-db"
    
    try:
        # Check if container is running
        result = subprocess.run(
            ["docker", "ps", "--filter", f"name={container_name}", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            check=True
        )
        
        if container_name in result.stdout:
            print(f"✅ PostgreSQL container '{container_name}' is already running")
            return True
            
        # Check if container exists but is stopped
        result = subprocess.run(
            ["docker", "ps", "-a", "--filter", f"name={container_name}", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            check=True
        )
        
        if container_name in result.stdout:
            print(f"🔄 Starting PostgreSQL container '{container_name}'...")
            subprocess.run(["docker", "start", container_name], check=True)
            
            # Wait for database to be ready
            print("⏳ Waiting for database to be ready...")
            time.sleep(3)
            print(f"✅ PostgreSQL container '{container_name}' started successfully")
            return True
        else:
            print(f"❌ PostgreSQL container '{container_name}' not found")
            print("Please ensure the container exists or create it first")
            return False
            
    except subprocess.CalledProcessError as e:
        print(f"❌ Error managing Docker container: {e}")
        return False
    except FileNotFoundError:
        print("❌ Docker not found. Please ensure Docker is installed and running")
        return False

def main():
    """Run the FastAPI server"""
    try:
        # Ensure PostgreSQL container is running before starting the server
        if not ensure_postgres_running():
            print("❌ Failed to start PostgreSQL container. Exiting...")
            sys.exit(1)
        
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
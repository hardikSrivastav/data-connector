#!/usr/bin/env python3
"""
PostgreSQL Health Check for Notion Clone
Verifies database connection, schema, and basic functionality
"""

import os
import sys
from pathlib import Path
import psycopg2
from psycopg2 import sql
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add the server directory to Python path
server_dir = Path(__file__).parent
sys.path.insert(0, str(server_dir))

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://notion_user:notion_password@localhost:5432/notion_clone")

def check_postgres_service():
    """Check if PostgreSQL service is running"""
    print("🔍 Checking PostgreSQL service...")
    
    import subprocess
    try:
        # Check if PostgreSQL is accepting connections
        result = subprocess.run(['pg_isready', '-h', 'localhost', '-p', '5432'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print("✅ PostgreSQL service is running and accepting connections")
            return True
        else:
            print("❌ PostgreSQL service is not responding")
            print(f"   Error: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print("❌ PostgreSQL service check timed out")
        return False
    except FileNotFoundError:
        print("⚠️  pg_isready command not found (PostgreSQL client tools not installed)")
        # Continue with connection test
        return None

def check_database_connection():
    """Test database connection with raw psycopg2"""
    print("\n🔍 Testing database connection...")
    
    try:
        # Parse connection details from URL
        parts = DATABASE_URL.replace('postgresql://', '').split('@')
        user_pass = parts[0].split(':')
        host_db = parts[1].split('/')
        host_port = host_db[0].split(':')
        
        username = user_pass[0]
        password = user_pass[1]
        host = host_port[0]
        port = int(host_port[1]) if len(host_port) > 1 else 5432
        database = host_db[1]
        
        print(f"   Connecting to: {host}:{port}")
        print(f"   Database: {database}")
        print(f"   Username: {username}")
        
        # Test connection
        conn = psycopg2.connect(
            host=host,
            port=port,
            database=database,
            user=username,
            password=password
        )
        
        # Test basic query
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        
        print("✅ Database connection successful!")
        print(f"   PostgreSQL version: {version}")
        
        cursor.close()
        conn.close()
        return True
        
    except psycopg2.OperationalError as e:
        print("❌ Database connection failed!")
        print(f"   Error: {str(e)}")
        
        if "database \"notion_clone\" does not exist" in str(e):
            print("\n💡 Solution: Run the setup script to create the database:")
            print("   ./setup_postgres.sh")
        elif "role \"notion_user\" does not exist" in str(e):
            print("\n💡 Solution: Create the database user:")
            print("   sudo -u postgres createuser --interactive --pwprompt notion_user")
        elif "password authentication failed" in str(e):
            print("\n💡 Solution: Check the password or recreate the user:")
            print("   sudo -u postgres psql -c \"ALTER USER notion_user WITH PASSWORD 'notion_password';\"")
        elif "could not connect to server" in str(e):
            print("\n💡 Solution: Start PostgreSQL service:")
            print("   macOS: brew services start postgresql")
            print("   Linux: sudo systemctl start postgresql")
            
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        return False

def check_sqlalchemy_connection():
    """Test SQLAlchemy connection and schema"""
    print("\n🔍 Testing SQLAlchemy ORM connection...")
    
    try:
        engine = create_engine(DATABASE_URL, echo=False)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        
        # Test connection
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1 as test"))
            print("✅ SQLAlchemy connection successful!")
            
        # Check if our tables exist
        with engine.connect() as conn:
            tables_query = text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name IN ('workspaces', 'pages', 'blocks', 'changes')
                ORDER BY table_name;
            """)
            
            result = conn.execute(tables_query)
            existing_tables = [row[0] for row in result.fetchall()]
            
            expected_tables = ['workspaces', 'pages', 'blocks', 'changes']
            
            print(f"\n📋 Database schema status:")
            for table in expected_tables:
                if table in existing_tables:
                    print(f"   ✅ Table '{table}' exists")
                else:
                    print(f"   ❌ Table '{table}' missing")
            
            if len(existing_tables) == len(expected_tables):
                print("✅ All required tables exist!")
                return check_table_data(conn)
            else:
                print("\n💡 Solution: Tables will be auto-created when you start the API server")
                print("   python run_api.py")
                return True
                
    except Exception as e:
        print(f"❌ SQLAlchemy connection failed: {str(e)}")
        return False

def check_table_data(conn):
    """Check existing data in tables"""
    print(f"\n📊 Current data summary:")
    
    try:
        tables = ['workspaces', 'pages', 'blocks', 'changes']
        
        for table in tables:
            try:
                result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                count = result.fetchone()[0]
                print(f"   {table}: {count} records")
            except Exception as e:
                print(f"   {table}: Error reading ({str(e)})")
        
        # Show recent changes if any
        try:
            result = conn.execute(text("""
                SELECT type, entity, entity_id, timestamp 
                FROM changes 
                ORDER BY timestamp DESC 
                LIMIT 5
            """))
            changes = result.fetchall()
            
            if changes:
                print(f"\n📝 Recent changes:")
                for change in changes:
                    print(f"   {change[0]} {change[1]} {change[2]} at {change[3]}")
            else:
                print(f"\n📝 No changes logged yet")
                
        except Exception:
            pass  # Table might not exist yet
            
        return True
        
    except Exception as e:
        print(f"❌ Error checking table data: {str(e)}")
        return False

def main():
    """Run all PostgreSQL checks"""
    print("🔍 PostgreSQL Health Check for Notion Clone")
    print("=" * 50)
    
    # Service check
    service_ok = check_postgres_service()
    
    # Connection check
    connection_ok = check_database_connection()
    
    if not connection_ok:
        print("\n❌ Cannot proceed with further checks due to connection issues")
        sys.exit(1)
    
    # SQLAlchemy check
    sqlalchemy_ok = check_sqlalchemy_connection()
    
    print("\n" + "=" * 50)
    if connection_ok and sqlalchemy_ok:
        print("🎉 PostgreSQL is ready for the Notion Clone!")
        print("\nNext steps:")
        print("1. Start the API server: python run_api.py")
        print("2. Start the web client: cd web && npm run dev")
        print("3. Visit: http://localhost:3000")
    else:
        print("❌ PostgreSQL setup needs attention")
        print("\nTry running the setup script: ./setup_postgres.sh")

if __name__ == "__main__":
    main() 
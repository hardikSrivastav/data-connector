#!/usr/bin/env python3
"""
Migration Runner Script
Execute Phase 2 database migration for user isolation
"""

import sys
import os

# Add the migration directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'server', 'application', 'migrations'))

def main():
    """Run the migration with proper error handling"""
    try:
        from add_user_ownership import run_migration, verify_migration, rollback_migration
        
        if len(sys.argv) > 1:
            command = sys.argv[1].lower()
            
            if command == "run":
                print("🚀 Running Phase 2 User Ownership Migration...")
                run_migration()
                print("✅ Migration completed successfully!")
                
            elif command == "verify":
                print("🔍 Verifying migration status...")
                verify_migration()
                
            elif command == "rollback":
                print("🔄 Rolling back migration...")
                rollback_migration()
                print("✅ Rollback completed!")
                
            else:
                print(f"❌ Unknown command: {command}")
                print("Usage: python run_migration.py [run|verify|rollback]")
                sys.exit(1)
        else:
            print("Usage: python run_migration.py [run|verify|rollback]")
            print("")
            print("Commands:")
            print("  run      - Execute the migration")
            print("  verify   - Check migration status")
            print("  rollback - Undo the migration")
            sys.exit(1)
            
    except ImportError as e:
        print(f"❌ Migration import failed: {e}")
        print("Make sure you're running from the project root directory")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 
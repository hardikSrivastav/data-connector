#!/usr/bin/env python3
"""
Run Reasoning Chains Migration

Simple script to run the reasoning chains migration safely.
"""

import sys
import os

# Add the server directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'server'))

try:
    # This file's location: run_reasoning_migration.py
    # Target migration file: server/application/migrations/add_reasoning_chains.py
    from server.application.migrations.add_reasoning_chains import run_migration
    
    print("🧠 Running Reasoning Chains Migration...")
    print("This will add the new reasoning_chains table without affecting existing data.")
    print()
    
    # Run the migration
    run_migration()
    
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you're running this from the project root directory.")
    sys.exit(1)
except Exception as e:
    print(f"❌ Migration failed: {e}")
    sys.exit(1) 
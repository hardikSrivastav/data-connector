#!/usr/bin/env python3
import os
import sys
sys.path.append('server')

try:
    import psycopg2
    DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://notion_user:notion_password@localhost:5432/notion_clone')
    
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    
    cur.execute('SELECT id, user_id, page_id, workspace_id, block_id, chart_type, created_at FROM charts ORDER BY created_at DESC LIMIT 3')
    results = cur.fetchall()
    
    if results:
        print('📊 RECENT CHART ENTRIES:')
        print('=' * 60)
        for row in results:
            chart_id, user_id, page_id, workspace_id, block_id, chart_type, created_at = row
            print(f'ID: {chart_id}')
            
            user_ok = user_id != 'default_value'
            page_ok = page_id != 'default_value' 
            workspace_ok = workspace_id != 'default_value'
            
            print(f'User: {user_id} ({"✅ OK" if user_ok else "❌ PLACEHOLDER"})')
            print(f'Page: {page_id} ({"✅ OK" if page_ok else "❌ PLACEHOLDER"})')
            print(f'Workspace: {workspace_id} ({"✅ OK" if workspace_ok else "❌ PLACEHOLDER"})')
            print(f'Block: {block_id or "NULL"}')
            print(f'Type: {chart_type}')
            print(f'Created: {created_at}')
            print('-' * 30)
            
        # Check if fix worked
        latest = results[0]
        latest_user_ok = latest[1] != 'default_value'
        latest_page_ok = latest[2] != 'default_value'
        latest_workspace_ok = latest[3] != 'default_value'
        
        if latest_user_ok and latest_page_ok and latest_workspace_ok:
            print('🎉 SUCCESS: Fix is working! Real user context IDs found.')
            print('📈 Charts should now appear in the CanvasWorkspace Charts tab.')
        else:
            print('❌ ISSUE: Still seeing placeholder values in most recent chart.')
            print('🔧 The fix may need more investigation.')
    else:
        print('No charts found in database')
        
    conn.close()
    
except ImportError:
    print('❌ psycopg2 not installed - please install with: pip install psycopg2-binary')
except Exception as e:
    print(f'❌ Database error: {e}')
    print('Make sure PostgreSQL is running and accessible')
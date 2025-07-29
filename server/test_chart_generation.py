#!/usr/bin/env python3
"""
Test script to generate a chart using the API endpoints with a specific session ID
"""

import requests
import json
import time

# Configuration
API_BASE_URL = "http://localhost:8787"
SESSION_ID = "4e7fe944-0998-4b1e-8d39-b822388ae9cd"

def test_chart_generation():
    """Test chart generation with a query that should create visualizations"""
    
    # Query that should generate a chart
    query_data = {
        "question": "show me the top 5 products by sales in a bar chart",
        "verbose": True,
        "show_outputs": True,
        "show_captured_data": True,
        "include_aggregated_data": True,
        "save_session": True
    }
    
    print(f"🚀 Testing chart generation for session: {SESSION_ID}")
    print(f"📊 Query: {query_data['question']}")
    print(f"🌐 API URL: {API_BASE_URL}/api/agent/langgraph/stream")
    
    try:
        # Make streaming request to LangGraph endpoint
        response = requests.post(
            f"{API_BASE_URL}/api/agent/langgraph/stream",
            json=query_data,
            headers={
                "Content-Type": "application/json",
                "Accept": "text/event-stream"
            },
            stream=True,
            timeout=120
        )
        
        print(f"📡 Response status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"❌ Request failed with status {response.status_code}")
            print(f"Response: {response.text}")
            return False
        
        print("📥 Processing streaming response...")
        visualization_events = []
        session_id_found = None
        
        # Process streaming response
        for line in response.iter_lines(decode_unicode=True):
            if line.startswith('data: '):
                try:
                    data = json.loads(line[6:])
                    event_type = data.get('type', 'unknown')
                    
                    # Capture session_id from any event
                    if 'session_id' in data and not session_id_found:
                        session_id_found = data['session_id']
                        print(f"📋 Found session_id in stream: {session_id_found}")
                    
                    # Look for visualization-related events
                    if event_type in ['visualization_complete', 'chart_config_json', 'hybrid_chart_config_json']:
                        visualization_events.append(data)
                        print(f"🎨 Found visualization event: {event_type}")
                    
                    # Print key events
                    if event_type in ['status', 'complete', 'error']:
                        message = data.get('message', data.get('error', ''))
                        print(f"📢 {event_type}: {message}")
                        
                        if event_type == 'complete':
                            print("✅ Query completed successfully")
                            break
                        elif event_type == 'error':
                            print(f"❌ Query failed: {message}")
                            return False
                            
                except json.JSONDecodeError:
                    continue
        
        print(f"\n📊 Summary:")
        print(f"   - Session ID from stream: {session_id_found}")
        print(f"   - Visualization events found: {len(visualization_events)}")
        
        return session_id_found, visualization_events
        
    except Exception as e:
        print(f"❌ Error during API call: {e}")
        return False

def check_chart_files(session_id):
    """Check if chart files were created for the session"""
    import os
    import glob
    
    charts_dir = "/Users/hardiksrivastava/Ceneca/data-connector/server/charts"
    
    print(f"\n📁 Checking for chart files in: {charts_dir}")
    
    # Look for files containing the session ID
    pattern1 = os.path.join(charts_dir, f"*{session_id}*.json")
    session_files = glob.glob(pattern1)
    
    # Also check for recent files (last 5 minutes)
    import time
    recent_files = []
    if os.path.exists(charts_dir):
        for file in os.listdir(charts_dir):
            if file.endswith('.json'):
                file_path = os.path.join(charts_dir, file)
                file_time = os.path.getmtime(file_path)
                if time.time() - file_time < 300:  # 5 minutes
                    recent_files.append(file_path)
    
    print(f"📋 Files with session ID: {len(session_files)}")
    print(f"📋 Recent files (last 5 min): {len(recent_files)}")
    
    for file in session_files:
        print(f"   📄 Session file: {file}")
    
    for file in recent_files:
        print(f"   📄 Recent file: {file}")
    
    return session_files, recent_files

def test_chart_endpoint(session_id):
    """Test the chart fetching endpoint"""
    
    print(f"\n🔍 Testing chart endpoint for session: {session_id}")
    
    try:
        response = requests.get(f"{API_BASE_URL}/api/agent/sessions/{session_id}/charts")
        
        print(f"📡 Response status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"📊 Charts found: {data.get('total_charts', 0)}")
            
            if data.get('charts'):
                for i, chart in enumerate(data['charts']):
                    chart_type = chart.get('metadata', {}).get('chart_type', 'unknown')
                    data_points = chart.get('metadata', {}).get('data_points', 0)
                    print(f"   📈 Chart {i+1}: {chart_type} ({data_points} points)")
            
            return data
        else:
            print(f"❌ Request failed: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error testing endpoint: {e}")
        return None

if __name__ == "__main__":
    print("🧪 Chart Generation Test")
    print("=" * 50)
    
    # Step 1: Generate chart
    result = test_chart_generation()
    
    if result:
        session_id_from_stream, viz_events = result
        actual_session_id = session_id_from_stream or SESSION_ID
        
        # Step 2: Check files
        session_files, recent_files = check_chart_files(actual_session_id)
        
        # Step 3: Test endpoint
        endpoint_result = test_chart_endpoint(actual_session_id)
        
        print("\n🎯 Test Results:")
        print(f"   ✅ Query executed successfully")
        print(f"   📋 Session ID: {actual_session_id}")
        print(f"   🎨 Visualization events: {len(viz_events)}")
        print(f"   📄 Chart files found: {len(session_files + recent_files)}")
        if endpoint_result:
            print(f"   🔍 Endpoint charts: {endpoint_result.get('total_charts', 0)}")
    else:
        print("❌ Test failed")
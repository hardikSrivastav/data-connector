#!/usr/bin/env python3
"""
Simple test script to understand visualization API response format
Uses built-in urllib to avoid dependency issues
"""
import urllib.request
import urllib.parse
import json
import sys

# Configuration
API_BASE_URL = "http://localhost:8787/api/agent"
CENECA_SESSION_ID = "ac1d5420-77b0-46c1-8124-d4c232237d23"

def make_request(method, endpoint, data=None):
    """Make HTTP request using urllib"""
    url = f"{API_BASE_URL}{endpoint}"
    headers = {"Content-Type": "application/json"}
    
    if data:
        data = json.dumps(data).encode('utf-8')
    
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            response_data = response.read().decode('utf-8')
            return response.status, json.loads(response_data)
    except urllib.error.HTTPError as e:
        return e.code, {"error": e.read().decode('utf-8')}
    except Exception as e:
        return 500, {"error": str(e)}

def test_visualization_query():
    """Test the /visualization/query endpoint"""
    print("🧪 Testing /visualization/query endpoint")
    
    payload = {
        "query": "show me a bar chart of top 5 products by sales",
        "chart_preferences": {"type": "bar"},
        "auto_generate": True,
        "performance_mode": False
    }
    
    status, response = make_request("POST", "/visualization/query", payload)
    
    print(f"Status: {status}")
    print(f"Response: {json.dumps(response, indent=2)}")
    
    if status == 200:
        print("\n📊 VISUALIZATION QUERY RESPONSE ANALYSIS:")
        print(f"   - success: {response.get('success')}")
        print(f"   - session_id: {response.get('session_id')}")
        print(f"   - chart_config present: {bool(response.get('chart_config'))}")
        print(f"   - chart_data present: {bool(response.get('chart_data'))}")
        print(f"   - suggestions count: {len(response.get('suggestions', []))}")
        
        if response.get('chart_config'):
            chart_config = response['chart_config']
            print(f"\n📈 CHART CONFIG STRUCTURE:")
            print(f"   - type: {chart_config.get('type', 'unknown')}")
            print(f"   - layout keys: {list(chart_config.get('layout', {}).keys())}")
            print(f"   - data structure: {type(chart_config.get('data', []))}")
            print(f"   - data length: {len(chart_config.get('data', []))}")
    
    return status == 200

def test_langgraph_stream():
    """Test streaming from /langgraph/stream endpoint"""
    print("\n🧪 Testing /langgraph/stream endpoint")
    
    payload = {
        "question": "show me top 3 products by revenue with a pie chart",
        "include_aggregated_data": True,
        "save_session": True,
        "verbose": True,
        "show_outputs": True
    }
    
    url = f"{API_BASE_URL}/langgraph/stream"
    headers = {"Content-Type": "application/json"}
    data = json.dumps(payload).encode('utf-8')
    
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            print(f"Status: {response.status}")
            print("📡 Streaming events:")
            
            visualization_events = []
            event_count = 0
            
            # Read streaming response line by line
            for line_bytes in response:
                line = line_bytes.decode('utf-8').strip()
                if line and line.startswith("data: "):
                    try:
                        event_data = json.loads(line[6:])  # Remove "data: " prefix
                        event_type = event_data.get("event")
                        event_count += 1
                        
                        print(f"   🔔 Event #{event_count}: {event_type}")
                        
                        # Capture visualization-related events
                        if event_type and any(keyword in event_type.lower() for keyword in 
                                            ['visualization', 'chart', 'plot']):
                            visualization_events.append(event_data)
                            print(f"   🎨 VISUALIZATION EVENT CAPTURED!")
                            print(f"       Keys: {list(event_data.keys())}")
                            
                            # Print key visualization data
                            if "chart_config" in event_data:
                                chart_config = event_data['chart_config']
                                print(f"       📈 Chart config type: {chart_config.get('type', 'unknown')}")
                                print(f"       📈 Chart title: {chart_config.get('layout', {}).get('title', 'N/A')}")
                                print(f"       📈 Data points: {len(chart_config.get('data', []))}")
                            
                            if "visualization_data" in event_data:
                                viz_data = event_data['visualization_data']
                                print(f"       🎯 Visualization data keys: {list(viz_data.keys())}")
                                
                        # Stop after reasonable number of events to avoid timeout
                        if event_count >= 50:
                            print(f"   📊 Stopped after {event_count} events to avoid timeout")
                            break
                            
                    except json.JSONDecodeError:
                        if len(line) < 100:  # Only print short lines to avoid spam
                            print(f"   ⚠️  Non-JSON line: {line}")
                            
            print(f"\n🎨 VISUALIZATION EVENTS SUMMARY:")
            print(f"   Total events processed: {event_count}")
            print(f"   Visualization events captured: {len(visualization_events)}")
            
            for i, event in enumerate(visualization_events, 1):
                print(f"\n   📊 Visualization Event #{i}:")
                print(f"      Type: {event.get('event')}")
                print(f"      Message: {event.get('message', 'N/A')}")
                
                # Print chart config in detail
                if 'chart_config' in event:
                    chart_config = event['chart_config']
                    print(f"      📈 Chart Configuration:")
                    print(f"         Type: {chart_config.get('type', 'unknown')}")
                    print(f"         Title: {chart_config.get('layout', {}).get('title', 'N/A')}")
                    print(f"         Data points: {len(chart_config.get('data', []))}")
                    
                    # Print a sample of the data structure
                    if chart_config.get('data'):
                        sample_data = chart_config['data'][0] if len(chart_config['data']) > 0 else {}
                        print(f"         Sample data keys: {list(sample_data.keys()) if isinstance(sample_data, dict) else 'Not dict'}")
                    
                    # Print layout info
                    layout = chart_config.get('layout', {})
                    print(f"         Layout keys: {list(layout.keys())}")
                    
                    print(f"      📄 Full chart config (first 500 chars):")
                    config_str = json.dumps(chart_config, indent=4)
                    print(f"         {config_str[:500]}{'...' if len(config_str) > 500 else ''}")
                    
            return len(visualization_events) > 0
            
    except Exception as e:
        print(f"❌ Stream test failed: {e}")
        return False

def main():
    """Main test function"""
    print("🧪 Testing Ceneca Visualization API")
    print(f"🌐 API Base URL: {API_BASE_URL}")
    print(f"🆔 Session ID: {CENECA_SESSION_ID}")
    print("=" * 80)
    
    # Test 1: Direct visualization endpoint
    success1 = test_visualization_query()
    
    # Test 2: LangGraph streaming for visualization events
    success2 = test_langgraph_stream()
    
    print("\n" + "=" * 80)
    print("🏁 TEST SUMMARY:")
    print(f"   Visualization Query: {'✅ Success' if success1 else '❌ Failed'}")
    print(f"   LangGraph Streaming: {'✅ Success' if success2 else '❌ Failed'}")
    
    if success1 or success2:
        print("\n✅ Successfully captured visualization data format!")
        print("   This data shows the structure that the frontend should expect.")
    else:
        print("\n❌ Could not capture visualization data format.")
        print("   The API might not be generating visualizations for the test queries.")

if __name__ == "__main__":
    main()
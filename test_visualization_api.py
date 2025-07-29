#!/usr/bin/env python3
"""
Test script to understand visualization API response format
"""
import requests
import json
import time

# Configuration
API_BASE_URL = "http://localhost:8787"
CENECA_SESSION_ID = "ac1d5420-77b0-46c1-8124-d4c232237d23"

def test_health():
    """Test basic API connectivity"""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        print(f"✅ Health check: {response.status_code}")
        if response.status_code == 200:
            print(f"   Response: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False

def test_visualization_query():
    """Test the /visualization/query endpoint"""
    try:
        payload = {
            "query": "show me a chart of sales by month",
            "chart_preferences": {"type": "line"},
            "auto_generate": True,
            "performance_mode": False
        }
        
        print(f"🔍 Testing /visualization/query with payload: {payload}")
        response = requests.post(
            f"{API_BASE_URL}/visualization/query",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        print(f"📊 Visualization query response: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Response structure:")
            print(f"   - success: {data.get('success')}")
            print(f"   - session_id: {data.get('session_id')}")
            print(f"   - chart_config keys: {list(data.get('chart_config', {}).keys()) if data.get('chart_config') else 'None'}")
            print(f"   - chart_data length: {len(data.get('chart_data', [])) if data.get('chart_data') else 0}")
            print(f"   - suggestions count: {len(data.get('suggestions', []))}")
            print(f"\n📋 Full response:")
            print(json.dumps(data, indent=2))
        else:
            print(f"❌ Error response: {response.text}")
            
    except Exception as e:
        print(f"❌ Visualization query test failed: {e}")

def test_langgraph_stream():
    """Test the /langgraph/stream endpoint to see visualization events"""
    try:
        payload = {
            "question": "show me the top 5 products by sales with a bar chart",
            "include_aggregated_data": True,
            "save_session": True,
            "verbose": True,
            "show_outputs": True
        }
        
        print(f"🔍 Testing /langgraph/stream with payload: {payload}")
        response = requests.post(
            f"{API_BASE_URL}/langgraph/stream",
            json=payload,
            headers={"Content-Type": "application/json"},
            stream=True,
            timeout=60
        )
        
        print(f"🌊 LangGraph stream response: {response.status_code}")
        
        if response.status_code == 200:
            print("📡 Streaming events:")
            visualization_events = []
            
            for line in response.iter_lines(decode_unicode=True):
                if line:
                    if line.startswith("data: "):
                        try:
                            event_data = json.loads(line[6:])  # Remove "data: " prefix
                            event_type = event_data.get("event")
                            
                            # Print basic event info
                            print(f"   🔔 Event: {event_type}")
                            
                            # Capture visualization-related events
                            if event_type and any(keyword in event_type.lower() for keyword in 
                                                ['visualization', 'chart', 'plot']):
                                visualization_events.append(event_data)
                                print(f"   🎨 VISUALIZATION EVENT CAPTURED: {event_type}")
                                print(f"       Keys: {list(event_data.keys())}")
                                
                                # Print key visualization data
                                if "chart_config" in event_data:
                                    print(f"       Chart config keys: {list(event_data['chart_config'].keys())}")
                                if "visualization_data" in event_data:
                                    print(f"       Visualization data keys: {list(event_data['visualization_data'].keys())}")
                            
                        except json.JSONDecodeError:
                            print(f"   ⚠️  Could not parse line: {line[:100]}...")
                            
            print(f"\n🎨 VISUALIZATION EVENTS SUMMARY:")
            print(f"   Total visualization events captured: {len(visualization_events)}")
            
            for i, event in enumerate(visualization_events, 1):
                print(f"\n   📊 Event #{i}:")
                print(f"      Type: {event.get('event')}")
                print(f"      Message: {event.get('message', 'N/A')}")
                if 'chart_config' in event:
                    chart_config = event['chart_config']
                    print(f"      Chart type: {chart_config.get('type', 'unknown')}")
                    print(f"      Chart title: {chart_config.get('layout', {}).get('title', 'N/A')}")
                    print(f"      Data points: {len(chart_config.get('data', []))}")
                    print(f"      Full chart config:")
                    print(json.dumps(chart_config, indent=8))
                    
        else:
            print(f"❌ Error response: {response.text}")
            
    except Exception as e:
        print(f"❌ LangGraph stream test failed: {e}")

def main():
    """Main test function"""
    print("🧪 Testing Ceneca Visualization API")
    print(f"🌐 API Base URL: {API_BASE_URL}")
    print(f"🆔 Session ID: {CENECA_SESSION_ID}")
    print("=" * 60)
    
    # Test basic connectivity
    if not test_health():
        print("❌ Cannot connect to API. Make sure the server is running.")
        return
    
    print("\n" + "=" * 60)
    print("🧪 Testing Visualization Endpoints")
    
    # Test direct visualization endpoint
    test_visualization_query()
    
    print("\n" + "=" * 60)
    print("🧪 Testing LangGraph Streaming for Visualization Events")
    
    # Test LangGraph streaming for visualization events
    test_langgraph_stream()

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Test script for the direct visualization connection
"""

import requests
import json
import time

def test_direct_visualization_endpoint():
    """Test the new /api/agent/visualization/query endpoint"""
    
    base_url = "http://localhost:8080"  # Adjust if different
    endpoint = f"{base_url}/api/agent/visualization/query"
    
    test_queries = [
        "show me sales data by region",
        "create a chart of user growth over time", 
        "display revenue trends",
        "show me performance metrics"
    ]
    
    print("🧪 Testing Direct Visualization Connection")
    print("=" * 50)
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n📊 Test {i}: '{query}'")
        print("-" * 30)
        
        payload = {
            "query": query,
            "chart_preferences": {
                "style": "modern",
                "title": f"Test Chart {i}"
            },
            "auto_generate": True,
            "performance_mode": False
        }
        
        try:
            start_time = time.time()
            
            response = requests.post(
                endpoint, 
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            duration = time.time() - start_time
            
            print(f"⏱️  Response time: {duration:.2f}s")
            print(f"📈 Status code: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Success: {result.get('success', 'Unknown')}")
                
                if result.get('success'):
                    data_summary = result.get('data_summary', {})
                    print(f"📊 Data: {data_summary.get('row_count', 0)} rows, {data_summary.get('column_count', 0)} columns")
                    
                    if result.get('chart_config'):
                        chart_type = result['chart_config'].get('type', 'unknown')
                        print(f"📈 Chart type: {chart_type}")
                    
                    print(f"🔧 Session ID: {result.get('session_id', 'N/A')}")
                    
                    performance = result.get('performance_metrics', {})
                    total_time = performance.get('total_time', 0)
                    print(f"⚡ Backend processing: {total_time:.2f}s")
                    
                else:
                    print(f"❌ Backend reported failure: {result.get('error_message', 'Unknown error')}")
            else:
                print(f"❌ HTTP Error: {response.status_code}")
                try:
                    error_detail = response.json()
                    print(f"Error detail: {error_detail}")
                except:
                    print(f"Error text: {response.text}")
                    
        except requests.exceptions.ConnectionError:
            print("❌ Connection failed - is the server running on port 8080?")
        except requests.exceptions.Timeout:
            print("❌ Request timed out after 30 seconds")
        except Exception as e:
            print(f"❌ Unexpected error: {str(e)}")
    
    print("\n" + "=" * 50)
    print("🏁 Direct visualization connection tests completed!")

if __name__ == "__main__":
    test_direct_visualization_endpoint() 
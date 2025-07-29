#!/usr/bin/env python3
"""
Test script to validate real query functionality with session-based visualization retrieval
"""

import requests
import json
import time

def test_real_query_with_visualizations():
    """Test real query execution and visualization retrieval using current session"""
    
    # Session configuration
    session_cookie = "188c6f43-4d24-4be4-a6bc-eb0923bbcc9f"
    base_url = "http://localhost:8787"
    
    headers = {
        'Content-Type': 'application/json',
        'Cookie': f'ceneca_session={session_cookie}'
    }
    
    print("🚀 Testing Real Query with Session-Based Visualizations")
    print("=" * 60)
    print(f"Session Cookie: {session_cookie}")
    print(f"Base URL: {base_url}")
    print()
    
    # Test query for sales analysis
    test_query = "show me the top 10 best selling products with sales analysis"
    
    payload = {
        "question": test_query
    }
    
    print(f"📊 STEP 1: Sending query to LangGraph endpoint")
    print(f"Query: {test_query}")
    print()
    
    try:
        # Send query to LangGraph endpoint
        response = requests.post(
            f"{base_url}/api/langgraph/query",
            headers=headers,
            json=payload,
            timeout=60
        )
        
        print(f"Response Status: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        print()
        
        if response.status_code == 200:
            response_data = response.json()
            print("✅ Query executed successfully!")
            print(f"Session ID: {response_data.get('session_id', 'Not provided')}")
            print(f"Status: {response_data.get('status', 'Unknown')}")
            print()
            
            # Extract session_id for chart retrieval
            query_session_id = response_data.get('session_id')
            if query_session_id:
                print(f"📈 STEP 2: Retrieving charts for session {query_session_id}")
                
                # Test chart retrieval
                chart_response = requests.get(
                    f"{base_url}/api/agent/sessions/{query_session_id}/charts",
                    headers=headers,
                    timeout=30
                )
                
                print(f"Chart Response Status: {chart_response.status_code}")
                
                if chart_response.status_code == 200:
                    chart_data = chart_response.json()
                    charts = chart_data.get('charts', [])
                    
                    print(f"✅ Found {len(charts)} chart(s) for session!")
                    
                    for i, chart in enumerate(charts, 1):
                        metadata = chart.get('metadata', {})
                        chart_summary = chart.get('chart_summary', {})
                        
                        print(f"\n📊 Chart {i}:")
                        print(f"   Type: {chart_summary.get('type', 'unknown')}")
                        print(f"   Title: {chart_summary.get('title', 'No title')}")
                        print(f"   Data Points: {chart_summary.get('data_points', 0)}")
                        print(f"   Generated: {metadata.get('generated_at', 'Unknown')}")
                        print(f"   User Query: {metadata.get('user_query', 'Not provided')}")
                        
                        # Check if chart config is properly structured
                        chart_config = chart.get('chart_config', {})
                        if chart_config:
                            print(f"   ✅ Chart config present with {len(chart_config.get('data', []))} data series")
                        else:
                            print(f"   ❌ No chart config found")
                    
                    if charts:
                        print(f"\n🎯 SUCCESS: Session-based visualization retrieval working correctly!")
                        print(f"   • Query executed with session ID: {query_session_id}")
                        print(f"   • Charts retrieved using session-based lookup")
                        print(f"   • Total charts found: {len(charts)}")
                    else:
                        print(f"\n⚠️  WARNING: No charts found for session {query_session_id}")
                        print(f"   This could mean:")
                        print(f"   • AI didn't select visualization tools")
                        print(f"   • Charts saved to different location")
                        print(f"   • Session ID mismatch")
                
                else:
                    print(f"❌ Chart retrieval failed: {chart_response.status_code}")
                    try:
                        error_data = chart_response.json()
                        print(f"Error details: {json.dumps(error_data, indent=2)}")
                    except:
                        print(f"Error response: {chart_response.text}")
            
            else:
                print("❌ No session_id returned from query")
        
        else:
            print(f"❌ Query failed: {response.status_code}")
            try:
                error_data = response.json()
                print(f"Error details: {json.dumps(error_data, indent=2)}")
            except:
                print(f"Error response: {response.text}")
    
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

if __name__ == "__main__":
    test_real_query_with_visualizations()
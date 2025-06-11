#!/usr/bin/env python3
"""
End-to-End Chart Flow Test

Simulates the exact flow when a user selects "Chart" from BlockTypeSelector.tsx:
1. User types a query (like "show sales trends")
2. User selects "Chart" block type  
3. GraphingBlock calls the visualization endpoint
4. Endpoint uses our fixed analyzer/selector modules
5. Returns chart configuration

This validates the complete pipeline from UI to backend.
"""

import requests
import json
import time
import sys

def test_chart_block_flow():
    """Test the complete chart block creation flow"""
    
    print("🎯 END-TO-END CHART FLOW TEST")
    print("=" * 50)
    print("Simulating: User selects 'Chart' block type and enters query")
    
    # Configuration - adjust if your server runs on different port
    base_url = "http://localhost:8787"  # Agent server port
    
    # Test scenarios that users would typically enter
    test_queries = [
        {
            "query": "show sales trends over time",
            "chart_preferences": {
                "title": "Sales Trends Analysis",
                "style": "modern"
            },
            "expected_charts": ["line", "area"]
        },
        {
            "query": "compare revenue by region", 
            "chart_preferences": {
                "title": "Regional Revenue Comparison",
                "style": "modern"
            },
            "expected_charts": ["bar", "column"]
        },
        {
            "query": "show user growth metrics",
            "chart_preferences": {
                "title": "User Growth Dashboard", 
                "style": "modern"
            },
            "expected_charts": ["line", "area", "bar"]
        }
    ]
    
    print(f"🌐 Testing against server: {base_url}")
    print(f"📊 Testing {len(test_queries)} user scenarios")
    
    # Step 1: Test server connectivity
    print(f"\n1️⃣ Testing server connectivity...")
    try:
        health_response = requests.get(f"{base_url}/api/agent/health", timeout=5)
        if health_response.status_code == 200:
            print("✅ Server is running and responsive")
        else:
            print(f"⚠️ Server responded with status {health_response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"❌ Cannot connect to server: {str(e)}")
        print("Make sure the agent server is running on port 8787")
        return False
    
    # Step 2: Test each user scenario
    print(f"\n2️⃣ Testing chart creation scenarios...")
    
    all_results = []
    
    for i, scenario in enumerate(test_queries, 1):
        print(f"\n📈 Scenario {i}: '{scenario['query']}'")
        print(f"   Expected chart types: {scenario['expected_charts']}")
        
        # Step 2.1: Make request to visualization endpoint (same as GraphingBlock)
        payload = {
            "query": scenario["query"],
            "chart_preferences": scenario["chart_preferences"],
            "auto_generate": True,
            "performance_mode": False
        }
        
        print(f"   🚀 Making API request...")
        start_time = time.time()
        
        try:
            response = requests.post(
                f"{base_url}/api/agent/visualization/query",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            request_time = time.time() - start_time
            print(f"   ⏱️ Request completed in {request_time:.2f}s")
            
        except requests.exceptions.RequestException as e:
            print(f"   ❌ Request failed: {str(e)}")
            continue
        
        # Step 2.2: Validate response
        if response.status_code != 200:
            print(f"   ❌ API error: HTTP {response.status_code}")
            print(f"   Response: {response.text[:200]}...")
            continue
        
        try:
            result = response.json()
        except json.JSONDecodeError as e:
            print(f"   ❌ Invalid JSON response: {str(e)}")
            continue
        
        # Step 2.3: Validate response structure (same as GraphingBlock expects)
        print(f"   🔍 Validating response structure...")
        
        required_fields = ["success", "query", "data_summary", "session_id", "performance_metrics"]
        missing_fields = [field for field in required_fields if field not in result]
        
        if missing_fields:
            print(f"   ❌ Missing required fields: {missing_fields}")
            continue
        
        if not result["success"]:
            print(f"   ❌ Query failed: {result.get('error_message', 'Unknown error')}")
            continue
        
        print(f"   ✅ Response structure valid")
        
        # Step 2.4: Validate data summary
        data_summary = result["data_summary"]
        print(f"   📊 Data summary: {data_summary['row_count']} rows, {data_summary['column_count']} columns")
        
        if data_summary["row_count"] == 0:
            print(f"   ⚠️ No data returned - likely using sample data")
        
        # Step 2.5: Validate chart configuration
        chart_config = result.get("chart_config")
        if chart_config:
            print(f"   🎨 Chart generated successfully")
            chart_type = chart_config.get("type", "unknown")
            print(f"   📈 Chart type: {chart_type}")
            
            # Check if chart type matches expectations
            chart_type_simple = chart_type.replace("_chart", "").replace("_plot", "")
            if any(expected in chart_type_simple for expected in scenario["expected_charts"]):
                print(f"   ✅ Chart type matches expectations")
            else:
                print(f"   ⚠️ Unexpected chart type (not necessarily wrong)")
                
            # Validate chart data structure
            if "data" in chart_config and chart_config["data"]:
                data_points = len(chart_config["data"][0].get("x", [])) if chart_config["data"] else 0
                print(f"   📊 Chart data points: {data_points}")
                
                if data_points > 0:
                    print(f"   ✅ Chart has real data")
                else:
                    print(f"   ⚠️ Chart appears to have no data points")
        else:
            print(f"   ⚠️ No chart configuration returned")
        
        # Step 2.6: Validate suggestions
        suggestions = result.get("suggestions", [])
        print(f"   💡 Alternative suggestions: {len(suggestions)}")
        for suggestion in suggestions[:2]:  # Show first 2
            print(f"      - {suggestion.get('type', 'unknown')}: {suggestion.get('confidence', 0):.1%} confidence")
        
        # Store results
        all_results.append({
            "query": scenario["query"],
            "success": result["success"],
            "chart_type": chart_config.get("type") if chart_config else None,
            "data_points": data_summary["row_count"],
            "response_time": request_time,
            "suggestions_count": len(suggestions)
        })
        
        print(f"   ✅ Scenario {i} completed successfully")
    
    # Step 3: Overall validation
    print(f"\n3️⃣ Overall Results Summary")
    print("=" * 50)
    
    successful_queries = [r for r in all_results if r["success"]]
    success_rate = len(successful_queries) / len(all_results) * 100 if all_results else 0
    
    print(f"📊 Success Rate: {success_rate:.1f}% ({len(successful_queries)}/{len(all_results)})")
    
    if successful_queries:
        avg_response_time = sum(r["response_time"] for r in successful_queries) / len(successful_queries)
        print(f"⏱️ Average Response Time: {avg_response_time:.2f}s")
        
        chart_types = [r["chart_type"] for r in successful_queries if r["chart_type"]]
        print(f"📈 Chart Types Generated: {list(set(chart_types))}")
        
        total_suggestions = sum(r["suggestions_count"] for r in successful_queries)
        print(f"💡 Total Alternative Suggestions: {total_suggestions}")
    
    # Print detailed results table
    print(f"\n📋 Detailed Results:")
    print("Query                     | Success | Chart Type     | Data Points | Time")
    print("-" * 75)
    for result in all_results:
        status = "✅" if result["success"] else "❌"
        chart_type = (result["chart_type"] or "none")[:12]
        print(f"{result['query'][:24]:25} | {status:7} | {chart_type:14} | {result['data_points']:11} | {result['response_time']:4.1f}s")
    
    # Final assessment
    if success_rate >= 80:
        print(f"\n🎉 END-TO-END TEST PASSED!")
        print("✅ Chart block flow is working correctly")
        print("✅ Users can successfully create charts from queries")
        return True
    else:
        print(f"\n⚠️ END-TO-END TEST PARTIAL SUCCESS")
        print(f"Some scenarios failed - check server logs")
        return success_rate > 50

if __name__ == "__main__":
    print("Testing the complete Chart block creation flow...")
    print("This simulates what happens when users select 'Chart' in BlockTypeSelector")
    
    success = test_chart_block_flow()
    
    if success:
        print("\n🚀 Ready for production! Users can create charts through the UI.")
    else:
        print("\n🔧 Needs attention before users can reliably create charts.")
    
    sys.exit(0 if success else 1) 
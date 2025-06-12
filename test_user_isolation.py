#!/usr/bin/env python3
"""
User Isolation Test Script
Test that user data isolation is working correctly across both servers
"""

import requests
import json
import time
import uuid

# Server endpoints - Updated to correct API paths
WEB_SERVER = "http://localhost:8787"  # Both use the same server now
AGENT_SERVER = "http://localhost:8787"

def test_authentication_status():
    """Test authentication status endpoints"""
    print("🔐 Testing Authentication Status...")
    
    # Test web server auth status
    try:
        response = requests.get(f"{WEB_SERVER}/api/auth/status")
        print(f"Web Server Auth Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"  User ID: {data.get('user_id')}")
            print(f"  Authenticated: {data.get('authenticated')}")
        else:
            print(f"  Error: {response.text}")
    except Exception as e:
        print(f"  ❌ Web server error: {e}")
    
    # Test agent server auth status
    try:
        response = requests.get(f"{AGENT_SERVER}/api/agent/auth/status")
        print(f"Agent Server Auth Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"  User ID: {data.get('user_id')}")
            print(f"  Auth Method: {data.get('auth_method')}")
        else:
            print(f"  Error: {response.text}")
    except Exception as e:
        print(f"  ❌ Agent server error: {e}")

def test_user_workspace_isolation():
    """Test that different users see different workspaces"""
    print("\n🏠 Testing Workspace Isolation...")
    
    # Simulate two different users with different session cookies
    user1_session = f"user1_session_{int(time.time())}"
    user2_session = f"user2_session_{int(time.time())}"
    
    users = [
        {"name": "User 1", "session": user1_session},
        {"name": "User 2", "session": user2_session}
    ]
    
    workspaces = {}
    
    for user in users:
        print(f"\n  Testing {user['name']}...")
        
        cookies = {"ceneca_session": user["session"]}
        
        try:
            # Get workspace for this user
            response = requests.get(f"{WEB_SERVER}/api/workspaces/main", cookies=cookies)
            
            if response.status_code == 200:
                workspace_data = response.json()
                workspaces[user["name"]] = workspace_data
                print(f"    ✅ Got workspace: {workspace_data['name']}")
                print(f"    📄 Pages: {len(workspace_data['pages'])}")
            else:
                print(f"    ❌ Failed to get workspace: {response.status_code}")
                
        except Exception as e:
            print(f"    ❌ Error: {e}")
    
    # Verify users have separate workspaces
    if len(workspaces) >= 2:
        user1_pages = len(workspaces["User 1"]["pages"])
        user2_pages = len(workspaces["User 2"]["pages"])
        print(f"\n  📊 Isolation Test: User 1 has {user1_pages} pages, User 2 has {user2_pages} pages")
        
        if user1_pages != user2_pages:
            print("  ✅ Users have different workspace content - isolation working!")
        else:
            print("  ⚠️ Users have same number of pages - might be sharing data")

def test_create_isolated_content():
    """Test creating content for different users"""
    print("\n📝 Testing Content Creation Isolation...")
    
    user1_session = f"test_user1_{int(time.time())}"
    user2_session = f"test_user2_{int(time.time())}"
    
    users = [
        {"name": "TestUser1", "session": user1_session, "page_title": "User 1 Private Page"},
        {"name": "TestUser2", "session": user2_session, "page_title": "User 2 Private Page"}
    ]
    
    created_pages = {}
    
    for user in users:
        print(f"\n  Creating content for {user['name']}...")
        
        cookies = {"ceneca_session": user["session"]}
        
        # Create a test page
        page_id = str(uuid.uuid4())
        page_data = {
            "id": page_id,
            "title": user["page_title"],
            "icon": "📝",
            "blocks": [
                {
                    "id": str(uuid.uuid4()),
                    "type": "text",
                    "content": f"This is private content for {user['name']}",
                    "order": 0,
                    "properties": {}
                }
            ],
            "createdAt": "2024-01-01T00:00:00Z",
            "updatedAt": "2024-01-01T00:00:00Z"
        }
        
        try:
            # Create workspace with the page
            workspace_data = {
                "id": "main",
                "name": "My Workspace",
                "pages": [page_data]
            }
            
            response = requests.post(
                f"{WEB_SERVER}/api/workspaces/main",
                json=workspace_data,
                cookies=cookies
            )
            
            if response.status_code == 200:
                print(f"    ✅ Created page: {user['page_title']}")
                created_pages[user["name"]] = page_id
            else:
                print(f"    ❌ Failed to create page: {response.status_code}")
                
        except Exception as e:
            print(f"    ❌ Error: {e}")
    
    # Test cross-user access (should fail)
    print("\n  🔒 Testing Cross-User Access Prevention...")
    
    if len(created_pages) >= 2:
        user1_page_id = created_pages["TestUser1"]
        user2_session_cookie = {"ceneca_session": f"test_user2_{int(time.time())}"}
        
        try:
            # Try to access User 1's page with User 2's session
            response = requests.get(
                f"{WEB_SERVER}/api/pages/{user1_page_id}",
                cookies=user2_session_cookie
            )
            
            if response.status_code == 404:
                print("    ✅ Cross-user access properly blocked (404)")
            elif response.status_code == 403:
                print("    ✅ Cross-user access properly blocked (403)")
            else:
                print(f"    ❌ Cross-user access not blocked! Status: {response.status_code}")
                
        except Exception as e:
            print(f"    ❌ Error testing cross-user access: {e}")

def test_agent_server_isolation():
    """Test that agent server respects user context"""
    print("\n🤖 Testing Agent Server User Isolation...")
    
    user_session = f"agent_test_{int(time.time())}"
    cookies = {"ceneca_session": user_session}
    
    test_queries = [
        {"question": "Show me my data", "analyze": False},
        {"question": "What are my recent activities?", "analyze": True}
    ]
    
    for query in test_queries:
        try:
            print(f"  Testing query: '{query['question']}'")
            
            response = requests.post(
                f"{AGENT_SERVER}/api/agent/query",
                json=query,
                cookies=cookies,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                data = response.json()
                user_context = data.get("user_context", {})
                if user_context.get("user_id"):
                    print(f"    ✅ Query executed with user context: {user_context['user_id']}")
                else:
                    print("    ⚠️ Query executed but no user context found")
            else:
                print(f"    ❌ Query failed: {response.status_code}")
                
        except Exception as e:
            print(f"    ❌ Error: {e}")

def main():
    """Run all user isolation tests"""
    print("🧪 User Isolation Test Suite")
    print("=" * 50)
    
    try:
        test_authentication_status()
        test_user_workspace_isolation()
        test_create_isolated_content()
        test_agent_server_isolation()
        
        print("\n" + "=" * 50)
        print("✅ User isolation tests completed!")
        print("\n💡 Tips:")
        print("- Check server logs for 🔐 authentication messages")
        print("- Monitor cross-user access attempts (should be 404s)")
        print("- Verify user_context in agent responses")
        
    except KeyboardInterrupt:
        print("\n🛑 Tests interrupted by user")
    except Exception as e:
        print(f"\n❌ Test suite failed: {e}")

if __name__ == "__main__":
    main() 
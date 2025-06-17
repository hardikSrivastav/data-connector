"""
Comprehensive Enterprise Authentication Test

Tests the complete authentication system in enterprise mode with no fallbacks.
This is the ONLY test for authentication - covers everything per singular-tests rule.
"""

import pytest
import asyncio
import tempfile
import os
import time
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import yaml

# Import the authentication system
from server.agent.auth.auth_manager import AuthManager
from server.agent.auth.config import AuthConfig, OIDCConfig
from server.agent.auth.request_auth import get_current_user_strict, get_current_user_optional
from server.agent.auth.endpoints import create_auth_router
from server.agent.auth.session_manager import SessionData


class TestEnterpriseAuthentication:
    """
    Comprehensive test for enterprise authentication system
    
    Tests ALL authentication functionality:
    - Auth manager initialization
    - Strict authentication enforcement  
    - No development fallbacks
    - Proper error handling
    - Router endpoints
    - Session management
    """
    
    @pytest.fixture
    def auth_config_file(self):
        """Create a temporary auth config file for testing"""
        config_data = {
            "sso": {
                "enabled": True,
                "default_protocol": "oidc",
                "oidc": {
                    "provider": "okta",
                    "client_id": "test-client-id",
                    "client_secret": "test-client-secret",
                    "issuer": "https://test.okta.com",
                    "discovery_url": "https://test.okta.com/.well-known/openid_configuration",
                    "redirect_uri": "http://localhost:8787/auth/callback",
                    "scopes": ["openid", "profile", "email"]
                }
            },
            "session_timeout": 3600,
            "role_mappings": {}
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            yield f.name
        
        os.unlink(f.name)
    
    @pytest.fixture
    def disabled_auth_config_file(self):
        """Create a config file with disabled auth"""
        config_data = {
            "sso": {
                "enabled": False,
                "default_protocol": "oidc",
                "oidc": {
                    "provider": "okta",
                    "client_id": "test-client-id", 
                    "client_secret": "test-client-secret",
                    "issuer": "https://test.okta.com",
                    "discovery_url": "https://test.okta.com/.well-known/openid_configuration",
                    "redirect_uri": "http://localhost:8787/auth/callback",
                    "scopes": ["openid", "profile", "email"]
                }
            },
            "session_timeout": 3600,
            "role_mappings": {}
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            yield f.name
            
        os.unlink(f.name)
    
    @pytest.fixture
    def mock_oidc_handler(self):
        """Mock OIDC handler for testing"""
        mock = AsyncMock()
        mock.get_provider_config = AsyncMock(return_value={"issuer": "test"})
        mock.generate_authorization_url = MagicMock(return_value=(
            "https://test.okta.com/oauth2/authorize?client_id=test",
            "test-state",
            "test-verifier"
        ))
        mock.handle_callback = AsyncMock(return_value="test-session-id")
        mock.logout_user = AsyncMock(return_value=True)
        mock.health_check = AsyncMock(return_value={"status": "healthy"})
        mock.cleanup = AsyncMock()
        return mock
    
    @pytest.fixture
    def mock_session_manager(self):
        """Mock session manager for testing"""
        mock = AsyncMock()
        mock.session_timeout = 3600
        mock.use_redis = False
        mock.health_check = AsyncMock(return_value={"status": "healthy"})
        mock.get_active_sessions_count = AsyncMock(return_value=5)
        mock.cleanup_expired_sessions = AsyncMock(return_value=2)
        mock.get_session = AsyncMock(return_value=None)
        mock._store_session = AsyncMock()
        mock.delete_session = AsyncMock()
        return mock
    
    @pytest.fixture
    def valid_session_data(self):
        """Valid session data for testing"""
        now = time.time()
        return SessionData(
            session_id="test-session",
            user_id="test-user-123",
            email="test@example.com",
            name="Test User",
            groups=["users"],
            roles=["admin"],
            provider="okta",
            created_at=now,
            last_accessed=now,
            expires_at=now + 3600
        )
    
    @pytest.mark.asyncio
    async def test_auth_manager_enterprise_mode_initialization(self, auth_config_file, mock_oidc_handler, mock_session_manager):
        """Test auth manager properly initializes in enterprise mode"""
        with patch('server.agent.auth.auth_manager.SessionManager', return_value=mock_session_manager), \
             patch('server.agent.auth.auth_manager.OIDCHandler', return_value=mock_oidc_handler):
            
            auth_manager = AuthManager()
            
            # Should successfully initialize with valid config
            result = await auth_manager.initialize(auth_config_file)
            
            assert result is True
            assert auth_manager.is_initialized
            assert auth_manager.is_enabled
            assert auth_manager.auth_config.enabled
            
            # Verify components were created
            assert auth_manager.session_manager is not None
            assert auth_manager.oidc_handler is not None
            
            # Verify OIDC connectivity was tested
            mock_oidc_handler.get_provider_config.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_auth_manager_rejects_disabled_sso(self, disabled_auth_config_file):
        """Test auth manager rejects disabled SSO in enterprise mode"""
        auth_manager = AuthManager()
        
        # Should raise RuntimeError for disabled SSO
        with pytest.raises(RuntimeError, match="Enterprise deployment requires SSO authentication"):
            await auth_manager.initialize(disabled_auth_config_file)
    
    @pytest.mark.asyncio
    async def test_auth_manager_rejects_missing_config(self):
        """Test auth manager rejects missing config file"""
        auth_manager = AuthManager()
        
        # Should raise RuntimeError for missing config
        with pytest.raises(RuntimeError, match="Enterprise deployment requires auth-config.yaml"):
            await auth_manager.initialize("/nonexistent/config.yaml")
    
    @pytest.mark.asyncio
    async def test_auth_manager_rejects_oidc_connectivity_failure(self, auth_config_file, mock_session_manager):
        """Test auth manager rejects OIDC connectivity failures"""
        # Mock OIDC handler that fails connectivity test
        mock_oidc_handler = AsyncMock()
        mock_oidc_handler.get_provider_config = AsyncMock(side_effect=Exception("Connection failed"))
        
        with patch('server.agent.auth.auth_manager.SessionManager', return_value=mock_session_manager), \
             patch('server.agent.auth.auth_manager.OIDCHandler', return_value=mock_oidc_handler):
            
            auth_manager = AuthManager()
            
            # Should raise RuntimeError for OIDC connectivity failure
            with pytest.raises(RuntimeError, match="Enterprise mode requires working OIDC connectivity"):
                await auth_manager.initialize(auth_config_file)
    
    @pytest.mark.asyncio
    async def test_strict_authentication_requires_valid_session(self, valid_session_data, mock_session_manager):
        """Test strict authentication properly validates sessions"""
        
        # Test case 1: Valid session should succeed
        valid_session_data.is_valid = MagicMock(return_value=True)
        mock_session_manager.get_session.return_value = valid_session_data
        
        with patch('server.agent.auth.request_auth.get_session_manager', return_value=mock_session_manager), \
             patch('server.agent.auth.request_auth.extract_session_id', return_value="valid-session-id"):
            
            # Mock request object
            request = MagicMock()
            request.cookies = {"ceneca_session": "valid-session-id"}
            request.url.path = "/api/test"
            
            # Mock auth manager as initialized and enabled
            with patch('server.agent.auth.request_auth.auth_manager') as mock_auth_manager:
                mock_auth_manager.is_initialized = True
                mock_auth_manager.is_enabled = True
                
                user = await get_current_user_strict(request)
                assert user == valid_session_data
        
        # Test case 2: No session should fail
        mock_session_manager.get_session.return_value = None
        
        with patch('server.agent.auth.request_auth.get_session_manager', return_value=mock_session_manager), \
             patch('server.agent.auth.request_auth.extract_session_id', return_value=None):
            
            request = MagicMock()
            request.cookies = {}
            request.url.path = "/api/test"
            
            with patch('server.agent.auth.request_auth.auth_manager') as mock_auth_manager:
                mock_auth_manager.is_initialized = True
                mock_auth_manager.is_enabled = True
                
                with pytest.raises(HTTPException) as exc_info:
                    await get_current_user_strict(request)
                
                assert exc_info.value.status_code == 401
                assert "Authentication required" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_strict_authentication_rejects_disabled_auth(self):
        """Test strict authentication rejects disabled auth"""
        request = MagicMock()
        request.url.path = "/api/test"
        
        # Mock auth manager as not enabled
        with patch('server.agent.auth.request_auth.auth_manager') as mock_auth_manager:
            mock_auth_manager.is_initialized = True
            mock_auth_manager.is_enabled = False
            
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user_strict(request)
            
            assert exc_info.value.status_code == 503
            assert "enterprise mode requires SSO" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_strict_authentication_rejects_uninitialized_auth(self):
        """Test strict authentication rejects uninitialized auth"""
        request = MagicMock()
        request.url.path = "/api/test"
        
        # Mock auth manager as not initialized
        with patch('server.agent.auth.request_auth.auth_manager') as mock_auth_manager:
            mock_auth_manager.is_initialized = False
            
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user_strict(request)
            
            assert exc_info.value.status_code == 503
            assert "Authentication system not initialized" in exc_info.value.detail
    
    def test_auth_router_creation_requires_enabled_sso(self, mock_oidc_handler, mock_session_manager):
        """Test auth router creation requires enabled SSO"""
        
        # Test with enabled SSO - should succeed
        enabled_config = AuthConfig(
            enabled=True,
            default_protocol="oidc",
            oidc=OIDCConfig(
                provider="okta",
                client_id="test-client-id",
                client_secret="test-client-secret",
                issuer="https://test.okta.com",
                discovery_url="https://test.okta.com/.well-known/openid_configuration",
                redirect_uri="http://localhost:8787/auth/callback",
                scopes=["openid", "profile", "email"],
                claims_mapping={}
            ),
            role_mappings={},
            session_timeout=3600,
            session_secret="test-secret"
        )
        
        router = create_auth_router(enabled_config, mock_oidc_handler, mock_session_manager)
        assert router is not None
        
        # Test with disabled SSO - should fail
        disabled_config = AuthConfig(
            enabled=False,
            default_protocol="oidc",
            oidc=OIDCConfig(
                provider="okta",
                client_id="test-client-id",
                client_secret="test-client-secret",
                issuer="https://test.okta.com",
                discovery_url="https://test.okta.com/.well-known/openid_configuration",
                redirect_uri="http://localhost:8787/auth/callback",
                scopes=["openid", "profile", "email"],
                claims_mapping={}
            ),
            role_mappings={},
            session_timeout=3600,
            session_secret="test-secret"
        )
        
        with pytest.raises(ValueError, match="Enterprise mode requires enabled SSO authentication"):
            create_auth_router(disabled_config, mock_oidc_handler, mock_session_manager)
    
    def test_auth_endpoints_work_with_valid_config(self, auth_config_file, mock_oidc_handler, mock_session_manager, valid_session_data):
        """Test all auth endpoints work with valid configuration"""
        
        # Create a test app with auth router
        config = AuthConfig.load_from_file(auth_config_file)
        router = create_auth_router(config, mock_oidc_handler, mock_session_manager)
        
        app = FastAPI()
        app.include_router(router)
        
        # Mock the dependencies
        def mock_get_current_user_strict():
            return valid_session_data
        
        def mock_require_admin():
            return valid_session_data
        
        app.dependency_overrides[get_current_user_strict] = mock_get_current_user_strict
        
        client = TestClient(app)
        
        # Test health endpoint
        response = client.get("/auth/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["healthy", "degraded"]
        assert data["sso_enabled"] is True
        assert data["mode"] == "enterprise"
        
        # Test login endpoint
        response = client.post("/auth/login")
        assert response.status_code == 200
        data = response.json()
        assert "authorization_url" in data
        assert data["authorization_url"].startswith("https://test.okta.com")
        
        # Test user info endpoint
        response = client.get("/auth/user")
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == "test-user-123"
        assert data["email"] == "test@example.com"
        assert data["authenticated"] is True
        
        # Test logout endpoint
        response = client.post("/auth/logout")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
    
    def test_auth_callback_handles_oauth_errors(self, auth_config_file, mock_oidc_handler, mock_session_manager):
        """Test auth callback properly handles OAuth errors"""
        
        config = AuthConfig.load_from_file(auth_config_file)
        router = create_auth_router(config, mock_oidc_handler, mock_session_manager)
        
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        
        # Test OAuth error response
        response = client.get("/auth/callback?error=access_denied&error_description=User%20denied%20access")
        assert response.status_code == 302
        assert "auth_error=access_denied" in response.headers["location"]
        
        # Test missing parameters
        response = client.get("/auth/callback")
        assert response.status_code == 302
        assert "auth_error=invalid_request" in response.headers["location"]
    
    @pytest.mark.asyncio
    async def test_no_development_fallbacks_exist(self):
        """Test that no development fallbacks exist anywhere in the system"""
        
        # This test ensures we don't accidentally introduce dev fallbacks
        
        # Check auth manager doesn't allow uninitialized state to work
        auth_manager = AuthManager()
        assert not auth_manager.is_enabled  # Should be False when not initialized
        
        # Check that routers can't be created without proper config
        with pytest.raises((RuntimeError, ValueError)):
            auth_manager.create_auth_router()
            
        with pytest.raises((RuntimeError, ValueError)):
            auth_manager.create_middleware(MagicMock())
    
    @pytest.mark.asyncio
    async def test_session_update_and_cleanup(self, valid_session_data, mock_session_manager):
        """Test session management works correctly"""
        
        # Mock valid session with proper update behavior
        valid_session_data.is_valid = MagicMock(return_value=True)
        valid_session_data.update_last_accessed = MagicMock()
        mock_session_manager.get_session.return_value = valid_session_data
        
        with patch('server.agent.auth.request_auth.get_session_manager', return_value=mock_session_manager), \
             patch('server.agent.auth.request_auth.extract_session_id', return_value="valid-session-id"):
            
            request = MagicMock()
            request.cookies = {"ceneca_session": "valid-session-id"}
            
            session_data = await get_current_user_optional(request)
            
            assert session_data == valid_session_data
            # Verify session was updated
            valid_session_data.update_last_accessed.assert_called_once()
            mock_session_manager._store_session.assert_called_once_with("valid-session-id", valid_session_data)
    
    @pytest.mark.asyncio
    async def test_comprehensive_error_handling(self, auth_config_file, mock_session_manager):
        """Test comprehensive error handling throughout the system"""
        
        # Test auth manager handles various initialization failures
        auth_manager = AuthManager()
        
        # Test OIDC handler creation failure
        with patch('server.agent.auth.auth_manager.OIDCHandler', side_effect=Exception("OIDC creation failed")):
            with pytest.raises(RuntimeError, match="Enterprise authentication initialization failed"):
                await auth_manager.initialize(auth_config_file)
        
        # Test session manager handles get_session_manager failure
        with patch('server.agent.auth.request_auth.auth_manager.session_manager', None):
            request = MagicMock()
            
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user_optional(request)
            
            assert exc_info.value.status_code == 503
            assert "Authentication system not properly configured" in exc_info.value.detail
    
    def test_health_check_comprehensive(self, auth_config_file, mock_oidc_handler, mock_session_manager):
        """Test comprehensive health check functionality"""
        
        config = AuthConfig.load_from_file(auth_config_file)
        router = create_auth_router(config, mock_oidc_handler, mock_session_manager)
        
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        
        # Test healthy system
        response = client.get("/auth/health")
        assert response.status_code == 200
        data = response.json()
        assert data["mode"] == "enterprise"
        assert data["sso_enabled"] is True
        assert data["provider"] == "okta"
        
        # Test degraded system (OIDC issues)
        mock_oidc_handler.health_check.return_value = {"status": "error", "error": "Connection failed"}
        
        response = client.get("/auth/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert "OIDC handler issue" in data["message"]
    
    def run_all_tests(self):
        """
        Run all tests in this comprehensive suite
        
        This ensures all enterprise authentication functionality is tested in one place
        following the singular-tests rule.
        """
        # This would be called by pytest, but documents that this is the 
        # single comprehensive test for authentication
        pass


# Test configuration and fixtures
@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 
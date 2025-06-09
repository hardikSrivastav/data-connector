"""
OIDC/OAuth2 authentication handler for Ceneca Agent Server

Handles the complete OAuth2 authorization code flow with Okta.
All token handling is done server-side for maximum security.
"""

import json
import time
import uuid
import base64
import hashlib
import secrets
import logging
from typing import Dict, Optional, Any, List, Tuple
from urllib.parse import urlencode, parse_qs, urlparse
import asyncio

# HTTP client imports
import httpx

from .config import AuthConfig, OIDCConfig
from .session_manager import SessionManager

logger = logging.getLogger(__name__)

class OIDCHandler:
    """
    Handles OIDC/OAuth2 authentication flow with enterprise identity providers
    """
    
    def __init__(self, auth_config: AuthConfig, session_manager: SessionManager):
        """
        Initialize OIDC handler
        
        Args:
            auth_config: Authentication configuration
            session_manager: Session manager instance
        """
        self.auth_config = auth_config
        self.oidc_config = auth_config.get_oidc_config()
        self.session_manager = session_manager
        
        # OIDC provider configuration (cached)
        self._provider_config: Optional[Dict[str, Any]] = None
        self._jwks: Optional[Dict[str, Any]] = None
        
        # PKCE state storage (for extra security)
        self._pkce_verifiers: Dict[str, str] = {}
        
        # HTTP client for OIDC operations
        self._http_client = httpx.AsyncClient(timeout=30.0)
        
        logger.info(f"Initialized OIDC handler for provider: {self.oidc_config.provider}")
    
    async def get_provider_config(self) -> Dict[str, Any]:
        """
        Get OIDC provider configuration from discovery endpoint
        
        Returns:
            Provider configuration dictionary
        """
        if self._provider_config is None:
            try:
                logger.info(f"Fetching OIDC discovery config from: {self.oidc_config.discovery_url}")
                
                response = await self._http_client.get(self.oidc_config.discovery_url)
                response.raise_for_status()
                
                self._provider_config = response.json()
                
                logger.info("Successfully loaded OIDC provider configuration")
                logger.debug(f"Provider endpoints: {list(self._provider_config.keys())}")
                
            except Exception as e:
                logger.error(f"Failed to fetch OIDC provider configuration: {e}")
                raise RuntimeError(f"Cannot fetch OIDC provider config: {e}")
        
        return self._provider_config
    
    async def get_jwks(self) -> Dict[str, Any]:
        """
        Get JSON Web Key Set (JWKS) for token validation
        
        Returns:
            JWKS dictionary
        """
        if self._jwks is None:
            provider_config = await self.get_provider_config()
            jwks_uri = provider_config.get('jwks_uri')
            
            if not jwks_uri:
                raise RuntimeError("No jwks_uri found in provider configuration")
            
            try:
                logger.info(f"Fetching JWKS from: {jwks_uri}")
                
                response = await self._http_client.get(jwks_uri)
                response.raise_for_status()
                
                self._jwks = response.json()
                
                logger.info("Successfully loaded JWKS")
                
            except Exception as e:
                logger.error(f"Failed to fetch JWKS: {e}")
                raise RuntimeError(f"Cannot fetch JWKS: {e}")
        
        return self._jwks
    
    def generate_authorization_url(self, state: Optional[str] = None) -> Tuple[str, str, str]:
        """
        Generate authorization URL for OIDC login
        
        Args:
            state: Optional state parameter for CSRF protection
            
        Returns:
            Tuple of (authorization_url, state, code_verifier)
        """
        if state is None:
            state = secrets.token_urlsafe(32)
        
        # Generate PKCE code verifier and challenge for additional security
        code_verifier = secrets.token_urlsafe(96)  # 128 characters, base64url
        code_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode()).digest()
        ).decode().rstrip('=')
        
        # Store code verifier for later verification
        self._pkce_verifiers[state] = code_verifier
        
        # Build authorization parameters
        auth_params = {
            'response_type': 'code',
            'client_id': self.oidc_config.client_id,
            'redirect_uri': self.oidc_config.redirect_uri,
            'scope': ' '.join(self.oidc_config.scopes),
            'state': state,
            'code_challenge': code_challenge,
            'code_challenge_method': 'S256',
            'nonce': secrets.token_urlsafe(32)  # Additional security
        }
        
        # Build full authorization URL
        auth_url = f"{self.oidc_config.issuer}/oauth2/v1/authorize?{urlencode(auth_params)}"
        
        logger.info(f"Generated authorization URL for state: {state[:8]}...")
        
        return auth_url, state, code_verifier
    
    async def handle_callback(self, code: str, state: str) -> str:
        """
        Handle OIDC callback and create user session
        
        Args:
            code: Authorization code from callback
            state: State parameter for CSRF protection
            
        Returns:
            Session ID for the authenticated user
            
        Raises:
            ValueError: If callback parameters are invalid
            RuntimeError: If token exchange or validation fails
        """
        logger.info(f"Handling OIDC callback for state: {state[:8]}...")
        
        # Verify state and get PKCE verifier
        if state not in self._pkce_verifiers:
            raise ValueError("Invalid or expired state parameter")
        
        code_verifier = self._pkce_verifiers.pop(state)
        
        try:
            # Exchange authorization code for tokens
            tokens = await self._exchange_code_for_tokens(code, code_verifier)
            
            # Validate and parse ID token
            user_info = await self._validate_and_parse_id_token(tokens['id_token'])
            
            # Get additional user info if needed
            if 'access_token' in tokens:
                additional_user_info = await self._get_user_info(tokens['access_token'])
                user_info.update(additional_user_info)
            
            # Extract user details
            user_id = user_info.get('sub')
            email = user_info.get(self.oidc_config.claims_mapping.get('email', 'email'))
            name = user_info.get(self.oidc_config.claims_mapping.get('name', 'name'))
            groups = user_info.get(self.oidc_config.claims_mapping.get('groups', 'groups'), [])
            
            if not user_id or not email:
                raise RuntimeError("Missing required user information (sub, email)")
            
            # Map groups to roles
            roles = self.auth_config.map_groups_to_roles(groups)
            
            # Create session
            session_id = await self.session_manager.create_session(
                user_id=user_id,
                email=email,
                name=name or email,
                groups=groups,
                roles=roles,
                provider=self.oidc_config.provider
            )
            
            logger.info(f"Successfully authenticated user: {email}")
            logger.info(f"User groups: {groups}")
            logger.info(f"Mapped roles: {roles}")
            
            return session_id
            
        except Exception as e:
            logger.error(f"OIDC callback failed: {e}")
            raise RuntimeError(f"Authentication failed: {e}")
    
    async def _exchange_code_for_tokens(self, code: str, code_verifier: str) -> Dict[str, str]:
        """
        Exchange authorization code for access and ID tokens
        
        Args:
            code: Authorization code
            code_verifier: PKCE code verifier
            
        Returns:
            Dictionary containing tokens
        """
        provider_config = await self.get_provider_config()
        token_endpoint = provider_config.get('token_endpoint')
        
        if not token_endpoint:
            raise RuntimeError("No token_endpoint found in provider configuration")
        
        # Prepare token request
        token_data = {
            'grant_type': 'authorization_code',
            'client_id': self.oidc_config.client_id,
            'client_secret': self.oidc_config.client_secret,
            'code': code,
            'redirect_uri': self.oidc_config.redirect_uri,
            'code_verifier': code_verifier
        }
        
        logger.info(f"Exchanging code for tokens at: {token_endpoint}")
        
        try:
            response = await self._http_client.post(
                token_endpoint,
                data=token_data,
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            )
            
            response.raise_for_status()
            tokens = response.json()
            
            if 'error' in tokens:
                raise RuntimeError(f"Token exchange error: {tokens.get('error_description', tokens['error'])}")
            
            logger.info("Successfully exchanged code for tokens")
            return tokens
            
        except httpx.HTTPStatusError as e:
            logger.error(f"Token exchange HTTP error: {e.response.status_code} - {e.response.text}")
            raise RuntimeError(f"Token exchange failed: HTTP {e.response.status_code}")
        except Exception as e:
            logger.error(f"Token exchange failed: {e}")
            raise RuntimeError(f"Token exchange failed: {e}")
    
    async def _validate_and_parse_id_token(self, id_token: str) -> Dict[str, Any]:
        """
        Validate and parse JWT ID token
        
        Args:
            id_token: JWT ID token
            
        Returns:
            Parsed token claims
        """
        try:
            # For production, you would validate the JWT signature using JWKS
            # For now, we'll do basic parsing and validation
            
            # Split JWT token
            parts = id_token.split('.')
            if len(parts) != 3:
                raise ValueError("Invalid JWT token format")
            
            # Decode header and payload (without signature verification for now)
            header = json.loads(base64.urlsafe_b64decode(parts[0] + '=='))
            payload = json.loads(base64.urlsafe_b64decode(parts[1] + '=='))
            
            # Basic validation
            current_time = time.time()
            
            # Check expiration
            if payload.get('exp', 0) < current_time:
                raise ValueError("ID token has expired")
            
            # Check not before
            if payload.get('nbf', 0) > current_time:
                raise ValueError("ID token not yet valid")
            
            # Check issuer
            if payload.get('iss') != self.oidc_config.issuer:
                raise ValueError(f"Invalid issuer: {payload.get('iss')}")
            
            # Check audience
            if payload.get('aud') != self.oidc_config.client_id:
                raise ValueError(f"Invalid audience: {payload.get('aud')}")
            
            logger.info("ID token validation successful")
            logger.debug(f"Token claims: {list(payload.keys())}")
            
            return payload
            
        except Exception as e:
            logger.error(f"ID token validation failed: {e}")
            raise RuntimeError(f"Invalid ID token: {e}")
    
    async def _get_user_info(self, access_token: str) -> Dict[str, Any]:
        """
        Get additional user information using access token
        
        Args:
            access_token: OAuth2 access token
            
        Returns:
            Additional user information
        """
        provider_config = await self.get_provider_config()
        userinfo_endpoint = provider_config.get('userinfo_endpoint')
        
        if not userinfo_endpoint:
            logger.info("No userinfo endpoint available")
            return {}
        
        try:
            logger.info("Fetching additional user info")
            
            response = await self._http_client.get(
                userinfo_endpoint,
                headers={'Authorization': f'Bearer {access_token}'}
            )
            
            response.raise_for_status()
            user_info = response.json()
            
            logger.info("Successfully fetched additional user info")
            return user_info
            
        except Exception as e:
            logger.warning(f"Failed to fetch user info: {e}")
            return {}
    
    async def logout_user(self, session_id: str) -> bool:
        """
        Logout user and clean up session
        
        Args:
            session_id: User session ID
            
        Returns:
            True if logout successful
        """
        try:
            # Delete session
            success = await self.session_manager.delete_session(session_id)
            
            if success:
                logger.info(f"User session logged out: {session_id[:8]}...")
            
            return success
            
        except Exception as e:
            logger.error(f"Logout failed: {e}")
            return False
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Health check for OIDC handler
        
        Returns:
            Health status information
        """
        status = {
            "provider": self.oidc_config.provider,
            "issuer": self.oidc_config.issuer,
            "client_id": self.oidc_config.client_id,
            "scopes": self.oidc_config.scopes
        }
        
        try:
            # Test provider discovery
            provider_config = await self.get_provider_config()
            status["provider_config_loaded"] = True
            status["provider_endpoints"] = list(provider_config.keys())
            
            # Test JWKS
            jwks = await self.get_jwks()
            status["jwks_loaded"] = True
            status["jwks_keys_count"] = len(jwks.get('keys', []))
            
            status["status"] = "healthy"
            
        except Exception as e:
            status["status"] = "error"
            status["error"] = str(e)
        
        return status
    
    async def cleanup(self) -> None:
        """Clean up resources"""
        await self._http_client.aclose()
        self._pkce_verifiers.clear() 
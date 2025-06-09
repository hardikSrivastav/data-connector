"""
Authentication configuration loader for Ceneca Agent Server

Loads and validates authentication settings from auth-config.yaml
"""

import os
import yaml
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class OIDCConfig:
    """OIDC/OAuth2 configuration"""
    provider: str
    client_id: str
    client_secret: str
    issuer: str
    discovery_url: str
    redirect_uri: str
    scopes: List[str]
    claims_mapping: Dict[str, str]

@dataclass
class AuthConfig:
    """Main authentication configuration"""
    enabled: bool
    default_protocol: str
    oidc: OIDCConfig
    role_mappings: Dict[str, str]
    
    # Session configuration
    session_timeout: int = 3600  # 1 hour default
    session_secret: str = ""  # Will be generated if empty
    
    @classmethod
    def load_from_file(cls, config_path: Optional[str] = None) -> 'AuthConfig':
        """
        Load authentication configuration from YAML file
        
        Args:
            config_path: Path to auth-config.yaml file. If None, uses default locations.
            
        Returns:
            AuthConfig instance
            
        Raises:
            FileNotFoundError: If config file is not found
            ValueError: If config is invalid
        """
        if config_path is None:
            # Try default locations
            possible_paths = [
                Path.home() / ".data-connector" / "auth-config.yaml",
                Path.cwd() / "auth-config.yaml",
                Path.cwd() / "config" / "auth-config.yaml"
            ]
            
            config_path = None
            for path in possible_paths:
                if path.exists():
                    config_path = str(path)
                    break
                    
            if not config_path:
                raise FileNotFoundError(
                    f"auth-config.yaml not found in any of: {[str(p) for p in possible_paths]}"
                )
        
        logger.info(f"Loading auth config from: {config_path}")
        
        try:
            with open(config_path, 'r') as f:
                config_data = yaml.safe_load(f)
        except Exception as e:
            raise ValueError(f"Failed to load auth config: {e}")
            
        return cls._from_dict(config_data)
    
    @classmethod
    def _from_dict(cls, config_data: Dict[str, Any]) -> 'AuthConfig':
        """Create AuthConfig from dictionary"""
        try:
            sso_config = config_data.get('sso', {})
            
            # OIDC configuration
            oidc_data = sso_config.get('oidc', {})
            oidc_config = OIDCConfig(
                provider=oidc_data.get('provider', ''),
                client_id=oidc_data.get('client_id', ''),
                client_secret=oidc_data.get('client_secret', ''),
                issuer=oidc_data.get('issuer', ''),
                discovery_url=oidc_data.get('discovery_url', ''),
                redirect_uri=oidc_data.get('redirect_uri', ''),
                scopes=oidc_data.get('scopes', ['openid', 'email', 'profile']),
                claims_mapping=oidc_data.get('claims_mapping', {})
            )
            
            # Validate required OIDC fields
            required_fields = ['client_id', 'client_secret', 'issuer', 'redirect_uri']
            for field in required_fields:
                if not getattr(oidc_config, field):
                    raise ValueError(f"Missing required OIDC field: {field}")
            
            # Generate session secret if not provided
            session_secret = os.environ.get('CENECA_SESSION_SECRET', '')
            if not session_secret:
                import secrets
                session_secret = secrets.token_urlsafe(32)
                logger.warning("Generated random session secret. For production, set CENECA_SESSION_SECRET environment variable.")
            
            return cls(
                enabled=sso_config.get('enabled', False),
                default_protocol=sso_config.get('default_protocol', 'oidc'),
                oidc=oidc_config,
                role_mappings=config_data.get('role_mappings', {}),
                session_timeout=int(os.environ.get('CENECA_SESSION_TIMEOUT', 3600)),
                session_secret=session_secret
            )
            
        except Exception as e:
            raise ValueError(f"Invalid auth configuration: {e}")
    
    def validate(self) -> None:
        """Validate the configuration"""
        if self.enabled:
            if self.default_protocol == 'oidc':
                if not self.oidc.client_id or not self.oidc.client_secret:
                    raise ValueError("OIDC client_id and client_secret are required when SSO is enabled")
                    
                if not self.oidc.issuer:
                    raise ValueError("OIDC issuer is required when SSO is enabled")
                    
                if not self.oidc.redirect_uri:
                    raise ValueError("OIDC redirect_uri is required when SSO is enabled")
    
    def get_oidc_config(self) -> OIDCConfig:
        """Get OIDC configuration"""
        return self.oidc
    
    def map_groups_to_roles(self, groups: List[str]) -> List[str]:
        """
        Map IdP groups to Ceneca roles
        
        Args:
            groups: List of groups from the identity provider
            
        Returns:
            List of Ceneca roles
        """
        roles = []
        for group in groups:
            if group in self.role_mappings:
                role = self.role_mappings[group]
                if role not in roles:
                    roles.append(role)
        
        # Default role if no mappings found
        if not roles:
            roles.append('user')
            
        return roles 
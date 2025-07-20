import os
import json
import hashlib
import yaml
import shutil
from typing import Dict, List, Optional, Union
from datetime import datetime
from pathlib import Path

class TemplateManager:
    def __init__(self):
        self.templates_dir = Path("templates")
        self.templates_dir.mkdir(exist_ok=True)
        
        # Initialize default templates if they don't exist
        self._create_default_templates()
        self._create_deployment_templates()
    
    def _create_default_templates(self):
        """Create default auth templates if they don't exist"""
        auth_v1_dir = self.templates_dir / "auth-v1.0.0"
        auth_v1_dir.mkdir(exist_ok=True)
        
        # Create auth.config.template
        auth_config_template = '''// Authentication Configuration
export const authConfig = {
  method: "{{AUTH_METHOD}}", // jwt, oauth, local
  secret: "{{SECRET_KEY}}",
  algorithm: "{{ALGORITHM}}", // HS256, RS256
  expiresIn: "{{EXPIRES_IN}}", // 24h, 7d, 30d
  
  // OAuth Configuration (if method includes oauth)
  oauth: {
    providers: {{OAUTH_PROVIDERS}}, // ["google", "github", "auth0"]
    redirectUrl: "{{REDIRECT_URL}}",
    clientId: "{{CLIENT_ID}}",
    clientSecret: "{{CLIENT_SECRET}}"
  },
  
  // Local Authentication (if method includes local)
  local: {
    usernameField: "{{USERNAME_FIELD}}", // email, username
    passwordField: "{{PASSWORD_FIELD}}", // password
    hashRounds: {{HASH_ROUNDS}} // 10, 12, 15
  },
  
  // Session Configuration
  session: {
    name: "{{SESSION_NAME}}",
    secure: {{SECURE_COOKIES}}, // true, false
    httpOnly: {{HTTP_ONLY}}, // true, false
    sameSite: "{{SAME_SITE}}" // strict, lax, none
  }
};
'''
        
        # Create .env.template
        env_template = '''# Authentication Environment Variables
AUTH_METHOD={{AUTH_METHOD}}
SECRET_KEY={{SECRET_KEY}}
ALGORITHM={{ALGORITHM}}
EXPIRES_IN={{EXPIRES_IN}}

# OAuth Configuration
OAUTH_CLIENT_ID={{CLIENT_ID}}
OAUTH_CLIENT_SECRET={{CLIENT_SECRET}}
OAUTH_REDIRECT_URL={{REDIRECT_URL}}

# Database Configuration
DATABASE_URL={{DATABASE_URL}}

# Session Configuration
SESSION_NAME={{SESSION_NAME}}
SECURE_COOKIES={{SECURE_COOKIES}}
HTTP_ONLY={{HTTP_ONLY}}
SAME_SITE={{SAME_SITE}}
'''
        
        # Create auth.middleware.template
        middleware_template = '''// Authentication Middleware
import jwt from 'jsonwebtoken';
import bcrypt from 'bcryptjs';
import { authConfig } from './auth.config.js';

export class AuthMiddleware {
  
  // JWT Token Generation
  generateToken(payload) {
    return jwt.sign(payload, authConfig.secret, {
      algorithm: authConfig.algorithm,
      expiresIn: authConfig.expiresIn
    });
  }
  
  // JWT Token Verification
  verifyToken(token) {
    try {
      return jwt.verify(token, authConfig.secret, {
        algorithms: [authConfig.algorithm]
      });
    } catch (error) {
      throw new Error('Invalid token');
    }
  }
  
  // Password Hashing (for local auth)
  async hashPassword(password) {
    return bcrypt.hash(password, authConfig.local.hashRounds);
  }
  
  // Password Verification (for local auth)
  async verifyPassword(password, hashedPassword) {
    return bcrypt.compare(password, hashedPassword);
  }
  
  // Express Middleware Function
  authenticate(req, res, next) {
    const token = req.headers.authorization?.split(' ')[1];
    
    if (!token) {
      return res.status(401).json({ error: 'No token provided' });
    }
    
    try {
      const decoded = this.verifyToken(token);
      req.user = decoded;
      next();
    } catch (error) {
      res.status(401).json({ error: 'Invalid token' });
    }
  }
  
  // OAuth Handler (if using OAuth)
  async handleOAuthCallback(provider, code) {
    // Implementation depends on {{AUTH_METHOD}} and {{OAUTH_PROVIDERS}}
    // This is a placeholder for OAuth integration
    throw new Error('OAuth integration not implemented');
  }
}

export default new AuthMiddleware();
'''
        
        # Write template files
        template_files = {
            "auth.config.template": auth_config_template,
            ".env.template": env_template,
            "auth.middleware.template": middleware_template
        }
        
        for filename, content in template_files.items():
            file_path = auth_v1_dir / filename
            if not file_path.exists():
                with open(file_path, 'w') as f:
                    f.write(content)
        
        # Create metadata file
        metadata_file = auth_v1_dir / "metadata.json"
        if not metadata_file.exists():
            metadata = {
                "version": "auth-v1.0.0",
                "name": "Basic Auth Template",
                "description": "Basic authentication template with JWT, OAuth, and local auth support",
                "hash": self._calculate_template_hash("auth-v1.0.0"),
                "created_at": datetime.utcnow().isoformat(),
                "schema": {
                    "type": "object",
                    "required": ["AUTH_METHOD", "SECRET_KEY"],
                    "properties": {
                        "AUTH_METHOD": {"type": "string", "enum": ["jwt", "oauth", "local", "jwt+oauth", "jwt+local"]},
                        "SECRET_KEY": {"type": "string", "minLength": 32},
                        "ALGORITHM": {"type": "string", "enum": ["HS256", "RS256"], "default": "HS256"},
                        "EXPIRES_IN": {"type": "string", "default": "24h"},
                        "OAUTH_PROVIDERS": {"type": "array", "items": {"type": "string"}},
                        "USERNAME_FIELD": {"type": "string", "default": "email"},
                        "PASSWORD_FIELD": {"type": "string", "default": "password"},
                        "HASH_ROUNDS": {"type": "integer", "default": 12, "minimum": 10, "maximum": 15}
                    }
                }
            }
            
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
    
    def _calculate_template_hash(self, version: str) -> str:
        """Calculate hash of all template files"""
        template_dir = self.templates_dir / version
        hash_obj = hashlib.sha256()
        
        for file_path in sorted(template_dir.glob("*.template")):
            with open(file_path, 'rb') as f:
                hash_obj.update(f.read())
        
        return hash_obj.hexdigest()
    
    def list_templates(self) -> List[Dict]:
        """List all available template versions"""
        templates = []
        
        for version_dir in self.templates_dir.iterdir():
            if version_dir.is_dir():
                metadata_file = version_dir / "metadata.json"
                if metadata_file.exists():
                    with open(metadata_file, 'r') as f:
                        metadata = json.load(f)
                        templates.append({
                            "version": metadata["version"],
                            "name": metadata["name"],
                            "description": metadata.get("description"),
                            "hash": metadata["hash"],
                            "schema": metadata.get("schema"),
                            "created_at": datetime.fromisoformat(metadata["created_at"]),
                            "category": metadata.get("category"),
                            "format": metadata.get("format")
                        })
        
        return sorted(templates, key=lambda x: x["created_at"], reverse=True)
    
    def get_template_info(self, version: str) -> Optional[Dict]:
        """Get template metadata"""
        template_dir = self.templates_dir / version
        metadata_file = template_dir / "metadata.json"
        
        if not metadata_file.exists():
            return None
        
        with open(metadata_file, 'r') as f:
            metadata = json.load(f)
            return {
                "version": metadata["version"],
                "name": metadata["name"],
                "description": metadata.get("description"),
                "hash": metadata["hash"],
                "schema": metadata.get("schema"),
                "created_at": datetime.fromisoformat(metadata["created_at"]),
                "category": metadata.get("category"),
                "format": metadata.get("format")
            }
    
    def get_template_files(self, version: str) -> Optional[List[Dict]]:
        """Get template files content"""
        template_dir = self.templates_dir / version
        
        if not template_dir.exists():
            return None
        
        files = []
        for file_path in template_dir.glob("*.template"):
            with open(file_path, 'r') as f:
                content = f.read()
                files.append({
                    "path": file_path.name,
                    "content": content,
                    "hash": hashlib.sha256(content.encode()).hexdigest()
                })
        
        return files
    
    def get_template_schema(self, version: str) -> Optional[Dict]:
        """Get template validation schema"""
        template_info = self.get_template_info(version)
        return template_info.get("schema") if template_info else None
    
    def _create_deployment_templates(self):
        """Create deployment templates from deploy-reference files"""
        deploy_reference_dir = Path("../deploy-reference")
        if not deploy_reference_dir.exists():
            return
        
        # Create deployment template versions
        self._create_ceneca_deployment_template()
        self._create_enterprise_deployment_template()
        self._create_auth_config_template()
        self._create_nginx_template()
        self._create_config_yaml_template()
    
    def _create_ceneca_deployment_template(self):
        """Create basic Ceneca deployment template"""
        template_dir = self.templates_dir / "ceneca-deployment-v1.0.0"
        template_dir.mkdir(exist_ok=True)
        
        # Copy and read the ceneca-docker-compose.yml file
        source_file = Path("../deploy-reference/ceneca-docker-compose.yml")
        if source_file.exists():
            with open(source_file, 'r') as f:
                compose_content = f.read()
            
            # Write as template
            template_file = template_dir / "docker-compose.yml.template"
            with open(template_file, 'w') as f:
                f.write(compose_content)
        
        # Create metadata
        metadata_file = template_dir / "metadata.json"
        if not metadata_file.exists():
            metadata = {
                "version": "ceneca-deployment-v1.0.0",
                "name": "Ceneca Basic Deployment",
                "description": "Basic Ceneca deployment with Docker Compose for development environments",
                "category": "deployment",
                "format": "docker-compose",
                "hash": self._calculate_template_hash("ceneca-deployment-v1.0.0"),
                "created_at": datetime.utcnow().isoformat(),
                "schema": {
                    "type": "object",
                    "required": ["LLM_API_KEY_VALUE", "POSTGRES_HOST", "MONGODB_HOST"],
                    "properties": {
                        "LLM_API_KEY_VALUE": {"type": "string", "description": "API key for LLM service"},
                        "POSTGRES_HOST": {"type": "string", "description": "PostgreSQL hostname"},
                        "POSTGRES_HOST_IP": {"type": "string", "description": "PostgreSQL IP address"},
                        "MONGODB_HOST": {"type": "string", "description": "MongoDB hostname"},
                        "MONGODB_HOST_IP": {"type": "string", "description": "MongoDB IP address"},
                        "QDRANT_HOST": {"type": "string", "description": "Qdrant hostname"},
                        "QDRANT_HOST_IP": {"type": "string", "description": "Qdrant IP address"}
                    }
                }
            }
            
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
    
    def _create_enterprise_deployment_template(self):
        """Create enterprise deployment template with NGINX"""
        template_dir = self.templates_dir / "enterprise-deployment-v1.0.0"
        template_dir.mkdir(exist_ok=True)
        
        # Copy enterprise-docker-compose.yml
        source_file = Path("../deploy-reference/enterprise-docker-compose.yml")
        if source_file.exists():
            with open(source_file, 'r') as f:
                compose_content = f.read()
            
            template_file = template_dir / "docker-compose.yml.template"
            with open(template_file, 'w') as f:
                f.write(compose_content)
        
        # Create metadata
        metadata_file = template_dir / "metadata.json"
        if not metadata_file.exists():
            metadata = {
                "version": "enterprise-deployment-v1.0.0",
                "name": "Ceneca Enterprise Deployment",
                "description": "Enterprise Ceneca deployment with NGINX reverse proxy and SSL support",
                "category": "deployment",
                "format": "docker-compose",
                "hash": self._calculate_template_hash("enterprise-deployment-v1.0.0"),
                "created_at": datetime.utcnow().isoformat(),
                "schema": {
                    "type": "object",
                    "required": ["LLM_API_KEY_VALUE", "POSTGRES_HOST", "MONGODB_HOST"],
                    "properties": {
                        "LLM_API_KEY_VALUE": {"type": "string", "description": "API key for LLM service"},
                        "POSTGRES_HOST": {"type": "string", "description": "PostgreSQL hostname"},
                        "POSTGRES_HOST_IP": {"type": "string", "description": "PostgreSQL IP address"},
                        "MONGODB_HOST": {"type": "string", "description": "MongoDB hostname"},
                        "MONGODB_HOST_IP": {"type": "string", "description": "MongoDB IP address"},
                        "QDRANT_HOST": {"type": "string", "description": "Qdrant hostname"},
                        "QDRANT_HOST_IP": {"type": "string", "description": "Qdrant IP address"}
                    }
                }
            }
            
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
    
    def _create_auth_config_template(self):
        """Create OIDC auth configuration template"""
        template_dir = self.templates_dir / "oidc-auth-v1.0.0"
        template_dir.mkdir(exist_ok=True)
        
        # Copy auth-config.yaml.template
        source_file = Path("../deploy-reference/auth-config.yaml.template")
        if source_file.exists():
            with open(source_file, 'r') as f:
                auth_content = f.read()
            
            template_file = template_dir / "auth-config.yaml.template"
            with open(template_file, 'w') as f:
                f.write(auth_content)
        
        # Create metadata
        metadata_file = template_dir / "metadata.json"
        if not metadata_file.exists():
            metadata = {
                "version": "oidc-auth-v1.0.0",
                "name": "OIDC Authentication Configuration",
                "description": "OIDC/SSO authentication configuration for enterprise identity providers",
                "category": "authentication",
                "format": "yaml",
                "hash": self._calculate_template_hash("oidc-auth-v1.0.0"),
                "created_at": datetime.utcnow().isoformat(),
                "schema": {
                    "type": "object",
                    "required": ["OIDC_PROVIDER", "OIDC_CLIENT_ID", "OIDC_CLIENT_SECRET", "DOMAIN_NAME"],
                    "properties": {
                        "OIDC_PROVIDER": {"type": "string", "description": "OIDC provider name (e.g., 'okta', 'azure')"},
                        "OIDC_CLIENT_ID": {"type": "string", "description": "OIDC client identifier"},
                        "OIDC_CLIENT_SECRET": {"type": "string", "description": "OIDC client secret"},
                        "OIDC_ISSUER": {"type": "string", "description": "OIDC issuer URL"},
                        "OIDC_DISCOVERY_URL": {"type": "string", "description": "OIDC discovery endpoint URL"},
                        "DOMAIN_NAME": {"type": "string", "description": "Application domain name for redirect URIs"},
                        "ROLE_GROUP_1": {"type": "string", "description": "First role group mapping"},
                        "ROLE_VALUE_1": {"type": "string", "description": "First role value"},
                        "ROLE_GROUP_2": {"type": "string", "description": "Second role group mapping"},
                        "ROLE_VALUE_2": {"type": "string", "description": "Second role value"},
                        "ROLE_GROUP_3": {"type": "string", "description": "Third role group mapping"},
                        "ROLE_VALUE_3": {"type": "string", "description": "Third role value"}
                    }
                }
            }
            
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
    
    def _create_nginx_template(self):
        """Create NGINX reverse proxy template"""
        template_dir = self.templates_dir / "nginx-proxy-v1.0.0"
        template_dir.mkdir(exist_ok=True)
        
        # Copy nginx.conf.template
        source_file = Path("../deploy-reference/nginx/nginx.conf.template")
        if source_file.exists():
            with open(source_file, 'r') as f:
                nginx_content = f.read()
            
            template_file = template_dir / "nginx.conf.template"
            with open(template_file, 'w') as f:
                f.write(nginx_content)
        
        # Create metadata
        metadata_file = template_dir / "metadata.json"
        if not metadata_file.exists():
            metadata = {
                "version": "nginx-proxy-v1.0.0",
                "name": "NGINX Reverse Proxy",
                "description": "NGINX reverse proxy configuration with SSL termination and security headers",
                "category": "infrastructure",
                "format": "nginx",
                "hash": self._calculate_template_hash("nginx-proxy-v1.0.0"),
                "created_at": datetime.utcnow().isoformat(),
                "schema": {
                    "type": "object",
                    "required": ["DOMAIN_NAME"],
                    "properties": {
                        "DOMAIN_NAME": {"type": "string", "description": "Domain name for SSL certificate and server configuration"}
                    }
                }
            }
            
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
    
    def _create_config_yaml_template(self):
        """Create main application config template"""
        template_dir = self.templates_dir / "ceneca-config-v1.0.0"
        template_dir.mkdir(exist_ok=True)
        
        # Copy config.yaml
        source_file = Path("../deploy-reference/config.yaml")
        if source_file.exists():
            with open(source_file, 'r') as f:
                config_content = f.read()
            
            template_file = template_dir / "config.yaml.template"
            with open(template_file, 'w') as f:
                f.write(config_content)
        
        # Create metadata
        metadata_file = template_dir / "metadata.json"
        if not metadata_file.exists():
            metadata = {
                "version": "ceneca-config-v1.0.0",
                "name": "Ceneca Application Configuration",
                "description": "Main application configuration with database and service connections",
                "category": "configuration",
                "format": "yaml",
                "hash": self._calculate_template_hash("ceneca-config-v1.0.0"),
                "created_at": datetime.utcnow().isoformat(),
                "schema": {
                    "type": "object",
                    "required": ["POSTGRES_USERNAME", "POSTGRES_PASSWORD", "POSTGRES_HOST", "POSTGRES_DATABASE"],
                    "properties": {
                        "POSTGRES_USERNAME": {"type": "string", "description": "PostgreSQL username"},
                        "POSTGRES_PASSWORD": {"type": "string", "description": "PostgreSQL password"},
                        "POSTGRES_HOST": {"type": "string", "description": "PostgreSQL hostname"},
                        "POSTGRES_DATABASE": {"type": "string", "description": "PostgreSQL database name"},
                        "MONGODB_USERNAME": {"type": "string", "description": "MongoDB username"},
                        "MONGODB_PASSWORD": {"type": "string", "description": "MongoDB password"},
                        "MONGODB_HOST": {"type": "string", "description": "MongoDB hostname"},
                        "MONGODB_DATABASE": {"type": "string", "description": "MongoDB database name"},
                        "QDRANT_HOST": {"type": "string", "description": "Qdrant hostname"},
                        "QDRANT_API_KEY": {"type": "string", "description": "Qdrant API key"}
                    }
                }
            }
            
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
    
    def validate_template_syntax(self, content: str, format_type: str) -> Dict[str, Union[bool, str]]:
        """Validate template syntax based on format"""
        try:
            if format_type == "yaml":
                # Try to parse YAML (with template variables, this might fail, so we do basic checks)
                if "{{" in content and "}}" in content:
                    # Has template variables, do basic validation
                    import re
                    # Check for balanced braces
                    if content.count("{{") != content.count("}}"):
                        return {"valid": False, "error": "Unbalanced template variable braces"}
                    return {"valid": True}
                else:
                    # No template variables, try full YAML parse
                    yaml.safe_load(content)
                    return {"valid": True}
            
            elif format_type == "docker-compose":
                # Basic Docker Compose validation
                if "services:" not in content:
                    return {"valid": False, "error": "Docker Compose file must contain 'services:' section"}
                return {"valid": True}
            
            elif format_type == "nginx":
                # Basic NGINX validation
                if "server {" not in content:
                    return {"valid": False, "error": "NGINX config must contain at least one server block"}
                return {"valid": True}
            
            else:
                return {"valid": True}  # Unknown format, assume valid
                
        except yaml.YAMLError as e:
            return {"valid": False, "error": f"YAML syntax error: {str(e)}"}
        except Exception as e:
            return {"valid": False, "error": f"Validation error: {str(e)}"}
    
    def get_template_categories(self) -> List[str]:
        """Get list of all template categories"""
        categories = set()
        
        for template in self.list_templates():
            metadata_file = self.templates_dir / template["version"] / "metadata.json"
            if metadata_file.exists():
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
                    if "category" in metadata:
                        categories.add(metadata["category"])
        
        return sorted(list(categories))
    
    def list_templates_by_category(self, category: str = None) -> List[Dict]:
        """List templates filtered by category"""
        all_templates = self.list_templates()
        
        if not category:
            return all_templates
        
        filtered_templates = []
        for template in all_templates:
            metadata_file = self.templates_dir / template["version"] / "metadata.json"
            if metadata_file.exists():
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
                    if metadata.get("category") == category:
                        template_copy = template.copy()
                        template_copy["category"] = metadata.get("category")
                        template_copy["format"] = metadata.get("format")
                        filtered_templates.append(template_copy)
        
        return filtered_templates
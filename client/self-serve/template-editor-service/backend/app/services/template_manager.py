import os
import json
import hashlib
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path

class TemplateManager:
    def __init__(self):
        self.templates_dir = Path("templates")
        self.templates_dir.mkdir(exist_ok=True)
        
        # Initialize default templates if they don't exist
        self._create_default_templates()
    
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
                            "created_at": datetime.fromisoformat(metadata["created_at"])
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
                "created_at": datetime.fromisoformat(metadata["created_at"])
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
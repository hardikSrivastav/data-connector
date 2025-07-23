from jose import jwt
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
import os
import json

class LicenseGenerator:
    def __init__(self):
        self.private_key = self._load_or_generate_private_key()
        self.public_key = self.private_key.public_key()
        self.algorithm = "RS256"
    
    def _load_or_generate_private_key(self):
        """Load private key from file or generate new one"""
        key_path = os.getenv("PRIVATE_KEY_PATH", "private_key.pem")
        
        if os.path.exists(key_path):
            with open(key_path, "rb") as key_file:
                return serialization.load_pem_private_key(
                    key_file.read(),
                    password=None,
                )
        else:
            # Generate new private key for development
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=4096,
            )
            
            # Save to file
            pem = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )
            
            with open(key_path, "wb") as key_file:
                key_file.write(pem)
                
            return private_key
    
    def generate_license_token(self, license_data: Dict[str, Any]) -> str:
        """Generate JWT license token"""
        
        # JWT Header
        header = {
            "alg": self.algorithm,
            "typ": "JWT",
            "kid": "license-key-1",
            "ver": "1.0"
        }
        
        # Simplified JWT Payload
        trial_expires = license_data.get("trial_expires")
        exp_timestamp = None
        if trial_expires:
            if isinstance(trial_expires, str):
                from datetime import datetime
                exp_timestamp = datetime.fromisoformat(trial_expires.replace('Z', '+00:00'))
            else:
                exp_timestamp = trial_expires
        
        payload = {
            # Customer Information
            "company_name": license_data.get("company_name"),
            "customer_id": str(license_data.get("customer_id")),
            "contact_email": license_data.get("contact_email"),
            
            # License Details
            "license_id": str(license_data.get("license_id")),
            "tier": license_data.get("tier"),
            "database_limit": license_data.get("database_limit"),
            "api_access": license_data.get("api_access", False),
            "custom_integrations": license_data.get("custom_integrations", False),
            
            # Trial expiration
            "trial_expires": trial_expires,
            
            # Standard JWT claims
            "iat": datetime.utcnow(),
            "exp": exp_timestamp or datetime.utcnow() + timedelta(days=365),
            "iss": "ceneca-license-service",
            "sub": str(license_data.get("customer_id"))
        }
        
        # Convert private key to PEM format for python-jose
        private_key_pem = self.private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        # Generate JWT token
        token = jwt.encode(
            payload,
            private_key_pem,
            algorithm=self.algorithm,
            headers=header
        )
        
        return token
    
    def get_public_key_pem(self) -> str:
        """Get public key in PEM format for client-side validation"""
        return self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode('utf-8')
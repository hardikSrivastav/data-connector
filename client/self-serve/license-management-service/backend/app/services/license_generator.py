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
        
        # JWT Payload
        payload = {
            # Customer Information
            "customer": {
                "company_name": license_data.get("company_name"),
                "customer_id": str(license_data.get("customer_id")),
                "contact_email": license_data.get("contact_email"),
                "industry_classification": license_data.get("industry_classification")
            },
            
            # License Details
            "license": {
                "license_id": str(license_data.get("license_id")),
                "product_sku": license_data.get("product_sku"),
                "edition_tier": license_data.get("edition_tier"),
                "license_type": license_data.get("license_type")
            },
            
            # Constraints
            "constraints": {
                "start_date": license_data.get("start_date").isoformat() if license_data.get("start_date") else None,
                "expiration_date": license_data.get("expiration_date").isoformat() if license_data.get("expiration_date") else None,
                "grace_period_days": license_data.get("grace_period_days", 30),
                "user_limit": license_data.get("user_limit"),
                "node_limit": license_data.get("node_limit"),
                "feature_flags": license_data.get("feature_flags", {}),
                "resource_limits": license_data.get("resource_limits", {})
            },
            
            # Hardware Binding
            "hardware_binding": {
                "binding_type": license_data.get("binding_type", "flexible"),
                "hardware_signatures": license_data.get("hardware_signatures", []),
                "tolerance_level": license_data.get("tolerance_level", 2)
            },
            
            # Operational Parameters
            "operational": {
                "phone_home_frequency": license_data.get("phone_home_frequency", 24),
                "offline_grace_period": license_data.get("offline_grace_period", 72),
                "usage_reporting_level": license_data.get("usage_reporting_level", "standard")
            },
            
            # Metadata
            "metadata": {
                "issue_date": datetime.utcnow().isoformat(),
                "issuer": license_data.get("issuer", "license-management-service"),
                "sales_order_reference": license_data.get("sales_order_reference"),
                "support_tier": license_data.get("support_tier")
            },
            
            # Standard JWT claims
            "iat": datetime.utcnow(),
            "exp": license_data.get("expiration_date") or datetime.utcnow() + timedelta(days=365),
            "iss": "license-management-service",
            "sub": str(license_data.get("customer_id"))
        }
        
        # Generate JWT token
        token = jwt.encode(
            payload=payload,
            key=self.private_key,
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
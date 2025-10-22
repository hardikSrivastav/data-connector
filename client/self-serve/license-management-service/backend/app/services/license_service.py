from jose import jwt
from datetime import datetime, timedelta
from typing import Dict, Any
import os

class LicenseService:
    def __init__(self):
        self.jwt_secret = os.getenv("JWT_SECRET", "your-super-secret-jwt-key-change-in-production")
        self.algorithm = "HS256"  # Using HMAC for simplicity
    
    def generate_jwt_token(self, license_data: Dict[str, Any]) -> str:
        """Generate JWT token for license"""
        
        # Create payload with license information
        payload = {
            # License details
            "license_id": license_data.get("license_id"),
            "customer_id": license_data.get("customer_id"),
            "company_name": license_data.get("company_name"),
            "contact_email": license_data.get("contact_email"),
            "license_key": license_data.get("license_key"),
            
            # Plan and limits
            "plan": license_data.get("plan"),
            "max_seats": license_data.get("max_seats"),
            "features": license_data.get("features", []),
            
            # Expiration dates
            "expires_at": license_data.get("expires_at"),
            "trial_expires_at": license_data.get("trial_expires_at"),
            
            # Standard JWT claims
            "iat": datetime.utcnow(),
            "exp": datetime.utcnow() + timedelta(days=365),  # Token valid for 1 year
            "iss": "ceneca-license-service",
            "sub": license_data.get("customer_id"),
            "aud": "ceneca-application"
        }
        
        # Generate and return JWT token
        token = jwt.encode(payload, self.jwt_secret, algorithm=self.algorithm)
        return token
    
    def verify_jwt_token(self, token: str) -> Dict[str, Any]:
        """Verify and decode JWT token"""
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=[self.algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            raise ValueError("Token has expired")
        except jwt.InvalidTokenError:
            raise ValueError("Invalid token")
    
    def validate_license_token(self, token: str) -> Dict[str, Any]:
        """Validate license token and return license info"""
        try:
            payload = self.verify_jwt_token(token)
            
            # Check if license is still valid
            now = datetime.utcnow()
            
            # Check JWT expiration
            exp_timestamp = payload.get("exp")
            if exp_timestamp and datetime.fromtimestamp(exp_timestamp) < now:
                raise ValueError("License token has expired")
            
            # Check license expiration
            expires_at = payload.get("expires_at")
            if expires_at:
                license_exp = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                if license_exp < now:
                    raise ValueError("License has expired")
            
            # Check trial expiration
            trial_expires_at = payload.get("trial_expires_at")
            if trial_expires_at:
                trial_exp = datetime.fromisoformat(trial_expires_at.replace('Z', '+00:00'))
                if trial_exp < now:
                    # Trial expired, but license might still be valid if it's paid
                    payload["trial_expired"] = True
                else:
                    payload["trial_expired"] = False
            
            return payload
            
        except Exception as e:
            raise ValueError(f"License validation failed: {str(e)}")
    
    def extract_license_info(self, token: str) -> Dict[str, Any]:
        """Extract license information without full validation (for display purposes)"""
        try:
            # Decode without verification for display purposes
            payload = jwt.decode(token, options={"verify_signature": False})
            return {
                "license_key": payload.get("license_key"),
                "company_name": payload.get("company_name"),
                "plan": payload.get("plan"),
                "max_seats": payload.get("max_seats"),
                "features": payload.get("features", []),
                "expires_at": payload.get("expires_at"),
                "trial_expires_at": payload.get("trial_expires_at")
            }
        except Exception as e:
            raise ValueError(f"Failed to extract license info: {str(e)}")
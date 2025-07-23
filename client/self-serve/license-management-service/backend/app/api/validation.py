from fastapi import APIRouter, HTTPException
from jose import jwt, JWTError
from app.services.license_generator import LicenseGenerator

router = APIRouter()

@router.post("/validate")
async def validate_license(license_token: str):
    """Simple license token validation"""
    
    try:
        # Get license generator to access public key
        license_generator = LicenseGenerator()
        public_key_pem = license_generator.get_public_key_pem()
        
        # Decode and validate JWT
        payload = jwt.decode(
            license_token,
            public_key_pem,
            algorithms=["RS256"]
        )
        
        return {
            "valid": True,
            "license_id": payload.get("license_id"),
            "tier": payload.get("tier"),
            "database_limit": payload.get("database_limit"),
            "api_access": payload.get("api_access", False),
            "custom_integrations": payload.get("custom_integrations", False),
            "trial_expires": payload.get("trial_expires"),
            "company_name": payload.get("company_name")
        }
        
    except JWTError as e:
        return {
            "valid": False,
            "reason": "Invalid or expired license token"
        }

@router.get("/public-key")
async def get_public_key():
    """Get public key for license validation"""
    license_generator = LicenseGenerator()
    return {
        "public_key": license_generator.get_public_key_pem(),
        "algorithm": "RS256",
        "key_id": "license-key-1"
    }
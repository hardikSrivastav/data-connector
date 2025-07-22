from jose import jwt
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple
from cryptography.hazmat.primitives import serialization
import os
import json

class LicenseValidator:
    def __init__(self):
        self.public_key = self._load_public_key()
        self.algorithm = "RS256"
    
    def _load_public_key(self):
        """Load public key from file"""
        private_key_path = os.getenv("PRIVATE_KEY_PATH", "private_key.pem")
        
        if os.path.exists(private_key_path):
            with open(private_key_path, "rb") as key_file:
                private_key = serialization.load_pem_private_key(
                    key_file.read(),
                    password=None,
                )
                return private_key.public_key()
        
        raise FileNotFoundError("Private key file not found for public key extraction")
    
    def validate_license_token(self, token: str, hardware_fingerprint: Optional[Dict[str, str]] = None) -> Tuple[bool, Dict[str, Any]]:
        """Validate JWT license token"""
        try:
            # Decode and verify JWT
            payload = jwt.decode(
                token,
                key=self.public_key,
                algorithms=[self.algorithm],
                options={"verify_exp": True}
            )
            
            # Check if license is expired
            exp_timestamp = payload.get("exp")
            if exp_timestamp:
                if isinstance(exp_timestamp, datetime):
                    exp_date = exp_timestamp
                else:
                    exp_date = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
                
                if datetime.now(timezone.utc) > exp_date:
                    return False, {
                        "reason": "license_expired",
                        "expired_at": exp_date.isoformat(),
                        "current_time": datetime.now(timezone.utc).isoformat()
                    }
            
            # Check start date
            constraints = payload.get("constraints", {})
            start_date_str = constraints.get("start_date")
            if start_date_str:
                start_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
                if datetime.now(timezone.utc) < start_date:
                    return False, {
                        "reason": "license_not_yet_valid",
                        "start_date": start_date.isoformat(),
                        "current_time": datetime.now(timezone.utc).isoformat()
                    }
            
            # Hardware binding validation
            if hardware_fingerprint:
                binding_result = self._validate_hardware_binding(payload, hardware_fingerprint)
                if not binding_result[0]:
                    return False, binding_result[1]
            
            # Return validation success with license details
            return True, {
                "license_id": payload.get("license", {}).get("license_id"),
                "customer_id": payload.get("customer", {}).get("customer_id"),
                "product_sku": payload.get("license", {}).get("product_sku"),
                "edition_tier": payload.get("license", {}).get("edition_tier"),
                "license_type": payload.get("license", {}).get("license_type"),
                "feature_flags": constraints.get("feature_flags", {}),
                "user_limit": constraints.get("user_limit"),
                "node_limit": constraints.get("node_limit"),
                "resource_limits": constraints.get("resource_limits", {}),
                "expires_at": payload.get("constraints", {}).get("expiration_date"),
                "operational": payload.get("operational", {})
            }
            
        except jwt.ExpiredSignatureError:
            return False, {"reason": "token_expired"}
        except jwt.InvalidTokenError as e:
            return False, {"reason": "invalid_token", "details": str(e)}
        except Exception as e:
            return False, {"reason": "validation_error", "details": str(e)}
    
    def _validate_hardware_binding(self, payload: Dict[str, Any], hardware_fingerprint: Dict[str, str]) -> Tuple[bool, Dict[str, Any]]:
        """Validate hardware binding constraints"""
        hardware_binding = payload.get("hardware_binding", {})
        binding_type = hardware_binding.get("binding_type", "flexible")
        
        if binding_type == "none":
            return True, {}
        
        expected_signatures = hardware_binding.get("hardware_signatures", [])
        tolerance_level = hardware_binding.get("tolerance_level", 2)
        
        if not expected_signatures:
            return True, {}  # No binding configured
        
        # Calculate hardware signature from fingerprint
        current_signature = self._generate_hardware_signature(hardware_fingerprint)
        
        if binding_type == "strict":
            # All hardware signatures must match exactly
            for expected_sig in expected_signatures:
                if current_signature != expected_sig:
                    return False, {
                        "reason": "hardware_mismatch",
                        "binding_type": "strict",
                        "expected": expected_signatures,
                        "current": current_signature
                    }
            return True, {}
        
        elif binding_type == "flexible":
            # Allow some tolerance in hardware changes
            matches = sum(1 for sig in expected_signatures if self._signatures_match(current_signature, sig, tolerance_level))
            
            if matches == 0:
                return False, {
                    "reason": "hardware_mismatch",
                    "binding_type": "flexible",
                    "tolerance_level": tolerance_level,
                    "expected": expected_signatures,
                    "current": current_signature
                }
            
            return True, {}
        
        return True, {}
    
    def _generate_hardware_signature(self, fingerprint: Dict[str, str]) -> str:
        """Generate hardware signature from fingerprint"""
        # Simple implementation - in production, use more sophisticated hashing
        signature_parts = []
        for key in sorted(fingerprint.keys()):
            signature_parts.append(f"{key}:{fingerprint[key]}")
        return "|".join(signature_parts)
    
    def _signatures_match(self, sig1: str, sig2: str, tolerance_level: int) -> bool:
        """Check if two hardware signatures match within tolerance"""
        parts1 = sig1.split("|")
        parts2 = sig2.split("|")
        
        matching_parts = sum(1 for p1, p2 in zip(parts1, parts2) if p1 == p2)
        total_parts = max(len(parts1), len(parts2))
        
        # Allow tolerance_level parts to be different
        return (total_parts - matching_parts) <= tolerance_level
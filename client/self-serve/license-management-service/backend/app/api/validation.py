from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from app.database.database import get_db
from app.models.schemas import LicenseValidation, License, UsageEvent
from app.models.pydantic_models import LicenseValidationRequest, LicenseValidationResponse
from app.services.license_validator import LicenseValidator

router = APIRouter()

@router.post("/validate", response_model=LicenseValidationResponse)
async def validate_license(
    validation_request: LicenseValidationRequest,
    db: Session = Depends(get_db)
):
    """Validate a license token"""
    
    validator = LicenseValidator()
    
    # Validate the license token
    is_valid, validation_details = validator.validate_license_token(
        validation_request.license_token,
        validation_request.hardware_fingerprint
    )
    
    # Log validation attempt
    validation_record = LicenseValidation(
        license_id=validation_details.get("license_id") if is_valid else None,
        validation_result="valid" if is_valid else "invalid",
        validation_details=validation_details,
        client_fingerprint=validation_request.hardware_fingerprint or {}
    )
    
    db.add(validation_record)
    
    # If validation successful, log usage event
    if is_valid:
        license_id = validation_details.get("license_id")
        if license_id:
            usage_event = UsageEvent(
                license_id=license_id,
                event_type="validation_success",
                event_data={"validation_id": str(validation_record.id)},
                client_info={
                    "hardware_fingerprint": validation_request.hardware_fingerprint,
                    "client_info": validation_request.client_info
                }
            )
            db.add(usage_event)
    
    db.commit()
    
    # Return validation response
    if is_valid:
        return LicenseValidationResponse(
            valid=True,
            license_id=validation_details.get("license_id"),
            expires_at=validation_details.get("expires_at"),
            feature_flags=validation_details.get("feature_flags", {}),
            user_limit=validation_details.get("user_limit"),
            node_limit=validation_details.get("node_limit"),
            resource_limits=validation_details.get("resource_limits", {})
        )
    else:
        return LicenseValidationResponse(
            valid=False,
            reason=validation_details.get("reason", "unknown_error")
        )

@router.get("/public-key")
async def get_public_key():
    """Get public key for client-side validation"""
    try:
        from app.services.license_generator import LicenseGenerator
        generator = LicenseGenerator()
        public_key_pem = generator.get_public_key_pem()
        
        return {
            "public_key": public_key_pem,
            "algorithm": "RS256",
            "key_id": "license-key-1"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving public key: {str(e)}")

@router.post("/usage")
async def report_usage(
    license_id: str,
    event_type: str,
    event_data: dict = None,
    user_count: int = None,
    resource_usage: dict = None,
    client_info: dict = None,
    db: Session = Depends(get_db)
):
    """Report usage telemetry"""
    
    # Verify license exists and is active
    license = db.query(License).filter(License.id == license_id, License.is_active == True).first()
    if not license:
        raise HTTPException(status_code=404, detail="License not found or inactive")
    
    # Create usage event
    usage_event = UsageEvent(
        license_id=license_id,
        event_type=event_type,
        event_data=event_data or {},
        user_count=user_count,
        resource_usage=resource_usage or {},
        client_info=client_info or {}
    )
    
    db.add(usage_event)
    db.commit()
    
    return {"message": "Usage reported successfully", "event_id": str(usage_event.id)}

@router.get("/license/{license_id}/status")
async def get_license_status(
    license_id: str,
    db: Session = Depends(get_db)
):
    """Get current license status and usage summary"""
    
    license = db.query(License).filter(License.id == license_id).first()
    if not license:
        raise HTTPException(status_code=404, detail="License not found")
    
    # Get recent validation attempts
    recent_validations = db.query(LicenseValidation).filter(
        LicenseValidation.license_id == license_id
    ).order_by(LicenseValidation.timestamp.desc()).limit(10).all()
    
    # Get usage summary
    usage_events = db.query(UsageEvent).filter(
        UsageEvent.license_id == license_id
    ).order_by(UsageEvent.timestamp.desc()).limit(50).all()
    
    return {
        "license_id": license_id,
        "is_active": license.is_active,
        "expires_at": license.expiration_date.isoformat() if license.expiration_date else None,
        "recent_validations": [
            {
                "timestamp": val.timestamp.isoformat(),
                "result": val.validation_result,
                "details": val.validation_details
            }
            for val in recent_validations
        ],
        "usage_summary": {
            "total_events": len(usage_events),
            "event_types": list(set(event.event_type for event in usage_events)),
            "last_activity": usage_events[0].timestamp.isoformat() if usage_events else None
        }
    }
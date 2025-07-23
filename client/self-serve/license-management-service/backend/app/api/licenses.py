from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID
from datetime import datetime, timedelta

from app.database.database import get_db
from app.models.schemas import License, Customer
from app.models.pydantic_models import LicenseCreate, LicenseResponse
from app.services.license_generator import LicenseGenerator

router = APIRouter()

# Tier configuration based on Ceneca pricing
TIER_CONFIG = {
    "starter": {
        "database_limit": 3,
        "api_access": False,
        "custom_integrations": False
    },
    "business": {
        "database_limit": 10,
        "api_access": True,
        "custom_integrations": False
    },
    "enterprise": {
        "database_limit": None,  # unlimited
        "api_access": True,
        "custom_integrations": True
    }
}

@router.post("/", response_model=LicenseResponse)
async def create_license(
    license_data: LicenseCreate,
    db: Session = Depends(get_db)
):
    """Create a new license with tier-based features"""
    
    # Verify customer exists
    customer = db.query(Customer).filter(Customer.id == license_data.customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    # Validate tier
    if license_data.tier not in TIER_CONFIG:
        raise HTTPException(status_code=400, detail="Invalid tier")
    
    tier_config = TIER_CONFIG[license_data.tier]
    
    # 14-day trial expiration
    trial_expires = datetime.utcnow() + timedelta(days=14)
    
    # Create license record
    db_license = License(
        customer_id=license_data.customer_id,
        tier=license_data.tier,
        database_limit=tier_config["database_limit"],
        api_access=tier_config["api_access"],
        custom_integrations=tier_config["custom_integrations"],
        trial_expires=trial_expires
    )
    
    db.add(db_license)
    db.commit()
    db.refresh(db_license)
    
    # Generate simple license token
    license_generator = LicenseGenerator()
    token_data = {
        "company_name": customer.company_name,
        "customer_id": str(license_data.customer_id),
        "contact_email": customer.contact_email,
        "license_id": str(db_license.id),
        "tier": db_license.tier,
        "database_limit": db_license.database_limit,
        "api_access": db_license.api_access,
        "custom_integrations": db_license.custom_integrations,
        "trial_expires": trial_expires.isoformat() if trial_expires else None
    }
    
    license_token = license_generator.generate_license_token(token_data)
    
    # Update license with token
    db_license.license_token = license_token
    db.commit()
    db.refresh(db_license)
    
    return db_license

@router.get("/", response_model=List[LicenseResponse])
async def list_licenses(
    customer_id: UUID,
    db: Session = Depends(get_db)
):
    """List licenses for a customer"""
    licenses = db.query(License).filter(License.customer_id == customer_id).all()
    return licenses

@router.get("/{license_id}", response_model=LicenseResponse)
async def get_license(
    license_id: UUID,
    db: Session = Depends(get_db)
):
    """Get license by ID"""
    license = db.query(License).filter(License.id == license_id).first()
    if not license:
        raise HTTPException(status_code=404, detail="License not found")
    return license

@router.get("/{license_id}/token")
async def get_license_token(
    license_id: UUID,
    db: Session = Depends(get_db)
):
    """Get license token for download"""
    license = db.query(License).filter(License.id == license_id).first()
    if not license:
        raise HTTPException(status_code=404, detail="License not found")
    
    return {
        "license_id": license_id,
        "license_token": license.license_token,
        "tier": license.tier,
        "trial_expires": license.trial_expires.isoformat() if license.trial_expires else None
    }
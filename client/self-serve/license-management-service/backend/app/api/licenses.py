from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.database.database import get_db
from app.models.schemas import License, Customer
from app.models.pydantic_models import LicenseCreate, LicenseResponse, CustomerResponse
from app.services.license_generator import LicenseGenerator

router = APIRouter()

@router.post("/", response_model=LicenseResponse)
async def create_license(
    license_data: LicenseCreate,
    db: Session = Depends(get_db)
):
    """Create a new license"""
    
    # Verify customer exists
    customer = db.query(Customer).filter(Customer.id == license_data.customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    # Create license record
    db_license = License(
        customer_id=license_data.customer_id,
        product_sku=license_data.product_sku,
        edition_tier=license_data.edition_tier,
        license_type=license_data.license_type,
        start_date=license_data.start_date,
        expiration_date=license_data.expiration_date,
        grace_period_days=license_data.grace_period_days,
        user_limit=license_data.user_limit,
        node_limit=license_data.node_limit,
        feature_flags=license_data.feature_flags,
        resource_limits=license_data.resource_limits,
        binding_type=license_data.binding_type,
        hardware_signatures=license_data.hardware_signatures,
        tolerance_level=license_data.tolerance_level,
        phone_home_frequency=license_data.phone_home_frequency,
        offline_grace_period=license_data.offline_grace_period,
        usage_reporting_level=license_data.usage_reporting_level,
        sales_order_reference=license_data.sales_order_reference,
        support_tier=license_data.support_tier
    )
    
    db.add(db_license)
    db.commit()
    db.refresh(db_license)
    
    # Generate license token
    license_generator = LicenseGenerator()
    
    token_data = {
        "company_name": customer.company_name,
        "customer_id": db_license.customer_id,
        "contact_email": customer.contact_email,
        "industry_classification": customer.industry_classification,
        "license_id": db_license.id,
        "product_sku": db_license.product_sku,
        "edition_tier": db_license.edition_tier,
        "license_type": db_license.license_type,
        "start_date": db_license.start_date,
        "expiration_date": db_license.expiration_date,
        "grace_period_days": db_license.grace_period_days,
        "user_limit": db_license.user_limit,
        "node_limit": db_license.node_limit,
        "feature_flags": db_license.feature_flags,
        "resource_limits": db_license.resource_limits,
        "binding_type": db_license.binding_type,
        "hardware_signatures": db_license.hardware_signatures,
        "tolerance_level": db_license.tolerance_level,
        "phone_home_frequency": db_license.phone_home_frequency,
        "offline_grace_period": db_license.offline_grace_period,
        "usage_reporting_level": db_license.usage_reporting_level,
        "issuer": db_license.issuer,
        "sales_order_reference": db_license.sales_order_reference,
        "support_tier": db_license.support_tier
    }
    
    license_token = license_generator.generate_license_token(token_data)
    
    # Update license with token
    db_license.license_token = license_token
    db.commit()
    db.refresh(db_license)
    
    return db_license

@router.get("/", response_model=List[LicenseResponse])
async def list_licenses(
    skip: int = 0,
    limit: int = 100,
    customer_id: UUID = None,
    db: Session = Depends(get_db)
):
    """List licenses with optional filtering"""
    query = db.query(License)
    
    if customer_id:
        query = query.filter(License.customer_id == customer_id)
    
    licenses = query.offset(skip).limit(limit).all()
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

@router.put("/{license_id}/revoke")
async def revoke_license(
    license_id: UUID,
    reason: str = "Administrative action",
    db: Session = Depends(get_db)
):
    """Revoke a license"""
    license = db.query(License).filter(License.id == license_id).first()
    if not license:
        raise HTTPException(status_code=404, detail="License not found")
    
    from datetime import datetime
    license.is_active = False
    license.revoked_at = datetime.utcnow()
    license.revocation_reason = reason
    
    db.commit()
    
    return {"message": "License revoked successfully"}

@router.get("/{license_id}/token")
async def get_license_token(
    license_id: UUID,
    db: Session = Depends(get_db)
):
    """Get license token for download"""
    license = db.query(License).filter(License.id == license_id).first()
    if not license:
        raise HTTPException(status_code=404, detail="License not found")
    
    if not license.is_active:
        raise HTTPException(status_code=400, detail="License is not active")
    
    return {
        "license_id": license_id,
        "license_token": license.license_token,
        "expires_at": license.expiration_date.isoformat() if license.expiration_date else None
    }
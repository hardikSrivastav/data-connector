from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID
from datetime import datetime, timedelta
import secrets
import string

from app.database.database import get_db
from app.models.schemas import License, Customer
from app.models.pydantic_models import LicenseCreate, LicenseResponse, LicenseValidationRequest, LicenseValidationResponse
from app.services.license_service import LicenseService

router = APIRouter()

# Plan configurations
PLANS = {
    "starter": {
        "max_seats": 5,
        "monthly_price": 2000,  # $20.00 per seat
        "features": ["basic_queries", "visualizations"]
    },
    "business": {
        "max_seats": 25,
        "monthly_price": 10000,  # $100.00 per seat  
        "features": ["basic_queries", "visualizations", "api_access", "advanced_queries"]
    },
    "enterprise": {
        "max_seats": 999,
        "monthly_price": 25000,  # $250.00 per seat
        "features": ["basic_queries", "visualizations", "api_access", "advanced_queries", "custom_integrations", "priority_support"]
    }
}

def generate_license_key(plan: str) -> str:
    """Generate a human-readable license key"""
    suffix = ''.join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(8))
    return f"ceneca-{plan}-2024-{suffix}"

@router.post("/", response_model=LicenseResponse)
async def create_license(license_data: LicenseCreate, db: Session = Depends(get_db)):
    """Create a new license"""
    
    # Validate plan
    if license_data.plan not in PLANS:
        raise HTTPException(status_code=400, detail=f"Invalid plan. Must be one of: {list(PLANS.keys())}")
    
    # Get or create customer
    customer = db.query(Customer).filter(Customer.id == license_data.customer_id).first()
    if not customer:
        # Auto-create customer for seamless flow
        customer = Customer(
            id=license_data.customer_id,
            company_name="Demo Company",
            contact_email="demo@example.com"
        )
        db.add(customer)
        db.commit()
        db.refresh(customer)
    
    plan_config = PLANS[license_data.plan]
    
    # Generate license
    license_key = generate_license_key(license_data.plan)
    trial_days = license_data.trial_days or 14
    
    db_license = License(
        customer_id=license_data.customer_id,
        license_key=license_key,
        plan=license_data.plan,
        max_seats=plan_config["max_seats"],
        features=plan_config["features"],
        monthly_price=plan_config["monthly_price"],
        expires_at=datetime.utcnow() + timedelta(days=365),  # 1 year
        trial_expires_at=datetime.utcnow() + timedelta(days=trial_days)
    )
    
    db.add(db_license)
    db.commit()
    db.refresh(db_license)
    
    # Generate JWT token
    license_service = LicenseService()
    token_data = {
        "license_id": str(db_license.id),
        "customer_id": str(customer.id),
        "company_name": customer.company_name,
        "contact_email": customer.contact_email,
        "license_key": license_key,
        "plan": license_data.plan,
        "max_seats": plan_config["max_seats"],
        "features": plan_config["features"],
        "expires_at": db_license.expires_at.isoformat(),
        "trial_expires_at": db_license.trial_expires_at.isoformat() if db_license.trial_expires_at else None
    }
    
    jwt_token = license_service.generate_jwt_token(token_data)
    
    # Update license with JWT
    db_license.jwt_token = jwt_token
    db.commit()
    db.refresh(db_license)
    
    return db_license

@router.get("/", response_model=List[LicenseResponse]) 
async def list_licenses(customer_id: UUID = None, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """List licenses, optionally filtered by customer"""
    query = db.query(License)
    
    if customer_id:
        query = query.filter(License.customer_id == customer_id)
    
    licenses = query.offset(skip).limit(limit).all()
    return licenses

@router.get("/{license_id}", response_model=LicenseResponse)
async def get_license(license_id: UUID, db: Session = Depends(get_db)):
    """Get license by ID"""
    license = db.query(License).filter(License.id == license_id).first()
    if not license:
        raise HTTPException(status_code=404, detail="License not found")
    return license

@router.post("/validate")
async def validate_license(validation_request: LicenseValidationRequest, db: Session = Depends(get_db)):
    """Validate license for agent use"""
    
    # Find license by key
    license = db.query(License).filter(License.license_key == validation_request.license_key).first()
    if not license:
        return LicenseValidationResponse(
            valid=False,
            error="License not found"
        )
    
    # Check if license is active
    if not license.is_active:
        return LicenseValidationResponse(
            valid=False,
            error="License is inactive"
        )
    
    # Check expiration
    now = datetime.utcnow()
    if license.expires_at < now:
        return LicenseValidationResponse(
            valid=False,
            error="License has expired"
        )
    
    # Check trial expiration
    is_trial = license.trial_expires_at and license.trial_expires_at > now
    if license.trial_expires_at and license.trial_expires_at < now:
        return LicenseValidationResponse(
            valid=False,
            error="Trial period has expired"
        )
    
    return LicenseValidationResponse(
        valid=True,
        license_info={
            "license_key": license.license_key,
            "plan": license.plan,
            "company_name": license.customer.company_name,
            "is_trial": is_trial,
            "trial_expires_at": license.trial_expires_at.isoformat() if license.trial_expires_at else None,
            "expires_at": license.expires_at.isoformat()
        },
        seats_available=license.max_seats,
        features=license.features
    )

@router.get("/{license_id}/download")
async def download_license(license_id: UUID, db: Session = Depends(get_db)):
    """Download license file for on-premise deployment"""
    license = db.query(License).filter(License.id == license_id).first()
    if not license:
        raise HTTPException(status_code=404, detail="License not found")
    
    return {
        "license_key": license.license_key,
        "jwt_token": license.jwt_token,
        "plan": license.plan,
        "max_seats": license.max_seats,
        "features": license.features,
        "deployment_instructions": {
            "agent_command": f"./ceneca-agent --license-key {license.license_key} --jwt-token {license.jwt_token}",
            "docker_env": f"LICENSE_KEY={license.license_key}\nJWT_TOKEN={license.jwt_token}",
            "config_file": f"license_key: {license.license_key}\njwt_token: {license.jwt_token}\nmax_seats: {license.max_seats}"
        }
    }
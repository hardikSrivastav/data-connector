from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.database.database import get_db
from app.models.schemas import Customer, TelemetryReport
from app.models.pydantic_models import CustomerCreate, CustomerResponse

router = APIRouter()

@router.post("/", response_model=CustomerResponse)
async def create_customer(customer_data: CustomerCreate, db: Session = Depends(get_db)):
    """Create a new customer"""
    
    # Check if customer already exists by email
    existing = db.query(Customer).filter(Customer.contact_email == customer_data.contact_email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Customer with this email already exists")
    
    # Create new customer
    db_customer = Customer(
        company_name=customer_data.company_name,
        contact_email=customer_data.contact_email,
        industry=customer_data.industry
    )
    
    db.add(db_customer)
    db.commit()
    db.refresh(db_customer)
    
    return db_customer

@router.get("/", response_model=List[CustomerResponse])
async def list_customers(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """List all customers"""
    customers = db.query(Customer).offset(skip).limit(limit).all()
    return customers

@router.get("/{customer_id}", response_model=CustomerResponse)
async def get_customer(customer_id: UUID, db: Session = Depends(get_db)):
    """Get customer by ID"""
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer

@router.get("/{customer_id}/dashboard")
async def get_customer_dashboard(customer_id: UUID, db: Session = Depends(get_db)):
    """Get customer dashboard data"""
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    # Get licenses and recent telemetry
    licenses = [license for license in customer.licenses if license.is_active]
    recent_reports = db.query(TelemetryReport).filter(
        TelemetryReport.customer_id == customer_id
    ).order_by(TelemetryReport.report_date.desc()).limit(30).all()
    
    return {
        "customer": customer,
        "licenses": licenses,
        "recent_usage": recent_reports,
        "total_licenses": len(licenses),
        "active_deployments": len(set(r.deployment_id for r in recent_reports if r.deployment_id))
    }
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.database.database import get_db
from app.models.schemas import Customer
from app.models.pydantic_models import CustomerCreate, CustomerResponse

router = APIRouter()

@router.post("/", response_model=CustomerResponse)
async def create_customer(
    customer_data: CustomerCreate,
    db: Session = Depends(get_db)
):
    """Create a new customer"""
    
    # Check if customer with email already exists
    existing_customer = db.query(Customer).filter(Customer.contact_email == customer_data.contact_email).first()
    if existing_customer:
        raise HTTPException(status_code=400, detail="Customer with this email already exists")
    
    db_customer = Customer(
        company_name=customer_data.company_name,
        contact_email=customer_data.contact_email,
        industry_classification=customer_data.industry_classification
    )
    
    db.add(db_customer)
    db.commit()
    db.refresh(db_customer)
    
    return db_customer

@router.get("/", response_model=List[CustomerResponse])
async def list_customers(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List customers"""
    customers = db.query(Customer).offset(skip).limit(limit).all()
    return customers

@router.get("/{customer_id}", response_model=CustomerResponse)
async def get_customer(
    customer_id: UUID,
    db: Session = Depends(get_db)
):
    """Get customer by ID"""
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer

@router.put("/{customer_id}", response_model=CustomerResponse)
async def update_customer(
    customer_id: UUID,
    customer_data: CustomerCreate,
    db: Session = Depends(get_db)
):
    """Update customer"""
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    customer.company_name = customer_data.company_name
    customer.contact_email = customer_data.contact_email
    customer.industry_classification = customer_data.industry_classification
    
    db.commit()
    db.refresh(customer)
    
    return customer

@router.delete("/{customer_id}")
async def delete_customer(
    customer_id: UUID,
    db: Session = Depends(get_db)
):
    """Delete customer"""
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    # Check if customer has active licenses
    if customer.licenses:
        active_licenses = [license for license in customer.licenses if license.is_active]
        if active_licenses:
            raise HTTPException(
                status_code=400, 
                detail=f"Cannot delete customer with {len(active_licenses)} active licenses"
            )
    
    db.delete(customer)
    db.commit()
    
    return {"message": "Customer deleted successfully"}
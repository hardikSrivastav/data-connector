from pydantic import BaseModel
from typing import Dict, List, Optional, Any
from datetime import datetime
from uuid import UUID

class CustomerBase(BaseModel):
    company_name: str
    contact_email: str
    industry_classification: Optional[str] = None

class CustomerCreate(CustomerBase):
    pass

class CustomerResponse(CustomerBase):
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class LicenseCreate(BaseModel):
    customer_id: UUID
    tier: str  # starter, business, enterprise

class LicenseResponse(BaseModel):
    id: UUID
    customer_id: UUID
    tier: str
    database_limit: Optional[int]
    api_access: bool
    custom_integrations: bool
    trial_expires: Optional[datetime]
    license_token: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True

# Simplified models - removed validation and usage tracking
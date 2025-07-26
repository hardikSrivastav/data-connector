from pydantic import BaseModel, EmailStr
from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import UUID

# Customer models
class CustomerBase(BaseModel):
    company_name: str
    contact_email: str
    industry: Optional[str] = None

class CustomerCreate(CustomerBase):
    pass

class CustomerResponse(CustomerBase):
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

# License models
class LicenseCreate(BaseModel):
    customer_id: UUID
    plan: str  # starter, business, enterprise
    trial_days: Optional[int] = 14

class LicenseResponse(BaseModel):
    id: UUID
    customer_id: UUID
    license_key: str
    plan: str
    max_seats: int
    features: List[str]
    monthly_price: Optional[int]
    issued_at: datetime
    expires_at: datetime
    trial_expires_at: Optional[datetime]
    jwt_token: str
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

# Telemetry models
class TelemetryData(BaseModel):
    license_key: str
    report_date: datetime
    deployment_id: Optional[str] = None
    active_users: Dict[str, Any]  # {"unique_daily": 8, "peak_concurrent": 5}
    usage_stats: Dict[str, Any]   # {"queries_executed": 1250}
    system_info: Dict[str, Any]   # {"version": "1.2.3", "os": "linux"}

class TelemetryResponse(BaseModel):
    id: UUID
    customer_id: UUID
    license_id: UUID
    license_key: str
    report_date: datetime
    deployment_id: Optional[str]
    active_users: Dict[str, Any]
    usage_stats: Dict[str, Any]
    system_info: Dict[str, Any]
    max_seats_used: int
    overage_seats: int
    created_at: datetime
    
    class Config:
        from_attributes = True

# License validation models
class LicenseValidationRequest(BaseModel):
    license_key: str
    user_id: str
    deployment_id: Optional[str] = None

class LicenseValidationResponse(BaseModel):
    valid: bool
    license_info: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    seats_available: Optional[int] = None
    features: Optional[List[str]] = None
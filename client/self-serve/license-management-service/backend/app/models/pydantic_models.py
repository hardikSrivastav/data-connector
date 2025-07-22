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
    product_sku: str
    edition_tier: str
    license_type: str  # perpetual, subscription, trial
    start_date: datetime
    expiration_date: Optional[datetime] = None
    grace_period_days: int = 30
    user_limit: Optional[int] = None
    node_limit: Optional[int] = None
    feature_flags: Dict[str, bool] = {}
    resource_limits: Dict[str, Any] = {}
    binding_type: str = "flexible"
    hardware_signatures: List[str] = []
    tolerance_level: int = 2
    phone_home_frequency: int = 24
    offline_grace_period: int = 72
    usage_reporting_level: str = "standard"
    sales_order_reference: Optional[str] = None
    support_tier: Optional[str] = None

class LicenseResponse(BaseModel):
    id: UUID
    customer_id: UUID
    product_sku: str
    edition_tier: str
    license_type: str
    start_date: datetime
    expiration_date: Optional[datetime]
    grace_period_days: int
    user_limit: Optional[int]
    node_limit: Optional[int]
    feature_flags: Dict[str, bool]
    resource_limits: Dict[str, Any]
    binding_type: str
    hardware_signatures: List[str]
    tolerance_level: int
    phone_home_frequency: int
    offline_grace_period: int
    usage_reporting_level: str
    issue_date: datetime
    issuer: str
    sales_order_reference: Optional[str]
    support_tier: Optional[str]
    is_active: bool
    revoked_at: Optional[datetime]
    revocation_reason: Optional[str]
    license_token: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True

class LicenseValidationRequest(BaseModel):
    license_token: str
    hardware_fingerprint: Optional[Dict[str, str]] = {}
    client_info: Optional[Dict[str, Any]] = {}

class LicenseValidationResponse(BaseModel):
    valid: bool
    license_id: Optional[UUID] = None
    reason: Optional[str] = None
    expires_at: Optional[datetime] = None
    feature_flags: Dict[str, bool] = {}
    user_limit: Optional[int] = None
    node_limit: Optional[int] = None
    resource_limits: Dict[str, Any] = {}

class UsageEventCreate(BaseModel):
    license_id: UUID
    event_type: str
    event_data: Optional[Dict[str, Any]] = {}
    user_count: Optional[int] = None
    resource_usage: Optional[Dict[str, Any]] = {}
    client_info: Optional[Dict[str, Any]] = {}

class UsageEventResponse(BaseModel):
    id: UUID
    license_id: UUID
    event_type: str
    event_data: Optional[Dict[str, Any]]
    user_count: Optional[int]
    resource_usage: Optional[Dict[str, Any]]
    client_info: Optional[Dict[str, Any]]
    timestamp: datetime
    
    class Config:
        from_attributes = True
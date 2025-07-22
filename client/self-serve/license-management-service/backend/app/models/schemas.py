from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from app.database.database import Base

class Customer(Base):
    __tablename__ = "customers"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_name = Column(String(255), nullable=False)
    contact_email = Column(String(255), nullable=False)
    industry_classification = Column(String(100))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    licenses = relationship("License", back_populates="customer")

class License(Base):
    __tablename__ = "licenses"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    product_sku = Column(String(100), nullable=False)
    edition_tier = Column(String(50), nullable=False)
    license_type = Column(String(20), nullable=False)  # perpetual, subscription, trial
    
    # Time constraints
    start_date = Column(DateTime(timezone=True), nullable=False)
    expiration_date = Column(DateTime(timezone=True))
    grace_period_days = Column(Integer, default=30)
    
    # Usage limits
    user_limit = Column(Integer)
    node_limit = Column(Integer)
    feature_flags = Column(JSON, default={})
    resource_limits = Column(JSON, default={})
    
    # Hardware binding
    binding_type = Column(String(20), default="flexible")  # strict, flexible, none
    hardware_signatures = Column(JSON, default=[])
    tolerance_level = Column(Integer, default=2)
    
    # Operational parameters
    phone_home_frequency = Column(Integer, default=24)  # hours
    offline_grace_period = Column(Integer, default=72)  # hours
    usage_reporting_level = Column(String(20), default="standard")
    
    # Metadata
    issue_date = Column(DateTime(timezone=True), server_default=func.now())
    issuer = Column(String(100), default="license-management-service")
    sales_order_reference = Column(String(100))
    support_tier = Column(String(50))
    
    # Status
    is_active = Column(Boolean, default=True)
    revoked_at = Column(DateTime(timezone=True))
    revocation_reason = Column(String(255))
    
    # Generated license file
    license_token = Column(Text)  # JWT token
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    customer = relationship("Customer", back_populates="licenses")
    usage_events = relationship("UsageEvent", back_populates="license")

class UsageEvent(Base):
    __tablename__ = "usage_events"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    license_id = Column(UUID(as_uuid=True), ForeignKey("licenses.id"), nullable=False)
    
    event_type = Column(String(50), nullable=False)  # validation, feature_usage, error, etc.
    event_data = Column(JSON)
    user_count = Column(Integer)
    resource_usage = Column(JSON)
    
    client_info = Column(JSON)  # hardware fingerprint, OS, etc.
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    
    license = relationship("License", back_populates="usage_events")

class LicenseValidation(Base):
    __tablename__ = "license_validations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    license_id = Column(UUID(as_uuid=True), ForeignKey("licenses.id"), nullable=False)
    
    validation_result = Column(String(20), nullable=False)  # valid, expired, invalid, etc.
    validation_details = Column(JSON)
    client_fingerprint = Column(JSON)
    
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type = Column(String(50), nullable=False)  # license, customer, etc.
    entity_id = Column(UUID(as_uuid=True), nullable=False)
    action = Column(String(50), nullable=False)  # create, update, delete, validate
    
    user_id = Column(String(100))
    changes = Column(JSON)
    audit_metadata = Column(JSON)
    
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
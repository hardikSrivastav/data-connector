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
    
    # Simple tier-based model
    tier = Column(String(20), nullable=False)  # starter, business, enterprise
    database_limit = Column(Integer)  # 3, 10, or null for unlimited
    api_access = Column(Boolean, default=False)
    custom_integrations = Column(Boolean, default=False)
    
    # Trial vs paid
    trial_expires = Column(DateTime(timezone=True))  # null for paid licenses
    
    # Generated license token
    license_token = Column(Text)  # JWT token
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    customer = relationship("Customer", back_populates="licenses")

# Simplified schema - removed UsageEvent, LicenseValidation, and AuditLog for basic functionality
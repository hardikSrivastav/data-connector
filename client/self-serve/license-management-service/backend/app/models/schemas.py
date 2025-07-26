from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.database.database import Base

class Customer(Base):
    __tablename__ = "customers"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_name = Column(String(255), nullable=False)
    contact_email = Column(String(255), nullable=False)
    industry = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    licenses = relationship("License", back_populates="customer")
    telemetry_reports = relationship("TelemetryReport", back_populates="customer")

class License(Base):
    __tablename__ = "licenses"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    
    # License details
    license_key = Column(String(50), unique=True, nullable=False)  # Short key like ceneca-business-2024-abc123
    plan = Column(String(20), nullable=False)  # starter, business, enterprise
    max_seats = Column(Integer, nullable=False)
    
    # Features
    features = Column(JSON, default=list)  # ["api_access", "advanced_queries"]
    
    # Billing
    monthly_price = Column(Integer)  # Price in cents
    
    # Dates
    issued_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    trial_expires_at = Column(DateTime)  # Null for paid licenses
    
    # JWT token
    jwt_token = Column(Text)
    
    # Status
    is_active = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    customer = relationship("Customer", back_populates="licenses")
    telemetry_reports = relationship("TelemetryReport", back_populates="license")

class TelemetryReport(Base):
    __tablename__ = "telemetry_reports"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    license_id = Column(UUID(as_uuid=True), ForeignKey("licenses.id"), nullable=False)
    license_key = Column(String(50), nullable=False)
    
    # Report metadata
    report_date = Column(DateTime, nullable=False)
    deployment_id = Column(String(100))  # Customer's deployment identifier
    
    # Usage data
    active_users = Column(JSON)  # {"unique_daily": 8, "peak_concurrent": 5, "user_list": [...]}
    usage_stats = Column(JSON)   # {"queries_executed": 1250, "databases_connected": 3}
    system_info = Column(JSON)   # {"version": "1.2.3", "os": "linux"}
    
    # Billing data
    max_seats_used = Column(Integer, default=0)
    overage_seats = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    customer = relationship("Customer", back_populates="telemetry_reports")
    license = relationship("License", back_populates="telemetry_reports")
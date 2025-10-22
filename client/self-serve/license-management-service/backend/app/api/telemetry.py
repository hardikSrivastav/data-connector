from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID
from datetime import datetime, timedelta

from app.database.database import get_db
from app.models.schemas import TelemetryReport, License
from app.models.pydantic_models import TelemetryData, TelemetryResponse

router = APIRouter()

@router.post("/phone-home")
async def receive_telemetry(telemetry_data: TelemetryData, db: Session = Depends(get_db)):
    """Receive telemetry data from on-premise agents"""
    
    # Find license by key
    license = db.query(License).filter(License.license_key == telemetry_data.license_key).first()
    if not license:
        return {"status": "error", "message": "License not found"}, 404
    
    # Check if license is still valid
    if not license.is_active or license.expires_at < datetime.utcnow():
        return {"status": "error", "message": "License invalid or expired"}, 403
    
    # Calculate seat usage
    active_users = telemetry_data.active_users
    peak_concurrent = active_users.get("peak_concurrent", 0)
    max_seats_used = peak_concurrent
    overage_seats = max(0, peak_concurrent - license.max_seats)
    
    # Store telemetry report
    db_report = TelemetryReport(
        customer_id=license.customer_id,
        license_id=license.id,
        license_key=telemetry_data.license_key,
        report_date=telemetry_data.report_date,
        deployment_id=telemetry_data.deployment_id,
        active_users=telemetry_data.active_users,
        usage_stats=telemetry_data.usage_stats,
        system_info=telemetry_data.system_info,
        max_seats_used=max_seats_used,
        overage_seats=overage_seats
    )
    
    db.add(db_report)
    db.commit()
    db.refresh(db_report)
    
    # Check for overages and send alerts if needed
    response_data = {
        "status": "ok",
        "message": "Telemetry received",
        "next_checkin_seconds": 86400,  # 24 hours
        "license_valid": True
    }
    
    if overage_seats > 0:
        response_data["warning"] = f"Seat overage detected: {overage_seats} seats over limit"
        response_data["overage_seats"] = overage_seats
        response_data["max_seats"] = license.max_seats
        response_data["action_required"] = "Please upgrade your license or reduce concurrent users"
    
    return response_data

@router.get("/", response_model=List[TelemetryResponse])
async def list_telemetry_reports(
    customer_id: UUID = None,
    license_key: str = None,
    days: int = 30,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List telemetry reports with optional filters"""
    
    query = db.query(TelemetryReport)
    
    # Apply filters
    if customer_id:
        query = query.filter(TelemetryReport.customer_id == customer_id)
    
    if license_key:
        query = query.filter(TelemetryReport.license_key == license_key)
    
    # Filter by date range
    if days > 0:
        start_date = datetime.utcnow() - timedelta(days=days)
        query = query.filter(TelemetryReport.report_date >= start_date)
    
    reports = query.order_by(TelemetryReport.report_date.desc()).offset(skip).limit(limit).all()
    return reports

@router.get("/analytics/{customer_id}")
async def get_usage_analytics(customer_id: UUID, days: int = 30, db: Session = Depends(get_db)):
    """Get usage analytics for a customer"""
    
    # Get reports for the specified period
    start_date = datetime.utcnow() - timedelta(days=days)
    reports = db.query(TelemetryReport).filter(
        TelemetryReport.customer_id == customer_id,
        TelemetryReport.report_date >= start_date
    ).order_by(TelemetryReport.report_date.desc()).all()
    
    if not reports:
        return {
            "customer_id": customer_id,
            "period_days": days,
            "total_reports": 0,
            "message": "No usage data available"
        }
    
    # Calculate analytics
    total_reports = len(reports)
    unique_deployments = len(set(r.deployment_id for r in reports if r.deployment_id))
    
    # Seat usage analytics
    max_seats_used = max(r.max_seats_used for r in reports)
    avg_seats_used = sum(r.max_seats_used for r in reports) / total_reports
    total_overage_incidents = sum(1 for r in reports if r.overage_seats > 0)
    max_overage = max(r.overage_seats for r in reports)
    
    # Feature usage (aggregate from usage_stats)
    total_queries = sum(r.usage_stats.get("queries_executed", 0) for r in reports)
    total_api_calls = sum(r.usage_stats.get("api_calls", 0) for r in reports)
    
    # Recent usage trend (last 7 days)
    recent_reports = [r for r in reports if r.report_date >= datetime.utcnow() - timedelta(days=7)]
    recent_avg_seats = sum(r.max_seats_used for r in recent_reports) / len(recent_reports) if recent_reports else 0
    
    return {
        "customer_id": customer_id,
        "period_days": days,
        "total_reports": total_reports,
        "unique_deployments": unique_deployments,
        "seat_usage": {
            "max_seats_used_ever": max_seats_used,
            "avg_seats_used": round(avg_seats_used, 1),
            "recent_avg_seats": round(recent_avg_seats, 1),
            "overage_incidents": total_overage_incidents,
            "max_overage": max_overage
        },
        "feature_usage": {
            "total_queries": total_queries,
            "total_api_calls": total_api_calls,
            "avg_queries_per_day": round(total_queries / days, 1) if days > 0 else 0
        },
        "billing_summary": {
            "billable_seats": max_seats_used,
            "overage_charges_applicable": total_overage_incidents > 0,
            "max_overage_seats": max_overage
        }
    }

@router.get("/billing/{customer_id}")
async def get_billing_data(customer_id: UUID, month: str = None, db: Session = Depends(get_db)):
    """Get billing data for a customer for a specific month (YYYY-MM format)"""
    
    if month:
        try:
            year, month_num = month.split('-')
            start_date = datetime(int(year), int(month_num), 1)
            if int(month_num) == 12:
                end_date = datetime(int(year) + 1, 1, 1)
            else:
                end_date = datetime(int(year), int(month_num) + 1, 1)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid month format. Use YYYY-MM")
    else:
        # Current month
        now = datetime.utcnow()
        start_date = datetime(now.year, now.month, 1)
        if now.month == 12:
            end_date = datetime(now.year + 1, 1, 1)
        else:
            end_date = datetime(now.year, now.month + 1, 1)
    
    # Get reports for the month
    reports = db.query(TelemetryReport).filter(
        TelemetryReport.customer_id == customer_id,
        TelemetryReport.report_date >= start_date,
        TelemetryReport.report_date < end_date
    ).all()
    
    if not reports:
        return {
            "customer_id": customer_id,
            "billing_period": f"{start_date.strftime('%Y-%m')}",
            "base_charges": 0,
            "overage_charges": 0,
            "total_charges": 0,
            "message": "No usage data for billing period"
        }
    
    # Get customer's license info for pricing
    license = db.query(License).filter(
        License.customer_id == customer_id,
        License.is_active == True
    ).first()
    
    if not license:
        raise HTTPException(status_code=404, detail="No active license found for customer")
    
    # Calculate billing
    max_seats_used = max(r.max_seats_used for r in reports)
    total_overage_seat_days = sum(r.overage_seats for r in reports)
    
    # Base charge: max seats used * monthly price per seat
    base_charges = max_seats_used * license.monthly_price
    
    # Overage charges: overage seat-days * daily overage rate
    overage_rate_daily = license.monthly_price // 30  # Daily rate
    overage_charges = total_overage_seat_days * overage_rate_daily
    
    total_charges = base_charges + overage_charges
    
    return {
        "customer_id": customer_id,
        "billing_period": f"{start_date.strftime('%Y-%m')}",
        "license_plan": license.plan,
        "base_seat_limit": license.max_seats,
        "max_seats_used": max_seats_used,
        "total_overage_seat_days": total_overage_seat_days,
        "pricing": {
            "monthly_price_per_seat_cents": license.monthly_price,
            "overage_rate_per_day_cents": overage_rate_daily
        },
        "charges": {
            "base_charges_cents": base_charges,
            "overage_charges_cents": overage_charges,
            "total_charges_cents": total_charges,
            "total_charges_dollars": round(total_charges / 100, 2)
        },
        "usage_days": len(reports)
    }
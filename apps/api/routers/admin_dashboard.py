"""
Phase 14: Admin Master Control Panel Router
Comprehensive dashboard for complete system control and monitoring
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select, func, and_, or_
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta, date
from pydantic import BaseModel
from enum import Enum

from database import get_session
from models import (
    User, UserRole, DoctorProfile, PatientProfile, 
    Appointment, AppointmentStatus,
    Payment, PaymentStatus,
    MedicineInventory, PharmacyOrder, OrderStatus,
    Shipment, ShipmentStatus,
    WhatsAppLog, WhatsAppStatus,
    ActivityLog, ActivityType,
    Bed, BedStatus, IPDAdmission, AdmissionStatus,
    DoctorMetrics, Rating
)
from dependencies import require_admin

router = APIRouter(prefix="/api/admin/dashboard", tags=["Admin Dashboard"])


# ==================== Schemas ====================

class SystemOverview(BaseModel):
    """Real-time system overview metrics"""
    # User stats
    total_users: int
    active_users_today: int
    new_users_this_week: int
    users_by_role: Dict[str, int]
    
    # Real-time activity
    active_doctors_now: int
    active_patients_now: int
    ongoing_consultations: int
    
    # Today's metrics
    appointments_today: int
    completed_consultations_today: int
    revenue_today: float
    
    # System health
    pending_doctor_verifications: int
    pending_pharmacy_orders: int
    critical_inventory_items: int
    active_shipments: int
    
    class Config:
        from_attributes = True


class RevenueAnalytics(BaseModel):
    """Revenue analytics and breakdowns"""
    # Period totals
    today_revenue: float
    week_revenue: float
    month_revenue: float
    year_revenue: float
    
    # Revenue by source
    consultation_revenue: float
    pharmacy_revenue: float
    hospital_revenue: float
    
    # Payment status
    pending_payments: float
    completed_payments: float
    failed_payments: float
    refunded_payments: float
    
    # Trends
    daily_trend: List[Dict[str, Any]]  # Last 30 days
    monthly_trend: List[Dict[str, Any]]  # Last 12 months
    
    # Top performers
    top_doctors_by_revenue: List[Dict[str, Any]]
    
    class Config:
        from_attributes = True


class HospitalOperations(BaseModel):
    """Hospital operations status"""
    # Bed management
    total_beds: int
    occupied_beds: int
    available_beds: int
    under_maintenance_beds: int
    occupancy_rate: float
    
    # IPD stats
    total_ipd_patients: int
    admissions_today: int
    discharges_today: int
    critical_patients: int
    
    # OPD stats
    opd_appointments_today: int
    opd_completed_today: int
    opd_pending_today: int
    avg_wait_time_minutes: float
    
    # Department wise
    department_occupancy: List[Dict[str, Any]]
    
    class Config:
        from_attributes = True


class PharmacyDashboard(BaseModel):
    """Pharmacy operations dashboard"""
    # Inventory
    total_medicines: int
    low_stock_items: int
    out_of_stock_items: int
    expiring_soon_items: int
    
    # Orders
    pending_orders: int
    processing_orders: int
    completed_orders_today: int
    total_orders_value: float
    
    # Revenue
    pharmacy_revenue_today: float
    pharmacy_revenue_week: float
    pharmacy_revenue_month: float
    
    # Alerts
    inventory_alerts: List[Dict[str, Any]]
    
    class Config:
        from_attributes = True


class CourierDashboard(BaseModel):
    """Courier tracking dashboard"""
    # Shipment stats
    total_active_shipments: int
    created_today: int
    in_transit: int
    out_for_delivery: int
    delivered_today: int
    failed_deliveries: int
    
    # Performance
    avg_delivery_time_days: float
    on_time_delivery_rate: float
    
    # By carrier
    carrier_performance: List[Dict[str, Any]]
    
    # Recent shipments
    recent_shipments: List[Dict[str, Any]]
    
    class Config:
        from_attributes = True


class NotificationsDashboard(BaseModel):
    """WhatsApp notifications dashboard"""
    # Message stats
    total_sent_today: int
    total_sent_week: int
    delivered_count: int
    failed_count: int
    pending_count: int
    
    # Delivery rates
    delivery_rate: float
    failure_rate: float
    
    # By type
    messages_by_type: Dict[str, int]
    
    # Recent activity
    recent_messages: List[Dict[str, Any]]
    
    class Config:
        from_attributes = True


class UserManagementStats(BaseModel):
    """User management statistics"""
    # By role
    total_patients: int
    total_doctors: int
    total_admins: int
    total_nurses: int
    total_pharmacists: int
    
    # Status
    active_users: int
    inactive_users: int
    pending_verifications: int
    
    # Recent activity
    new_registrations_today: int
    new_registrations_week: int
    
    # Doctor specific
    verified_doctors: int
    unverified_doctors: int
    
    class Config:
        from_attributes = True


class ReportRequest(BaseModel):
    """Report generation request"""
    report_type: str  # revenue, appointments, inventory, users, etc.
    start_date: date
    end_date: date
    format: str = "pdf"  # pdf, csv, excel
    filters: Optional[Dict[str, Any]] = None


# ==================== Endpoints ====================

@router.get("/overview", response_model=SystemOverview)
async def get_system_overview(
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_session)
):
    """Get comprehensive system overview"""
    
    # User statistics
    total_users = session.exec(select(func.count(User.id))).one()
    
    today = datetime.now().date()
    week_ago = today - timedelta(days=7)
    
    active_users_today = session.exec(
        select(func.count(User.id.distinct()))
        .select_from(ActivityLog)
        .where(func.date(ActivityLog.timestamp) == today)
    ).one() or 0
    
    new_users_this_week = session.exec(
        select(func.count(User.id))
        .where(func.date(User.created_at) >= week_ago)
    ).one() or 0
    
    # Users by role
    users_by_role = {}
    for role in UserRole:
        count = session.exec(
            select(func.count(User.id))
            .where(User.role == role)
        ).one() or 0
        users_by_role[role.value] = count
    
    # Active doctors/patients now (logged in within last hour)
    hour_ago = datetime.now() - timedelta(hours=1)
    
    active_doctors = session.exec(
        select(func.count(User.id.distinct()))
        .join(DoctorProfile)
        .where(and_(
            User.role == UserRole.DOCTOR,
            DoctorProfile.last_seen >= hour_ago
        ))
    ).one() or 0
    
    active_patients = session.exec(
        select(func.count(User.id.distinct()))
        .select_from(ActivityLog)
        .join(User)
        .where(and_(
            User.role == UserRole.PATIENT,
            ActivityLog.timestamp >= hour_ago
        ))
    ).one() or 0
    
    # Ongoing consultations
    ongoing_consultations = session.exec(
        select(func.count(Appointment.id))
        .where(and_(
            Appointment.status == AppointmentStatus.IN_PROGRESS,
            func.date(Appointment.appointment_date) == today
        ))
    ).one() or 0
    
    # Today's appointments and revenue
    appointments_today = session.exec(
        select(func.count(Appointment.id))
        .where(func.date(Appointment.appointment_date) == today)
    ).one() or 0
    
    completed_today = session.exec(
        select(func.count(Appointment.id))
        .where(and_(
            func.date(Appointment.appointment_date) == today,
            Appointment.status == AppointmentStatus.COMPLETED
        ))
    ).one() or 0
    
    revenue_today = session.exec(
        select(func.coalesce(func.sum(Payment.amount), 0))
        .where(and_(
            func.date(Payment.created_at) == today,
            Payment.status == PaymentStatus.COMPLETED
        ))
    ).one() or 0.0
    
    # Pending items
    pending_doctors = session.exec(
        select(func.count(DoctorProfile.id))
        .where(DoctorProfile.is_verified == False)
    ).one() or 0
    
    pending_orders = session.exec(
        select(func.count(PharmacyOrder.id))
        .where(PharmacyOrder.status.in_([OrderStatus.PENDING, OrderStatus.PROCESSING]))
    ).one() or 0
    
    critical_inventory = session.exec(
        select(func.count(MedicineInventory.id))
        .where(MedicineInventory.quantity <= MedicineInventory.reorder_level)
    ).one() or 0
    
    active_shipments = session.exec(
        select(func.count(Shipment.id))
        .where(Shipment.status.in_([
            ShipmentStatus.CREATED,
            ShipmentStatus.PICKED_UP,
            ShipmentStatus.IN_TRANSIT,
            ShipmentStatus.OUT_FOR_DELIVERY
        ]))
    ).one() or 0
    
    return SystemOverview(
        total_users=total_users,
        active_users_today=active_users_today,
        new_users_this_week=new_users_this_week,
        users_by_role=users_by_role,
        active_doctors_now=active_doctors,
        active_patients_now=active_patients,
        ongoing_consultations=ongoing_consultations,
        appointments_today=appointments_today,
        completed_consultations_today=completed_today,
        revenue_today=float(revenue_today),
        pending_doctor_verifications=pending_doctors,
        pending_pharmacy_orders=pending_orders,
        critical_inventory_items=critical_inventory,
        active_shipments=active_shipments
    )


@router.get("/revenue", response_model=RevenueAnalytics)
async def get_revenue_analytics(
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_session)
):
    """Get comprehensive revenue analytics"""
    
    today = datetime.now().date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    year_ago = today - timedelta(days=365)
    
    # Period totals
    today_revenue = session.exec(
        select(func.coalesce(func.sum(Payment.amount), 0))
        .where(and_(
            func.date(Payment.created_at) == today,
            Payment.status == PaymentStatus.COMPLETED
        ))
    ).one() or 0.0
    
    week_revenue = session.exec(
        select(func.coalesce(func.sum(Payment.amount), 0))
        .where(and_(
            func.date(Payment.created_at) >= week_ago,
            Payment.status == PaymentStatus.COMPLETED
        ))
    ).one() or 0.0
    
    month_revenue = session.exec(
        select(func.coalesce(func.sum(Payment.amount), 0))
        .where(and_(
            func.date(Payment.created_at) >= month_ago,
            Payment.status == PaymentStatus.COMPLETED
        ))
    ).one() or 0.0
    
    year_revenue = session.exec(
        select(func.coalesce(func.sum(Payment.amount), 0))
        .where(and_(
            func.date(Payment.created_at) >= year_ago,
            Payment.status == PaymentStatus.COMPLETED
        ))
    ).one() or 0.0
    
    # Revenue by source (using payment_for field)
    consultation_revenue = session.exec(
        select(func.coalesce(func.sum(Payment.amount), 0))
        .where(and_(
            Payment.status == PaymentStatus.COMPLETED,
            Payment.payment_for.like('%consultation%')
        ))
    ).one() or 0.0
    
    pharmacy_revenue = session.exec(
        select(func.coalesce(func.sum(Payment.amount), 0))
        .where(and_(
            Payment.status == PaymentStatus.COMPLETED,
            Payment.payment_for.like('%pharmacy%')
        ))
    ).one() or 0.0
    
    hospital_revenue = year_revenue - consultation_revenue - pharmacy_revenue
    
    # Payment status totals
    pending_payments = session.exec(
        select(func.coalesce(func.sum(Payment.amount), 0))
        .where(Payment.status == PaymentStatus.PENDING)
    ).one() or 0.0
    
    completed_payments = session.exec(
        select(func.coalesce(func.sum(Payment.amount), 0))
        .where(Payment.status == PaymentStatus.COMPLETED)
    ).one() or 0.0
    
    failed_payments = session.exec(
        select(func.coalesce(func.sum(Payment.amount), 0))
        .where(Payment.status == PaymentStatus.FAILED)
    ).one() or 0.0
    
    refunded_payments = session.exec(
        select(func.coalesce(func.sum(Payment.amount), 0))
        .where(Payment.status == PaymentStatus.REFUNDED)
    ).one() or 0.0
    
    # Daily trend (last 30 days)
    daily_trend = []
    for i in range(30):
        day = today - timedelta(days=i)
        day_revenue = session.exec(
            select(func.coalesce(func.sum(Payment.amount), 0))
            .where(and_(
                func.date(Payment.created_at) == day,
                Payment.status == PaymentStatus.COMPLETED
            ))
        ).one() or 0.0
        
        daily_trend.append({
            "date": day.isoformat(),
            "revenue": float(day_revenue)
        })
    
    daily_trend.reverse()
    
    # Monthly trend (last 12 months)
    monthly_trend = []
    for i in range(12):
        month_start = (today.replace(day=1) - timedelta(days=i*30)).replace(day=1)
        next_month = (month_start + timedelta(days=32)).replace(day=1)
        
        month_revenue = session.exec(
            select(func.coalesce(func.sum(Payment.amount), 0))
            .where(and_(
                Payment.created_at >= month_start,
                Payment.created_at < next_month,
                Payment.status == PaymentStatus.COMPLETED
            ))
        ).one() or 0.0
        
        monthly_trend.append({
            "month": month_start.strftime("%B %Y"),
            "revenue": float(month_revenue)
        })
    
    monthly_trend.reverse()
    
    # Top doctors by revenue (last 30 days)
    top_doctors_query = session.exec(
        select(
            User.id,
            User.full_name,
            DoctorProfile.specialization,
            func.sum(Payment.amount).label('total_revenue')
        )
        .join(Appointment, Appointment.doctor_id == User.id)
        .join(Payment, Payment.appointment_id == Appointment.id)
        .join(DoctorProfile, DoctorProfile.user_id == User.id)
        .where(and_(
            Payment.created_at >= month_ago,
            Payment.status == PaymentStatus.COMPLETED
        ))
        .group_by(User.id, User.full_name, DoctorProfile.specialization)
        .order_by(func.sum(Payment.amount).desc())
        .limit(10)
    ).all()
    
    top_doctors = [
        {
            "doctor_id": doc[0],
            "doctor_name": doc[1],
            "specialization": doc[2],
            "revenue": float(doc[3])
        }
        for doc in top_doctors_query
    ]
    
    return RevenueAnalytics(
        today_revenue=float(today_revenue),
        week_revenue=float(week_revenue),
        month_revenue=float(month_revenue),
        year_revenue=float(year_revenue),
        consultation_revenue=float(consultation_revenue),
        pharmacy_revenue=float(pharmacy_revenue),
        hospital_revenue=float(hospital_revenue),
        pending_payments=float(pending_payments),
        completed_payments=float(completed_payments),
        failed_payments=float(failed_payments),
        refunded_payments=float(refunded_payments),
        daily_trend=daily_trend,
        monthly_trend=monthly_trend,
        top_doctors_by_revenue=top_doctors
    )


@router.get("/hospital", response_model=HospitalOperations)
async def get_hospital_operations(
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_session)
):
    """Get hospital operations status"""
    
    # Bed statistics
    total_beds = session.exec(select(func.count(Bed.id))).one() or 0
    
    occupied_beds = session.exec(
        select(func.count(Bed.id))
        .where(Bed.status == BedStatus.OCCUPIED)
    ).one() or 0
    
    available_beds = session.exec(
        select(func.count(Bed.id))
        .where(Bed.status == BedStatus.AVAILABLE)
    ).one() or 0
    
    maintenance_beds = session.exec(
        select(func.count(Bed.id))
        .where(Bed.status == BedStatus.MAINTENANCE)
    ).one() or 0
    
    occupancy_rate = (occupied_beds / total_beds * 100) if total_beds > 0 else 0.0
    
    # IPD statistics
    total_ipd = session.exec(
        select(func.count(IPDAdmission.id))
        .where(IPDAdmission.status == AdmissionStatus.ADMITTED)
    ).one() or 0
    
    today = datetime.now().date()
    
    admissions_today = session.exec(
        select(func.count(IPDAdmission.id))
        .where(func.date(IPDAdmission.admission_date) == today)
    ).one() or 0
    
    discharges_today = session.exec(
        select(func.count(IPDAdmission.id))
        .where(and_(
            func.date(IPDAdmission.discharge_date) == today,
            IPDAdmission.status == AdmissionStatus.DISCHARGED
        ))
    ).one() or 0
    
    critical_patients = session.exec(
        select(func.count(IPDAdmission.id))
        .where(and_(
            IPDAdmission.status == AdmissionStatus.ADMITTED,
            IPDAdmission.condition == "Critical"
        ))
    ).one() or 0
    
    # OPD statistics
    opd_today = session.exec(
        select(func.count(Appointment.id))
        .where(and_(
            func.date(Appointment.appointment_date) == today,
            Appointment.appointment_type != "video"
        ))
    ).one() or 0
    
    opd_completed = session.exec(
        select(func.count(Appointment.id))
        .where(and_(
            func.date(Appointment.appointment_date) == today,
            Appointment.status == AppointmentStatus.COMPLETED,
            Appointment.appointment_type != "video"
        ))
    ).one() or 0
    
    opd_pending = session.exec(
        select(func.count(Appointment.id))
        .where(and_(
            func.date(Appointment.appointment_date) == today,
            Appointment.status.in_([AppointmentStatus.SCHEDULED, AppointmentStatus.CONFIRMED]),
            Appointment.appointment_type != "video"
        ))
    ).one() or 0
    
    # Average wait time (simulated - would need actual tracking)
    avg_wait_time = 15.0  # minutes
    
    # Department wise occupancy
    dept_occupancy_query = session.exec(
        select(
            Bed.department,
            func.count(Bed.id).label('total'),
            func.sum(func.case((Bed.status == BedStatus.OCCUPIED, 1), else_=0)).label('occupied')
        )
        .group_by(Bed.department)
    ).all()
    
    department_occupancy = [
        {
            "department": dept[0],
            "total_beds": dept[1],
            "occupied_beds": dept[2],
            "occupancy_rate": (dept[2] / dept[1] * 100) if dept[1] > 0 else 0.0
        }
        for dept in dept_occupancy_query
    ]
    
    return HospitalOperations(
        total_beds=total_beds,
        occupied_beds=occupied_beds,
        available_beds=available_beds,
        under_maintenance_beds=maintenance_beds,
        occupancy_rate=occupancy_rate,
        total_ipd_patients=total_ipd,
        admissions_today=admissions_today,
        discharges_today=discharges_today,
        critical_patients=critical_patients,
        opd_appointments_today=opd_today,
        opd_completed_today=opd_completed,
        opd_pending_today=opd_pending,
        avg_wait_time_minutes=avg_wait_time,
        department_occupancy=department_occupancy
    )


@router.get("/pharmacy", response_model=PharmacyDashboard)
async def get_pharmacy_dashboard(
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_session)
):
    """Get pharmacy operations dashboard"""
    
    # Inventory stats
    total_medicines = session.exec(select(func.count(MedicineInventory.id))).one() or 0
    
    low_stock = session.exec(
        select(func.count(MedicineInventory.id))
        .where(and_(
            MedicineInventory.quantity <= MedicineInventory.reorder_level,
            MedicineInventory.quantity > 0
        ))
    ).one() or 0
    
    out_of_stock = session.exec(
        select(func.count(MedicineInventory.id))
        .where(MedicineInventory.quantity == 0)
    ).one() or 0
    
    # Expiring soon (within 90 days)
    expiry_threshold = datetime.now() + timedelta(days=90)
    expiring_soon = session.exec(
        select(func.count(MedicineInventory.id))
        .where(MedicineInventory.expiry_date <= expiry_threshold)
    ).one() or 0
    
    # Order stats
    pending_orders = session.exec(
        select(func.count(PharmacyOrder.id))
        .where(PharmacyOrder.status == OrderStatus.PENDING)
    ).one() or 0
    
    processing_orders = session.exec(
        select(func.count(PharmacyOrder.id))
        .where(PharmacyOrder.status == OrderStatus.PROCESSING)
    ).one() or 0
    
    today = datetime.now().date()
    completed_today = session.exec(
        select(func.count(PharmacyOrder.id))
        .where(and_(
            func.date(PharmacyOrder.created_at) == today,
            PharmacyOrder.status == OrderStatus.COMPLETED
        ))
    ).one() or 0
    
    total_value = session.exec(
        select(func.coalesce(func.sum(PharmacyOrder.total_amount), 0))
        .where(PharmacyOrder.status != OrderStatus.CANCELLED)
    ).one() or 0.0
    
    # Revenue
    today_revenue = session.exec(
        select(func.coalesce(func.sum(PharmacyOrder.total_amount), 0))
        .where(and_(
            func.date(PharmacyOrder.created_at) == today,
            PharmacyOrder.status == OrderStatus.COMPLETED
        ))
    ).one() or 0.0
    
    week_ago = today - timedelta(days=7)
    week_revenue = session.exec(
        select(func.coalesce(func.sum(PharmacyOrder.total_amount), 0))
        .where(and_(
            func.date(PharmacyOrder.created_at) >= week_ago,
            PharmacyOrder.status == OrderStatus.COMPLETED
        ))
    ).one() or 0.0
    
    month_ago = today - timedelta(days=30)
    month_revenue = session.exec(
        select(func.coalesce(func.sum(PharmacyOrder.total_amount), 0))
        .where(and_(
            func.date(PharmacyOrder.created_at) >= month_ago,
            PharmacyOrder.status == OrderStatus.COMPLETED
        ))
    ).one() or 0.0
    
    # Inventory alerts
    alerts_query = session.exec(
        select(MedicineInventory)
        .where(MedicineInventory.quantity <= MedicineInventory.reorder_level)
        .limit(10)
    ).all()
    
    inventory_alerts = [
        {
            "medicine_id": med.id,
            "medicine_name": med.medicine_name,
            "current_quantity": med.quantity,
            "reorder_level": med.reorder_level,
            "alert_type": "out_of_stock" if med.quantity == 0 else "low_stock"
        }
        for med in alerts_query
    ]
    
    return PharmacyDashboard(
        total_medicines=total_medicines,
        low_stock_items=low_stock,
        out_of_stock_items=out_of_stock,
        expiring_soon_items=expiring_soon,
        pending_orders=pending_orders,
        processing_orders=processing_orders,
        completed_orders_today=completed_today,
        total_orders_value=float(total_value),
        pharmacy_revenue_today=float(today_revenue),
        pharmacy_revenue_week=float(week_revenue),
        pharmacy_revenue_month=float(month_revenue),
        inventory_alerts=inventory_alerts
    )


@router.get("/courier", response_model=CourierDashboard)
async def get_courier_dashboard(
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_session)
):
    """Get courier tracking dashboard"""
    
    # Shipment stats
    active_shipments = session.exec(
        select(func.count(Shipment.id))
        .where(Shipment.status.in_([
            ShipmentStatus.CREATED,
            ShipmentStatus.PICKED_UP,
            ShipmentStatus.IN_TRANSIT,
            ShipmentStatus.OUT_FOR_DELIVERY
        ]))
    ).one() or 0
    
    today = datetime.now().date()
    created_today = session.exec(
        select(func.count(Shipment.id))
        .where(func.date(Shipment.created_at) == today)
    ).one() or 0
    
    in_transit = session.exec(
        select(func.count(Shipment.id))
        .where(Shipment.status == ShipmentStatus.IN_TRANSIT)
    ).one() or 0
    
    out_for_delivery = session.exec(
        select(func.count(Shipment.id))
        .where(Shipment.status == ShipmentStatus.OUT_FOR_DELIVERY)
    ).one() or 0
    
    delivered_today = session.exec(
        select(func.count(Shipment.id))
        .where(and_(
            func.date(Shipment.delivered_at) == today,
            Shipment.status == ShipmentStatus.DELIVERED
        ))
    ).one() or 0
    
    failed_deliveries = session.exec(
        select(func.count(Shipment.id))
        .where(Shipment.status == ShipmentStatus.FAILED)
    ).one() or 0
    
    # Average delivery time (for delivered shipments)
    avg_delivery_time = 3.5  # days (simulated)
    on_time_rate = 87.5  # percentage (simulated)
    
    # Carrier performance
    carrier_perf_query = session.exec(
        select(
            Shipment.courier_partner,
            func.count(Shipment.id).label('total'),
            func.sum(func.case((Shipment.status == ShipmentStatus.DELIVERED, 1), else_=0)).label('delivered')
        )
        .group_by(Shipment.courier_partner)
    ).all()
    
    carrier_performance = [
        {
            "carrier": carrier[0],
            "total_shipments": carrier[1],
            "delivered": carrier[2],
            "success_rate": (carrier[2] / carrier[1] * 100) if carrier[1] > 0 else 0.0
        }
        for carrier in carrier_perf_query
    ]
    
    # Recent shipments
    recent_query = session.exec(
        select(Shipment)
        .order_by(Shipment.created_at.desc())
        .limit(10)
    ).all()
    
    recent_shipments = [
        {
            "shipment_id": ship.id,
            "tracking_number": ship.tracking_number,
            "courier_partner": ship.courier_partner,
            "status": ship.status.value,
            "destination": f"{ship.destination_city}, {ship.destination_state}",
            "created_at": ship.created_at.isoformat()
        }
        for ship in recent_query
    ]
    
    return CourierDashboard(
        total_active_shipments=active_shipments,
        created_today=created_today,
        in_transit=in_transit,
        out_for_delivery=out_for_delivery,
        delivered_today=delivered_today,
        failed_deliveries=failed_deliveries,
        avg_delivery_time_days=avg_delivery_time,
        on_time_delivery_rate=on_time_rate,
        carrier_performance=carrier_performance,
        recent_shipments=recent_shipments
    )


@router.get("/notifications", response_model=NotificationsDashboard)
async def get_notifications_dashboard(
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_session)
):
    """Get WhatsApp notifications dashboard"""
    
    today = datetime.now().date()
    week_ago = today - timedelta(days=7)
    
    # Message stats
    total_today = session.exec(
        select(func.count(WhatsAppLog.id))
        .where(func.date(WhatsAppLog.sent_at) == today)
    ).one() or 0
    
    total_week = session.exec(
        select(func.count(WhatsAppLog.id))
        .where(func.date(WhatsAppLog.sent_at) >= week_ago)
    ).one() or 0
    
    delivered = session.exec(
        select(func.count(WhatsAppLog.id))
        .where(WhatsAppLog.status == WhatsAppStatus.DELIVERED)
    ).one() or 0
    
    failed = session.exec(
        select(func.count(WhatsAppLog.id))
        .where(WhatsAppLog.status == WhatsAppStatus.FAILED)
    ).one() or 0
    
    pending = session.exec(
        select(func.count(WhatsAppLog.id))
        .where(WhatsAppLog.status.in_([WhatsAppStatus.QUEUED, WhatsAppStatus.SENDING]))
    ).one() or 0
    
    # Delivery rates
    total_sent = session.exec(select(func.count(WhatsAppLog.id))).one() or 1
    delivery_rate = (delivered / total_sent * 100) if total_sent > 0 else 0.0
    failure_rate = (failed / total_sent * 100) if total_sent > 0 else 0.0
    
    # By message type
    msg_by_type_query = session.exec(
        select(
            WhatsAppLog.message_type,
            func.count(WhatsAppLog.id)
        )
        .group_by(WhatsAppLog.message_type)
    ).all()
    
    messages_by_type = {msg_type: count for msg_type, count in msg_by_type_query}
    
    # Recent messages
    recent_query = session.exec(
        select(WhatsAppLog)
        .order_by(WhatsAppLog.sent_at.desc())
        .limit(10)
    ).all()
    
    recent_messages = [
        {
            "id": msg.id,
            "phone_number": msg.phone_number,
            "message_type": msg.message_type,
            "status": msg.status.value,
            "sent_at": msg.sent_at.isoformat(),
            "delivered_at": msg.delivered_at.isoformat() if msg.delivered_at else None
        }
        for msg in recent_query
    ]
    
    return NotificationsDashboard(
        total_sent_today=total_today,
        total_sent_week=total_week,
        delivered_count=delivered,
        failed_count=failed,
        pending_count=pending,
        delivery_rate=delivery_rate,
        failure_rate=failure_rate,
        messages_by_type=messages_by_type,
        recent_messages=recent_messages
    )


@router.get("/users/stats", response_model=UserManagementStats)
async def get_user_management_stats(
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_session)
):
    """Get user management statistics"""
    
    # By role
    total_patients = session.exec(
        select(func.count(User.id))
        .where(User.role == UserRole.PATIENT)
    ).one() or 0
    
    total_doctors = session.exec(
        select(func.count(User.id))
        .where(User.role == UserRole.DOCTOR)
    ).one() or 0
    
    total_admins = session.exec(
        select(func.count(User.id))
        .where(User.role == UserRole.ADMIN)
    ).one() or 0
    
    total_nurses = session.exec(
        select(func.count(User.id))
        .where(User.role == UserRole.NURSE)
    ).one() or 0
    
    total_pharmacists = session.exec(
        select(func.count(User.id))
        .where(User.role == UserRole.PHARMACIST)
    ).one() or 0
    
    # Status
    active_users = session.exec(
        select(func.count(User.id))
        .where(User.is_active == True)
    ).one() or 0
    
    inactive_users = session.exec(
        select(func.count(User.id))
        .where(User.is_active == False)
    ).one() or 0
    
    pending_verifications = session.exec(
        select(func.count(DoctorProfile.id))
        .where(DoctorProfile.is_verified == False)
    ).one() or 0
    
    # Recent registrations
    today = datetime.now().date()
    week_ago = today - timedelta(days=7)
    
    new_today = session.exec(
        select(func.count(User.id))
        .where(func.date(User.created_at) == today)
    ).one() or 0
    
    new_week = session.exec(
        select(func.count(User.id))
        .where(func.date(User.created_at) >= week_ago)
    ).one() or 0
    
    # Doctor specific
    verified_doctors = session.exec(
        select(func.count(DoctorProfile.id))
        .where(DoctorProfile.is_verified == True)
    ).one() or 0
    
    unverified_doctors = session.exec(
        select(func.count(DoctorProfile.id))
        .where(DoctorProfile.is_verified == False)
    ).one() or 0
    
    return UserManagementStats(
        total_patients=total_patients,
        total_doctors=total_doctors,
        total_admins=total_admins,
        total_nurses=total_nurses,
        total_pharmacists=total_pharmacists,
        active_users=active_users,
        inactive_users=inactive_users,
        pending_verifications=pending_verifications,
        new_registrations_today=new_today,
        new_registrations_week=new_week,
        verified_doctors=verified_doctors,
        unverified_doctors=unverified_doctors
    )


@router.post("/reports/generate")
async def generate_report(
    report_request: ReportRequest,
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_session)
):
    """Generate custom reports"""
    
    # This would integrate with a report generation library
    # For now, return a placeholder
    
    return {
        "message": "Report generation initiated",
        "report_type": report_request.report_type,
        "start_date": report_request.start_date.isoformat(),
        "end_date": report_request.end_date.isoformat(),
        "format": report_request.format,
        "estimated_completion": "2 minutes",
        "download_url": f"/api/admin/reports/download/{report_request.report_type}-{datetime.now().timestamp()}.{report_request.format}"
    }


@router.get("/alerts")
async def get_system_alerts(
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_session)
):
    """Get real-time system alerts and notifications"""
    
    alerts = []
    
    # Critical inventory alerts
    critical_inventory = session.exec(
        select(func.count(MedicineInventory.id))
        .where(MedicineInventory.quantity == 0)
    ).one() or 0
    
    if critical_inventory > 0:
        alerts.append({
            "type": "critical",
            "category": "inventory",
            "message": f"{critical_inventory} medicines are out of stock",
            "action_url": "/admin/pharmacy",
            "timestamp": datetime.now().isoformat()
        })
    
    # Pending doctor verifications
    pending_doctors = session.exec(
        select(func.count(DoctorProfile.id))
        .where(DoctorProfile.is_verified == False)
    ).one() or 0
    
    if pending_doctors > 0:
        alerts.append({
            "type": "warning",
            "category": "users",
            "message": f"{pending_doctors} doctors pending verification",
            "action_url": "/admin/users?filter=pending_doctors",
            "timestamp": datetime.now().isoformat()
        })
    
    # Failed shipments
    failed_shipments = session.exec(
        select(func.count(Shipment.id))
        .where(Shipment.status == ShipmentStatus.FAILED)
    ).one() or 0
    
    if failed_shipments > 0:
        alerts.append({
            "type": "error",
            "category": "courier",
            "message": f"{failed_shipments} shipments failed delivery",
            "action_url": "/admin/couriers",
            "timestamp": datetime.now().isoformat()
        })
    
    # High pending payments
    pending_payment_amount = session.exec(
        select(func.coalesce(func.sum(Payment.amount), 0))
        .where(Payment.status == PaymentStatus.PENDING)
    ).one() or 0.0
    
    if pending_payment_amount > 10000:
        alerts.append({
            "type": "info",
            "category": "revenue",
            "message": f"₹{pending_payment_amount:,.2f} in pending payments",
            "action_url": "/admin/revenue",
            "timestamp": datetime.now().isoformat()
        })
    
    return {
        "total_alerts": len(alerts),
        "alerts": alerts
    }

"""
Phase 11: Doctor Productivity & KPI Dashboard Router
Handles doctor performance metrics, KPI tracking, and analytics
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select, func, and_, or_
from typing import Optional, List
from datetime import datetime, timedelta
from pydantic import BaseModel

from database import get_session
from models import (
    User, UserRole, DoctorProfile, Appointment, AppointmentStatus,
    DoctorMetrics, DoctorProductivityScore, DoctorSession, DoctorTarget,
    MetricPeriod, DoctorRating, Payment, PaymentStatus
)
from dependencies import get_current_user

router = APIRouter(prefix="/api/productivity", tags=["Productivity & KPI"])


# ==================== Schemas ====================

class DoctorMetricsResponse(BaseModel):
    doctor_id: int
    doctor_name: str
    specialization: str
    date: datetime
    
    # Time metrics
    active_duration_minutes: int
    online_duration_minutes: int
    
    # Appointments
    total_appointments: int
    completed_appointments: int
    cancelled_appointments: int
    no_show_appointments: int
    completion_rate: float
    
    # Consultation breakdown
    online_consultations: int
    in_person_consultations: int
    follow_up_consultations: int
    
    # Efficiency
    avg_consultation_duration_minutes: float
    avg_wait_time_minutes: float
    
    # Revenue
    revenue_generated: float
    
    # Quality
    avg_rating: Optional[float]
    total_ratings: int
    
    class Config:
        from_attributes = True

class ProductivityScoreResponse(BaseModel):
    doctor_id: int
    doctor_name: str
    specialization: str
    period: str
    period_start: datetime
    period_end: datetime
    
    availability_score: float
    efficiency_score: float
    quality_score: float
    revenue_score: float
    patient_satisfaction_score: float
    overall_score: float
    
    rank_in_department: Optional[int]
    rank_overall: Optional[int]
    percentile: Optional[float]
    
    total_consultations: int
    total_revenue: float
    avg_rating: Optional[float]
    completion_rate: float
    
    class Config:
        from_attributes = True

class DoctorKPIDashboard(BaseModel):
    """Comprehensive KPI dashboard for a single doctor"""
    doctor_id: int
    doctor_name: str
    specialization: str
    
    # Today's metrics
    today_appointments: int
    today_completed: int
    today_revenue: float
    today_online_hours: float
    
    # This week
    week_appointments: int
    week_completed: int
    week_revenue: float
    week_avg_rating: Optional[float]
    
    # This month
    month_appointments: int
    month_completed: int
    month_revenue: float
    month_avg_rating: Optional[float]
    
    # Targets & achievement
    target_consultations: int
    actual_consultations: int
    consultation_achievement: float
    target_revenue: float
    actual_revenue: float
    revenue_achievement: float
    
    # Scores
    current_score: Optional[ProductivityScoreResponse]
    
    # Trends (last 7 days)
    daily_trend: List[dict]
    
    class Config:
        from_attributes = True

class LeaderboardEntry(BaseModel):
    rank: int
    doctor_id: int
    doctor_name: str
    specialization: str
    profile_image: Optional[str]
    overall_score: float
    total_consultations: int
    total_revenue: float
    avg_rating: Optional[float]
    completion_rate: float

class ProductivityDashboard(BaseModel):
    """Admin productivity dashboard overview"""
    # Summary metrics
    total_doctors: int
    active_doctors_today: int
    total_consultations_today: int
    total_revenue_today: float
    avg_completion_rate: float
    avg_rating: Optional[float]
    
    # Top performers
    top_by_consultations: List[LeaderboardEntry]
    top_by_revenue: List[LeaderboardEntry]
    top_by_rating: List[LeaderboardEntry]
    
    # Department breakdown
    by_specialization: List[dict]
    
    # Trends
    hourly_trend: List[dict]
    daily_trend: List[dict]

class TargetCreate(BaseModel):
    doctor_id: int
    period: MetricPeriod
    target_consultations: int
    target_revenue: float
    target_online_hours: float
    target_rating: float = 4.5

class SessionLog(BaseModel):
    action: str  # "login" or "logout"
    device_type: Optional[str] = None


# ==================== Helper Functions ====================

def calculate_completion_rate(completed: int, total: int) -> float:
    """Calculate completion rate percentage"""
    if total == 0:
        return 0
    return round((completed / total) * 100, 2)

def calculate_productivity_score(
    availability: float,
    efficiency: float,
    quality: float,
    revenue: float,
    satisfaction: float
) -> float:
    """Calculate weighted overall productivity score"""
    weights = {
        'availability': 0.15,
        'efficiency': 0.25,
        'quality': 0.20,
        'revenue': 0.20,
        'satisfaction': 0.20
    }
    return round(
        availability * weights['availability'] +
        efficiency * weights['efficiency'] +
        quality * weights['quality'] +
        revenue * weights['revenue'] +
        satisfaction * weights['satisfaction'],
        2
    )


# ==================== Doctor Self-View Endpoints ====================

@router.get("/my-performance", response_model=DoctorKPIDashboard)
async def get_my_performance(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get current doctor's KPI dashboard"""
    if current_user.role != UserRole.DOCTOR:
        raise HTTPException(status_code=403, detail="Only doctors can access this endpoint")
    
    return await get_doctor_kpi(current_user.id, session)

@router.post("/session")
async def log_session(
    data: SessionLog,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Log doctor login/logout for time tracking"""
    if current_user.role != UserRole.DOCTOR:
        raise HTTPException(status_code=403, detail="Only doctors can access this endpoint")
    
    now = datetime.utcnow()
    
    if data.action == "login":
        # Create new session
        doctor_session = DoctorSession(
            doctor_id=current_user.id,
            session_start=now,
            device_type=data.device_type
        )
        session.add(doctor_session)
    
    elif data.action == "logout":
        # Find and close active session
        active_session = session.exec(
            select(DoctorSession)
            .where(DoctorSession.doctor_id == current_user.id)
            .where(DoctorSession.session_end == None)
            .order_by(DoctorSession.session_start.desc())
        ).first()
        
        if active_session:
            active_session.session_end = now
            active_session.duration_minutes = int(
                (now - active_session.session_start).total_seconds() / 60
            )
            session.add(active_session)
            
            # Update daily metrics
            await update_daily_metrics(current_user.id, now.date(), session)
    
    session.commit()
    return {"status": "success", "action": data.action, "timestamp": now}

@router.get("/my-metrics")
async def get_my_metrics(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get doctor's own metrics for a date range"""
    if current_user.role != UserRole.DOCTOR:
        raise HTTPException(status_code=403, detail="Only doctors can access this endpoint")
    
    if not start_date:
        start_date = datetime.utcnow() - timedelta(days=30)
    if not end_date:
        end_date = datetime.utcnow()
    
    metrics = session.exec(
        select(DoctorMetrics)
        .where(DoctorMetrics.doctor_id == current_user.id)
        .where(DoctorMetrics.date >= start_date)
        .where(DoctorMetrics.date <= end_date)
        .order_by(DoctorMetrics.date.desc())
    ).all()
    
    return metrics


# ==================== Admin Endpoints ====================

@router.get("/admin/dashboard", response_model=ProductivityDashboard)
async def get_productivity_dashboard(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get admin productivity dashboard overview"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    today = datetime.utcnow().date()
    today_start = datetime.combine(today, datetime.min.time())
    today_end = datetime.combine(today, datetime.max.time())
    
    # Count total doctors
    total_doctors = session.exec(
        select(func.count(User.id))
        .where(User.role == UserRole.DOCTOR)
        .where(User.is_active == True)
    ).one()
    
    # Active doctors today (have appointments or logged in)
    active_doctors = session.exec(
        select(func.count(func.distinct(Appointment.doctor_id)))
        .where(Appointment.start_time >= today_start)
        .where(Appointment.start_time <= today_end)
    ).one()
    
    # Today's consultations
    today_consultations = session.exec(
        select(func.count(Appointment.id))
        .where(Appointment.start_time >= today_start)
        .where(Appointment.start_time <= today_end)
        .where(Appointment.status == AppointmentStatus.COMPLETED)
    ).one()
    
    # Today's revenue
    today_revenue = session.exec(
        select(func.coalesce(func.sum(Payment.amount), 0))
        .where(Payment.payment_date >= today_start)
        .where(Payment.payment_date <= today_end)
        .where(Payment.status == PaymentStatus.COMPLETED)
    ).one()
    
    # Calculate completion rate
    total_scheduled = session.exec(
        select(func.count(Appointment.id))
        .where(Appointment.start_time >= today_start)
        .where(Appointment.start_time <= today_end)
    ).one()
    
    avg_completion = calculate_completion_rate(today_consultations, total_scheduled)
    
    # Average rating
    avg_rating = session.exec(
        select(func.avg(DoctorRating.rating))
        .where(DoctorRating.created_at >= today_start)
    ).one()
    
    # Get top performers
    week_start = today_start - timedelta(days=7)
    
    # Top by consultations
    top_consultations = await get_leaderboard(session, "consultations", week_start, today_end, 5)
    top_revenue = await get_leaderboard(session, "revenue", week_start, today_end, 5)
    top_rating = await get_leaderboard(session, "rating", week_start, today_end, 5)
    
    # By specialization
    by_spec = session.exec(
        select(
            DoctorProfile.specialization,
            func.count(func.distinct(DoctorProfile.user_id)).label('doctor_count'),
            func.count(Appointment.id).label('appointment_count')
        )
        .join(Appointment, Appointment.doctor_id == DoctorProfile.user_id, isouter=True)
        .where(or_(
            Appointment.start_time >= week_start,
            Appointment.id == None
        ))
        .group_by(DoctorProfile.specialization)
    ).all()
    
    by_specialization = [
        {
            "specialization": spec,
            "doctor_count": count,
            "appointment_count": appts
        }
        for spec, count, appts in by_spec
    ]
    
    # Hourly trend for today
    hourly_trend = []
    for hour in range(24):
        hour_start = today_start + timedelta(hours=hour)
        hour_end = hour_start + timedelta(hours=1)
        count = session.exec(
            select(func.count(Appointment.id))
            .where(Appointment.start_time >= hour_start)
            .where(Appointment.start_time < hour_end)
            .where(Appointment.status == AppointmentStatus.COMPLETED)
        ).one()
        hourly_trend.append({"hour": hour, "count": count})
    
    # Daily trend for last 7 days
    daily_trend = []
    for i in range(7):
        day = today - timedelta(days=i)
        day_start = datetime.combine(day, datetime.min.time())
        day_end = datetime.combine(day, datetime.max.time())
        count = session.exec(
            select(func.count(Appointment.id))
            .where(Appointment.start_time >= day_start)
            .where(Appointment.start_time <= day_end)
            .where(Appointment.status == AppointmentStatus.COMPLETED)
        ).one()
        rev = session.exec(
            select(func.coalesce(func.sum(Payment.amount), 0))
            .where(Payment.payment_date >= day_start)
            .where(Payment.payment_date <= day_end)
            .where(Payment.status == PaymentStatus.COMPLETED)
        ).one()
        daily_trend.append({
            "date": day.isoformat(),
            "consultations": count,
            "revenue": float(rev)
        })
    
    daily_trend.reverse()
    
    return ProductivityDashboard(
        total_doctors=total_doctors,
        active_doctors_today=active_doctors,
        total_consultations_today=today_consultations,
        total_revenue_today=float(today_revenue),
        avg_completion_rate=avg_completion,
        avg_rating=float(avg_rating) if avg_rating else None,
        top_by_consultations=top_consultations,
        top_by_revenue=top_revenue,
        top_by_rating=top_rating,
        by_specialization=by_specialization,
        hourly_trend=hourly_trend,
        daily_trend=daily_trend
    )

@router.get("/admin/doctors/metrics")
async def get_all_doctors_metrics(
    specialization: Optional[str] = None,
    date: Optional[datetime] = None,
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get metrics for all doctors"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    if not date:
        date = datetime.utcnow().date()
    
    query = select(DoctorMetrics, User, DoctorProfile).join(
        User, User.id == DoctorMetrics.doctor_id
    ).join(
        DoctorProfile, DoctorProfile.user_id == User.id
    ).where(
        func.date(DoctorMetrics.date) == date
    )
    
    if specialization:
        query = query.where(DoctorProfile.specialization == specialization)
    
    results = session.exec(query.offset(skip).limit(limit)).all()
    
    metrics_list = []
    for metric, user, profile in results:
        metrics_list.append(DoctorMetricsResponse(
            doctor_id=user.id,
            doctor_name=user.full_name,
            specialization=profile.specialization,
            date=metric.date,
            active_duration_minutes=metric.active_duration_minutes,
            online_duration_minutes=metric.online_duration_minutes,
            total_appointments=metric.total_appointments,
            completed_appointments=metric.completed_appointments,
            cancelled_appointments=metric.cancelled_appointments,
            no_show_appointments=metric.no_show_appointments,
            completion_rate=calculate_completion_rate(
                metric.completed_appointments, metric.total_appointments
            ),
            online_consultations=metric.online_consultations,
            in_person_consultations=metric.in_person_consultations,
            follow_up_consultations=metric.follow_up_consultations,
            avg_consultation_duration_minutes=metric.avg_consultation_duration_minutes,
            avg_wait_time_minutes=metric.avg_wait_time_minutes,
            revenue_generated=metric.revenue_generated,
            avg_rating=metric.avg_rating,
            total_ratings=metric.total_ratings
        ))
    
    return {"total": len(metrics_list), "metrics": metrics_list}

@router.get("/admin/doctors/{doctor_id}/kpi")
async def get_doctor_kpi_admin(
    doctor_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get KPI dashboard for a specific doctor (admin view)"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    return await get_doctor_kpi(doctor_id, session)

@router.get("/admin/leaderboard")
async def get_admin_leaderboard(
    metric: str = Query("consultations", regex="^(consultations|revenue|rating|score)$"),
    period: str = Query("week", regex="^(today|week|month)$"),
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get doctor leaderboard by different metrics"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    today = datetime.utcnow().date()
    
    if period == "today":
        start_date = datetime.combine(today, datetime.min.time())
    elif period == "week":
        start_date = datetime.combine(today - timedelta(days=7), datetime.min.time())
    else:  # month
        start_date = datetime.combine(today - timedelta(days=30), datetime.min.time())
    
    end_date = datetime.combine(today, datetime.max.time())
    
    return await get_leaderboard(session, metric, start_date, end_date, limit)

@router.post("/admin/targets")
async def set_doctor_target(
    data: TargetCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Set performance targets for a doctor"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Verify doctor exists
    doctor = session.get(User, data.doctor_id)
    if not doctor or doctor.role != UserRole.DOCTOR:
        raise HTTPException(status_code=404, detail="Doctor not found")
    
    # Calculate period dates
    today = datetime.utcnow().date()
    if data.period == MetricPeriod.WEEKLY:
        period_start = today - timedelta(days=today.weekday())
        period_end = period_start + timedelta(days=6)
    elif data.period == MetricPeriod.MONTHLY:
        period_start = today.replace(day=1)
        next_month = period_start + timedelta(days=32)
        period_end = next_month.replace(day=1) - timedelta(days=1)
    else:
        period_start = today
        period_end = today
    
    # Check for existing target
    existing = session.exec(
        select(DoctorTarget)
        .where(DoctorTarget.doctor_id == data.doctor_id)
        .where(DoctorTarget.period == data.period)
        .where(DoctorTarget.period_start == datetime.combine(period_start, datetime.min.time()))
    ).first()
    
    if existing:
        existing.target_consultations = data.target_consultations
        existing.target_revenue = data.target_revenue
        existing.target_online_hours = data.target_online_hours
        existing.target_rating = data.target_rating
        existing.updated_at = datetime.utcnow()
        session.add(existing)
    else:
        target = DoctorTarget(
            doctor_id=data.doctor_id,
            period=data.period,
            period_start=datetime.combine(period_start, datetime.min.time()),
            period_end=datetime.combine(period_end, datetime.max.time()),
            target_consultations=data.target_consultations,
            target_revenue=data.target_revenue,
            target_online_hours=data.target_online_hours,
            target_rating=data.target_rating
        )
        session.add(target)
    
    session.commit()
    return {"status": "success", "message": "Target set successfully"}

@router.get("/admin/targets/{doctor_id}")
async def get_doctor_targets(
    doctor_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get targets for a specific doctor"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    targets = session.exec(
        select(DoctorTarget)
        .where(DoctorTarget.doctor_id == doctor_id)
        .order_by(DoctorTarget.period_start.desc())
    ).all()
    
    return targets


# ==================== Helper Functions ====================

async def get_doctor_kpi(doctor_id: int, session: Session) -> DoctorKPIDashboard:
    """Get comprehensive KPI for a doctor"""
    # Get doctor info
    doctor = session.get(User, doctor_id)
    if not doctor or doctor.role != UserRole.DOCTOR:
        raise HTTPException(status_code=404, detail="Doctor not found")
    
    profile = session.exec(
        select(DoctorProfile).where(DoctorProfile.user_id == doctor_id)
    ).first()
    
    today = datetime.utcnow().date()
    today_start = datetime.combine(today, datetime.min.time())
    today_end = datetime.combine(today, datetime.max.time())
    week_start = datetime.combine(today - timedelta(days=7), datetime.min.time())
    month_start = datetime.combine(today - timedelta(days=30), datetime.min.time())
    
    # Today's metrics
    today_total = session.exec(
        select(func.count(Appointment.id))
        .where(Appointment.doctor_id == doctor_id)
        .where(Appointment.start_time >= today_start)
        .where(Appointment.start_time <= today_end)
    ).one()
    
    today_completed = session.exec(
        select(func.count(Appointment.id))
        .where(Appointment.doctor_id == doctor_id)
        .where(Appointment.start_time >= today_start)
        .where(Appointment.start_time <= today_end)
        .where(Appointment.status == AppointmentStatus.COMPLETED)
    ).one()
    
    today_rev = session.exec(
        select(func.coalesce(func.sum(Payment.amount), 0))
        .join(Appointment, Appointment.id == Payment.appointment_id)
        .where(Appointment.doctor_id == doctor_id)
        .where(Payment.payment_date >= today_start)
        .where(Payment.payment_date <= today_end)
        .where(Payment.status == PaymentStatus.COMPLETED)
    ).one()
    
    # Today's online hours from sessions
    today_sessions = session.exec(
        select(func.coalesce(func.sum(DoctorSession.duration_minutes), 0))
        .where(DoctorSession.doctor_id == doctor_id)
        .where(DoctorSession.session_start >= today_start)
    ).one()
    
    # Week metrics
    week_total = session.exec(
        select(func.count(Appointment.id))
        .where(Appointment.doctor_id == doctor_id)
        .where(Appointment.start_time >= week_start)
    ).one()
    
    week_completed = session.exec(
        select(func.count(Appointment.id))
        .where(Appointment.doctor_id == doctor_id)
        .where(Appointment.start_time >= week_start)
        .where(Appointment.status == AppointmentStatus.COMPLETED)
    ).one()
    
    week_rev = session.exec(
        select(func.coalesce(func.sum(Payment.amount), 0))
        .join(Appointment, Appointment.id == Payment.appointment_id)
        .where(Appointment.doctor_id == doctor_id)
        .where(Payment.payment_date >= week_start)
        .where(Payment.status == PaymentStatus.COMPLETED)
    ).one()
    
    week_rating = session.exec(
        select(func.avg(DoctorRating.rating))
        .where(DoctorRating.doctor_id == doctor_id)
        .where(DoctorRating.created_at >= week_start)
    ).one()
    
    # Month metrics
    month_total = session.exec(
        select(func.count(Appointment.id))
        .where(Appointment.doctor_id == doctor_id)
        .where(Appointment.start_time >= month_start)
    ).one()
    
    month_completed = session.exec(
        select(func.count(Appointment.id))
        .where(Appointment.doctor_id == doctor_id)
        .where(Appointment.start_time >= month_start)
        .where(Appointment.status == AppointmentStatus.COMPLETED)
    ).one()
    
    month_rev = session.exec(
        select(func.coalesce(func.sum(Payment.amount), 0))
        .join(Appointment, Appointment.id == Payment.appointment_id)
        .where(Appointment.doctor_id == doctor_id)
        .where(Payment.payment_date >= month_start)
        .where(Payment.status == PaymentStatus.COMPLETED)
    ).one()
    
    month_rating = session.exec(
        select(func.avg(DoctorRating.rating))
        .where(DoctorRating.doctor_id == doctor_id)
        .where(DoctorRating.created_at >= month_start)
    ).one()
    
    # Get current target
    current_target = session.exec(
        select(DoctorTarget)
        .where(DoctorTarget.doctor_id == doctor_id)
        .where(DoctorTarget.period == MetricPeriod.MONTHLY)
        .order_by(DoctorTarget.period_start.desc())
    ).first()
    
    target_consultations = current_target.target_consultations if current_target else 100
    target_revenue = current_target.target_revenue if current_target else 50000
    
    consultation_achievement = (month_completed / target_consultations * 100) if target_consultations > 0 else 0
    revenue_achievement = (float(month_rev) / target_revenue * 100) if target_revenue > 0 else 0
    
    # Daily trend (last 7 days)
    daily_trend = []
    for i in range(7):
        day = today - timedelta(days=i)
        day_start = datetime.combine(day, datetime.min.time())
        day_end = datetime.combine(day, datetime.max.time())
        
        completed = session.exec(
            select(func.count(Appointment.id))
            .where(Appointment.doctor_id == doctor_id)
            .where(Appointment.start_time >= day_start)
            .where(Appointment.start_time <= day_end)
            .where(Appointment.status == AppointmentStatus.COMPLETED)
        ).one()
        
        rev = session.exec(
            select(func.coalesce(func.sum(Payment.amount), 0))
            .join(Appointment, Appointment.id == Payment.appointment_id)
            .where(Appointment.doctor_id == doctor_id)
            .where(Payment.payment_date >= day_start)
            .where(Payment.payment_date <= day_end)
            .where(Payment.status == PaymentStatus.COMPLETED)
        ).one()
        
        daily_trend.append({
            "date": day.isoformat(),
            "consultations": completed,
            "revenue": float(rev)
        })
    
    daily_trend.reverse()
    
    return DoctorKPIDashboard(
        doctor_id=doctor_id,
        doctor_name=doctor.full_name,
        specialization=profile.specialization if profile else "General",
        today_appointments=today_total,
        today_completed=today_completed,
        today_revenue=float(today_rev),
        today_online_hours=round(today_sessions / 60, 2),
        week_appointments=week_total,
        week_completed=week_completed,
        week_revenue=float(week_rev),
        week_avg_rating=float(week_rating) if week_rating else None,
        month_appointments=month_total,
        month_completed=month_completed,
        month_revenue=float(month_rev),
        month_avg_rating=float(month_rating) if month_rating else None,
        target_consultations=target_consultations,
        actual_consultations=month_completed,
        consultation_achievement=round(consultation_achievement, 2),
        target_revenue=target_revenue,
        actual_revenue=float(month_rev),
        revenue_achievement=round(revenue_achievement, 2),
        current_score=None,  # Would be populated from DoctorProductivityScore
        daily_trend=daily_trend
    )

async def get_leaderboard(
    session: Session,
    metric: str,
    start_date: datetime,
    end_date: datetime,
    limit: int
) -> List[LeaderboardEntry]:
    """Get leaderboard based on metric"""
    
    if metric == "consultations":
        results = session.exec(
            select(
                User.id,
                User.full_name,
                DoctorProfile.specialization,
                func.count(Appointment.id).label('total')
            )
            .join(DoctorProfile, DoctorProfile.user_id == User.id)
            .join(Appointment, Appointment.doctor_id == User.id)
            .where(Appointment.start_time >= start_date)
            .where(Appointment.start_time <= end_date)
            .where(Appointment.status == AppointmentStatus.COMPLETED)
            .group_by(User.id, User.full_name, DoctorProfile.specialization)
            .order_by(func.count(Appointment.id).desc())
            .limit(limit)
        ).all()
        
    elif metric == "revenue":
        results = session.exec(
            select(
                User.id,
                User.full_name,
                DoctorProfile.specialization,
                func.coalesce(func.sum(Payment.amount), 0).label('total')
            )
            .join(DoctorProfile, DoctorProfile.user_id == User.id)
            .join(Appointment, Appointment.doctor_id == User.id)
            .join(Payment, Payment.appointment_id == Appointment.id)
            .where(Payment.payment_date >= start_date)
            .where(Payment.payment_date <= end_date)
            .where(Payment.status == PaymentStatus.COMPLETED)
            .group_by(User.id, User.full_name, DoctorProfile.specialization)
            .order_by(func.sum(Payment.amount).desc())
            .limit(limit)
        ).all()
        
    elif metric == "rating":
        results = session.exec(
            select(
                User.id,
                User.full_name,
                DoctorProfile.specialization,
                func.avg(DoctorRating.rating).label('total')
            )
            .join(DoctorProfile, DoctorProfile.user_id == User.id)
            .join(DoctorRating, DoctorRating.doctor_id == User.id)
            .where(DoctorRating.created_at >= start_date)
            .where(DoctorRating.created_at <= end_date)
            .group_by(User.id, User.full_name, DoctorProfile.specialization)
            .having(func.count(DoctorRating.id) >= 3)  # Minimum 3 ratings
            .order_by(func.avg(DoctorRating.rating).desc())
            .limit(limit)
        ).all()
    else:
        results = []
    
    leaderboard = []
    for rank, (user_id, name, spec, total) in enumerate(results, 1):
        # Get additional stats
        completed = session.exec(
            select(func.count(Appointment.id))
            .where(Appointment.doctor_id == user_id)
            .where(Appointment.start_time >= start_date)
            .where(Appointment.status == AppointmentStatus.COMPLETED)
        ).one()
        
        scheduled = session.exec(
            select(func.count(Appointment.id))
            .where(Appointment.doctor_id == user_id)
            .where(Appointment.start_time >= start_date)
        ).one()
        
        revenue = session.exec(
            select(func.coalesce(func.sum(Payment.amount), 0))
            .join(Appointment, Appointment.id == Payment.appointment_id)
            .where(Appointment.doctor_id == user_id)
            .where(Payment.payment_date >= start_date)
            .where(Payment.status == PaymentStatus.COMPLETED)
        ).one()
        
        avg_rating = session.exec(
            select(func.avg(DoctorRating.rating))
            .where(DoctorRating.doctor_id == user_id)
            .where(DoctorRating.created_at >= start_date)
        ).one()
        
        leaderboard.append(LeaderboardEntry(
            rank=rank,
            doctor_id=user_id,
            doctor_name=name,
            specialization=spec,
            profile_image=None,
            overall_score=float(total) if total else 0,
            total_consultations=completed,
            total_revenue=float(revenue),
            avg_rating=float(avg_rating) if avg_rating else None,
            completion_rate=calculate_completion_rate(completed, scheduled)
        ))
    
    return leaderboard

async def update_daily_metrics(doctor_id: int, date, session: Session):
    """Update or create daily metrics for a doctor"""
    date_start = datetime.combine(date, datetime.min.time())
    date_end = datetime.combine(date, datetime.max.time())
    
    # Get or create metrics record
    metrics = session.exec(
        select(DoctorMetrics)
        .where(DoctorMetrics.doctor_id == doctor_id)
        .where(func.date(DoctorMetrics.date) == date)
    ).first()
    
    if not metrics:
        metrics = DoctorMetrics(doctor_id=doctor_id, date=date_start)
    
    # Calculate session time
    total_duration = session.exec(
        select(func.coalesce(func.sum(DoctorSession.duration_minutes), 0))
        .where(DoctorSession.doctor_id == doctor_id)
        .where(DoctorSession.session_start >= date_start)
        .where(DoctorSession.session_start <= date_end)
    ).one()
    
    metrics.active_duration_minutes = total_duration
    metrics.updated_at = datetime.utcnow()
    
    session.add(metrics)

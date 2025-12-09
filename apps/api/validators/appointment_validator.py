"""Appointment validation logic"""
from datetime import datetime, date, timedelta
from fastapi import HTTPException, status
from sqlmodel import Session, select, func
from models import Appointment, AppointmentStatus, AppointmentType, DoctorAvailability, DoctorProfile
from validators.time_validator import (
    validate_datetime_range, 
    validate_not_in_past, 
    get_duration_minutes
)
from validators.business_rules import get_business_rules


def validate_appointment_time_not_past(start_time: datetime) -> None:
    """Validate appointment is not in the past"""
    validate_not_in_past(start_time)


def validate_appointment_duration(start_time: datetime, end_time: datetime) -> None:
    """Validate appointment duration is within limits"""
    validate_datetime_range(start_time, end_time)
    
    rules = get_business_rules()
    duration_minutes = get_duration_minutes(start_time, end_time)
    
    if duration_minutes < rules.MIN_APPOINTMENT_DURATION_MINUTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Appointment must be at least {rules.MIN_APPOINTMENT_DURATION_MINUTES} minutes"
        )
    
    if duration_minutes > rules.MAX_APPOINTMENT_DURATION_MINUTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Appointment cannot exceed {rules.MAX_APPOINTMENT_DURATION_MINUTES} minutes"
        )


def validate_advance_booking_limit(start_time: datetime, appointment_type: AppointmentType) -> None:
    """Validate appointment is not too far in advance"""
    rules = get_business_rules()
    
    # Emergency appointments can bypass this check
    if appointment_type == AppointmentType.EMERGENCY and rules.ALLOW_EMERGENCY_SAME_DAY:
        return
    
    days_ahead = (start_time.date() - date.today()).days
    
    if days_ahead > rules.MAX_ADVANCE_BOOKING_DAYS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot book more than {rules.MAX_ADVANCE_BOOKING_DAYS} days in advance"
        )


def validate_minimum_booking_notice(start_time: datetime, appointment_type: AppointmentType) -> None:
    """Validate minimum notice period before appointment"""
    rules = get_business_rules()
    
    # Emergency appointments can bypass this check
    if appointment_type == AppointmentType.EMERGENCY:
        return
    
    hours_until = (start_time - datetime.utcnow()).total_seconds() / 3600
    
    if hours_until < rules.MIN_BOOKING_NOTICE_HOURS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Appointments must be booked at least {rules.MIN_BOOKING_NOTICE_HOURS} hours in advance"
        )


def validate_patient_daily_limit(session: Session, patient_id: int, appointment_date: date) -> None:
    """Validate patient hasn't exceeded daily appointment limit"""
    rules = get_business_rules()
    
    count = session.exec(
        select(func.count(Appointment.id)).where(
            Appointment.patient_id == patient_id,
            func.date(Appointment.start_time) == appointment_date,
            Appointment.status.in_([AppointmentStatus.SCHEDULED])
        )
    ).first()
    
    if count >= rules.MAX_APPOINTMENTS_PER_PATIENT_PER_DAY:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximum {rules.MAX_APPOINTMENTS_PER_PATIENT_PER_DAY} appointments per day allowed"
        )


def validate_doctor_daily_limit(session: Session, doctor_id: int, appointment_date: date) -> None:
    """Validate doctor hasn't exceeded daily appointment limit"""
    rules = get_business_rules()
    
    # Get doctor's custom limit if set
    doctor_profile = session.exec(
        select(DoctorProfile).where(DoctorProfile.user_id == doctor_id)
    ).first()
    
    max_appointments = doctor_profile.max_appointments_per_day if doctor_profile and hasattr(doctor_profile, 'max_appointments_per_day') else rules.MAX_APPOINTMENTS_PER_DOCTOR_PER_DAY
    
    count = session.exec(
        select(func.count(Appointment.id)).where(
            Appointment.doctor_id == doctor_id,
            func.date(Appointment.start_time) == appointment_date,
            Appointment.status.in_([AppointmentStatus.SCHEDULED])
        )
    ).first()
    
    if count >= max_appointments:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Doctor has reached maximum appointments for this day"
        )


def validate_doctor_availability(
    session: Session, 
    doctor_id: int, 
    start_time: datetime, 
    end_time: datetime
) -> None:
    """Validate doctor is available during requested time"""
    day_of_week = start_time.weekday()
    start_time_str = start_time.strftime("%H:%M")
    end_time_str = end_time.strftime("%H:%M")
    
    availability = session.exec(
        select(DoctorAvailability).where(
            DoctorAvailability.doctor_id == doctor_id,
            DoctorAvailability.day_of_week == day_of_week,
            DoctorAvailability.is_available == True
        )
    ).first()
    
    if not availability:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Doctor is not available on this day"
        )
    
    # Check if requested time is within availability window
    if start_time_str < availability.start_time or end_time_str > availability.end_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Doctor is only available from {availability.start_time} to {availability.end_time}"
        )


def validate_no_time_conflict(
    session: Session,
    doctor_id: int,
    start_time: datetime,
    end_time: datetime,
    exclude_appointment_id: int = None
) -> None:
    """Validate no time slot conflicts"""
    query = select(Appointment).where(
        Appointment.doctor_id == doctor_id,
        Appointment.status == AppointmentStatus.SCHEDULED,
        Appointment.start_time < end_time,
        Appointment.end_time > start_time
    )
    
    if exclude_appointment_id:
        query = query.where(Appointment.id != exclude_appointment_id)
    
    conflicting = session.exec(query).first()
    
    if conflicting:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This time slot is already booked"
        )


def validate_cancellation_policy(appointment: Appointment) -> None:
    """Validate cancellation is allowed per policy"""
    rules = get_business_rules()
    
    if appointment.status == AppointmentStatus.CANCELLED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Appointment is already cancelled"
        )
    
    if appointment.status == AppointmentStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot cancel completed appointment"
        )
    
    hours_until = (appointment.start_time - datetime.utcnow()).total_seconds() / 3600
    
    if hours_until < rules.CANCELLATION_HOURS_BEFORE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel within {rules.CANCELLATION_HOURS_BEFORE} hours of appointment. Please contact support."
        )


def validate_reschedule_limit(appointment: Appointment) -> None:
    """Validate reschedule limit not exceeded"""
    rules = get_business_rules()
    
    reschedule_count = getattr(appointment, 'reschedule_count', 0)
    
    if reschedule_count >= rules.MAX_RESCHEDULES_PER_APPOINTMENT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximum {rules.MAX_RESCHEDULES_PER_APPOINTMENT} reschedules allowed. Please cancel and create a new appointment."
        )


def get_queue_number_for_appointment(
    session: Session,
    doctor_id: int,
    appointment_date: date,
    appointment_type: AppointmentType
) -> int:
    """Generate appropriate queue number based on appointment type"""
    rules = get_business_rules()
    
    # Emergency appointments get priority
    if appointment_type == AppointmentType.EMERGENCY:
        return rules.EMERGENCY_QUEUE_PRIORITY
    
    # Regular queue number generation
    max_queue = session.exec(
        select(func.max(Appointment.queue_number)).where(
            Appointment.doctor_id == doctor_id,
            func.date(Appointment.start_time) == appointment_date
        )
    ).first()
    
    return (max_queue or 0) + 1
